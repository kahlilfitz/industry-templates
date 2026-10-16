# Human-test tracker specification

This page specifies the human-test tracker workbook well enough to build one from scratch. The
tracker records the two-person human spot check that must pass before an evaluated ZIP is
published. An automated Cowork `Ready` verdict is not a substitute for it. See
[Release process](../release-process.md), step 5.

## File and location

| Item | Rule |
|---|---|
| File name | `<plugin-slug>-human-test-tracker.xlsx`; in the Retail library layout (Professional Services Wave 1), `<Title Case Slug> - Human Test Tracker.xlsx` |
| Location | SharePoint library, the plugin folder (`<Industry>/<plugin-slug>/`, or `<Industry>/Wave <n>/<Title Case Slug>/` in the Retail layout), next to `Evaluation/` and `PLUGIN-DETAILS-AND-DEPLOYMENT.md` |
| Workbooks | One per plugin, for its whole life |
| Sheets | One sheet per evaluated version, named exactly by version (for example `1.0.2`), plus a `How to use` sheet |
| Sheet order | Newest version first, `How to use` last |
| Repository | Never commit a tracker, or a copy of one, to this repository |

A new evaluated version adds a new tab. Never overwrite or delete an earlier version's tab; it is
the record of what was tested on that ZIP.

## Sensitivity label

The library applies an encrypting sensitivity label to workbooks placed in it. After that:

- edit the workbook only in Excel desktop, Excel for the web, or through Excel COM automation;
- `openpyxl`, LibreOffice and other non-Office tools cannot open the labelled file;
- when automating, open read-only unless you intend to write, and always close without saving if
  you only read.

To create a new tracker, build it locally first (any tool works on an unlabelled file), check it in
Excel, then place it in the library. To add a version tab later, use Excel: right-click the newest
version tab, choose **Move or Copy**, tick **Create a copy**, place it first, rename it to the new
version, update the header block, replace the prompt rows and clear every tester column.

## Version sheet layout

Columns A to O. Rows 1 and 2 are blank spacing. Freeze panes below row 12 so the header block and
table header stay visible. Turn on AutoFilter on the table header. Wrap text in the prompt,
expected-result and notes columns. Make the table header bold with a fill colour.

### Header block (rows 3 to 10)

Labels in column A, values in column B.

| Row | Label (A) | Value (B) |
|---:|---|---|
| 3 | Plugin | `<plugin-slug>  (<Display name>)` |
| 4 | Artefact version | `<version>` |
| 5 | Evaluated zip | `<plugin-slug>.zip  -  <bytes> bytes  -  <file count> files` |
| 6 | Zip SHA-256 | `<SHA-256>` from the archived `recommendations.html` |
| 7 | Automated verdict | `<Ready>  -  publication pending human review  (<one-line summary>)` |
| 8 | Automated evidence | `Evaluation/<version>/  (plugin-health.html, behavioral-test-report.html, recommendations.html)` |
| 9 | Human spot check | `REQUIRED before publish - 2 independent testers on every prompt below` |
| 10 | Status | `NOT STARTED`, then `IN PROGRESS`, then `COMPLETE - PASS` or `COMPLETE - FAIL` |

Row 11 is blank.

### Table (header row 12, prompts from row 13)

| Column | Header | Content |
|---|---|---|
| A | `#` | Sequence number, 1 to n |
| B | `Test` | Short test name; prefix critical paths with `Critical path — ` |
| C | `Prompt` | Exact prompt text the tester pastes into Cowork |
| D | `Inputs` | Demo-data path or synthetic probe to attach or reference |
| E | `Expected result` | Observable pass condition |
| F | `Skill owner / basis` | Category and owning skill, for example `Behavioral should-not-trigger — owner: <skill>` |
| G | `T1 name` | Tester 1 |
| H | `T1 date` | Date tester 1 ran the prompt |
| I | `T1 result` | `Pass`, `Fail` or `Blocked` |
| J | `T1 notes` | What happened; required on `Fail` or `Blocked` |
| K | `T2 name` | Tester 2 |
| L | `T2 date` | Date tester 2 ran the prompt |
| M | `T2 result` | `Pass`, `Fail` or `Blocked` |
| N | `T2 notes` | What happened; required on `Fail` or `Blocked` |
| O | `Agreed outcome` | Formula, never typed |

Columns G to J are tester 1's group and K to N are tester 2's group. The two groups are independent:
a tester completes their own group without reading the other group first.

### Data validation

| Range | Rule |
|---|---|
| `I13:I<L>` | List: `Pass,Fail,Blocked` |
| `M13:M<L>` | List: `Pass,Fail,Blocked` |
| `B<L+14>` (owner decision) | List: `Publish,Fix and re-evaluate,Do not publish` |

No other cells carry validation. `<L>` is the last prompt row; see
[Row numbering](#row-numbering).

### Agreed outcome formula

In `O13`, filled down to `O<L>`:

```text
=IF(OR(I13="",M13=""),"awaiting",IF(AND(I13="Pass",M13="Pass"),"Pass",IF(OR(I13="Fail",M13="Fail"),"Fail","review")))
```

| T1 / T2 | Agreed outcome |
|---|---|
| Either blank | `awaiting` |
| Pass / Pass | `Pass` |
| Any Fail | `Fail` |
| Anything else (Pass/Blocked, Blocked/Blocked) | `review` |

### Row numbering

The prompt count `n` varies by version, so the summary and sign-off rows are defined relative to the
last prompt row:

```text
L = 12 + n        (prompts occupy rows 13 to L)
```

With the standard 30 prompts, `L` is 42, which gives the row numbers shown in brackets below. For
any other count, compute every row and range from `L`; do not keep the 30-prompt numbers. If you add
prompts to an existing tab, rebuild the summary and sign-off blocks at the new offsets and re-check
every formula range against the table below.

### Summary and sign-off block

Row `L+1` is blank. Every range runs from row 13 to row `L`.

| Row (n = 30) | Label (A) | Formula or value (B) |
|---|---|---|
| `L+2` (44) | Summary | |
| `L+3` (45) | Prompts in scope | `=COUNTA(B13:B<L>)` |
| `L+4` (46) | Tester 1 complete | `=COUNTIF(I13:I<L>,"Pass")+COUNTIF(I13:I<L>,"Fail")+COUNTIF(I13:I<L>,"Blocked")` |
| `L+5` (47) | Tester 2 complete | `=COUNTIF(M13:M<L>,"Pass")+COUNTIF(M13:M<L>,"Fail")+COUNTIF(M13:M<L>,"Blocked")` |
| `L+6` (48) | Agreed Pass | `=COUNTIF(O13:O<L>,"Pass")` |
| `L+7` (49) | Agreed Fail | `=COUNTIF(O13:O<L>,"Fail")` |
| `L+8` (50) | Needs review | `=COUNTIF(O13:O<L>,"review")` |
| `L+9` (51) | Still awaiting | `=COUNTIF(O13:O<L>,"awaiting")` |
| `L+10` (52) | (blank) | |
| `L+11` (53) | Publish gate | `=IF(AND(B<L+3>=B<L+6>,B<L+7>=0,B<L+8>=0,B<L+9>=0),"PASS","NOT CLEARED")` |
| `L+12` (54) | (blank) | |
| `L+13` (55) | Discrepancies resolved | Short note for every `review` or `Fail` row and how it was settled |
| `L+14` (56) | Owner decision | `Publish`, `Fix and re-evaluate` or `Do not publish` |
| `L+15` (57) | Decided by | Accountable owner's role |
| `L+16` (58) | Decision date | `YYYY-MM-DD` |

Write `<L>` and `<L+k>` as literal row numbers; for example, with 34 prompts `L` is 46, the
publish-gate cell is `B57` and its formula is
`=IF(AND(B49=B52,B53=0,B54=0,B55=0),"PASS","NOT CLEARED")`.

Add conditional formatting: green for `Pass` and red for `Fail` in columns I, M and O, amber for
`review` in column O, and green `PASS` / red `NOT CLEARED` on the publish-gate cell.

The publish gate covers the reviewers only. Promotion needs both the publish gate at `PASS` and
the owner decision at `Publish`. `Fix and re-evaluate` and `Do not publish` both mean the ZIP is not
promoted; see the release process,
[step 6](../release-process.md#step-6-publish-and-file-the-evidence).

## Prompt set

Aim for 30 prompts per version (rows 13 to 42). Both reviewers run every prompt in the tracker; the
critical-path prompts are the mandatory minimum the tracker must contain. Build them in this order:

| Category | Typical count | Source |
|---|---:|---|
| Critical path | 4 | One end-to-end run of the drama scenario, a claimed-approval override attempt, a send/publish boundary request, and the plugin's signature trap |
| Sample prompts | 10 to 22 | `tests/sample-test-prompts.csv` in the evaluated ZIP, one row per CSV line |
| Should-trigger | 8 to 10 | One or two per skill, from the behavioral report's should-trigger cases |
| Should-not-trigger | 4 | A prompt that belongs to a sibling, per skill boundary |
| Injection probe | 1 or more | An instruction embedded in source data that tries to clear a hold |
| Report spot checks | 0 to 8 | Any prompts `recommendations.html` lists under "Pending human-review evidence" |

Every critical-path prompt from the plugin details document must appear. Every blocker and `WEAK`
fixed since the previous version needs at least one prompt. If the total exceeds 30, add prompt rows
and place the summary and sign-off block at the offsets in [Row numbering](#row-numbering) rather
than dropping critical paths.

`tests/sample-test-prompts.csv` exists in three shapes across submissions. Map them as follows:

| CSV header | Mapping |
|---|---|
| `Number,Test,Prompt,Inputs,Expected result,Basis` | Columns A to F directly |
| `prompt,expected_behavior` | Prompt to C, expected behavior to E; write B, D and F by hand |
| `Number,Prompt` | Prompt to C; write B, D, E and F from the SKILL.md and expected outputs |

Use only synthetic demo data in prompts. Never put real client, colleague or tenant details in a
tracker.

## How to use sheet

Two columns, row 1 title `How to use this tracker`, freeze below row 2. Rows 3 to 9 are numbered
rules in column A with the text in column B:

1. One workbook per plugin. Add a new tab for each version; never overwrite a previous tab.
2. Two independent testers run every prompt in the tracker. Independent means they do not see each
   other's notes first. The critical-path prompts are the mandatory minimum the tracker must
   contain.
3. Install the exact ZIP filed in `Evaluation/<version>/`. Do not rebuild it.
4. The prompts come from `tests/sample-test-prompts.csv` plus any human spot-check prompts listed
   in `recommendations.html`.
5. Record Pass, Fail or Blocked in the T1/T2 result columns. Agreed outcome is calculated.
6. `review` means the two testers disagree. Resolve it before publishing; note the resolution.
7. The publish gate is PASS only when both testers pass every prompt and all agreed outcomes are
   Pass. The ZIP is promoted only when the publish gate is PASS and the owner decision is Publish.

Then: row 11 `Source` citing the testing strategy document and section, row 12 `Quote` with the
strategy's human spot-check requirement, and row 14 `Note`: "The automated Cowork evaluation is
NOT a substitute for this step."

## Acceptance

The human gate for a version has passed, and the ZIP may be promoted, only when every item is true.
Row references use `L`, the last prompt row (42 for 30 prompts).

- [ ] Header block rows 3 to 8 match the archived reports, including the SHA-256.
- [ ] Both testers installed the exact evaluated ZIP and recorded name and date on every row.
- [ ] Both testers ran every prompt in the tracker, including every critical-path prompt, and
  `B<L+4>` and `B<L+5>` equal `B<L+3>`.
- [ ] Every `Fail`, `Blocked` and `review` row has notes and was investigated; resolutions are
  recorded in row `L+13`.
- [ ] The publish gate `B<L+11>` shows `PASS` (`B53` for 30 prompts).
- [ ] Row 10 status reads `COMPLETE - PASS`.
- [ ] The owner decision `B<L+14>` reads `Publish`, with role and date in rows `L+15` and `L+16`.
- [ ] `PLUGIN-DETAILS-AND-DEPLOYMENT.md` section 8 human-gate status is updated to match.

If the owner decision is `Fix and re-evaluate` or `Do not publish`, the ZIP is not promoted even
when the publish gate shows `PASS`. A `Blocked` result from a tooling problem is rerun, not waived.
A genuine `Fail` means the version is not published: fix the plugin, increment the version,
re-evaluate, and add a new tab.
