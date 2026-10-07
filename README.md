# Wanderleaf — Full Travel Planner Starter

A warm, paper-like Travel Planner built with FastAPI, Jinja, SQLite (development DB), authentication, saved trips, destination exploration, itinerary/cost generation, comparison, profile settings and PDF export.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8010
```
Open `http://127.0.0.1:8010`.

## What already works
- Register, login and logout (hashed passwords)
- User-specific saved trips
- Create trip: destination, days, travelers, budget, travel style and hotel
- Generated day-wise itinerary
- Estimated transport/stay/food/activity cost and budget check
- Destination explorer, attractions, hotels, weather/map placeholders
- Compare two destinations
- Profile/settings and preferred currency field
- Delete saved trips
- PDF export for saved trips
- Responsive warm brown paper/journal UI

## API SETUP — the only part you need to replace later
All external API inputs are isolated in **`services/external_apis.py`**. The website currently uses safe demo data from **`services/demo_data.py`**, so it works without any API account.

1. Copy `.env.example` to `.env`.
2. Put real keys into these variables when ready:
   - `WEATHER_API_KEY`
   - `PLACES_API_KEY`
   - `HOTELS_API_KEY`
   - `MAPS_API_KEY`
   - `CURRENCY_API_KEY`
3. Open `services/external_apis.py`. Every replacement point is labelled **`API INPUT EXAMPLE`**. Replace the demo return with the request to your chosen provider while keeping the returned dictionary shape the same.

This means the rest of `app.py`, templates and database code does not have to be rewritten when you connect real APIs.

## Database note
For zero-setup local testing this ZIP uses SQLite at `data/travel.db`. For the final PostgreSQL deployment, replace the small `sqlite3` persistence layer with PostgreSQL/SQLAlchemy; the page flow and API adapter structure can stay the same.

## Scope note
Wanderleaf plans trips and provides estimates. It intentionally does not perform real hotel/flight bookings or payments.

## Live APIs (added)
`services/external_apis.py` now talks to real providers and falls back to the demo data on any failure.
- **Default:** demo data, exactly as before (works offline).
- **`USE_FREE_APIS=true`** in `.env`: live weather + geocoding (Open-Meteo) and exchange rates (Frankfurter), no account needed.
- **Real keys:** `WEATHER_API_KEY` (OpenWeatherMap), `MAPS_API_KEY` (Google Geocoding), `PLACES_API_KEY` (OpenTripMap: attractions + hotel names for places not in `demo_data.py`), `CURRENCY_API_KEY` (exchangerate-api.com).
- `HOTELS_API_KEY` is reserved: no hotel-price provider is connected yet, so hotel prices for new places are estimates.
- Open `GET /api/status` to see which provider each feature is using.
