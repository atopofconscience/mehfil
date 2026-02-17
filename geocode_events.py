"""Add geocoding coordinates to events for map display."""

import os
import json
import time
import requests
from dotenv import load_dotenv

# Boston area venue coordinates (pre-cached for common venues)
KNOWN_VENUES = {
    "boston": (42.3601, -71.0589),
    "cambridge": (42.3736, -71.1097),
    "somerville": (42.3876, -71.0995),
    "brookline": (42.3318, -71.1212),
    "boston, ma": (42.3601, -71.0589),
    "cambridge, ma": (42.3736, -71.1097),
    "mit": (42.3601, -71.0942),
    "harvard": (42.3770, -71.1167),
    "boston university": (42.3505, -71.1054),
    "northeastern": (42.3398, -71.0892),
    "faneuil hall": (42.3601, -71.0549),
    "boston common": (42.3550, -71.0656),
    "seaport": (42.3519, -71.0449),
    "back bay": (42.3503, -71.0810),
    "south end": (42.3420, -71.0692),
    "north end": (42.3647, -71.0542),
    "downtown crossing": (42.3555, -71.0602),
    "beacon hill": (42.3588, -71.0707),
    "fenway": (42.3467, -71.0972),
    "allston": (42.3539, -71.1337),
    "brighton": (42.3464, -71.1627),
    "jamaica plain": (42.3097, -71.1151),
    "roxbury": (42.3152, -71.0886),
    "dorchester": (42.3016, -71.0674),
    "isbcc": (42.3307, -71.0834),
    "islamic society of boston": (42.3307, -71.0834),
    "encore boston harbor": (42.3876, -71.0756),
    "memoire": (42.3876, -71.0756),
}


def geocode_location(location):
    """Get coordinates for a location using Nominatim (free geocoding)."""
    if not location:
        return None, None

    location_lower = location.lower()

    # Check known venues first
    for venue, coords in KNOWN_VENUES.items():
        if venue in location_lower:
            return coords

    # Try Nominatim geocoding (free, but rate-limited)
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{location}, Boston, MA",
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "BostonCommunityEvents/1.0"}

        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

    except Exception as e:
        print(f"Geocoding error for '{location}': {e}")

    # Default to Boston center
    return 42.3601, -71.0589


def geocode_events():
    """Add coordinates to events in the JSON file."""
    load_dotenv()

    json_path = os.path.join(os.path.dirname(__file__), "dashboard", "events.json")

    if not os.path.exists(json_path):
        print("Error: events.json not found. Run export_events.py first.")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    events = data.get("events", [])
    updated = 0

    for event in events:
        if not event.get("latitude") or not event.get("longitude"):
            location = event.get("location") or event.get("address") or "Boston"
            lat, lng = geocode_location(location)

            if lat and lng:
                event["latitude"] = lat
                event["longitude"] = lng
                updated += 1
                print(f"Geocoded: {event['name'][:40]}... -> ({lat}, {lng})")

            # Rate limiting for Nominatim
            time.sleep(1)

    # Save updated events
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {updated} events with coordinates")


if __name__ == "__main__":
    geocode_events()
