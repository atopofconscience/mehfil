"""Main script to scrape events and push to Notion."""

import os
from dotenv import load_dotenv

from scrapers import (
    EventbriteScraper,
    BostonCalendarScraper,
    AllEventsScraper,
    MeetupScraper,
    ISBCCScraper,
    UniversityEventsScraper,
    TicketmasterScraper,
    BandsintownScraper,
    DiceScraper,
    SulekhaScraper,
    BrownPaperTicketsScraper,
    GoogleEventsScraper,
    FacebookEventsScraper,
)
from notion_db import NotionEventClient


def main():
    # Load environment variables from .env file
    load_dotenv()

    print("=" * 50)
    print("Boston Community Events Scraper")
    print("=" * 50)

    # Initialize scrapers
    scrapers = [
        EventbriteScraper(),
        BostonCalendarScraper(),
        AllEventsScraper(),
        SulekhaScraper(),
        GoogleEventsScraper(),
        FacebookEventsScraper(),
        BandsintownScraper(),
        MeetupScraper(),
        ISBCCScraper(),
        UniversityEventsScraper(),
    ]

    # Scrape all sources
    all_events = []
    for scraper in scrapers:
        print(f"\nScraping {scraper.SOURCE_NAME}...")
        try:
            events = scraper.scrape()
            print(f"  Found {len(events)} events")
            all_events.extend(events)
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nTotal events found: {len(all_events)}")

    if not all_events:
        print("No events found. Exiting.")
        return

    # Push to Notion
    print("\nPushing events to Notion...")
    try:
        notion = NotionEventClient()
        results = notion.add_events(all_events, skip_duplicates=True)
        print(f"\nResults:")
        print(f"  Added: {results['added']}")
        print(f"  Skipped (duplicates): {results['skipped']}")
        print(f"  Errors: {results['errors']}")
    except Exception as e:
        print(f"Error connecting to Notion: {e}")
        print("Make sure NOTION_TOKEN and NOTION_DATABASE_ID are set correctly.")

    print("\nDone!")


if __name__ == "__main__":
    main()
