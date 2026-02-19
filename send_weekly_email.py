"""
Weekly personalized event email sender for Mehfil.

This script:
1. Reads events for the upcoming week
2. Fetches subscribers and their interests from Brevo
3. Generates personalized emails based on interests
4. Sends via Brevo API

Run manually or via GitHub Actions every Sunday.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_API_URL = "https://api.brevo.com/v3"
SENDER_EMAIL = "hello@mehfil.com"  # Update with your verified sender
SENDER_NAME = "Mehfil Boston"

# Map form interests to event categories
INTEREST_TO_CATEGORY = {
    "desi": ["South Asian", "Music & Dance"],  # Desi & Bollywood
    "arab": ["Middle Eastern"],  # Arab & Persian
    "arts": ["Arts & Crafts"],
    "music": ["Music & Dance"],
    "food": ["Food & Markets"],
    "cultural": ["Cultural Festival"],
    "wellness": ["Sports & Outdoors"],
    "career": ["Career & Tech", "Talks & Lectures"],  # Career & Tech events
}

# Max events per email
MAX_EVENTS_PER_EMAIL = 7


def load_events():
    """Load events from the JSON file."""
    with open("dashboard/events.json", "r") as f:
        data = json.load(f)
    return data.get("events", [])


def get_upcoming_events(events, days=7):
    """Filter events happening in the next N days."""
    today = datetime.now().date()
    end_date = today + timedelta(days=days)

    upcoming = []
    for event in events:
        try:
            event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
            if today <= event_date <= end_date:
                upcoming.append(event)
        except (ValueError, KeyError):
            continue

    # Sort by date
    upcoming.sort(key=lambda e: e["date"])
    return upcoming


def categorize_events(events):
    """Group events by category."""
    by_category = defaultdict(list)

    for event in events:
        categories = event.get("categories", ["Community"])
        for cat in categories:
            by_category[cat].append(event)

    return dict(by_category)


def get_events_for_subscriber(events, subscriber):
    """Get events matching a subscriber's full preferences."""
    interests = subscriber.get("interests", [])
    location_pref = subscriber.get("location", "all")
    price_prefs = subscriber.get("price_prefs", [])

    # Build list of category filters from interests
    interest_cats = []
    for i in interests:
        interest_cats.extend(INTEREST_TO_CATEGORY.get(i, []))

    matched_events = []

    for event in events:
        event_cats = event.get("categories", [])

        # Interest filter: if subscriber selected interests, event must match at least one
        if interest_cats:
            if not any(cat in event_cats for cat in interest_cats):
                continue

        # Location filter
        if location_pref and location_pref != "all":
            event_location = f"{event.get('location', '')} {event.get('address', '')}".lower()
            if location_pref.lower() not in event_location:
                continue

        # Price filter
        if price_prefs:
            event_price = (event.get("price") or "").lower()
            if "free" in price_prefs and "paid" not in price_prefs:
                if "free" not in event_price:
                    continue
            elif "paid" in price_prefs and "free" not in price_prefs:
                if "free" in event_price or not event_price:
                    continue

        matched_events.append(event)

    # Sort by date and limit
    matched_events.sort(key=lambda e: e["date"])
    return matched_events[:MAX_EVENTS_PER_EMAIL]


def format_event_html(event):
    """Format a single event as HTML."""
    date = datetime.strptime(event["date"], "%Y-%m-%d")
    date_str = date.strftime("%A, %B %d")
    time_str = event.get("time", "Time TBA")
    location = event.get("location", "Location TBA")
    price = event.get("price", "")
    url = event.get("url", "#")

    price_badge = ""
    if price:
        if "free" in price.lower():
            price_badge = '<span style="background:#059669;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">FREE</span>'
        else:
            price_badge = f'<span style="background:#c53030;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{price}</span>'

    return f"""
    <div style="border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:16px;background:white;">
        <div style="color:#718096;font-size:13px;margin-bottom:4px;">{date_str} &bull; {time_str}</div>
        <a href="{url}" style="color:#1e3a5f;font-size:18px;font-weight:600;text-decoration:none;">{event["name"]}</a>
        <div style="color:#4a5568;font-size:14px;margin-top:8px;">📍 {location}</div>
        <div style="margin-top:8px;">{price_badge}</div>
    </div>
    """


def generate_email_html(subscriber_name, events, interests):
    """Generate the full email HTML."""
    events_html = "\n".join(format_event_html(e) for e in events[:10])  # Limit to 10

    interest_tags = ", ".join(interests) if interests else "all events"
    greeting = f"Hi {subscriber_name}," if subscriber_name else "Hi there,"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f7fafc;margin:0;padding:20px;">
        <div style="max-width:600px;margin:0 auto;background:#f7fafc;">
            <!-- Header -->
            <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2c5282 100%);color:white;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:28px;">☕ Mehfil</h1>
                <p style="margin:8px 0 0;opacity:0.9;">Your Weekly Boston Events</p>
            </div>

            <!-- Content -->
            <div style="background:white;padding:24px;border-radius:0 0 12px 12px;">
                <p style="font-size:16px;color:#2d3748;">{greeting}</p>

                <p style="font-size:16px;color:#2d3748;">
                    Here are this week's events picked just for you based on your interests in <strong>{interest_tags}</strong>:
                </p>

                <div style="margin:24px 0;">
                    {events_html}
                </div>

                <div style="text-align:center;margin-top:24px;">
                    <a href="https://atopofconscience.github.io/mehfil/"
                       style="display:inline-block;background:#1e3a5f;color:white;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;">
                        See All Events
                    </a>
                </div>

                <p style="font-size:14px;color:#718096;margin-top:32px;text-align:center;">
                    You're receiving this because you signed up for Mehfil weekly picks.<br>
                    <a href="{{{{ unsubscribe }}}}" style="color:#718096;">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def generate_no_events_html(subscriber_name, interests):
    """Generate email when no matching events found."""
    greeting = f"Hi {subscriber_name}," if subscriber_name else "Hi there,"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f7fafc;margin:0;padding:20px;">
        <div style="max-width:600px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2c5282 100%);color:white;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:28px;">☕ Mehfil</h1>
            </div>
            <div style="background:white;padding:24px;border-radius:0 0 12px 12px;">
                <p>{greeting}</p>
                <p>It's a quiet week for your interests, but there might be other great events happening!</p>
                <div style="text-align:center;margin:24px 0;">
                    <a href="https://atopofconscience.github.io/mehfil/"
                       style="display:inline-block;background:#1e3a5f;color:white;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;">
                        Browse All Events
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def get_subscribers_from_brevo():
    """Fetch subscribers from Brevo contact list."""
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    # Get all contacts with their attributes
    response = requests.get(
        f"{BREVO_API_URL}/contacts",
        headers=headers,
        params={"limit": 500}
    )

    if response.status_code != 200:
        print(f"Error fetching contacts: {response.text}")
        return []

    contacts = response.json().get("contacts", [])

    subscribers = []
    for contact in contacts:
        attrs = contact.get("attributes", {})
        subscribers.append({
            "email": contact["email"],
            "name": attrs.get("FIRSTNAME", ""),
            "interests": [i.strip() for i in attrs.get("INTERESTS", "").split(",") if i.strip()],
            "location": attrs.get("LOCATION", "all"),
            "price_prefs": [p.strip() for p in attrs.get("PRICE_PREF", "").split(",") if p.strip()]
        })

    return subscribers


def send_email_via_brevo(to_email, to_name, subject, html_content):
    """Send an email via Brevo API."""
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content
    }

    response = requests.post(
        f"{BREVO_API_URL}/smtp/email",
        headers=headers,
        json=payload
    )

    if response.status_code == 201:
        print(f"  ✓ Sent to {to_email}")
        return True
    else:
        print(f"  ✗ Failed for {to_email}: {response.text}")
        return False


def main():
    """Main function to send weekly emails."""
    print("=" * 50)
    print("Mehfil Weekly Email Sender")
    print("=" * 50)

    if not BREVO_API_KEY:
        print("ERROR: BREVO_API_KEY environment variable not set")
        print("\nTo test locally, export your API key:")
        print("  export BREVO_API_KEY=your_api_key_here")
        return

    # Load and filter events
    print("\n1. Loading events...")
    events = load_events()
    print(f"   Total events: {len(events)}")

    upcoming = get_upcoming_events(events, days=7)
    print(f"   Events this week: {len(upcoming)}")

    if not upcoming:
        print("   No events this week, skipping email send.")
        return

    events_by_category = categorize_events(upcoming)
    print(f"   Categories: {list(events_by_category.keys())}")

    # Get subscribers
    print("\n2. Fetching subscribers from Brevo...")
    subscribers = get_subscribers_from_brevo()
    print(f"   Total subscribers: {len(subscribers)}")

    if not subscribers:
        print("   No subscribers found.")
        return

    # Send personalized emails
    print("\n3. Sending personalized emails...")
    today = datetime.now().strftime("%B %d")
    subject = f"Your Boston Events This Week - {today}"

    sent = 0
    failed = 0

    for subscriber in subscribers:
        email = subscriber["email"]
        name = subscriber.get("name", "")

        # Get events matching their preferences
        has_preferences = (subscriber.get("interests") or
                          subscriber.get("location", "all") != "all" or
                          subscriber.get("price_prefs"))

        if has_preferences:
            matched_events = get_events_for_subscriber(upcoming, subscriber)
        else:
            # No specific preferences = send top events
            matched_events = upcoming[:MAX_EVENTS_PER_EMAIL]

        # Build preference description for email
        pref_desc = subscriber.get("interests", []) or ["all events"]

        # Generate email
        if matched_events:
            html = generate_email_html(name, matched_events, pref_desc)
        else:
            html = generate_no_events_html(name, pref_desc)

        # Send
        if send_email_via_brevo(email, name, subject, html):
            sent += 1
        else:
            failed += 1

    print(f"\n4. Complete!")
    print(f"   Sent: {sent}")
    print(f"   Failed: {failed}")


if __name__ == "__main__":
    main()
