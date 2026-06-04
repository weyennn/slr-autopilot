"""
Export hasil screening SLR ke HTML dashboard interaktif.
Self-contained — satu file HTML tanpa dependency eksternal.

Usage:
  python export_html.py
  python export_html.py -i data/Ready\ \(1\).ris -l output/screening_log.json
  python export_html.py -o output/dashboard.html
"""

import json
import io
import base64
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# ── Parser ────────────────────────────────────────────────────────────────────
def parse_ris(filepath):
    articles, current = [], {}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('ER  -'):
                if current:
                    articles.append(current)
                    current = {}
            elif '  - ' in line:
                tag, value = line[:2].strip(), line[6:]
                if tag == 'TY':
                    current = {'TY': value}
                elif tag in current:
                    current[tag] = [current[tag], value] if not isinstance(current[tag], list) else current[tag] + [value]
                else:
                    current[tag] = value
    return articles

def flatten(val):
    if isinstance(val, list):
        return '; '.join(val)
    return val or ''

# ── Charts ────────────────────────────────────────────────────────────────────
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close(fig)
    return base64.b64encode(buf.read()).decode()

def make_charts(inc, exc):
    charts = {}

    # Pie chart
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie([inc, exc], labels=['Include', 'Exclude'],
           colors=['#2ecc71', '#e74c3c'], autopct='%1.1f%%',
           startangle=90, wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    ax.set_title('Include vs Exclude', fontsize=12, fontweight='bold', pad=12)
    charts['pie'] = fig_to_b64(fig)

    # Bar chart
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(['Include', 'Exclude'], [inc, exc],
                  color=['#2ecc71', '#e74c3c'], width=0.4, edgecolor='white')
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + max(inc, exc)*0.01,
                f'{int(h):,}', ha='center', fontweight='bold', fontsize=11)
    ax.set_ylim(0, max(inc, exc) * 1.12)
    ax.set_title('Jumlah Artikel', fontsize=12, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    charts['bar'] = fig_to_b64(fig)

    return charts

# ── HTML Template ─────────────────────────────────────────────────────────────
def build_html(articles, log, charts, generated_at):
    rows_inc, rows_exc = [], []
    for i, article in enumerate(articles):
        d = log.get(str(i), {"decision": "undecided", "confidence": "-", "reason": "-"})
        row = {
            "no":         i + 1,
            "title":      flatten(article.get("TI")),
            "authors":    flatten(article.get("AU")),
            "year":       flatten(article.get("PY") or article.get("Y1")),
            "journal":    flatten(article.get("JO") or article.get("JF") or article.get("T2")),
            "confidence": d.get("confidence", "-"),
            "reason":     d.get("reason", "-"),
            "doi":        flatten(article.get("DO")),
        }
        if d["decision"] == "include":
            rows_inc.append(row)
        elif d["decision"] == "exclude":
            rows_exc.append(row)

    total = len(articles)
    inc   = len(rows_inc)
    exc   = len(rows_exc)
    rate  = f"{inc/total*100:.1f}%" if total else "0%"

    def table_rows(rows):
        html = ""
        for r in rows:
            doi_link = f'<a href="https://doi.org/{r["doi"]}" target="_blank">{r["doi"]}</a>' if r["doi"] else "-"
            conf_cls = {"high": "conf-high", "medium": "conf-med", "low": "conf-low"}.get(r["confidence"], "")
            html += f"""
            <tr>
              <td>{r["no"]}</td>
              <td class="title-cell">{r["title"]}</td>
              <td>{r["authors"][:60]}{"..." if len(r["authors"]) > 60 else ""}</td>
              <td>{r["year"]}</td>
              <td>{r["journal"][:40]}{"..." if len(r["journal"]) > 40 else ""}</td>
              <td><span class="badge {conf_cls}">{r["confidence"]}</span></td>
              <td class="reason-cell">{r["reason"]}</td>
              <td>{doi_link}</td>
            </tr>"""
        return html

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SLR Autopilot — Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #2c3e50; }}

  header {{ background: linear-gradient(135deg, #2c3e50, #3498db); color: white; padding: 28px 40px; }}
  header h1 {{ font-size: 1.8rem; font-weight: 700; letter-spacing: -0.5px; }}
  header p  {{ margin-top: 4px; opacity: 0.8; font-size: 0.9rem; }}

  .container {{ max-width: 1300px; margin: 0 auto; padding: 28px 24px; }}

  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .stat-card {{ background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  .stat-card .label {{ font-size: 0.8rem; color: #7f8c8d; text-transform: uppercase; letter-spacing: .5px; }}
  .stat-card .value {{ font-size: 2rem; font-weight: 700; margin-top: 4px; }}
  .stat-card.green .value {{ color: #2ecc71; }}
  .stat-card.red   .value {{ color: #e74c3c; }}
  .stat-card.blue  .value {{ color: #3498db; }}

  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 28px; }}
  .chart-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.07); text-align: center; }}
  .chart-card img {{ max-width: 100%; height: auto; }}

  .table-section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  .table-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }}
  .tabs {{ display: flex; gap: 8px; }}
  .tab {{ padding: 8px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 600; transition: all .2s; background: #f0f2f5; color: #7f8c8d; }}
  .tab.active {{ background: #3498db; color: white; }}
  .search-box {{ padding: 8px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 0.9rem; width: 260px; outline: none; }}
  .search-box:focus {{ border-color: #3498db; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th {{ background: #f8f9fa; padding: 10px 12px; text-align: left; font-weight: 600; color: #555; border-bottom: 2px solid #eee; white-space: nowrap; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f0f2f5; vertical-align: top; }}
  tr:hover td {{ background: #fafbfc; }}
  .title-cell {{ font-weight: 500; max-width: 280px; }}
  .reason-cell {{ max-width: 220px; color: #666; font-size: 0.82rem; }}
  a {{ color: #3498db; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .badge {{ padding: 3px 8px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }}
  .conf-high {{ background: #d5f5e3; color: #1e8449; }}
  .conf-med  {{ background: #fef9e7; color: #b7950b; }}
  .conf-low  {{ background: #fadbd8; color: #922b21; }}

  .no-result {{ text-align: center; padding: 40px; color: #aaa; }}
  footer {{ text-align: center; padding: 20px; color: #aaa; font-size: 0.8rem; }}
</style>
</head>
<body>

<header>
  <h1>SLR Autopilot</h1>
  <p>Screening Dashboard &mdash; {generated_at}</p>
</header>

<div class="container">

  <div class="stats">
    <div class="stat-card">
      <div class="label">Total Artikel</div>
      <div class="value">{total:,}</div>
    </div>
    <div class="stat-card green">
      <div class="label">Include</div>
      <div class="value">{inc:,}</div>
    </div>
    <div class="stat-card red">
      <div class="label">Exclude</div>
      <div class="value">{exc:,}</div>
    </div>
    <div class="stat-card blue">
      <div class="label">Include Rate</div>
      <div class="value">{rate}</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card"><img src="data:image/png;base64,{charts['pie']}" alt="Pie Chart"></div>
    <div class="chart-card"><img src="data:image/png;base64,{charts['bar']}" alt="Bar Chart"></div>
  </div>

  <div class="table-section">
    <div class="table-header">
      <div class="tabs">
        <button class="tab active" onclick="switchTab('include', this)">Include ({inc})</button>
        <button class="tab" onclick="switchTab('exclude', this)">Exclude ({exc})</button>
      </div>
      <input class="search-box" type="text" id="search" placeholder="Cari judul atau penulis..." oninput="filterTable()">
    </div>

    <div id="tab-include">
      <table id="tbl-include">
        <thead><tr><th>#</th><th>Judul</th><th>Penulis</th><th>Tahun</th><th>Jurnal</th><th>Conf.</th><th>Alasan AI</th><th>DOI</th></tr></thead>
        <tbody>{table_rows(rows_inc)}</tbody>
      </table>
    </div>

    <div id="tab-exclude" style="display:none">
      <table id="tbl-exclude">
        <thead><tr><th>#</th><th>Judul</th><th>Penulis</th><th>Tahun</th><th>Jurnal</th><th>Conf.</th><th>Alasan AI</th><th>DOI</th></tr></thead>
        <tbody>{table_rows(rows_exc)}</tbody>
      </table>
    </div>
  </div>

</div>

<footer>Generated by SLR Autopilot &mdash; {generated_at}</footer>

<script>
  let activeTab = 'include';

  function switchTab(tab, btn) {{
    activeTab = tab;
    document.getElementById('tab-include').style.display = tab === 'include' ? '' : 'none';
    document.getElementById('tab-exclude').style.display = tab === 'exclude' ? '' : 'none';
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('search').value = '';
    filterTable();
  }}

  function filterTable() {{
    const q = document.getElementById('search').value.toLowerCase();
    const tbody = document.querySelector('#tbl-' + activeTab + ' tbody');
    let visible = 0;
    tbody.querySelectorAll('tr').forEach(row => {{
      const text = row.textContent.toLowerCase();
      const show = text.includes(q);
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
  }}
</script>
</body>
</html>"""

# ── CLI & Main ────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="Export hasil screening SLR ke HTML dashboard")
    parser.add_argument("-i", "--input",  default="sample.ris",                help="Input RIS file (default: sample.ris)")
    parser.add_argument("-l", "--log",    default="output/screening_log.json",  help="Screening log JSON (default: output/screening_log.json)")
    parser.add_argument("-o", "--output", default="output/dashboard.html",      help="Output HTML file (default: output/dashboard.html)")
    return parser.parse_args()


def main():
    args = parse_args()

    print("Membaca RIS...")
    articles = parse_ris(args.input)
    print(f"Total artikel: {len(articles)}")

    print("Membaca log screening...")
    with open(args.log, 'r') as f:
        log = json.load(f)

    inc = sum(1 for v in log.values() if v.get('decision') == 'include')
    exc = sum(1 for v in log.values() if v.get('decision') == 'exclude')

    print("Membuat chart...")
    charts = make_charts(inc, exc)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(articles, log, charts, generated_at)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nSelesai! Buka: {args.output}")
    print(f"  Include : {inc} artikel")
    print(f"  Exclude : {exc} artikel")


if __name__ == "__main__":
    main()
