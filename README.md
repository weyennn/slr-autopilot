# SLR Autopilot

Automated abstract screening tool for Systematic Literature Review (SLR) using AI via local API router.

Built for the research topic: **How Southeast Asian Legal Frameworks Respond to Big Tech Self-Regulation in the Context of Content Moderation and Freedom of Expression.**

## The Problem

Screening thousands of academic abstracts manually is exhausting:

- **Manual (Rayyan):** read 3,886 abstracts one by one → ~32 hours
- **SLR Autopilot:** automated AI screening → ~20 minutes

## How it works

```
RIS file (exported from Rayyan/Scopus/etc.)
    ↓
slr_screening.py  →  sends each abstract to AI model via local API router
    ↓
screening_log.json  (resumeable progress log)
    ↓
export_excel.py  →  hasil_screening.xlsx (4 sheets + charts)
```

## Requirements

- Python 3.10+
- Local API router (e.g. [9Router / Kiro](https://kiro.ai)) running on `localhost:20128`

```bash
pip install -r requirements.txt
```

## Usage

**1. Run screening**
```bash
# Default (sample.ris)
python slr_screening.py

# Custom input file
python slr_screening.py -i data/myfile.ris

# Use a more accurate model
python slr_screening.py -i data/myfile.ris -m kr/claude-sonnet-4.5

# Review low-confidence decisions interactively
python slr_screening.py --review

# Full options
python slr_screening.py --help
```

**2. Export to Excel**
```bash
python export_excel.py
```

Generates `hasil_screening.xlsx` with sheets: All, Include, Exclude, Summary, Visualisasi.

## CLI Options

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | `sample.ris` | Input RIS file |
| `-m`, `--model` | `kr/claude-haiku-4.5` | AI model to use |
| `-c`, `--concurrency` | `5` | Parallel requests |
| `-d`, `--delay` | `2` | Delay between batches (seconds) |
| `-o`, `--output-dir` | `output/` | Output folder |
| `--review` | — | Interactive review for low-confidence results |

## Output

| File | Description |
|---|---|
| `output/screening_log.json` | Full log: decision + confidence + reason per article |
| `output/included.ris` | Articles that passed screening |
| `output/excluded.ris` | Articles that were excluded |
| `output/hasil_screening.ris` | All articles with decision tag |
| `output/hasil_screening.xlsx` | Excel report with 4 sheets + 4 charts |

## Features

- **Resume-able** — continues from where it left off if interrupted
- **Async parallel** — processes multiple articles simultaneously
- **Rate limit handling** — auto retry with exponential backoff
- **Interactive review mode** — manually override low-confidence AI decisions
- **Excel export** — metadata + decisions + confidence + reason + visualizations
