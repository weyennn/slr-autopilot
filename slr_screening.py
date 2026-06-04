"""
SLR Screening Tool - Content Moderation & Freedom of Expression in Southeast Asia
Menggunakan Kiro AI via 9Router (localhost:20128)

Usage:
  python slr_screening.py                          # pakai default (sample.ris)
  python slr_screening.py -i data/Ready\ \(1\).ris # input custom
  python slr_screening.py -m kr/claude-sonnet-4.5  # ganti model
  python slr_screening.py --review                 # review artikel low-confidence
  python slr_screening.py --dry-run                # validasi file tanpa panggil API
  python slr_screening.py --help
"""

import re
import json
import asyncio
import argparse
import aiohttp
from pathlib import Path
from tqdm import tqdm

# ── Default Konfigurasi ───────────────────────────────────────────────────────
ROUTER_BASE_URL       = "http://localhost:20128/v1"
DEFAULT_MODEL         = "kr/claude-haiku-4.5"
DEFAULT_INPUT         = "sample.ris"
DEFAULT_OUTPUT_DIR    = "output"
LOG_FILENAME          = "screening_log.json"
CONCURRENT_REQUESTS   = 5
DELAY_BETWEEN_BATCHES = 2

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a systematic literature review screener. Your task is to screen abstracts for relevance to a specific research topic.

RESEARCH TOPIC: How Southeast Asian Legal Frameworks Respond to Big Tech Self-Regulation in the Context of Content Moderation and Freedom of Expression.

INCLUSION CRITERIA - Include if the article discusses ANY of:
1. Content moderation by social media / digital platforms (Facebook, Twitter/X, YouTube, TikTok, etc.)
2. Freedom of expression / free speech in digital/online context
3. Platform governance, platform regulation, or self-regulation by tech companies
4. Digital/internet laws or regulations in Southeast Asia (Indonesia, Malaysia, Thailand, Vietnam, Philippines, Singapore, Myanmar, Cambodia, Laos, Brunei)
5. Hate speech, disinformation, misinformation regulation online
6. Big Tech regulation, platform accountability
7. Digital rights, online censorship
8. Social media law, internet governance in SE Asia context

EXCLUSION CRITERIA - Exclude if the article is ONLY about:
- Traditional/offline media regulation (no digital/platform component)
- Content moderation in non-SE Asian developed countries (US, EU, UK) with no SE Asia relevance
- Pure technical/algorithmic content moderation without legal/governance angle
- Ride-hailing, e-commerce, blockchain, fintech (unless specifically about platform content governance)
- COVID-19, health policy, environmental topics
- Cybersecurity (technical) without freedom of expression angle

RESPONSE FORMAT (JSON only, no other text):
{
  "decision": "include" or "exclude",
  "confidence": "high" or "medium" or "low",
  "reason": "one sentence explanation"
}"""

# ── Duplicate Detection ───────────────────────────────────────────────────────
def find_duplicates(articles):
    seen_titles, seen_dois = {}, {}
    duplicates = []
    for i, article in enumerate(articles):
        title = (article.get('TI') or '').lower().strip()
        doi   = (article.get('DO') or '').lower().strip()
        if doi and doi in seen_dois:
            duplicates.append((i, seen_dois[doi], 'DOI'))
        elif title and title in seen_titles:
            duplicates.append((i, seen_titles[title], 'Title'))
        else:
            if doi:   seen_dois[doi]     = i
            if title: seen_titles[title] = i
    return duplicates

# ── RIS Parser ────────────────────────────────────────────────────────────────
def parse_ris(filepath):
    articles = []
    current = {}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('ER  -'):
                if current:
                    articles.append(current)
                    current = {}
            elif '  - ' in line:
                tag = line[:2].strip()
                value = line[6:]
                if tag == 'TY':
                    current = {'TY': value, '_raw_lines': [line]}
                elif tag in current:
                    if isinstance(current[tag], list):
                        current[tag].append(value)
                    else:
                        current[tag] = [current[tag], value]
                    current['_raw_lines'].append(line)
                else:
                    current[tag] = value
                    current['_raw_lines'].append(line)
            elif current:
                current['_raw_lines'].append(line)
    return articles


def rebuild_ris_entry(article, decision):
    lines = article.get('_raw_lines', []).copy()
    lines.append(
        f'N1  - SCREENING: {decision["decision"].upper()} '
        f'| Confidence: {decision["confidence"]} | {decision["reason"]}'
    )
    lines.append('ER  -')
    lines.append('')
    return '\n'.join(lines)

# ── Screening ─────────────────────────────────────────────────────────────────
async def screen_article(session, article, model):
    title    = article.get('TI', 'No title')
    abstract = article.get('AB', '')
    keywords = article.get('KW', '')

    if isinstance(keywords, list):
        keywords = ', '.join(keywords)

    if not abstract:
        return {"decision": "exclude", "confidence": "high", "reason": "No abstract available."}

    user_message = f"Title: {title}\n\nAbstract: {abstract}\n\nKeywords: {keywords}\n\nPlease screen this article."

    payload = {
        "model": model,
        "max_tokens": 150,
        "stream": False,
        "messages": [{"role": "user", "content": user_message}],
        "system": SYSTEM_PROMPT,
    }
    headers = {"Authorization": "Bearer dummy", "Content-Type": "application/json"}

    for attempt in range(3):
        try:
            async with session.post(
                f"{ROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data['choices'][0]['message']['content'].strip()
                    content = re.sub(r'```json\s*|\s*```', '', content).strip()
                    return json.loads(content)
                elif resp.status == 429:
                    await asyncio.sleep(10 * (attempt + 1))
                else:
                    await asyncio.sleep(5)
        except json.JSONDecodeError:
            await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(5)

    return {"decision": "undecided", "confidence": "low", "reason": "Screening failed after retries."}


async def screen_all(pending, log, log_path, model, concurrency, delay):
    connector = aiohttp.TCPConnector(limit=concurrency)

    with tqdm(total=len(pending), desc="Screening", unit="artikel",
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:

        async with aiohttp.ClientSession(connector=connector) as session:
            for batch_start in range(0, len(pending), concurrency):
                batch   = pending[batch_start:batch_start + concurrency]
                indices = [i for i, _ in batch]
                tasks   = [screen_article(session, a, model) for _, a in batch]
                results = await asyncio.gather(*tasks)

                for idx, result in zip(indices, results):
                    log[str(idx)] = result

                with open(log_path, 'w') as f:
                    json.dump(log, f, indent=2)

                pbar.update(len(batch))
                pbar.set_postfix({
                    "include": sum(1 for v in log.values() if v['decision'] == 'include'),
                    "exclude": sum(1 for v in log.values() if v['decision'] == 'exclude'),
                })

                if batch_start + concurrency < len(pending):
                    await asyncio.sleep(delay)

# ── Review Mode ───────────────────────────────────────────────────────────────
def run_review_mode(articles, log, log_path):
    low_conf = [
        (i, a) for i, a in enumerate(articles)
        if log.get(str(i), {}).get('confidence') in ('low', 'medium')
    ]

    if not low_conf:
        print("\nTidak ada artikel dengan confidence low/medium. Semua sudah yakin!")
        return

    print(f"\n{'='*60}")
    print(f"REVIEW MODE — {len(low_conf)} artikel perlu dicek ulang")
    print(f"{'='*60}")

    changed = 0
    for idx, (i, article) in enumerate(low_conf):
        current  = log.get(str(i), {})
        title    = article.get('TI', 'No title')
        abstract = (article.get('AB', '') or '')[:400]

        print(f"\n[{idx+1}/{len(low_conf)}]")
        print(f"Judul       : {title}")
        print(f"Abstrak     : {abstract}...")
        print(f"AI Decision : {current.get('decision', '').upper()} ({current.get('confidence')})")
        print(f"Alasan      : {current.get('reason', '')}")
        print("\n  [i] Include  [e] Exclude  [Enter] Keep AI decision  [q] Quit")

        try:
            choice = input("Pilihan: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nReview dihentikan.")
            break

        if choice == 'q':
            break
        elif choice == 'i':
            log[str(i)] = {"decision": "include", "confidence": "high", "reason": "Manually overridden to include."}
            changed += 1
            print("  → Include ✓")
        elif choice == 'e':
            log[str(i)] = {"decision": "exclude", "confidence": "high", "reason": "Manually overridden to exclude."}
            changed += 1
            print("  → Exclude ✓")

    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    print(f"\nReview selesai. {changed} artikel diubah keputusannya.")

# ── Output ────────────────────────────────────────────────────────────────────
def write_output(articles, log, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    included, excluded, undecided = [], [], []

    with open(output_dir / "hasil_screening.ris", 'w', encoding='utf-8') as f_all, \
         open(output_dir / "included.ris",        'w', encoding='utf-8') as f_inc, \
         open(output_dir / "excluded.ris",        'w', encoding='utf-8') as f_exc:

        for i, article in enumerate(articles):
            decision  = log.get(str(i), {"decision": "undecided", "confidence": "low", "reason": "Not processed"})
            ris_entry = rebuild_ris_entry(article, decision)
            f_all.write(ris_entry + '\n')

            if decision['decision'] == 'include':
                f_inc.write(ris_entry + '\n')
                included.append(i)
            elif decision['decision'] == 'exclude':
                f_exc.write(ris_entry + '\n')
                excluded.append(i)
            else:
                undecided.append(i)

    return included, excluded, undecided

# ── CLI & Main ────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="SLR Abstract Screening Tool — AI-powered include/exclude screening",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python slr_screening.py
  python slr_screening.py -i data/Ready\\ \\(1\\).ris
  python slr_screening.py -i data/Ready\\ \\(1\\).ris -m kr/claude-sonnet-4.5
  python slr_screening.py --review
        """
    )
    parser.add_argument("-i", "--input",       default=DEFAULT_INPUT,      help=f"Input RIS file (default: {DEFAULT_INPUT})")
    parser.add_argument("-m", "--model",       default=DEFAULT_MODEL,      help=f"Model (default: {DEFAULT_MODEL})")
    parser.add_argument("-c", "--concurrency", default=CONCURRENT_REQUESTS, type=int, help=f"Paralel requests (default: {CONCURRENT_REQUESTS})")
    parser.add_argument("-d", "--delay",       default=DELAY_BETWEEN_BATCHES, type=float, help=f"Delay antar batch detik (default: {DELAY_BETWEEN_BATCHES})")
    parser.add_argument("-o", "--output-dir",  default=DEFAULT_OUTPUT_DIR, help=f"Output folder (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--review",            action="store_true",        help="Review interaktif untuk artikel low/medium confidence")
    parser.add_argument("--dry-run",           action="store_true",        help="Validasi file & deteksi duplikat tanpa panggil API")
    return parser.parse_args()


async def main():
    args = parse_args()

    input_path  = Path(args.input)
    output_dir  = Path(args.output_dir)
    log_path    = output_dir / LOG_FILENAME

    print("=" * 60)
    print("SLR Screening Tool - Content Moderation & SE Asia")
    print("=" * 60)
    print(f"Input  : {input_path}")
    print(f"Model  : {args.model}")
    print(f"Output : {output_dir}/")

    if not input_path.exists():
        print(f"\nERROR: File '{input_path}' tidak ditemukan.")
        return

    print(f"\nMemuat file...")
    articles = parse_ris(str(input_path))
    total    = len(articles)
    print(f"Total artikel: {total}")

    # Duplicate detection
    dups = find_duplicates(articles)
    if dups:
        print(f"Duplikat terdeteksi: {len(dups)} artikel")
        for i, j, method in dups[:5]:
            print(f"  #{i+1} ≈ #{j+1} ({method})")
        if len(dups) > 5:
            print(f"  ... dan {len(dups)-5} lainnya")
    else:
        print("Tidak ada duplikat.")

    if args.dry_run:
        print("\n[DRY RUN] Selesai — tidak ada artikel yang diproses.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        with open(log_path, 'r') as f:
            log = json.load(f)
        print(f"Melanjutkan: {len(log)} sudah diproses")
    else:
        log = {}

    pending = [(i, a) for i, a in enumerate(articles) if str(i) not in log]
    print(f"Sisa: {len(pending)} artikel\n")

    if pending:
        await screen_all(pending, log, log_path, args.model, args.concurrency, args.delay)

    if args.review:
        run_review_mode(articles, log, log_path)

    print("\nMembuat file output...")
    included, excluded, undecided = write_output(articles, log, output_dir)

    conf = {"high": 0, "medium": 0, "low": 0}
    for v in log.values():
        c = v.get('confidence', 'low')
        conf[c] = conf.get(c, 0) + 1

    print("\n" + "=" * 60)
    print("HASIL SCREENING")
    print("=" * 60)
    print(f"Total artikel  : {total}")
    print(f"Include        : {len(included)} ({len(included)/total*100:.1f}%)")
    print(f"Exclude        : {len(excluded)} ({len(excluded)/total*100:.1f}%)")
    print(f"Undecided      : {len(undecided)}")
    print(f"\nConfidence AI  :")
    print(f"  High         : {conf['high']}")
    print(f"  Medium       : {conf['medium']}")
    print(f"  Low          : {conf['low']}")
    print(f"\nOutput tersimpan di: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
