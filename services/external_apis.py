"""External API adapters (weather, maps, places/hotels, currency).

Same function names and return shapes as the original, so routes, templates and the PDF are unchanged.
Behaviour:
  * No real key and USE_FREE_APIS off  -> built-in demo data (original behaviour, works offline).
  * A real key in .env                  -> that provider is used.
  * USE_FREE_APIS=true                  -> keyless providers (Open-Meteo, Frankfurter) are used where no key is set.
Any network/JSON failure silently falls back to demo data, and results are cached.
"""
import json
import os
import time
import urllib.parse
import urllib.request

from .demo_data import DESTINATIONS
from .places_data import PLACES, canonical

_cache = {}
_q = urllib.parse.quote
_STATIC_RATES = {"INR": 1, "USD": 0.012, "EUR": 0.011, "GBP": 0.0092, "JPY": 1.8}
_DEMO_WEATHER = {"temperature": 24, "condition": "Pleasant", "source": "demo"}
_DEFAULT = {"country": "Demo destination", "season": "Year-round", "climate": "Check live weather", "daily": 3500,
            "lat": 18.52, "lng": 73.85,
            "attractions": [["Old Town Walk", 0, 2], ["Local Market", 500, 2], ["City Viewpoint", 300, 2]],
            "hotels": [["Central Stay", 3200, 4.2], ["Traveller House", 2200, 4.0]]}
_WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle",
        55: "Drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Rain showers", 81: "Rain showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
        95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"}


def _key(name):
    v = os.getenv(name, "").strip()
    return "" if not v or v.upper().startswith("YOUR_") else v


def _free():
    return os.getenv("USE_FREE_APIS", "").strip().lower() in ("1", "true", "yes", "on")


def _get(url, ttl=1800):
    """GET JSON with a 4 s timeout and an in-memory cache. Returns None on any failure."""
    hit = _cache.get(url)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Wanderleaf/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        _cache[url] = (time.time() + 120, None)      # don't hammer a failing provider
        return None
    _cache[url] = (time.time() + ttl, data)
    return data


def _known(name):
    n = str(name).strip().lower()
    return next((v for k, v in DESTINATIONS.items() if k.lower() == n), None)


def _geocode(name):
    c = canonical(name)
    if c:                                           # curated: correct country/coordinates, no network needed
        p = PLACES[c]
        return {"lat": p["lat"], "lng": p["lng"], "country": p["country"], "source": "curated"}
    k = _key("MAPS_API_KEY")
    if k:
        j = _get(f"https://maps.googleapis.com/maps/api/geocode/json?address={_q(name)}&key={k}", 86400)
        try:
            r = j["results"][0]
            loc = r["geometry"]["location"]
            country = next((c["long_name"] for c in r["address_components"] if "country" in c["types"]), None)
            return {"lat": loc["lat"], "lng": loc["lng"], "country": country, "source": "google-maps"}
        except Exception:
            pass
    if _free():
        nm = " ".join(str(name).lower().replace("pardesh", "pradesh").split())
        j = _get(f"https://geocoding-api.open-meteo.com/v1/search?name={_q(nm)}&count=10", 86400)
        try:
            r = max(j["results"], key=lambda z: z.get("population") or 0)       # the best-known match, not the first one
            return {"lat": r["latitude"], "lng": r["longitude"], "country": r.get("country"), "source": "open-meteo"}
        except Exception:
            pass
    return None


def _places(g, kinds, limit, rated=True):
    k = _key("PLACES_API_KEY")
    if not (k and g):
        return []
    url = (f"https://api.opentripmap.com/0.1/en/places/radius?radius=15000&lon={g['lng']}&lat={g['lat']}"
           f"&kinds={kinds}&format=json&limit=20{'&rate=2' if rated else ''}&apikey={k}")
    out, seen = [], set()
    for p in (_get(url, 86400) or []):
        n = str(p.get("name", "")).strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append((n, str(p.get("rate", "1"))[:1]))
    return out[:limit]


def destination_info(name):
    known = _known(name)
    if known:
        return known                                  # rich built-in data (attractions, hotels, season...)
    from . import hotel_data
    d = json.loads(json.dumps(_DEFAULT))
    c = canonical(name)
    if c:                                             # curated place: right country, season, climate, coordinates
        p = PLACES[c]
        d.update(country=p["country"], season=p["season"], climate=p["climate"], daily=p["daily"], lat=p["lat"], lng=p["lng"])
    else:
        g = _geocode(str(name))
        if g:
            d["lat"], d["lng"] = g["lat"], g["lng"]
            if g.get("country"):
                d["country"], d["climate"] = g["country"], "See live weather"
            att = _places(g, "interesting_places", 4)
            if att:
                d["attractions"] = [[n, 0, 2] for n, _ in att]
    d["hotels"] = [[h["name"], h["base_price"], h["rating"]] for h in hotel_data.hotels_for(name, d["lat"], d["lng"], d["daily"])]
    return d


def map_info(name):
    if not _known(name):
        g = _geocode(str(name))
        if g:
            return {"lat": g["lat"], "lng": g["lng"], "source": g["source"]}
    d = destination_info(name)
    return {"lat": d["lat"], "lng": d["lng"], "source": "demo"}


def weather(name):
    m = map_info(name)
    lat, lng = m["lat"], m["lng"]
    k = _key("WEATHER_API_KEY")
    if k:
        j = _get(f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&units=metric&appid={k}", 900)
        try:
            return {"temperature": round(j["main"]["temp"]), "condition": str(j["weather"][0]["main"]), "source": "openweathermap"}
        except Exception:
            pass
    if _free():
        j = _get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,weather_code", 900)
        try:
            c = j["current"]
            return {"temperature": round(c["temperature_2m"]), "condition": _WMO.get(int(c["weather_code"]), "Fair"), "source": "open-meteo"}
        except Exception:
            pass
    return dict(_DEMO_WEATHER)


def exchange_rate(currency):
    """Units of `currency` per 1 INR (estimates are calculated in INR)."""
    if currency == "INR":
        return 1
    k = _key("CURRENCY_API_KEY")
    if k:
        j = _get(f"https://v6.exchangerate-api.com/v6/{k}/latest/INR", 21600)
        try:
            return float(j["conversion_rates"][currency])
        except Exception:
            pass
    if _free():
        j = _get("https://api.frankfurter.app/latest?from=INR&to=USD,EUR,GBP,JPY", 21600)
        try:
            return float(j["rates"][currency])
        except Exception:
            pass
    return _STATIC_RATES.get(currency, 1)


def exchange(amount, currency):
    return round(amount * exchange_rate(currency), 2)


def status():
    """Which provider each feature uses right now (no secrets)."""
    return {
        "weather": "openweathermap" if _key("WEATHER_API_KEY") else "open-meteo" if _free() else "demo",
        "maps": "google-maps" if _key("MAPS_API_KEY") else "open-meteo" if _free() else "demo",
        "places": "opentripmap (attractions)" if _key("PLACES_API_KEY") else "demo",
        "hotels": "synthetic dataset (data/hotels.csv + data/hotel_availability.csv)"
                  + (" (HOTELS_API_KEY is set, but no live hotel provider is connected yet)" if _key("HOTELS_API_KEY") else ""),
        "currency": "exchangerate-api" if _key("CURRENCY_API_KEY") else "frankfurter" if _free() else "static",
        "free_apis_enabled": _free(),
    }
