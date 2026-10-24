"""Recompute the supplied sensitivity calculator and save an audited copy.

The source workbook is read only. Other worksheet parts and input values are
preserved. Existing styles/namespaces remain intact through cell-level edits.
"""
from collections import Counter
import csv
from html import escape
from itertools import permutations
import json
from pathlib import Path
import re
from statistics import stdev
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from inspect_workbook import NS, read_workbook


SOURCE = Path(r"C:\Users\norud\Downloads\Chapter 3 PD1 Calculator.xlsx")
DIRECTORY = Path(__file__).resolve().parent
OUTPUT = DIRECTORY / "Chapter 3 PD1 Calculator - audited.xlsx"


def normalized(values, maximize):
    low, high = min(values), max(values)
    if high == low:
        return [5.5] * len(values)
    return [1 + 9 * ((value - low) if maximize else (high - value)) / (high - low) for value in values]


def score_rows(rankings, weight_rows):
    scores, winners = [], []
    for weights in weight_rows:
        row = [sum(weights[index] * rankings[index][design] for index in range(5)) / sum(weights)
               for design in range(3)]
        scores.append(row)
        best = max(row)
        tied = [index for index, value in enumerate(row) if abs(value - best) <= 1e-10]
        winners.append(tied[0] if len(tied) == 1 else None)
    return scores, winners


def main():
    original = read_workbook(SOURCE)
    sheet = original["sheets"][0]
    cells = sheet["cells"]
    names = [cells[f"{column}3"]["value"] for column in "BCD"]
    raw = [[cells[f"{column}{row}"]["value"] for column in "BCD"] for row in range(4, 9)]
    importance = [cells[f"C{row}"]["value"] for row in range(13, 18)]
    weight_rows = [[cells[f"{column}{row}"]["value"] for column in "BCDEF"] for row in range(35, 155)]
    assert len(set(importance)) == 5 and sum(importance) > 0
    assert len(weight_rows) == 120 and {tuple(row) for row in weight_rows} == set(permutations(importance))
    original_rankings = [normalized(values, False) for values in raw]
    corrected_rankings = [normalized(values, index == 2) for index, values in enumerate(raw)]
    old_scores, old_winners = score_rows(original_rankings, weight_rows)
    new_scores, new_winners = score_rows(corrected_rankings, weight_rows)
    before_counts = [old_winners.count(index) for index in range(3)]
    after_counts = [new_winners.count(index) for index in range(3)]
    assert before_counts == [cells[f"{column}35"]["value"] for column in "PQR"] == [30, 86, 4]
    assert after_counts == [120, 0, 0]
    cache_error = max(abs(old_scores[row - 35][index] - cells[f"{column}{row}"]["value"])
                      for row in range(35, 155) for index, column in enumerate("LMN"))
    assert cache_error < 1e-8

    with ZipFile(SOURCE) as archive:
        original_xml = archive.read(sheet["part"]).decode("utf-8")
        xml = original_xml
        original_tree = ET.fromstring(original_xml)
        attributes = {cell.attrib["r"]: dict(cell.attrib)
                      for cell in original_tree.findall("s:sheetData/s:row/s:c", NS)}
        strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        text_values = ["".join(item.itertext()) for item in strings.findall("s:si", NS)]
        changed = []

        def put(address, value, formula=None, shared_string=False, style_from=None):
            nonlocal xml
            attrs = dict(attributes.get(address, attributes.get(style_from, {})))
            attrs["r"] = address
            attrs.pop("t", None)
            if formula is not None:
                attrs["t"] = "str" if isinstance(value, str) else "n"
                body = "<f>" + escape(formula) + "</f><v>" + escape(str(value) if isinstance(value, str) else format(value, ".17g")) + "</v>"
            elif shared_string:
                attrs["t"] = "s"
                body = f"<v>{text_values.index(value)}</v>"
            elif isinstance(value, str):
                attrs["t"] = "inlineStr"
                body = "<is><t>" + escape(value) + "</t></is>"
            else:
                attrs["t"] = "n"
                body = "<v>" + format(value, ".17g") + "</v>"
            element = "<c " + " ".join(f'{key}="{escape(str(item), quote=True)}"' for key, item in attrs.items()) + ">" + body + "</c>"
            pattern = r'<c\b[^>]*\br="' + re.escape(address) + r'"[^>]*(?:/>|>.*?</c>)'
            xml, replacements = re.subn(pattern, lambda match: element, xml, count=1, flags=re.DOTALL)
            if not replacements:
                row = int(re.search(r"\d+", address).group())
                pattern = r'(<row\b[^>]*\br="' + str(row) + r'"[^>]*>)(.*?)(</row>)'
                xml, replacements = re.subn(pattern, lambda match: match[1] + match[2] + element + match[3], xml, count=1, flags=re.DOTALL)
            assert replacements == 1, address
            changed.append(address)

        put("B15", "Maximize", shared_string=True)
        for index, preference_row in enumerate(range(13, 18)):
            put(f"D{preference_row}", importance[index] / sum(importance) * 100,
                f"C{preference_row}/$C$18*100")
            rank_row, raw_row = 23 + index, 4 + index
            put(f"B{rank_row}", importance[index], f"C{preference_row}")
            put(f"C{rank_row}", importance[index] / sum(importance) * 100, f"D{preference_row}")
            area = f"$B{raw_row}:$D{raw_row}"
            for design, (target, source_column) in enumerate(zip("DEF", "BCD")):
                source_cell = f"{source_column}{raw_row}"
                formula = (f'IF(MAX({area})=MIN({area}),5.5,'
                           f'IF($B${preference_row}="Maximize",'
                           f'1+9*({source_cell}-MIN({area}))/(MAX({area})-MIN({area})),'
                           f'1+9*(MAX({area})-{source_cell})/(MAX({area})-MIN({area}))))')
                put(f"{target}{rank_row}", corrected_rankings[index][design], formula)
        base_scores = score_rows(corrected_rankings, [importance])[0][0]
        for index, column in enumerate("DEF"):
            put(f"{column}28", base_scores[index], f"SUMPRODUCT({column}23:{column}27,$C$23:$C$27)/100")

        # All 120 weighting scenarios now link to their source weights through
        # standard cell references, replacing PERMUTE and frozen pasted values.
        source_weight = {value: f"$C${13 + index}" for index, value in enumerate(importance)}
        for row, weights in zip(range(35, 155), weight_rows):
            for index, column in enumerate("BCDEF"):
                put(f"{column}{row}", weights[index], source_weight[weights[index]])
            for index, column in enumerate("GHIJK"):
                put(f"{column}{row}", weights[index] / sum(weights) * 100, f"{'BCDEF'[index]}{row}/$C$18*100")
            for index, (column, ranking_column) in enumerate(zip("LMN", "DEF")):
                terms = [f"{ranking_column}${23 + item}*${'GHIJK'[item]}{row}" for item in range(5)]
                put(f"{column}{row}", new_scores[row - 35][index], "SUM(" + ",".join(terms) + ")/100")
            area = f"L{row}:N{row}"
            winner = new_winners[row - 35]
            put(f"O{row}", "Tie" if winner is None else names[winner],
                f'IF(COUNTIF({area},MAX({area}))>1,"Tie",INDEX($L$34:$N$34,1,MATCH(MAX({area}),{area},0)))')
        for index, column in enumerate("PQR"):
            put(f"{column}34", names[index], f"{'LMN'[index]}34")
            put(f"{column}35", after_counts[index], f'COUNTIF($O$35:$O$154,{column}34)')
        for index, column in enumerate("STU"):
            put(f"{column}34", names[index], f"{'LMN'[index]}34")
            put(f"{column}35", stdev(row[index] for row in new_scores), f"STDEVA({'LMN'[index]}35:{'LMN'[index]}154)")
        put("V34", "Ties", style_from="P34")
        put("V35", new_winners.count(None), 'COUNTIF($O$35:$O$154,"Tie")', style_from="P35")
        xml = re.sub(r'(<row\b[^>]*\br="(?:34|35)"[^>]*\bspans=")1:21(")', r'\g<1>1:22\2', xml)
        ET.fromstring(xml)  # Reject malformed XML before creating a copy.
        with ZipFile(OUTPUT, "w") as destination:
            for item in archive.infolist():
                destination.writestr(item, xml.encode("utf-8") if item.filename == sheet["part"] else archive.read(item.filename))

    audited = read_workbook(OUTPUT)
    checked = audited["sheets"][0]["cells"]
    for row in range(4, 9):
        for column in "BCD":
            assert checked[f"{column}{row}"]["value"] == cells[f"{column}{row}"]["value"]
    for row in range(13, 18):
        assert checked[f"C{row}"]["value"] == cells[f"C{row}"]["value"]
    assert checked["B15"]["value"] == "Maximize"
    assert [checked[f"{column}35"]["value"] for column in "PQR"] == after_counts
    assert not any("PERMUTE(" in (value.get("formula") or "").upper() for value in checked.values())
    assert {tuple(checked[f"{column}{row}"]["value"] for column in "BCDEF") for row in range(35, 155)} == set(permutations(importance))
    with ZipFile(SOURCE) as source_archive, ZipFile(OUTPUT) as copy_archive:
        assert copy_archive.testzip() is None
        assert source_archive.namelist() == copy_archive.namelist()
        unchanged_parts = [name for name in source_archive.namelist() if name != sheet["part"]]
        assert all(source_archive.read(name) == copy_archive.read(name) for name in unchanged_parts)
    assert read_workbook(SOURCE)["sha256"] == original["sha256"]
    assert normalized([7, 7, 7], True) == [5.5, 5.5, 5.5]
    assert score_rows([[5.5] * 3] * 5, [importance])[1] == [None]
    summary = {"source": str(SOURCE), "source_sha256": original["sha256"], "copy": str(OUTPUT),
               "copy_sha256": audited["sha256"], "sheet": sheet["name"],
               "original_winner_counts": dict(zip(names, before_counts)),
               "corrected_winner_counts": dict(zip(names, after_counts)),
               "original_base_scores": dict(zip(names, score_rows(original_rankings, [importance])[0][0])),
               "corrected_base_scores": dict(zip(names, base_scores)),
               "normalized_before": original_rankings, "normalized_after": corrected_rankings,
               "criterion_weights": importance, "weight_scenarios": 120,
               "interpretation": "All permutations of criterion weights, not independent benchmark measurements.",
               "original_cached_score_max_error": cache_error, "ties": new_winners.count(None),
               "changed_cells": changed, "untouched_zip_parts": len(unchanged_parts),
               "validation": "Independent Python arithmetic and ZIP/XML/cache checks; not native Excel recalculation.",
               "raw_inputs_preserved": True, "original_file_preserved": True}
    (DIRECTORY / "audit-results.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (DIRECTORY / "sensitivity-comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Weight scenario", "Storage weight", "Latency weight", "MI weight", "RAM weight", "CPU weight",
                         *["Original score: " + name for name in names], "Original winner",
                         *["Corrected score: " + name for name in names], "Corrected winner"])
        for index, weights in enumerate(weight_rows):
            old, new = old_winners[index], new_winners[index]
            writer.writerow([f"S{index + 1}", *weights, *old_scores[index], "Tie" if old is None else names[old],
                             *new_scores[index], "Tie" if new is None else names[new]])
    print(json.dumps({key: summary[key] for key in ("copy", "original_winner_counts", "corrected_winner_counts", "corrected_base_scores", "raw_inputs_preserved", "original_file_preserved")}, indent=2))


if __name__ == "__main__":
    main()
