"""Scraper for Ticketmaster events using Playwright."""

import re
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class TicketmasterScraper(BaseScraper):
    """Scrapes Ticketmaster for South Asian and Middle Eastern events in Boston."""

    SOURCE_NAME = "Ticketmaster"

    # Search terms - comedians, artists, cultural events
    SEARCH_TERMS = [
        # South Asian comedians - male
        "vir das", "samay raina", "zakir khan", "kenny sebastian",
        "abhishek upmanyu", "kanan gill", "anubhav singh bassi",
        # South Asian comedians - female
        "aditi mittal", "sumukhi suresh", "kaneez surka", "urooj ashfaq",
        "aishwarya mohanraj", "prashasti singh", "neeti palta",
        "shreeja chaturvedi", "agrima joshua",
        # Middle Eastern comedians
        "hasan minhaj", "maz jobrani", "mo amer", "ramy youssef",
        # Music artists
        "arijit singh", "shreya ghoshal", "ar rahman", "pritam",
        "atif aslam", "rahat fateh ali khan", "sonu nigam",
        "sunidhi chauhan", "neha kakkar",
        # Cultural keywords
        "bollywood", "desi party", "holi", "diwali", "navratri",
        "bhangra", "garba", "qawwali",
    ]

    def __init__(self):
        self.base_url = "https://www.ticketmaster.com"

    def scrape(self) -> List[Event]:
        """Scrape Ticketmaster for cultural events."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not available, skipping Ticketmaster")
            return []

        all_events = []
        seen_urls = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                page = context.new_page()

                for term in self.SEARCH_TERMS:
                    try:
                        events = self._search(page, term)
                        for event in events:
                            if event.url not in seen_urls:
                                seen_urls.add(event.url)
                                all_events.append(event)
                                print(f"    Found: {event.name}")
                    except Exception as e:
                        continue

                browser.close()
        except Exception as e:
            print(f"  Playwright error: {e}")

        return all_events

    def _search(self, page, query: str) -> List[Event]:
        """Search Ticketmaster for events near Boston."""
        events = []

        search_url = f"{self.base_url}/search?q={query}&lat=42.3601&long=-71.0589&radius=50"
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find event links
        event_links = soup.find_all("a", href=lambda h: h and "/event/" in str(h))

        for link in event_links[:10]:
            try:
                event = self._parse_event_link(link, query)
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event_link(self, link, search_term: str):
        """Parse an event link into an Event object."""
        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        name = link.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        name = re.sub(r'\s+', ' ', name).strip()

        if name.lower() in ["see tickets", "view details", "buy tickets"]:
            return None

        return Event(
            name=name,
            date=datetime.now(),
            location="Boston Area",
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name, search_term),
        )

    def _categorize(self, name: str, search_term: str) -> List[str]:
        """Categorize event based on content."""
        text = f"{name} {search_term}".lower()
        categories = []

        if any(kw in text for kw in SOUTH_ASIAN_KEYWORDS):
            categories.append("South Asian")
        if any(kw in text for kw in MIDDLE_EASTERN_KEYWORDS):
            categories.append("Middle Eastern")

        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                if cat not in categories:
                    categories.append(cat)

        if not categories:
            categories.append("Comedy" if "comedy" in text else "Music & Dance")

        return categories
