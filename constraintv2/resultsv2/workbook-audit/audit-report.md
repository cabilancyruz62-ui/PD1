# PupVitals workbook scoring audit

Audited file: `Chapter 3 PD1 Calculator.xlsx`, sheet **Copy of Chapter 3**.

The original workbook in Downloads is unchanged. The corrected copy is [Chapter 3 PD1 Calculator - audited.xlsx](<Chapter 3 PD1 Calculator - audited.xlsx>).

## Confirmed scoring error

Cell **B15** specifies **Minimize** for Maintainability Index. The normalization in **D25:F25** therefore gives the highest score to the lowest MI. Higher MI represents higher maintainability according to [Radon's MI grading](https://radon.readthedocs.io/en/latest/commandline.html#the-mi-command).

| Design | Given MI | Original normalized score | Corrected normalized score |
| --- | ---: | ---: | ---: |
| ArUco | 64.27 | 1.0000 | 10.0000 |
| ORB + RANSAC | 32.98 | 10.0000 | 1.0000 |
| Optical flow | 40.97 | 7.7018 | 3.2982 |

The corrected preference is **Maximize**. Storage, latency, RAM and CPU remain **Minimize**. A lower MI is not a better maintenance result.

## Recomputed results with the same inputs

| Result | ArUco | ORB + RANSAC | Optical flow |
| --- | ---: | ---: | ---: |
| Original winner count | 30 | 86 | 4 |
| Corrected winner count | 120 | 0 | 0 |
| Original score at the stated weights | 5.489888 | 6.286773 | 4.853678 |
| Corrected score at the stated weights | 7.064888 | 4.711773 | 4.083041 |

The counts change because the MI preference was reversed. The input measurements and importance weights were not edited to choose a particular winner. No ties occur in either original or corrected results for these inputs.

## What the 120 rows represent

Rows **35-154** contain all **5! = 120 permutations** of weights **6, 10, 7, 9, 8**. Every criterion receives each weight 24 times. These are weight sensitivity scenarios, not 120 newly measured benchmark runs. The workbook contains no random sampling for these scenarios.

The fixed importance settings apply to the base weighted score in D28:F28. The sensitivity grid deliberately changes which criterion receives each weight. Its winner count is not a measured success rate, confidence level, or probability that a design is best. Changing the original ordering of the same five distinct weights does not change the set of all 120 permutations.

See [sensitivity-comparison.csv](sensitivity-comparison.csv) for the original and corrected scores and winners for every weight scenario.

## Corrections in the copied workbook

- B15 is **Maximize**. D23:F27 now follows each criterion's preference label, including the corrected MI direction.
- A criterion with identical values for all designs receives the same neutral score of 5.5; normalization avoids division by zero. This adds the same weighted contribution to each design.
- Percentage weights and all 120 sensitivity weight rows use ordinary cell references to the original importance cells. The two `PERMUTE(...)` calls and frozen sensitivity weights are replaced on the PupVitals sheet. This keeps the current scenarios unchanged while allowing source weights to propagate.
- Weighted scores and winner-count caches are recomputed independently. Exact ties produce **Tie**, with a separate tally in V35, rather than assigning the first design by column order. Current ties: zero.
- Standard-deviation headers S34:U34 now match their actual ArUco / ORB / optical-flow score columns. These deviations describe variation across weight assignments, not measurement repeatability.
- All raw inputs B4:D8 and importance values C13:C17 remain unchanged. All other ZIP parts, including the two unrelated template worksheets, are preserved byte for byte.

## Input provenance still needs checking

The spreadsheet uses storage values **13.1 / 20.8 / 17.6**, while the application's saved tracker-source results use **0.002890 / 0.007358 / 0.006090 MB**. Those are different quantities or measurement versions; their units and source need to be established before publication.

The workbook uses ArUco CPU **49%**, matching the current edited CSV, while the saved original constraint JSON has approximately **43.996%**. The audited workbook retains **49%** as supplied. It does not overwrite either source or infer which measurement the user intended.

The current application benchmark also remains exploratory: short trials, synthetic targets, software graphics and mode-specific dog screen sizes can affect CPU/RAM comparisons. A formal study should use consistent recorded inputs, equal rendering workloads, repeated trials with balanced order, and tracking correctness/loss checks. [NIST experimental design guidance](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm) explains controlling nuisance factors and randomizing the remaining variation.

## Validation and limits

Independent arithmetic reproduces the original scenario scores to within approximately **4.95e-10**, including the exact original 30 / 86 / 4 counts. The corrected normalized scores, base totals, all 120 scenario scores, winner counts and sample standard deviations were recomputed and stored in the copied workbook.

ZIP integrity, XML parsing, preserved raw inputs, complete weight permutations, equal-value/tie cases, unchanged other archive parts and the original file's SHA-256 were checked. Validation used Python arithmetic and workbook XML/caches; the copy has not been recalculated by a native Excel application in this environment. The two unrelated worksheets retain their original formulas and were not corrected.

Detailed values and file hashes are in [audit-results.json](audit-results.json). No application benchmark observations were changed and no new physical tracking tests were performed.
