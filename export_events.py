"""Export events from Notion to JSON for the web dashboard."""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client


def export_events():
    """Export all events from Notion to a JSON file."""
    load_dotenv()

    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not database_id:
        print("Error: NOTION_TOKEN and NOTION_DATABASE_ID must be set")
        return

    client = Client(auth=token)
    events = []
    has_more = True
    start_cursor = None

    print("Fetching events from Notion...")

    while has_more:
        response = client.databases.query(
            database_id=database_id,
            start_cursor=start_cursor,
            sorts=[{"property": "Date", "direction": "ascending"}],
        )

        for page in response["results"]:
            props = page.get("properties", {})

            # Extract event data
            event = {
                "id": page["id"],
                "name": _get_title(props.get("Name", {})),
                "date": _get_date(props.get("Date", {})),
                "time": _get_text(props.get("Time", {})),
                "location": _get_text(props.get("Location", {})),
                "address": _get_text(props.get("Address", {})),
                "price": _get_text(props.get("Price", {})),
                "description": _get_text(props.get("Description", {})),
                "url": props.get("URL", {}).get("url"),
                "source": _get_select(props.get("Source", {})),
                "categories": _get_multi_select(props.get("Category", {})),
                "latitude": props.get("Latitude", {}).get("number"),
                "longitude": props.get("Longitude", {}).get("number"),
            }

            # Only include future events
            if event["date"]:
                try:
                    event_date = datetime.strptime(event["date"], "%Y-%m-%d")
                    if event_date >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                        events.append(event)
                except ValueError:
                    events.append(event)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    # Write to JSON file
    output_path = os.path.join(os.path.dirname(__file__), "dashboard", "events.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump({"events": events, "updated": datetime.now().isoformat()}, f, indent=2)

    print(f"Exported {len(events)} events to {output_path}")
    return events


def _get_title(prop):
    """Extract title text from a Notion title property."""
    title = prop.get("title", [])
    return title[0].get("text", {}).get("content", "") if title else ""


def _get_text(prop):
    """Extract text from a Notion rich_text property."""
    rich_text = prop.get("rich_text", [])
    return rich_text[0].get("text", {}).get("content", "") if rich_text else ""


def _get_date(prop):
    """Extract date from a Notion date property."""
    date = prop.get("date", {})
    return date.get("start") if date else None


def _get_select(prop):
    """Extract value from a Notion select property."""
    select = prop.get("select", {})
    return select.get("name") if select else ""


def _get_multi_select(prop):
    """Extract values from a Notion multi_select property."""
    multi = prop.get("multi_select", [])
    return [item.get("name") for item in multi]


if __name__ == "__main__":
    export_events()
