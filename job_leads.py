#!/usr/bin/env python3
"""
Daily job-lead finder for logistics / supply chain / manufacturing recruitment.

Pulls fresh postings from Reed and Adzuna (both free, both legal to query via API —
unlike Indeed, which has no public API and prohibits scraping in its ToS).

Each posting serves two purposes:
  - Candidate lead: an open role you could fill.
  - Sales lead: the company behind it, especially ones posting multiple roles
    (a strong signal they're actively hiring and might want recruitment help).

Output: a single self-contained dashboard.html file.

Setup:
  1. Get a free Reed API key:   https://www.reed.co.uk/developers/jobseeker
  2. Get a free Adzuna API key: https://developer.adzuna.com/
  3. Set them as environment variables (or GitHub Secrets, see workflow file):
       REED_API_KEY
       ADZUNA_APP_ID
       ADZUNA_APP_KEY
  4. Edit CONFIG below to match your search.
  5. Run: python job_leads.py
"""

import os
import re
import json
import html
import requests
from datetime import datetime, timezone
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIG — edit this to match your search
# ---------------------------------------------------------------------------
CONFIG = {
    # Search terms — one search is run per keyword, per location
    "keywords": [
        "logistics manager",
        "supply chain manager",
        "warehouse manager",
        "operations manager logistics",
        "manufacturing manager",
        "procurement manager",
    ],
    # UK locations to search. Use "UK" for a nationwide Adzuna search.
    "locations": ["UK"],
    # Results per keyword/location pair, per source (API max is usually 50-100)
    "results_per_search": 25,
    # Skip companies you already work with, so they don't show up as "leads"
    "existing_clients": [
        # "Example Logistics Ltd",
    ],
    # Only flag a company as a strong sales lead once it has at least this many
    # open roles found today
    "sales_lead_min_postings": 2,
}

REED_API_KEY = os.environ.get("REED_API_KEY", "")
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

OUTPUT_FILE = "dashboard.html"


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def fetch_reed(keyword, location):
    if not REED_API_KEY:
        return []
    url = "https://www.reed.co.uk/api/1.0/search"
    params = {
        "keywords": keyword,
        "locationName": None if location == "UK" else location,
        "resultsToTake": CONFIG["results_per_search"],
    }
    try:
        resp = requests.get(url, params=params, auth=(REED_API_KEY, ""), timeout=20)
        resp.raise_for_status()
        data = resp.json().get("results", [])
    except requests.RequestException as e:
        print(f"[reed] error for '{keyword}' / '{location}': {e}")
        return []

    out = []
    for j in data:
        out.append({
            "source": "Reed",
            "title": j.get("jobTitle", "").strip(),
            "company": (j.get("employerName") or "Unknown").strip(),
            "location": j.get("locationName", "").strip(),
            "url": j.get("jobUrl", ""),
            "posted_date": j.get("date", ""),
            "salary": j.get("minimumSalary") and j.get("maximumSalary") and
                      f"£{int(j['minimumSalary']):,} - £{int(j['maximumSalary']):,}" or "",
            "snippet": (j.get("jobDescription") or "")[:220].strip(),
        })
    return out


def fetch_adzuna(keyword, location):
    if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
        return []
    url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "where": None if location == "UK" else location,
        "results_per_page": CONFIG["results_per_search"],
        "content-type": "application/json",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("results", [])
    except requests.RequestException as e:
        print(f"[adzuna] error for '{keyword}' / '{location}': {e}")
        return []

    out = []
    for j in data:
        salary_min = j.get("salary_min")
        salary_max = j.get("salary_max")
        salary = ""
        if salary_min and salary_max:
            salary = f"£{int(salary_min):,} - £{int(salary_max):,}"
        out.append({
            "source": "Adzuna",
            "title": (j.get("title") or "").strip(),
            "company": (j.get("company", {}).get("display_name") or "Unknown").strip(),
            "location": (j.get("location", {}).get("display_name") or "").strip(),
            "url": j.get("redirect_url", ""),
            "posted_date": (j.get("created") or "")[:10],
            "salary": salary,
            "snippet": (j.get("description") or "")[:220].strip(),
        })
    return out


def clean_title(title):
    return re.sub(r"\s+", " ", title).strip()


def dedupe(postings):
    seen = {}
    for p in postings:
        key = (clean_title(p["title"]).lower(), p["company"].strip().lower(), p["location"].strip().lower())
        if key not in seen:
            seen[key] = p
    return list(seen.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    all_postings = []
    for keyword in CONFIG["keywords"]:
        for location in CONFIG["locations"]:
            all_postings += fetch_reed(keyword, location)
            all_postings += fetch_adzuna(keyword, location)

    all_postings = dedupe(all_postings)

    excluded = {c.strip().lower() for c in CONFIG["existing_clients"]}
    all_postings = [p for p in all_postings if p["company"].strip().lower() not in excluded]

    # Sales leads: group by company
    by_company = defaultdict(list)
    for p in all_postings:
        by_company[p["company"]].append(p)

    sales_leads = sorted(
        [{"company": c, "roles": rs, "count": len(rs)} for c, rs in by_company.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Candidate leads: individual roles, most recent first
    def sort_key(p):
        return p.get("posted_date") or ""
    candidate_leads = sorted(all_postings, key=sort_key, reverse=True)

    render_dashboard(candidate_leads, sales_leads)
    print(f"Done. {len(all_postings)} unique postings across {len(by_company)} companies.")
    print(f"Wrote {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------
def render_dashboard(candidate_leads, sales_leads):
    run_date = datetime.now(timezone.utc).strftime("%d %b %Y")
    run_time = datetime.now(timezone.utc).strftime("%H:%M UTC")

    strong_leads = [s for s in sales_leads if s["count"] >= CONFIG["sales_lead_min_postings"]]
    other_leads = [s for s in sales_leads if s["count"] < CONFIG["sales_lead_min_postings"]]

    def esc(s):
        return html.escape(s or "")

    def company_card(entry, flagged):
        roles_html = "".join(
            f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a>'
            f'<span class="meta">{esc(r["location"])}'
            f'{" · " + esc(r["salary"]) if r["salary"] else ""}</span></li>'
            for r in entry["roles"]
        )
        badge = '<span class="stamp">ACTIVE HIRING</span>' if flagged else ""
        return f"""
        <article class="lead-card{' flagged' if flagged else ''}">
          <header>
            <h3>{esc(entry['company'])}</h3>
            {badge}
          </header>
          <div class="count">{entry['count']} open role{'s' if entry['count'] != 1 else ''}</div>
          <ul class="roles">{roles_html}</ul>
        </article>"""

    sales_html = "".join(company_card(e, True) for e in strong_leads)
    sales_html += "".join(company_card(e, False) for e in other_leads[:30])

    rows_html = ""
    for p in candidate_leads:
        rows_html += f"""
        <tr>
          <td class="job-title"><a href="{esc(p['url'])}" target="_blank" rel="noopener">{esc(p['title'])}</a></td>
          <td>{esc(p['company'])}</td>
          <td>{esc(p['location'])}</td>
          <td>{esc(p['salary']) or '—'}</td>
          <td>{esc(p['posted_date']) or '—'}</td>
          <td><span class="tag tag-{p['source'].lower()}">{esc(p['source'])}</span></td>
        </tr>"""

    total = len(candidate_leads)
    companies = len(sales_leads)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Lead Manifest — {run_date}</title>
<style>
  :root {{
    --bg: #161d27;
    --panel: #1d2632;
    --panel-line: #2c3846;
    --ink: #eee9dd;
    --ink-dim: #9aa7b4;
    --amber: #e8871e;
    --steel: #5f8ab5;
    --green: #6a9955;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: 'IBM Plex Sans', -apple-system, Segoe UI, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: var(--steel); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .manifest-head {{
    border-bottom: 2px solid var(--panel-line);
    padding: 28px 32px 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 16px;
  }}
  .manifest-head h1 {{
    font-family: 'Oswald', 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 28px;
    margin: 0 0 4px;
  }}
  .manifest-head .sub {{
    color: var(--ink-dim);
    font-size: 13px;
    font-family: 'IBM Plex Mono', monospace;
  }}
  .odometer {{
    display: flex;
    gap: 22px;
    font-family: 'IBM Plex Mono', monospace;
  }}
  .odo-item {{ text-align: right; }}
  .odo-item .n {{
    font-size: 30px;
    font-weight: 600;
    color: var(--amber);
    line-height: 1;
  }}
  .odo-item .l {{
    font-size: 11px;
    color: var(--ink-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}

  main {{ padding: 28px 32px 60px; max-width: 1200px; margin: 0 auto; }}

  section.block {{ margin-bottom: 44px; }}
  section.block > h2 {{
    font-family: 'Oswald', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 15px;
    color: var(--amber);
    border-bottom: 1px solid var(--panel-line);
    padding-bottom: 8px;
    margin-bottom: 18px;
  }}
  section.block > p.desc {{
    color: var(--ink-dim);
    font-size: 13px;
    margin: -12px 0 18px;
  }}

  .lead-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
  }}
  .lead-card {{
    background: var(--panel);
    border: 1px solid var(--panel-line);
    border-left: 3px solid var(--panel-line);
    padding: 14px 16px;
    border-radius: 3px;
  }}
  .lead-card.flagged {{ border-left-color: var(--amber); }}
  .lead-card header {{
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 8px;
  }}
  .lead-card h3 {{ font-size: 15px; margin: 0 0 4px; }}
  .stamp {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.08em;
    color: var(--amber);
    border: 1px solid var(--amber);
    padding: 2px 6px;
    border-radius: 2px;
    transform: rotate(3deg);
    white-space: nowrap;
    flex-shrink: 0;
  }}
  .lead-card .count {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--ink-dim);
    margin-bottom: 8px;
  }}
  .lead-card ul.roles {{ list-style: none; margin: 0; padding: 0; }}
  .lead-card ul.roles li {{
    font-size: 13px;
    padding: 5px 0;
    border-top: 1px solid var(--panel-line);
  }}
  .lead-card ul.roles li:first-child {{ border-top: none; }}
  .lead-card .meta {{
    display: block;
    color: var(--ink-dim);
    font-size: 11px;
    margin-top: 1px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  thead th {{
    text-align: left;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 11px;
    color: var(--ink-dim);
    border-bottom: 1px solid var(--panel-line);
    padding: 8px 10px;
  }}
  tbody td {{
    padding: 10px;
    border-bottom: 1px solid var(--panel-line);
    vertical-align: top;
  }}
  tbody tr:hover {{ background: var(--panel); }}
  .job-title a {{ color: var(--ink); font-weight: 500; }}

  .tag {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 2px;
    letter-spacing: 0.03em;
  }}
  .tag-reed {{ background: rgba(95,138,181,0.18); color: var(--steel); }}
  .tag-adzuna {{ background: rgba(106,153,85,0.18); color: var(--green); }}

  footer {{
    color: var(--ink-dim);
    font-size: 11px;
    text-align: center;
    padding: 20px;
    font-family: 'IBM Plex Mono', monospace;
  }}

  @media (max-width: 640px) {{
    .manifest-head {{ padding: 20px 16px; }}
    main {{ padding: 20px 16px 40px; }}
  }}
</style>
</head>
<body>

<div class="manifest-head">
  <div>
    <h1>Daily Lead Manifest</h1>
    <div class="sub">Logistics · Supply Chain · Manufacturing — run {run_date}, {run_time}</div>
  </div>
  <div class="odometer">
    <div class="odo-item"><div class="n">{total}</div><div class="l">Open roles</div></div>
    <div class="odo-item"><div class="n">{companies}</div><div class="l">Companies</div></div>
    <div class="odo-item"><div class="n">{len(strong_leads)}</div><div class="l">Active hirers</div></div>
  </div>
</div>

<main>
  <section class="block">
    <h2>Sales leads — companies to pitch</h2>
    <p class="desc">Grouped by company. Amber-flagged "Active hiring" companies have {CONFIG['sales_lead_min_postings']}+ open roles today — a stronger signal they need recruitment support.</p>
    <div class="lead-grid">
      {sales_html if sales_html.strip() else '<p style="color:var(--ink-dim)">No leads found — check your API keys are set.</p>'}
    </div>
  </section>

  <section class="block">
    <h2>Candidate leads — open roles</h2>
    <p class="desc">Every unique role found today, most recent first.</p>
    <table>
      <thead>
        <tr><th>Role</th><th>Company</th><th>Location</th><th>Salary</th><th>Posted</th><th>Source</th></tr>
      </thead>
      <tbody>
        {rows_html if rows_html.strip() else '<tr><td colspan="6" style="color:var(--ink-dim)">No roles found.</td></tr>'}
      </tbody>
    </table>
  </section>
</main>

<footer>Generated automatically · Reed &amp; Adzuna APIs · not affiliated with Indeed</footer>

</body>
</html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()
