"""Setup script to configure Notion database with required properties."""

import os
from dotenv import load_dotenv
from notion_client import Client


def setup_database():
    """Add required properties to the Notion database."""
    load_dotenv()

    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not database_id:
        print("Error: NOTION_TOKEN and NOTION_DATABASE_ID must be set in .env")
        return False

    client = Client(auth=token)

    # Define the properties we need
    properties = {
        "Name": {"title": {}},
        "Date": {"date": {}},
        "Source": {
            "select": {
                "options": [
                    {"name": "Eventbrite", "color": "orange"},
                    {"name": "Boston Calendar", "color": "blue"},
                    {"name": "AllEvents", "color": "green"},
                    {"name": "Meetup", "color": "red"},
                    {"name": "ISBCC", "color": "purple"},
                    {"name": "MIT Events", "color": "gray"},
                    {"name": "Harvard Events", "color": "brown"},
                    {"name": "BU Events", "color": "pink"},
                    {"name": "Northeastern Events", "color": "yellow"},
                ]
            }
        },
        "URL": {"url": {}},
        "Time": {"rich_text": {}},
        "Location": {"rich_text": {}},
        "Address": {"rich_text": {}},
        "Price": {"rich_text": {}},
        "Description": {"rich_text": {}},
        "Category": {
            "multi_select": {
                "options": [
                    {"name": "South Asian", "color": "orange"},
                    {"name": "Middle Eastern", "color": "blue"},
                    {"name": "Cultural Festival", "color": "purple"},
                    {"name": "Religious", "color": "green"},
                    {"name": "Food & Markets", "color": "red"},
                    {"name": "Arts & Crafts", "color": "pink"},
                    {"name": "Theater & Film", "color": "gray"},
                    {"name": "Comedy", "color": "yellow"},
                    {"name": "Coffee & Chai", "color": "brown"},
                    {"name": "Sports & Outdoors", "color": "green"},
                    {"name": "Music & Dance", "color": "purple"},
                    {"name": "Talks & Lectures", "color": "blue"},
                    {"name": "Community", "color": "default"},
                ]
            }
        },
        "Latitude": {"number": {}},
        "Longitude": {"number": {}},
    }

    try:
        # Update the database with the properties
        client.databases.update(
            database_id=database_id,
            properties=properties,
        )
        print("Successfully configured Notion database!")
        print("\nProperties added:")
        for prop in properties:
            print(f"  - {prop}")
        return True

    except Exception as e:
        print(f"Error updating database: {e}")
        return False


if __name__ == "__main__":
    setup_database()
