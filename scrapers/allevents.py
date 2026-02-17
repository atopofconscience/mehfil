"""Scraper for AllEvents.in - requires Playwright for full functionality."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class AllEventsScraper(BaseScraper):
    """Scrapes AllEvents.in for South Asian and Middle Eastern events in Boston."""

    SOURCE_NAME = "AllEvents"

    SEARCH_TERMS = ["indian", "south-asian", "bollywood", "desi", "middle-eastern", "persian"]

    def __init__(self):
        self.base_url = "https://allevents.in/boston"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape AllEvents.in - uses Playwright if available, otherwise limited scraping."""
        if PLAYWRIGHT_AVAILABLE:
            return self._scrape_with_playwright()
        else:
            return self._scrape_basic()

    def _scrape_with_playwright(self) -> List[Event]:
        """Full scraping with Playwright."""
        all_events = []
        seen_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for term in self.SEARCH_TERMS:
                try:
                    url = f"{self.base_url}/{term}"
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)

                    # Scroll to load more
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1500)

                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    # Find event cards
                    event_cards = soup.find_all("a", href=lambda h: h and "/e/" in str(h))

                    for card in event_cards[:10]:
                        event = self._parse_event_card(card)
                        if event and event.url not in seen_urls:
                            seen_urls.add(event.url)
                            all_events.append(event)

                except Exception as e:
                    continue

            browser.close()

        return all_events

    def _scrape_basic(self) -> List[Event]:
        """Basic scraping without JavaScript - limited results."""
        # AllEvents requires JavaScript, so we can only get limited data
        # from the FAQ section which mentions upcoming events
        events = []

        try:
            response = requests.get(f"{self.base_url}/indian", headers=self.headers, timeout=15)
            if response.status_code != 200:
                return events

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to extract event info from FAQ answers
            faq_answers = soup.find_all("div", class_=lambda c: c and "answer" in str(c).lower())

            for answer in faq_answers:
                text = answer.get_text()
                # Look for event patterns like "EVENT NAME is happening on DATE"
                matches = re.findall(
                    r'([A-Z][^.]+?) is happening on (\w+ \d+ \w+ \d+)(?: from ([\d:]+\s*[AP]M))?',
                    text,
                    re.IGNORECASE
                )

                for match in matches:
                    name, date_str, time_str = match[0], match[1], match[2] if len(match) > 2 else None

                    # Parse date
                    date = self._parse_date(date_str)
                    if date:
                        events.append(Event(
                            name=name.strip(),
                            date=date,
                            time=time_str,
                            location="Boston, MA",
                            url=f"{self.base_url}/indian",
                            source=self.SOURCE_NAME,
                            category=self._categorize(name),
                        ))

        except Exception:
            pass

        return events

    def _parse_event_card(self, card) -> Event:
        """Parse an event card."""
        url = card.get("href", "")
        if not url.startswith("http"):
            url = "https://allevents.in" + url

        # Get text content
        text = card.get_text(" ", strip=True)
        if not text or len(text) < 10:
            return None

        # Try to extract name and date
        # Format often: "EVENT NAME Fri 20 Feb 2026 10:30 PM"
        parts = text.split()

        # Find date pattern
        date_match = re.search(r'(\w{3})\s+(\d{1,2})\s+(\w{3})\s+(\d{4})', text)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', text)

        date = datetime.now()
        time_str = None

        if date_match:
            try:
                date_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)} {date_match.group(4)}"
                date = datetime.strptime(date_str, "%a %d %b %Y")
            except ValueError:
                pass

        if time_match:
            time_str = time_match.group(1)

        # Event name is everything before the date
        name = text
        if date_match:
            name = text[:date_match.start()].strip()

        if not name or len(name) < 5:
            return None

        return Event(
            name=name,
            date=date,
            time=time_str,
            location="Boston, MA",
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name),
        )

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string like 'Fri 20 Feb 2026'."""
        formats = [
            "%a %d %b %Y",
            "%A %d %B %Y",
            "%d %b %Y",
            "%B %d %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _categorize(self, name: str) -> List[str]:
        """Assign categories based on event content."""
        text = name.lower()
        categories = []

        if any(kw in text for kw in SOUTH_ASIAN_KEYWORDS):
            categories.append("South Asian")
        if any(kw in text for kw in MIDDLE_EASTERN_KEYWORDS):
            categories.append("Middle Eastern")

        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                if cat not in categories:
                    categories.append(cat)

        return categories if categories else ["Community"]
