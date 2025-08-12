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
