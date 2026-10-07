"""Curated destination facts (country, coordinates, season, climate, hotel-naming themes).
Fixes ambiguous names (e.g. Kerala is in India, not Finland) and works offline."""

def _p(country, lat, lng, daily, peak, season, climate, themes, areas):
    return dict(country=country, lat=lat, lng=lng, daily=daily, peak=peak, season=season, climate=climate, themes=themes, areas=areas)

PLACES = {
    "Kyoto": _p("Japan", 35.0116, 135.7681, 5200, [3, 4, 5, 10, 11], "March–May / Oct–Nov", "Mild spring and autumn", ["Gion", "Higashiyama", "Arashiyama", "Kamo River", "Nishijin"], ["Gion", "Higashiyama", "Kyoto Station", "Arashiyama", "Nakagyo"]),
    "Goa": _p("India", 15.2993, 74.124, 3000, [11, 12, 1, 2], "November–February", "Warm and coastal", ["Candolim", "Palolem", "Fontainhas", "Anjuna", "Colva"], ["Calangute", "Panaji", "Palolem", "Anjuna", "Colva"]),
    "Jaipur": _p("India", 26.9124, 75.7873, 2800, [10, 11, 12, 1, 2, 3], "October–March", "Dry and pleasant in winter", ["Amer", "Rajmahal", "Johari", "Hawa Mahal", "Sanganer"], ["Pink City", "C-Scheme", "Amer Road", "Bani Park", "MI Road"]),
    "Kerala": _p("India", 10.8505, 76.2711, 3200, [10, 11, 12, 1, 2, 3], "September–March", "Tropical, warm and humid", ["Backwater", "Spice Garden", "Coconut Grove", "Malabar", "Periyar"], ["Alleppey", "Fort Kochi", "Munnar", "Kovalam", "Thekkady"]),
    "Bali": _p("Indonesia", -8.4095, 115.1889, 4800, [6, 7, 8, 9], "April–October", "Tropical, dry season Apr–Oct", ["Ubud", "Rice Terrace", "Frangipani", "Uluwatu", "Sanur"], ["Ubud", "Seminyak", "Canggu", "Uluwatu", "Sanur"]),
    "Paris": _p("France", 48.8566, 2.3522, 9500, [5, 6, 7, 8, 12], "April–June / Sept–Oct", "Mild, four distinct seasons", ["Montmartre", "Seine", "Le Marais", "Saint-Germain", "Louvre"], ["Le Marais", "Montmartre", "Latin Quarter", "Champs-Élysées", "Bastille"]),
    "Maldives": _p("Maldives", 3.2028, 73.2207, 14000, [11, 12, 1, 2, 3, 4], "November–April", "Tropical, warm all year", ["Coral", "Lagoon", "Atoll", "Reef", "Sunset"], ["Malé", "Maafushi", "North Malé Atoll", "Ari Atoll", "Baa Atoll"]),
    "Uttarakhand": _p("India", 30.0668, 79.0193, 2600, [4, 5, 6, 10], "March–June / Sept–Nov", "Cool Himalayan, snow in winter", ["Himalaya", "Ganga", "Deodar", "Valley View", "Kedar"], ["Rishikesh", "Mussoorie", "Nainital", "Haridwar", "Auli"]),
    "Himachal Pradesh": _p("India", 31.1048, 77.1734, 2800, [4, 5, 6, 12, 1], "March–June / Dec–Jan", "Cool mountain, snow in winter", ["Pine Valley", "Beas", "Deodar", "Snowline", "Apple Orchard"], ["Manali", "Shimla", "Dharamshala", "Kasol", "Kullu"]),
    "Santorini": _p("Greece", 36.3932, 25.4615, 11000, [5, 6, 7, 8, 9], "May–September", "Hot, dry summers", ["Caldera", "Aegean", "Whitewash", "Blue Dome", "Sunset"], ["Oia", "Fira", "Imerovigli", "Kamari", "Perissa"]),
    "Dubai": _p("United Arab Emirates", 25.2048, 55.2708, 8500, [11, 12, 1, 2, 3], "November–March", "Hot desert, mild winters", ["Marina", "Creek", "Desert Palm", "Burj View", "Jumeirah"], ["Downtown", "Marina", "Deira", "Jumeirah", "Business Bay"]),
    "Rome": _p("Italy", 41.9028, 12.4964, 8800, [4, 5, 6, 9, 10], "April–June / Sept–Oct", "Mediterranean", ["Colosseo", "Trastevere", "Pantheon", "Tiber", "Spanish Steps"], ["Centro Storico", "Trastevere", "Monti", "Prati", "Termini"]),
    "London": _p("United Kingdom", 51.5072, -0.1276, 10500, [6, 7, 8, 12], "June–September", "Mild and changeable", ["Thames", "Covent Garden", "Mayfair", "Kensington", "Soho"], ["Covent Garden", "Kensington", "Soho", "South Bank", "Paddington"]),
    "New York": _p("United States", 40.7128, -74.006, 12500, [5, 6, 9, 10, 12], "April–June / Sept–Nov", "Four seasons, cold winters", ["Midtown", "Brooklyn Bridge", "Central Park", "Hudson", "SoHo"], ["Midtown", "Lower Manhattan", "Brooklyn", "Upper West Side", "Chelsea"]),
    "Tokyo": _p("Japan", 35.6762, 139.6503, 6500, [3, 4, 10, 11], "March–May / Oct–Nov", "Humid summers, mild winters", ["Shibuya", "Asakusa", "Ginza", "Sumida", "Ueno"], ["Shinjuku", "Shibuya", "Asakusa", "Ginza", "Ueno"]),
    "Thailand": _p("Thailand", 13.7563, 100.5018, 3800, [11, 12, 1, 2, 3], "November–February", "Tropical, hot and humid", ["Chao Phraya", "Lotus", "Orchid", "Andaman", "Siam"], ["Bangkok Riverside", "Sukhumvit", "Phuket Old Town", "Patong", "Chiang Mai"]),
    "Agra": _p("India", 27.1767, 78.0081, 2900, [10, 11, 12, 1, 2, 3], "October–March", "Hot summers, cool winters", ["Taj View", "Mughal", "Yamuna", "Fatehabad", "Sikandra"], ["Taj Ganj", "Fatehabad Road", "Cantonment", "Sadar Bazaar", "Sikandra"]),
    "Switzerland": _p("Switzerland", 46.8182, 8.2275, 14500, [6, 7, 8, 12, 1, 2], "June–September / Dec–Mar", "Alpine, cold snowy winters", ["Alpine", "Matterhorn", "Edelweiss", "Lakeside", "Glacier"], ["Zurich", "Lucerne", "Interlaken", "Zermatt", "Geneva"]),
}
ALIASES = {"himachal": "Himachal Pradesh", "himachal pardesh": "Himachal Pradesh", "himachal pradesh": "Himachal Pradesh", "uttaranchal": "Uttarakhand",
           "swiss": "Switzerland", "alps": "Switzerland", "greece": "Santorini", "nyc": "New York", "bangkok": "Thailand", "phuket": "Thailand",
           "taj mahal": "Agra", "maldive": "Maldives", "uae": "Dubai", "italy": "Rome", "japan": "Tokyo", "france": "Paris", "england": "London"}


def canonical(name):
    n = " ".join(str(name).lower().split())
    for k in PLACES:
        if k.lower() == n:
            return k
    return ALIASES.get(n)
