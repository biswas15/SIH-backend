# Thermal Risk Backend - Phase 1

This backend service provides weather ingestion functionality, retrieving forecast data for specific areas around Haldia.

## Tech Stack
- Python 3.9+
- FastAPI
- Uvicorn
- HTTPX
- Open-Meteo (Free weather API)

## Setup

1. Create a virtual environment and install dependencies:
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

2. Start the FastAPI development server:
```powershell
uvicorn main:app --reload
```

## Testing the API

To test the endpoint, open a new terminal or use any REST client (like Postman).

**Using cURL:**
```powershell
curl.exe "http://127.0.0.1:8000/api/weather?area_id=H01"
```

You should receive a standardized JSON response containing the 72-hour forecast (temperature, humidity, wind speed) for Haldia Township.
