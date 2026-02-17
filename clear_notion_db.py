"""Clear all entries from the Notion database."""

import os
from dotenv import load_dotenv
from notion_client import Client


def clear_database():
    """Delete all pages from the Notion database."""
    load_dotenv()

    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not database_id:
        print("Error: NOTION_TOKEN and NOTION_DATABASE_ID must be set")
        return

    client = Client(auth=token)

    print("Fetching existing entries...")
    pages_to_delete = []
    has_more = True
    start_cursor = None

    while has_more:
        response = client.databases.query(
            database_id=database_id,
            start_cursor=start_cursor,
        )

        for page in response["results"]:
            pages_to_delete.append(page["id"])

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    print(f"Found {len(pages_to_delete)} entries to delete...")

    deleted = 0
    for page_id in pages_to_delete:
        try:
            client.pages.update(page_id=page_id, archived=True)
            deleted += 1
            if deleted % 10 == 0:
                print(f"  Deleted {deleted}/{len(pages_to_delete)}...")
        except Exception as e:
            print(f"  Error deleting page: {e}")

    print(f"\nDeleted {deleted} entries from Notion database")


if __name__ == "__main__":
    clear_database()
