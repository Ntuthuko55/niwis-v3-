# NIWIS v2

National Integrated Water Information System (NIWIS) is a dashboard for exploring South African climate, drought, satellite, water-storage, and time-series data.

## Run locally

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open the local Vite URL displayed in the terminal. The frontend proxies API requests to `http://localhost:8000`.

## Project layout

- `frontend/` - React and Vite dashboard
- `backend/` - FastAPI services and analysis pipelines
- `csv's/` - local climate, hydrology, and satellite input data
- `South_Africa_Provinces/` - provincial source datasets

## Notes

Local environment files, development logs, virtual environments, and generated build output are excluded from version control.
