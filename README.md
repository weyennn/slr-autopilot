# SLR Autopilot

Automated abstract screening tool for Systematic Literature Review (SLR) using AI via local API router.

Screens thousands of academic article abstracts automatically — deciding include/exclude based on a configurable research topic and criteria — then exports results to Excel or an interactive HTML dashboard.

## The Problem

Screening thousands of abstracts manually is exhausting:

- **Manual:** read abstracts one by one → dozens of hours
- **SLR Autopilot:** automated AI screening → minutes

## How it works

```
RIS file (exported from Rayyan/Scopus/Web of Science/etc.)
    ↓
slr_screening.py  →  sends each abstract to AI model via local API router
    ↓
output/screening_log.json  (resumeable progress log)
    ↓
export_excel.py   →  output/hasil_screening.xlsx  (4 sheets + charts)
export_html.py    →  output/dashboard.html         (interactive dashboard)
export_prisma.py  →  output/prisma_flow.png + output/prisma_report.docx
                     (PRISMA 2020 flow diagram + 27-item checklist)
```

## Requirements

- Python 3.10+
- Local AI API router (e.g. [Kiro / 9Router](https://kiro.ai)) running on `localhost:20128`

```bash
pip install -r requirements.txt
```

## Configuration

Before running, edit the `SYSTEM_PROMPT` in `slr_screening.py` to match your research topic and inclusion/exclusion criteria. The current sample is set up for a Southeast Asia content moderation SLR.

## Usage

**1. Validate your RIS file (dry run)**
```bash
python slr_screening.py --dry-run -i yourfile.ris
```
Checks article count, detects duplicates — without calling the API.

**2. Run screening**
```bash
# Default (sample.ris)
python slr_screening.py

# Custom input file
python slr_screening.py -i yourfile.ris

# Use a more accurate model
python slr_screening.py -i yourfile.ris -m kr/claude-sonnet-4.5

# Review low-confidence decisions interactively after screening
python slr_screening.py -i yourfile.ris --review
```

**3. Export to Excel**
```bash
python export_excel.py -i yourfile.ris -l output/screening_log.json
```

**4. Export to HTML dashboard**
```bash
python export_html.py -i yourfile.ris -l output/screening_log.json
```
Opens as a single self-contained HTML file — no internet connection needed.

**5. Export PRISMA 2020 flow diagram + report**
```bash
python export_prisma.py -i yourfile.ris -l output/screening_log.json

# With manual full-text screening counts (after you finish that stage)
python export_prisma.py \
  --fulltext-assessed 83 --fulltext-excluded 12 \
  --fulltext-reasons "Wrong topic:7; No full text:3; Wrong language:2"
```
Generates `prisma_flow.png` (publication-ready) + `prisma_report.docx` (editable in Word: diagram + 27-item PRISMA 2020 checklist + abstract checklist). Source: https://www.prisma-statement.org/prisma-2020

## CLI Options

**slr_screening.py**

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | `sample.ris` | Input RIS file |
| `-m`, `--model` | `kr/claude-haiku-4.5` | AI model to use |
| `-c`, `--concurrency` | `5` | Parallel requests |
| `-d`, `--delay` | `2` | Delay between batches (seconds) |
| `-o`, `--output-dir` | `output/` | Output folder |
| `--dry-run` | — | Validate file without calling the API |
| `--review` | — | Interactively review low-confidence results |

**export_excel.py / export_html.py**

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | `sample.ris` | Input RIS file |
| `-l`, `--log` | `output/screening_log.json` | Screening log file |
| `-o`, `--output` | `output/hasil_screening.xlsx` / `output/dashboard.html` | Output file |

## Output

| File | Description |
|---|---|
| `output/screening_log.json` | Full log: decision + confidence + reason per article |
| `output/included.ris` | Articles that passed screening |
| `output/excluded.ris` | Articles that were excluded |
| `output/hasil_screening.ris` | All articles with decision tag |
| `output/hasil_screening.xlsx` | Excel report: 4 sheets + 4 charts |
| `output/dashboard.html` | Interactive HTML dashboard with search & filter |
| `output/prisma_flow.png` | PRISMA 2020 flow diagram (publication-ready) |
| `output/prisma_report.docx` | PRISMA report: diagram + 27-item + abstract checklist |

See the [`examples/`](examples/) folder for sample output from running on `sample.ris`.

## Features

- **Configurable** — swap in any research topic and criteria via `SYSTEM_PROMPT`
- **Resume-able** — continues from where it left off if interrupted
- **Async parallel** — processes multiple articles simultaneously
- **Duplicate detection** — flags duplicate titles/DOIs before screening
- **Dry-run mode** — validate your RIS file before committing API calls
- **Rate limit handling** — auto retry with exponential backoff
- **Interactive review** — manually override low-confidence AI decisions
- **Excel export** — full metadata + decisions + confidence + reason + 4 charts
- **HTML dashboard** — searchable, tabbed, self-contained — shareable without Excel
- **PRISMA 2020** — auto-generated flow diagram (PNG) + editable DOCX with 27-item checklist
