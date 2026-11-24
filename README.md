# AI Tools Usage Among College Students – Survey Dashboard

Students answer a **Google Form**; responses land in a linked **Google Sheet**; this Flask app reads the
Sheet (as CSV) and shows a live, password-protected analytics dashboard.

```
Google Form  ->  Google Sheet ("Form Responses 1")  ->  dashboard.py (Flask)  ->  admin dashboard
```

## Run locally

```powershell
python -m pip install -r requirements.txt
$env:SHEET_CSV_URL="<published or export CSV link of the Form Responses 1 tab>"
$env:FORM_URL="<your Google Form link>"
$env:ADMIN_PASSWORD="choose-a-password"
$env:SECRET_KEY="any-long-random-text"
python dashboard.py
```

Open http://localhost:5000 and sign in.

## Configuration

| Variable | Purpose |
|---|---|
| `SHEET_CSV_URL` | CSV link of the Form Responses tab (required) |
| `FORM_URL` | Public Google Form link shown on the dashboard |
| `ADMIN_PASSWORD` | Dashboard password (default `admin123` – change it) |
| `SECRET_KEY` | Session signing key |

## Notes
- Columns are read by position (Timestamp, then Q1–Q17). Finish the form before collecting responses.
- Published CSVs can lag a few minutes; the Sheet's `export?format=csv&gid=…` link is live (needs "Anyone with the link: Viewer").
- Deploy with `gunicorn dashboard:app` (see `Procfile`). Never commit the CSV link or passwords.
