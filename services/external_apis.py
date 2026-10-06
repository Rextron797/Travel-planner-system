"""External API adapters. Replace ONLY the marked demo sections when adding live providers.
The rest of the app calls these functions, so UI/routes do not need to change."""
import os
from .demo_data import DESTINATIONS

def destination_info(name):
    # API INPUT EXAMPLE: use PLACES_API_KEY here and return this same dictionary shape.
    key=os.getenv("PLACES_API_KEY","")
    return DESTINATIONS.get(name, {"country":"Demo destination","season":"Year-round","climate":"Check live weather","daily":3500,"lat":18.52,"lng":73.85,"attractions":[["Old Town Walk",0,2],["Local Market",500,2],["City Viewpoint",300,2]],"hotels":[["Central Stay",3200,4.2],["Traveller House",2200,4.0]]})

def weather(name):
    # API INPUT EXAMPLE: WEATHER_API_KEY -> OpenWeather/WeatherAPI request can replace this return.
    return {"temperature":24,"condition":"Pleasant","source":"demo"}

def map_info(name):
    # API INPUT EXAMPLE: MAPS_API_KEY -> Google Maps/Mapbox/OSM adapter.
    d=destination_info(name); return {"lat":d["lat"],"lng":d["lng"],"source":"demo"}

def exchange(amount, currency):
    # API INPUT EXAMPLE: CURRENCY_API_KEY -> exchange-rate provider. Base estimates are INR.
    rates={"INR":1,"USD":0.012,"EUR":0.011,"GBP":0.0092}; return round(amount*rates.get(currency,1),2)
