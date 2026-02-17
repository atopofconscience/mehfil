"""Notion client for pushing events to the database."""

import os
from notion_client import Client
from scrapers.base import Event


class NotionEventClient:
    """Client for managing events in Notion database."""

    def __init__(self):
        self.token = os.getenv("NOTION_TOKEN")
        self.database_id = os.getenv("NOTION_DATABASE_ID")

        if not self.token:
            raise ValueError("NOTION_TOKEN environment variable is required")
        if not self.database_id:
            raise ValueError("NOTION_DATABASE_ID environment variable is required")

        self.client = Client(auth=self.token)

    def add_event(self, event: Event) -> dict:
        """Add an event to the Notion database."""
        properties = {
            "Name": {"title": [{"text": {"content": event.name[:2000]}}]},
            "Date": {"date": {"start": event.date.strftime("%Y-%m-%d")}},
            "Source": {"select": {"name": event.source}},
            "URL": {"url": event.url},
        }

        # Add optional fields if present
        if event.time:
            properties["Time"] = {
                "rich_text": [{"text": {"content": event.time[:2000]}}]
            }

        if event.location:
            properties["Location"] = {
                "rich_text": [{"text": {"content": event.location[:2000]}}]
            }

        if event.address:
            properties["Address"] = {
                "rich_text": [{"text": {"content": event.address[:2000]}}]
            }

        if event.price:
            properties["Price"] = {
                "rich_text": [{"text": {"content": event.price[:2000]}}]
            }

        if event.description:
            properties["Description"] = {
                "rich_text": [{"text": {"content": event.description[:2000]}}]
            }

        if event.category:
            properties["Category"] = {
                "multi_select": [{"name": cat} for cat in event.category]
            }

        if event.latitude:
            properties["Latitude"] = {"number": event.latitude}

        if event.longitude:
            properties["Longitude"] = {"number": event.longitude}

        return self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )

    def get_existing_urls(self) -> set:
        """Get all existing event URLs to avoid duplicates."""
        urls = set()
        has_more = True
        start_cursor = None

        while has_more:
            response = self.client.databases.query(
                database_id=self.database_id,
                start_cursor=start_cursor,
            )

            for page in response["results"]:
                url_prop = page.get("properties", {}).get("URL", {})
                if url_prop.get("url"):
                    urls.add(url_prop["url"])

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return urls

    def add_events(self, events, skip_duplicates: bool = True) -> dict:
        """Add multiple events to Notion, optionally skipping duplicates."""
        added = 0
        skipped = 0
        errors = 0

        existing_urls = self.get_existing_urls() if skip_duplicates else set()

        for event in events:
            if event.url in existing_urls:
                skipped += 1
                continue

            try:
                self.add_event(event)
                added += 1
                existing_urls.add(event.url)  # Track newly added
                print(f"Added: {event.name[:50]}...")
            except Exception as e:
                errors += 1
                print(f"Error adding '{event.name[:30]}': {e}")

        return {"added": added, "skipped": skipped, "errors": errors}
