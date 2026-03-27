# DEMO-GD

FastAPI demo backend for Apifox / frontend integration.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## URLs

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Persistence

- SQLite database file: [demo.db](GD-MVP/algorithm_platform/demo/demo.db)
- Database bootstrap and schema: [db.py](GD-MVP/algorithm_platform/demo/db.py)

## Seed Data

Initial seed data is inserted only when the database is empty.

- Algorithm UUID: `alg-7f3d91b2-1f0f-4e1c-b123-001`
- Version UUID: `ver-b4e1b301-cb17-44f9-a001-101`
- Version UUID: `ver-a99d1c01-2f17-47f1-b001-102`
- Image UUID: `img-3e3f9bb1-82c3-45aa-a111-301`

## Main Structure

- API layer: [app.py](GD-MVP/algorithm_platform/demo/app.py)
- Database layer: [db.py](GD-MVP/algorithm_platform/demo/db.py)
- Request models: [models.py](GD-MVP/algorithm_platform/demo/models.py)
