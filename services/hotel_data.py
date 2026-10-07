"""Synthetic hotel dataset: hotels (price, location, amenities) + a nightly availability/price calendar.

Deterministic (seeded). `python -m services.hotel_data` writes data/hotels.csv and data/hotel_availability.csv.
At runtime the CSVs are used when present (edit them freely); any date outside the CSV calendar is computed with the
same model, so availability always works. The three original destinations keep their original hotel names/prices/ratings.
"""
import csv
import hashlib
import random
from datetime import date, timedelta
from pathlib import Path

from .demo_data import DESTINATIONS
from .places_data import PLACES, canonical

DATA = Path(__file__).resolve().parent.parent / "data"
START, DAYS = date(2026, 10, 1), 182
CATS = [  # name, stars, price x daily-budget, rating range, rooms range, amenities, name kinds
    ("Budget", 2, (0.28, 0.5), (3.8, 4.3), (12, 30), ["Free Wi-Fi", "Air conditioning"], ["Hostel", "Guesthouse", "Stay", "Inn"]),
    ("Mid-range", 3, (0.6, 1.0), (4.1, 4.6), (30, 90), ["Free Wi-Fi", "Air conditioning", "Breakfast included"], ["Residency", "Boutique Hotel", "Courtyard", "Suites"]),
    ("Luxury", 5, (1.8, 3.2), (4.5, 4.9), (40, 160), ["Free Wi-Fi", "Air conditioning", "Breakfast included", "Swimming pool", "Spa"], ["Grand Resort", "Palace Hotel", "Retreat", "Spa Resort"]),
]
EXTRAS = ["Parking", "Airport shuttle", "Gym", "24h reception", "Restaurant", "Bar", "Laundry", "Rooftop terrace"]
HOTEL_FIELDS = ["hotel_id", "destination", "country", "name", "category", "stars", "rating", "reviews", "area", "distance_km", "lat", "lng",
                "base_price", "total_rooms", "amenities", "free_cancellation", "check_in_time", "check_out_time", "currency", "data_source"]
_cache = {}


def _rng(*parts):
    return random.Random(int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12], 16))


def _record(hid, place, country, info, cat_i, name, price, rating):
    cat = CATS[cat_i]
    r = _rng("rec", hid)
    dist = round(r.uniform(0.3, 8.0), 1)
    return {"hotel_id": hid, "destination": place, "country": country, "name": name, "category": cat[0], "stars": cat[1],
            "rating": rating, "reviews": r.randint(80, 4200), "area": r.choice(info["areas"]), "distance_km": dist,
            "lat": round(info["lat"] + r.uniform(-1, 1) * dist / 111, 5), "lng": round(info["lng"] + r.uniform(-1, 1) * dist / 111, 5),
            "base_price": int(price), "total_rooms": r.randint(*cat[4]),
            "amenities": cat[5] + r.sample(EXTRAS, 1 + cat_i + (cat_i == 2)), "free_cancellation": r.random() < 0.6,
            "check_in_time": "14:00", "check_out_time": "11:00", "currency": "INR", "data_source": "synthetic"}


def _generate(place, info, counts, start_id, originals=()):
    out, used, n = [], {h[0] for h in originals}, start_id
    for name, price, rating in originals:
        ratio = price / info["daily"]
        out.append(_record(f"H{n:03d}", place, info["country"], info, 0 if ratio < 0.55 else 1 if ratio < 1.3 else 2, name, price, rating)); n += 1
    for cat_i, count in enumerate(counts):
        cat = CATS[cat_i]
        for j in range(count):
            r = _rng("gen", place, cat_i, j)
            for _ in range(20):
                nm = f"{r.choice(info['themes'])} {r.choice(cat[6])}"
                if nm not in used:
                    break
            used.add(nm)
            out.append(_record(f"H{n:03d}", place, info["country"], info, cat_i, nm,
                               round(info["daily"] * r.uniform(*cat[2]) / 100) * 100, round(r.uniform(*cat[3]), 1))); n += 1
    return out


def build_all():
    rows = []
    for place, info in PLACES.items():
        orig = DESTINATIONS.get(place, {}).get("hotels", ())
        rows += _generate(place, info, (2, 2, 2) if orig else (3, 4, 2), len(rows) + 1, orig)
    return rows


def night(h, day):
    """(rooms_available, price_inr) for one hotel night - seasonality, weekends and holiday peaks."""
    info = PLACES.get(h["destination"], {})
    peak = day.month in info.get("peak", [])
    wk = day.weekday() in (4, 5)
    hol = (day.month == 12 and day.day >= 20) or (day.month == 1 and day.day <= 2) or (day.month == 11 and 6 <= day.day <= 10)
    occ = min(0.97, max(0.2, 0.42 + 0.22 * peak + 0.1 * wk + 0.2 * hol + _rng(h["hotel_id"], day.isoformat()).uniform(-0.1, 0.12)))
    price = round(h["base_price"] * max(0.85, 1 + 0.2 * peak + 0.1 * wk + 0.18 * hol + (occ - 0.6) * 0.2) / 50) * 50
    return max(0, round(h["total_rooms"] * (1 - occ))), int(price)


def _from_csv(r):
    for k in ("stars", "reviews", "base_price", "total_rooms"):
        r[k] = int(r[k])
    for k in ("rating", "distance_km", "lat", "lng"):
        r[k] = float(r[k])
    r["amenities"], r["free_cancellation"] = r["amenities"].split("|"), r["free_cancellation"] in ("1", "True", "true")
    return r


def _load():
    if _cache:
        return
    hp, ap = DATA / "hotels.csv", DATA / "hotel_availability.csv"
    rows = [_from_csv(r) for r in csv.DictReader(open(hp, encoding="utf-8"))] if hp.exists() else build_all()
    av = {}
    if ap.exists():
        for r in csv.DictReader(open(ap, encoding="utf-8")):
            av[(r["hotel_id"], r["date"])] = (int(r["rooms_available"]), int(r["price_inr"]))
    by = {}
    for h in rows:
        by.setdefault(h["destination"], []).append(h)
    _cache.update(rows=rows, by=by, av=av)


def stay_night(h, day):
    _load()
    return _cache["av"].get((h["hotel_id"], day.isoformat())) or night(h, day)


def hotels_for(destination, lat=None, lng=None, daily=None):
    _load()
    c = canonical(destination)
    if c in _cache["by"]:
        return _cache["by"][c]
    key = ("u", str(destination).strip().lower())
    if key not in _cache:       # any other place: a small deterministic set around its coordinates
        nm = str(destination).strip().title()
        info = {"country": "", "lat": lat or 0.0, "lng": lng or 0.0, "daily": daily or 3500, "themes": [nm, "Central", "Heritage", "Garden"], "areas": ["City Centre", "Old Town", "Station Area", "Riverside"]}
        tag = int(hashlib.md5(key[1].encode()).hexdigest()[:4], 16)
        hs = _generate(nm, info, (2, 2, 1), 0)
        for i, h in enumerate(hs):
            h["hotel_id"] = f"U{tag:04x}{i}"
        _cache[key] = hs
    return _cache[key]


def write_csvs():
    DATA.mkdir(exist_ok=True)
    rows = build_all()
    with open(DATA / "hotels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, HOTEL_FIELDS)
        w.writeheader()
        for h in rows:
            w.writerow({**h, "amenities": "|".join(h["amenities"]), "free_cancellation": int(h["free_cancellation"])})
    with open(DATA / "hotel_availability.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hotel_id", "date", "rooms_available", "price_inr"])
        for h in rows:
            for k in range(DAYS):
                d = START + timedelta(days=k)
                w.writerow([h["hotel_id"], d.isoformat(), *night(h, d)])
    return len(rows), DAYS


if __name__ == "__main__":
    print("hotels, days:", write_csvs())
