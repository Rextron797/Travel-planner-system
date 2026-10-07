"""Single source of truth for trip-cost and itinerary logic.

Used by the original HTML routes, the JSON API and the PDF export so the
numbers are always identical. The cost formula is unchanged from the original app.
"""
import math

from services.external_apis import destination_info, weather, map_info

STYLES = {"Budget": 0.75, "Mid-Range": 1.0, "Luxury": 1.65}
TRANSPORT_BASE = 5000      # flat transport estimate (INR) before the style factor
FOOD_SHARE = 0.35          # share of a destination's daily base spent on food
SLOTS = ("Morning", "Afternoon")


class PlanError(ValueError):
    """Raised for invalid plan inputs; routes turn it into a 400 response."""


def _num(value, label, cast):
    try:
        out = cast(value)
    except (TypeError, ValueError):
        raise PlanError(f"{label} must be a number.")
    if isinstance(out, float) and not math.isfinite(out):
        raise PlanError(f"{label} must be a number.")
    return out


def _itinerary(attractions, days):
    plan = []
    if not attractions:
        return plan
    n = len(attractions)
    for i in range(days):
        picks = [attractions[i % n], attractions[(i + 1) % n]]
        details = [
            {"slot": slot, "name": a[0], "hours": a[2], "cost": a[1]}
            for slot, a in zip(SLOTS, picks)
        ]
        details.append({"slot": "Evening", "name": "Dinner and a local stroll", "hours": None, "cost": None})
        plan.append({"day": i + 1, "items": [a[0] for a in picks], "details": details})
    return plan


def compute_plan(destination, days, travelers, budget, style="Mid-Range", hotel=""):
    destination = str(destination or "").strip()
    if not destination or len(destination) > 80:
        raise PlanError("Enter a destination (up to 80 characters).")
    days = max(1, min(_num(days, "Days", int), 30))
    travelers = max(1, min(_num(travelers, "Travelers", int), 20))
    budget = max(0.0, _num(budget, "Budget", float))
    style = style if style in STYLES else "Mid-Range"
    factor = STYLES[style]

    d = destination_info(destination)
    hotels = d.get("hotels") or []
    if not hotels:
        raise PlanError("No hotel data available for this destination.")
    selected = next((h for h in hotels if h[0] == hotel), hotels[0])
    attractions = d.get("attractions", [])
    daily = d.get("daily", 1500)

    stay = round(selected[1] * days * factor)
    food = round(daily * FOOD_SHARE * days * travelers * factor)
    transport = round(TRANSPORT_BASE * factor)
    activities = round(sum(a[1] for a in attractions) * travelers)
    total = stay + food + transport + activities

    return {
        "destination": destination, "days": days, "travelers": travelers, "budget": budget,
        "style": style, "hotel": selected[0],
        "stay": stay, "food": food, "transport": transport, "activities": activities, "total": total,
        "within_budget": (total <= budget) if budget > 0 else None,
        "budget_gap": round(budget - total) if budget > 0 else None,
        "per_person": round(total / travelers), "per_day": round(total / days),
        "factor": factor, "daily_base": daily, "hotel_rate": selected[1], "hotel_rating": selected[2],
        "shares": {k: round(v * 100 / total) if total else 0
                   for k, v in (("transport", transport), ("stay", stay), ("food", food), ("activities", activities))},
        "itinerary": _itinerary(attractions, days),
        "weather": weather(destination),
        "info": {**{k: d.get(k) for k in ("country", "season", "climate")}, **map_info(destination),
                 "attractions": attractions, "hotels": hotels},
    }
