# Daily Job Leads — Logistics / Supply Chain / Manufacturing

Automatically pulls fresh job postings each morning and builds a dashboard
splitting them into:

- **Sales leads** — companies currently hiring, grouped and flagged when they
  have multiple open roles (a sign they may want recruitment help)
- **Candidate leads** — every open role found, most recent first

It uses **Reed** and **Adzuna**, not Indeed — Indeed has no public API for
reading job postings and its Terms of Service prohibit automated scraping.
Reed and Adzuna both offer free, legal APIs with UK coverage and similar data.

## 1. Get two free API keys (takes a few minutes, no cost)

- **Reed**: sign up at https://www.reed.co.uk/developers/jobseeker — you get
  an API key instantly.
- **Adzuna**: register at https://developer.adzuna.com/ — you get an
  `app_id` and `app_key` instantly.

## 2. Set up the automation (fully hands-off, free)

1. Create a free GitHub account if you don't have one: https://github.com
2. Create a new **private** repository (e.g. `job-leads`) and upload all the
   files in this folder to it (`job_leads.py`, `.github/workflows/daily-leads.yml`,
   this README).
3. In the repo, go to **Settings → Secrets and variables → Actions** and add
   three repository secrets:
   - `REED_API_KEY`
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
4. Go to **Settings → Pages**, set the source to "Deploy from a branch",
   branch `main`, folder `/docs`. GitHub will give you a URL like
   `https://yourusername.github.io/job-leads/`.
5. Go to the **Actions** tab and run the "Daily Job Leads" workflow once
   manually (there's a "Run workflow" button) to check it works. After that
   it runs automatically every morning at 06:30 UTC — no further action
   needed. Bookmark the Pages URL as your daily dashboard.

## 3. Adjust the search to fit you

Open `job_leads.py` and edit the `CONFIG` block near the top:

- `keywords` — the job titles/terms to search for
- `locations` — use `["UK"]` for nationwide, or add specific towns/cities
- `existing_clients` — list companies to exclude, so current clients don't
  show up as "leads"
- `sales_lead_min_postings` — how many open roles a company needs before
  it's flagged as an active hiring signal

## 4. Running it locally instead (optional)

If you'd rather run it on your own PC each morning instead of using GitHub
Actions, you can:

```
pip install requests
set REED_API_KEY=your-key-here          (Windows)
set ADZUNA_APP_ID=your-id-here
set ADZUNA_APP_KEY=your-key-here
python job_leads.py
```

This creates `dashboard.html` in the same folder — open it in a browser.
For it to run automatically every day, add it to Windows Task Scheduler.
The GitHub Actions route in step 2 is simpler since it needs no PC left on.
