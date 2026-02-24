#!/usr/bin/env python3
"""
Send weekly event picks via iMessage.
Just run: python send_imessage.py

No setup required - uses your Mac's Messages app directly.
"""

import json
import subprocess
from datetime import datetime


def load_events():
    """Load and filter events."""
    with open("dashboard/events.json") as f:
        data = json.load(f)

    today = datetime.now().date()

    # Filter: future events, no junk names
    junk = ["cookie", "sign up", "log in", "privacy", "terms"]
    good_events = []

    for e in data["events"]:
        name = e.get("name", "")
        if not name or any(j in name.lower() for j in junk):
            continue
        try:
            event_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if event_date >= today:
                good_events.append(e)
        except:
            continue

    # Sort by date
    good_events.sort(key=lambda x: x["date"])
    return good_events[:7]


def format_message(events):
    """Format events as a simple text message."""
    lines = ["Your 7 Events This Week\n"]

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
    # Escape quotes for AppleScript
    message = message.replace('"', '\\"')

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
    # Your phone number (or email) - change this!
    YOUR_NUMBER = input("Enter your phone number or iMessage email: ").strip()

    print("\nLoading events...")
    events = load_events()

    if not events:
        print("No events found!")
        return

    message = format_message(events)

    print("\n--- Preview ---")
    print(message)
    print("--- End Preview ---\n")

    confirm = input("Send this message? (y/n): ").strip().lower()
    if confirm == "y":
        send_imessage(YOUR_NUMBER, message)
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
