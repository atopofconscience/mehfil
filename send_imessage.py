#!/usr/bin/env python3
"""
Send weekly event picks with weather-aware recommendations.

Usage:
  python send_imessage.py              # Copy to clipboard (default)
  python send_imessage.py --preview    # Preview message only
  python send_imessage.py --send       # Send via iMessage (requires permissions)
  python send_imessage.py --add        # Add a subscriber
  python send_imessage.py --list       # List subscribers
  python send_imessage.py --remove     # Remove a subscriber

No external setup required.
"""

import json
import random
import subprocess
import urllib.request
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path


# Boston coordinates
BOSTON_LAT = 42.3601
BOSTON_LON = -71.0589

# Subscribers file
SUBSCRIBERS_FILE = Path(__file__).parent / "imessage_subscribers.json"

# Weather thresholds (adjusted per user feedback)
HEAT_THRESHOLD = 35  # °C - heat wave
FREEZING_THRESHOLD = -5  # °C - freezing cold
SNOW_THRESHOLD = 2  # cm - significant snow
RAIN_THRESHOLD = 15  # mm - heavy rain

# Indoor categories (good for bad weather)
INDOOR_CATEGORIES = [
    "Arts & Crafts", "Theater & Film", "Food & Markets", "Comedy",
    "Coffee & Chai", "Talks & Lectures", "Career & Tech", "Religious"
]

# Outdoor categories (good for nice weather)
OUTDOOR_CATEGORIES = [
    "Sports & Outdoors", "Cultural Festival"
]


def load_subscribers():
    """Load subscribers from JSON file."""
    if SUBSCRIBERS_FILE.exists():
        with open(SUBSCRIBERS_FILE) as f:
            return json.load(f)
    return {"subscribers": []}


def save_subscribers(data):
    """Save subscribers to JSON file."""
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_subscriber():
    """Add a new subscriber."""
    data = load_subscribers()

    print("Add iMessage Subscriber")
    print("-" * 30)
    phone = input("Phone number or iMessage email: ").strip()
    name = input("Name (optional): ").strip()

    if not phone:
        print("No phone number entered.")
        return

    # Check if already exists
    for sub in data["subscribers"]:
        if sub["phone"] == phone:
            print(f"Already subscribed: {phone}")
            return

    data["subscribers"].append({
        "phone": phone,
        "name": name or phone,
        "added": datetime.now().isoformat()
    })

    save_subscribers(data)
    print(f"Added: {name or phone} ({phone})")


def remove_subscriber():
    """Remove a subscriber."""
    data = load_subscribers()

    if not data["subscribers"]:
        print("No subscribers.")
        return

    print("Current subscribers:")
    for i, sub in enumerate(data["subscribers"], 1):
        print(f"  {i}. {sub['name']} ({sub['phone']})")

    choice = input("\nEnter number to remove (or 'cancel'): ").strip()

    if choice.lower() == 'cancel':
        return

    try:
        idx = int(choice) - 1
        removed = data["subscribers"].pop(idx)
        save_subscribers(data)
        print(f"Removed: {removed['name']}")
    except (ValueError, IndexError):
        print("Invalid selection.")


def list_subscribers():
    """List all subscribers."""
    data = load_subscribers()

    if not data["subscribers"]:
        print("No subscribers yet.")
        print("Run: python send_imessage.py --add")
        return

    print(f"Subscribers ({len(data['subscribers'])}):")
    print("-" * 40)
    for sub in data["subscribers"]:
        print(f"  {sub['name']}: {sub['phone']}")


def get_weather_forecast():
    """Get 7-day weather forecast for Boston using Open-Meteo (free, no API key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={BOSTON_LAT}&longitude={BOSTON_LON}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,weather_code"
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
        return "unknown", "📅", ""

    dates = weather_data.get("time", [])
    temps_max = weather_data.get("temperature_2m_max", [])
    temps_min = weather_data.get("temperature_2m_min", [])
    rain = weather_data.get("precipitation_sum", [])
    snow = weather_data.get("snowfall_sum", [])
    codes = weather_data.get("weather_code", [])

    # WMO weather codes: 71-77 = snow, 51-67 = rain/drizzle, 80-82 = showers, 95-99 = thunderstorm

    total_rain = sum(rain) if rain else 0
    total_snow = sum(snow) if snow else 0
    avg_high = sum(temps_max) / len(temps_max) if temps_max else 10
    avg_low = sum(temps_min) / len(temps_min) if temps_min else 0

    # Count snow days
    snow_days = sum(1 for s in snow if s > 0)

    # Find specific bad weather days
    bad_weather_days = []
    for i, code in enumerate(codes):
        if code >= 71 and code <= 77:  # Snow codes
            day_name = datetime.strptime(dates[i], "%Y-%m-%d").strftime("%A")
            bad_weather_days.append(f"{day_name} (snow)")
        elif code >= 51 and code <= 67:  # Rain codes
            day_name = datetime.strptime(dates[i], "%Y-%m-%d").strftime("%A")
            bad_weather_days.append(f"{day_name} (rain)")

    # Determine overall condition
    if total_snow >= SNOW_THRESHOLD or snow_days >= 2:
        condition = "snow"
        emoji = "❄️"
        if bad_weather_days:
            note = f"Snow on {bad_weather_days[0].split()[0]} - cozy indoor picks!"
        else:
            note = f"Snow expected ({total_snow:.1f}cm) - staying warm indoors!"
    elif avg_low <= FREEZING_THRESHOLD:
        condition = "freezing"
        emoji = "🥶"
        note = f"Brutal cold ({avg_low:.0f}°C lows) - warm indoor events!"
    elif total_rain >= RAIN_THRESHOLD:
        condition = "rainy"
        emoji = "🌧️"
        note = f"Rainy week ({total_rain:.0f}mm) - indoor activities!"
    elif avg_high >= HEAT_THRESHOLD:
        condition = "heat"
        emoji = "🔥"
        note = f"Heat wave ({avg_high:.0f}°C) - AC is your friend!"
    elif len(bad_weather_days) >= 3:
        condition = "mixed"
        emoji = "🌦️"
        note = "Mixed weather - mostly indoor picks"
    else:
        condition = "nice"
        emoji = "☀️"
        note = f"Nice week ahead ({avg_high:.0f}°C) - great for outdoors!"

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
    with open(Path(__file__).parent / "dashboard/events.json") as f:
        data = json.load(f)

    today = datetime.now().date()
    end_date = today + timedelta(days=7)

    # Filter: future events within 7 days, no junk names
    junk = ["cookie", "sign up", "log in", "privacy", "terms"]
    # Skip restaurants and permanent attractions - we want actual events
    not_events = ["sarma", "holiday lights", "consignment", "restaurant",
                  "mall lights", "2025-2026", "designer consignment"]
    good_events = []

    for e in data["events"]:
        name = e.get("name", "")
        if not name or any(j in name.lower() for j in junk):
            continue
        if any(n in name.lower() for n in not_events):
            continue
        try:
            event_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if today <= event_date <= end_date:
                e["is_indoor"] = is_indoor_event(e)
                good_events.append(e)
        except:
            continue

    # Score each event by relevance
    prefer_indoor = weather_condition in ["snow", "rainy", "heat", "freezing", "mixed"]

    def score_event(e):
        score = 0
        cats = e.get("categories", [])

        # Community relevance (highest priority)
        if "South Asian" in cats:
            score += 100
        if "Middle Eastern" in cats:
            score += 100

        # Cultural events
        if "Cultural Festival" in cats:
            score += 50
        if "Music & Dance" in cats:
            score += 40
        if "Food & Markets" in cats:
            score += 40

        # Free events get a boost
        price = (e.get("price") or "").lower()
        if "free" in price:
            score += 30

        # Weather appropriateness
        is_indoor = e.get("is_indoor", True)
        if prefer_indoor and is_indoor:
            score += 20
        elif not prefer_indoor and not is_indoor:
            score += 20

        # Has time listed (more organized)
        if e.get("time"):
            score += 10

        return score

    # Sort by score (highest first), then by date
    good_events.sort(key=lambda e: (-score_event(e), e["date"]))

    # Remove duplicates (same name)
    seen_names = set()
    unique_events = []
    for e in good_events:
        name = e["name"].lower().strip()
        if name not in seen_names:
            seen_names.add(name)
            unique_events.append(e)

    return unique_events[:7]


# Inspirational quotes
QUOTES = [
    "She remembered who she was and the game changed. ✨",
    "Good things are coming. Keep going. 💫",
    "You're allowed to be both a masterpiece and a work in progress. 🦋",
    "Create the life you can't wait to wake up to. ☀️",
    "Your vibe attracts your tribe. 💕",
    "She believed she could, so she did. 🌸",
    "Plot twist: everything works out. 🌙",
    "Main character energy only. 💅",
    "Healing isn't linear, but you're doing amazing. 🌷",
    "The universe has your back, babe. ⭐",
]

# Weather vibes
WEATHER_VIBES = {
    "snow": "Cozy girl winter is HERE. Grab your chai, light a candle, and let's find you some warm indoor plans ❄️",
    "freezing": "It's giving polar vortex. Time for hot cocoa and cozy indoor vibes 🥶",
    "rainy": "Rainy days = self care days. Here's some indoor inspo for you 🌧️",
    "heat": "Hot girl summer called - let's find you some AC and cold drinks 🔥",
    "mixed": "The weather can't make up its mind but we've got you covered 🌦️",
    "nice": "Perfect weather alert! Get outside and touch grass bestie ☀️",
}


def format_message(events, weather_emoji, weather_note, weather_condition="nice"):
    """Format events as a simple text message."""
    # Get vibes intro
    vibes = WEATHER_VIBES.get(weather_condition, WEATHER_VIBES["nice"])
    quote = random.choice(QUOTES)

    header = f"{weather_emoji} Your Weekly Picks\n\n{vibes}"

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

    # Add quote and link
    lines.append(f"\n{quote}")
    lines.append("atopofconscience.github.io/mehfil")
    return "\n\n".join(lines)


def copy_to_clipboard(message):
    """Copy message to clipboard using pbcopy."""
    result = subprocess.run(
        ["pbcopy"],
        input=message.encode(),
        capture_output=True
    )
    return result.returncode == 0


def send_imessage(phone_number, message):
    """Send iMessage using AppleScript."""
    # Escape quotes and backslashes for AppleScript
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
        return True
    else:
        print(f"  Error sending to {phone_number}: {result.stderr}")
        return False


def send_to_all():
    """Send weekly picks to all subscribers."""
    data = load_subscribers()

    if not data["subscribers"]:
        print("No subscribers yet!")
        print("Add yourself: python send_imessage.py --add")
        return

    print("Fetching Boston weather forecast...")
    weather_data = get_weather_forecast()
    condition, emoji, note = analyze_weather(weather_data)
    print(f"  Weather: {emoji} {condition}")
    print(f"  {note}")

    print("\nLoading events (weather-adjusted)...")
    events = load_events(condition)

    if not events:
        print("No events found!")
        return

    message = format_message(events, emoji, note, condition)

    print(f"\nSending to {len(data['subscribers'])} subscriber(s)...")

    sent = 0
    failed = 0
    for sub in data["subscribers"]:
        print(f"  Sending to {sub['name']}...", end=" ")
        if send_imessage(sub["phone"], message):
            print("✓")
            sent += 1
        else:
            print("✗")
            failed += 1

    print(f"\nDone! Sent: {sent}, Failed: {failed}")


def get_message():
    """Generate the weather-aware message."""
    print("Fetching Boston weather forecast...")
    weather_data = get_weather_forecast()
    condition, emoji, note = analyze_weather(weather_data)
    print(f"  Weather: {emoji} {condition}")
    print(f"  {note}")

    print("\nLoading events (weather-adjusted)...")
    events = load_events(condition)

    if not events:
        print("No events found!")
        return None

    return format_message(events, emoji, note, condition)


def clipboard():
    """Copy message to clipboard."""
    message = get_message()
    if not message:
        return

    if copy_to_clipboard(message):
        print("\n" + "=" * 50)
        print("COPIED TO CLIPBOARD!")
        print("Just open Messages and paste (⌘V)")
        print("=" * 50)
        print(message)
        print("=" * 50)
    else:
        print("Failed to copy to clipboard.")


def preview():
    """Preview the message without sending."""
    message = get_message()
    if not message:
        return

    print("\n" + "=" * 50)
    print("MESSAGE PREVIEW")
    print("=" * 50)
    print(message)
    print("=" * 50)


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--add":
            add_subscriber()
        elif arg == "--remove":
            remove_subscriber()
        elif arg == "--list":
            list_subscribers()
        elif arg == "--preview":
            preview()
        elif arg == "--send":
            send_to_all()
        elif arg == "--help":
            print(__doc__)
        else:
            print(f"Unknown option: {arg}")
            print("Use --help for usage info")
    else:
        # Default: copy to clipboard
        clipboard()


if __name__ == "__main__":
    main()
