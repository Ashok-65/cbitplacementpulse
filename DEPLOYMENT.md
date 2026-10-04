# Deploying PlacementPulse

The homepage loads the complete, verified placement archive from
`Backend/data/cbit_pdf_placements.json`. Keep this file in the deployment; it
contains 7,898 records across 11 cohorts. The site displays 25 rows per page,
with filters and search covering the full archive.

## Deploy on Vercel

1. Push this project to a Git provider and import that repository in Vercel.
2. Set the project root to the repository root. Use the **Other** framework
   preset; leave the build and output-directory fields empty.
3. Deploy. Vercel reads the Python dependencies from the root
   `requirements.txt` and routes the site and API through `api/index.py`.
4. After deployment, check `https://<your-domain>/api/health` for
   `"status": "healthy"` and
   `https://<your-domain>/api/cbit-pdf-placements` for a JSON `records` array
   containing 7,898 records. Open the site and check that its footer reports
   **7,898 placement records loaded** and the pager shows **316 pages**.
5. In Vercel's project settings, assign a domain if you want a custom URL.

`vercel.json` explicitly bundles the archive and frontend assets with the
Python function. On Vercel, SQLite is placed under `/tmp` so the function can
start on its read-only deployment filesystem. `/tmp` is temporary and
per-instance: CSV uploads and other database changes are not durable there.
The homepage's official placement archive is bundled with each deployment and
does not depend on SQLite. For durable uploads or editable database records,
configure `DATABASE_URL` to a persistent PostgreSQL database before deploying.

## Deploy with Docker

The Docker image includes both the Flask app and the complete archive. Start
the production container with Docker Compose:

```powershell
docker compose up --build -d
```

Compose keeps the SQLite database in `Backend/instance` on the host and serves
the site on port 5000. For a Docker host that supplies its own `PORT`, the
container now binds to that port. Persist `/app/Backend/instance` when running
the image outside Compose.

## Updating the official archive

Rebuild `Backend/data/cbit_pdf_placements.json` with
`Backend/import_cbit_placements_pdf.py`, verify that extraction completes for
each cohort, then deploy the updated file. The build script checks extracted
row counts against the official cohort totals and fails rather than publishing
an incomplete archive.
