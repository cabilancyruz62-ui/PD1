"""Read an XLSX as data, preserving formulas and cached values for an audit."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import posixpath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def read_workbook(path):
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(item.itertext()) for item in root.findall("s:si", NS)]
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        result = {"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "calculation_settings": book.find("s:calcPr", NS).attrib,
                  "sheets": []}
        for definition in book.findall("s:sheets/s:sheet", NS):
            target = targets[definition.attrib[f"{{{REL}}}id"]]
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            sheet = ET.fromstring(archive.read(part))
            cells = {}
            for cell in sheet.findall("s:sheetData/s:row/s:c", NS):
                raw = cell.find("s:v", NS)
                value = raw.text if raw is not None else None
                kind = cell.get("t", "n")
                if kind == "s" and value is not None:
                    value = strings[int(value)]
                elif kind == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif kind == "n" and value is not None:
                    value = float(value)
                    if value.is_integer():
                        value = int(value)
                formula = cell.find("s:f", NS)
                if value is not None or formula is not None:
                    cells[cell.attrib["r"]] = {
                        "value": value, "type": kind, "style": cell.get("s"),
                        "formula": formula.text if formula is not None else None,
                        "formula_attributes": formula.attrib if formula is not None else None,
                    }
            dimension = sheet.find("s:dimension", NS)
            result["sheets"].append({"name": definition.attrib["name"], "part": part,
                                      "dimension": dimension.attrib if dimension is not None else None,
                                      "cells": cells})
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("workbook-cells.json"))
    args = parser.parse_args()
    report = read_workbook(args.workbook)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for sheet in report["sheets"]:
        cells = sheet["cells"]
        print("SHEET", sheet["name"], sheet["dimension"], "cells", len(cells))
        print("FORMULAS", sum(item["formula_attributes"] is not None for item in cells.values()))
        for address, item in cells.items():
            row = int("".join(char for char in address if char.isdigit()))
            if row <= 28 or isinstance(item["value"], str) and "winner" in item["value"].lower():
                print(address, str(item["value"])[:160], "FORMULA", item["formula"] or "")
