# Environment Setup

The `.env` file is **local-only** and must never be committed to git. It stores database credentials and your approved ReliefWeb appname on your machine only.

Copy the template from `.env.example` and create a plain-text `.env` file in the project root:

```
DATABASE_URL=postgresql://crisis_user:crisis_password@127.0.0.1:5432/crisis_resource_db
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=crisis_resource_db
POSTGRES_USER=crisis_user
POSTGRES_PASSWORD=crisis_password

RELIEFWEB_API_URL=https://api.reliefweb.int/v2/reports
RELIEFWEB_APPNAME=your_reliefweb_appname_here
GDACS_RSS_URL=https://www.gdacs.org/xml/rss.xml

API_HOST=0.0.0.0
API_PORT=8000
```

Replace `your_reliefweb_appname_here` with your approved ReliefWeb appname after you receive it.

## Format rules

- Every non-comment line must be `KEY=value`.
- Do not include quotes around values unless the value itself requires them.
- Do not include PowerShell syntax such as `@"`, `"@`, or `Set-Content` inside `.env`.
- Do not paste shell commands into `.env` — only environment variable assignments.
- `docker-compose.yml` is the source of truth for local PostgreSQL credentials. Your `.env` must match those values.

## Verify dotenv loading

From the project root:

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); print(os.getenv('DATABASE_URL'))"
```

Expected output:

```
postgresql://crisis_user:crisis_password@127.0.0.1:5432/crisis_resource_db
```

If this prints `None`, your `.env` file is missing, malformed, or not in the project root.

## Docker reset (if credentials changed)

If you changed PostgreSQL credentials in `docker-compose.yml`, reset the local database volume:

```bash
docker compose down -v
docker compose up -d
```

Then recreate `.env` from `.env.example` and rerun:

```bash
python -m database.test_connection
python -m database.load_reports
```
