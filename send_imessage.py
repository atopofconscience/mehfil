#!/usr/bin/env python3
"""
Send weekly event picks via iMessage with weather-aware recommendations.
Just run: python send_imessage.py

No setup required - uses your Mac's Messages app directly.
"""

import json
import subprocess
import urllib.request
from datetime import datetime, timedelta


# Boston coordinates
BOSTON_LAT = 42.3601
BOSTON_LON = -71.0589

# Indoor categories (good for bad weather)
INDOOR_CATEGORIES = [
    "Arts & Crafts", "Theater & Film", "Food & Markets", "Comedy",
    "Coffee & Chai", "Talks & Lectures", "Career & Tech", "Religious"
]

# Outdoor categories (good for nice weather)
OUTDOOR_CATEGORIES = [
    "Sports & Outdoors", "Cultural Festival"
]


def get_weather_forecast():
    """Get 7-day weather forecast for Boston using Open-Meteo (free, no API key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={BOSTON_LAT}&longitude={BOSTON_LON}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,weathercode"
        f"&timezone=America/New_York"
        f"&forecast_days=7"
    )

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("daily", {})
    except Exception as e:
        print(f"  Weather fetch failed: {e}")
        return None


def analyze_weather(weather_data):
    """Analyze weather and return conditions + recommendation."""
    if not weather_data:
        return None, "unknown", ""

    dates = weather_data.get("date", [])
    temps_max = weather_data.get("temperature_2m_max", [])
    temps_min = weather_data.get("temperature_2m_min", [])
    rain = weather_data.get("precipitation_sum", [])
    snow = weather_data.get("snowfall_sum", [])
    codes = weather_data.get("weathercode", [])

    # Weather code meanings (WMO codes)
    # 0-3: Clear/Cloudy, 45-48: Fog, 51-67: Rain/Drizzle, 71-77: Snow, 80-82: Showers, 85-86: Snow showers, 95-99: Thunderstorm

    bad_days = []
    total_rain = sum(rain) if rain else 0
    total_snow = sum(snow) if snow else 0
    avg_high = sum(temps_max) / len(temps_max) if temps_max else 50

    # Check for bad weather days
    for i, code in enumerate(codes):
        if code >= 51:  # Any precipitation
            bad_days.append(dates[i] if i < len(dates) else f"Day {i+1}")

    # Determine overall condition
    if total_snow > 5:
        condition = "snow"
        emoji = "❄️"
        note = f"Snow expected ({total_snow:.1f}cm) - cozy indoor picks!"
    elif total_rain > 20:
        condition = "rainy"
        emoji = "🌧️"
        note = f"Rainy week ahead ({total_rain:.1f}mm) - indoor events!"
    elif avg_high > 30:  # 86°F
        condition = "heat"
        emoji = "🔥"
        note = f"Heat wave ({avg_high:.0f}°C highs) - stay cool indoors!"
    elif avg_high < 0:  # Below freezing
        condition = "freezing"
        emoji = "🥶"
        note = f"Freezing temps ({avg_high:.0f}°C) - warm indoor spots!"
    elif len(bad_days) >= 4:
        condition = "mixed"
        emoji = "🌦️"
        note = "Mixed weather - mostly indoor picks"
    else:
        condition = "nice"
        emoji = "☀️"
        note = f"Great week ahead ({avg_high:.0f}°C) - get outside!"

    return condition, emoji, note


def is_indoor_event(event):
    """Check if event is likely indoors."""
    categories = event.get("categories", [])
    name = event.get("name", "").lower()
    location = event.get("location", "").lower()

    # Check categories
    for cat in categories:
        if cat in INDOOR_CATEGORIES:
            return True
        if cat in OUTDOOR_CATEGORIES:
            return False

    # Check name/location hints
    indoor_hints = ["museum", "gallery", "restaurant", "theater", "theatre", "cinema",
                    "studio", "lounge", "cafe", "coffee", "library", "center", "centre",
                    "hall", "room", "hotel", "bar", "club", "temple", "mosque", "church"]
    outdoor_hints = ["park", "beach", "trail", "hike", "outdoor", "garden", "field",
                     "plaza", "street", "marathon", "run", "walk"]

    text = f"{name} {location}"
    if any(hint in text for hint in outdoor_hints):
        return False
    if any(hint in text for hint in indoor_hints):
        return True

    return True  # Default to indoor (safer assumption)


def load_events(weather_condition):
    """Load and filter events, prioritizing based on weather."""
    with open("dashboard/events.json") as f:
        data = json.load(f)

    today = datetime.now().date()
    end_date = today + timedelta(days=7)

    # Filter: future events within 7 days, no junk names
    junk = ["cookie", "sign up", "log in", "privacy", "terms"]
    good_events = []

    for e in data["events"]:
        name = e.get("name", "")
        if not name or any(j in name.lower() for j in junk):
            continue
        try:
            event_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if today <= event_date <= end_date:
                e["is_indoor"] = is_indoor_event(e)
                good_events.append(e)
        except:
            continue

    # Sort by date first
    good_events.sort(key=lambda x: x["date"])

    # Weather-based prioritization
    prefer_indoor = weather_condition in ["snow", "rainy", "heat", "freezing", "mixed"]

    if prefer_indoor:
        # Put indoor events first, then outdoor
        indoor = [e for e in good_events if e.get("is_indoor", True)]
        outdoor = [e for e in good_events if not e.get("is_indoor", True)]
        good_events = indoor + outdoor
    else:
        # Nice weather - mix it up, slight preference for outdoor
        outdoor = [e for e in good_events if not e.get("is_indoor", True)]
        indoor = [e for e in good_events if e.get("is_indoor", True)]
        # Interleave: outdoor, indoor, outdoor, indoor...
        good_events = []
        for i in range(max(len(outdoor), len(indoor))):
            if i < len(outdoor):
                good_events.append(outdoor[i])
            if i < len(indoor):
                good_events.append(indoor[i])

    return good_events[:7]


def format_message(events, weather_emoji, weather_note):
    """Format events as a simple text message."""
    header = f"{weather_emoji} Your 7 Picks This Week"
    if weather_note:
        header += f"\n{weather_note}"

    lines = [header + "\n"]

    for i, e in enumerate(events, 1):
        date = datetime.strptime(e["date"], "%Y-%m-%d").strftime("%a %b %d")
        time = e.get("time") or ""
        loc = e.get("location") or ""
        price = e.get("price") or ""

        # Keep it short for iMessage
        line = f"{i}. {e['name'][:40]}"
        if len(e['name']) > 40:
            line += "..."
        line += f"\n   {date}"
        if time:
            line += f" {time}"
        if loc:
            line += f"\n   {loc[:30]}"
        if price and "free" in price.lower():
            line += " - FREE"

        lines.append(line)

    lines.append("\nmehfil.com")
    return "\n\n".join(lines)


def send_imessage(phone_number, message):
    """Send iMessage using AppleScript."""
    # Escape quotes and newlines for AppleScript
    message = message.replace('\\', '\\\\').replace('"', '\\"')

    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{phone_number}" of targetService
        send "{message}" to targetBuddy
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"Sent to {phone_number}")
        return True
    else:
        print(f"Error: {result.stderr}")
        return False


def main():
    print("Fetching Boston weather forecast...")
    weather_data = get_weather_forecast()
    condition, emoji, note = analyze_weather(weather_data)
    print(f"  Weather: {emoji} {condition} - {note}")

    print("\nLoading events (weather-adjusted)...")
    events = load_events(condition)

    if not events:
        print("No events found!")
        return

    message = format_message(events, emoji, note)

    print("\n--- Preview ---")
    print(message)
    print("--- End Preview ---\n")

    YOUR_NUMBER = input("Enter your phone number or iMessage email (or 'skip' to just preview): ").strip()

    if YOUR_NUMBER.lower() == 'skip':
        print("Preview only - not sent.")
        return

    send_imessage(YOUR_NUMBER, message)


if __name__ == "__main__":
    main()
