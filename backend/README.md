# BDC API (FastAPI)

## Setup

1. Create a virtual environment and install deps:
```
pip install -r webapp/backend/requirements.txt
```

2. Create a `.env` file in `webapp/backend/` with:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bdc_dev
DB_USER=your_user
DB_PASSWORD=your_password
```

3. Run the API:
```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir webapp/backend
```

## Endpoints
- GET /health
- GET /meta/states
- GET /meta/counties?state=Alabama
- GET /reports/run?script=Location%20Level&state=Alabama&counties=01001&counties=01003

## Encrypted .env (optional but recommended)

You can store secrets in an encrypted `.env.enc` instead of plaintext `.env`.

### 1) Install dependencies

```
pip install -r webapp/backend/requirements.txt
```

### 2) Generate encryption key

```
python webapp/backend/app/envsec.py gen-key
```

Copy the printed key and store it securely (for local dev, you can set it in your shell profile or a secret manager). Do not commit the key.

### 3) Encrypt your `.env`

```
python webapp/backend/app/envsec.py encrypt webapp/backend/.env webapp/backend/.env.enc
```

You can delete `.env` after verifying `.env.enc` works.

### 4) Run the API with the key

Set `ENV_ENC_KEY` in your environment before running the API. Example (PowerShell):

```powershell
$env:ENV_ENC_KEY = "<paste-key-here>"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir webapp/backend
```

At startup, if `.env.enc` exists and `ENV_ENC_KEY` is set, the app will decrypt it in-memory and load variables without creating a plaintext file.

### 5) Decrypt for editing (optional)

```
python webapp/backend/app/envsec.py decrypt webapp/backend/.env.enc -o webapp/backend/.env
```

Prefer editing a temporary `.env` and re-encrypting.

## Git safeguards

- The repo is configured to ignore env files via root `.gitignore`.
- A local git hook in `.githooks/pre-commit` blocks committing `.env*` and `.env.enc` files.

Enable the hook:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

You can bypass in emergencies with `--no-verify` (not recommended).