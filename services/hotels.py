"""Hotel options for a destination and dates: price, location, amenities, availability.

Data comes from the synthetic dataset in services/hotel_data.py (data/hotels.csv + data/hotel_availability.csv),
because no free API provides live availability. Every item carries source="synthetic-dataset".
To use a real provider later, return its results from `_live_hotels` in the same shape.
"""
from datetime import date, timedelta

from . import hotel_data
from .external_apis import destination_info


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValueError("Check-in must be a date like 2026-11-20.")


def _live_hotels(destination, check_in, nights, travelers):
    return None  # plug a real provider in here


def hotel_options(destination, check_in=None, nights=1, travelers=2):
    live = _live_hotels(destination, check_in, nights, travelers)
    if live:
        return live
    d = destination_info(destination)
    ci = parse_date(check_in)
    nights = max(1, min(int(nights or 1), 30))
    rooms = max(1, -(-int(travelers or 1) // 2))        # 2 guests per room
    out = []
    for h in hotel_data.hotels_for(destination, d["lat"], d["lng"], d["daily"]):
        item = {k: h[k] for k in ("hotel_id", "name", "category", "stars", "rating", "reviews", "area", "distance_km", "lat", "lng",
                                  "amenities", "free_cancellation", "check_in_time", "check_out_time")}
        item.update(base_price=h["base_price"], rooms_needed=rooms, source="synthetic-dataset")
        if ci:
            stays = [hotel_data.stay_night(h, ci + timedelta(days=k)) for k in range(nights)]
            left, total = min(s[0] for s in stays), sum(s[1] for s in stays)
            item.update(price=round(total / nights), total=total, rooms_left=left, available=left >= rooms,
                        status="Sold out" if left == 0 else "Not enough rooms for your group" if left < rooms
                        else f"Only {left} room{'s' * (left != 1)} left" if left <= 3 else "Available")
        else:
            item.update(price=h["base_price"], total=h["base_price"] * nights, rooms_left=None, available=None,
                        status="Pick dates to check availability")
        out.append(item)
    return out
