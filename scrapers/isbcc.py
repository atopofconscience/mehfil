"""Scraper for ISBCC (Islamic Society of Boston Cultural Center) events using Playwright."""

import re
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, Event


class ISBCCScraper(BaseScraper):
    """Scrapes ISBCC for Islamic community events in Boston."""

    SOURCE_NAME = "ISBCC"

    def __init__(self):
        self.base_url = "https://www.isbcc.org"
        self.events_url = "https://www.isbcc.org/events"
        # ISBCC location is fixed
        self.location = "Islamic Society of Boston Cultural Center"
        self.address = "100 Malcolm X Blvd, Boston, MA 02119"
        self.latitude = 42.3307
        self.longitude = -71.0834

    def scrape(self) -> List[Event]:
        """Scrape ISBCC for events using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not installed, skipping ISBCC")
            return []

        events = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()

            try:
                page.goto(self.events_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Scroll to load content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Find event items - ISBCC likely uses WordPress or similar
                event_items = soup.find_all("article") or \
                             soup.find_all("div", {"class": lambda c: c and "event" in str(c).lower()}) or \
                             soup.find_all("div", {"class": lambda c: c and "tribe" in str(c).lower()}) or \
                             soup.find_all("li", {"class": lambda c: c and "event" in str(c).lower()})

                for item in event_items[:20]:
                    try:
                        event = self._parse_event_item(item)
                        if event:
                            events.append(event)
                    except Exception:
                        continue

                # Also try to find events in a calendar view
                calendar_events = soup.find_all("a", {"class": lambda c: c and "tribe" in str(c).lower()})
                for item in calendar_events[:20]:
                    try:
                        event = self._parse_calendar_link(item)
                        if event and event.url not in [e.url for e in events]:
                            events.append(event)
                    except Exception:
                        continue

            except Exception as e:
                print(f"  Error scraping ISBCC: {e}")

            browser.close()

        return events

    def _parse_event_item(self, item):
        """Parse an event item into an Event object."""
        link = item.find("a", href=True)
        if not link:
            return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        # Get title
        title_elem = item.find(["h2", "h3", "h4"]) or link
        name = title_elem.get_text(strip=True) if title_elem else ""

        if not name or len(name) < 3:
            return None

        # Get date
        date_elem = item.find("time") or \
                    item.find(["span", "div"], {"class": lambda c: c and "date" in str(c).lower()})
        date = datetime.now()
        time_str = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            date, time_str = self._parse_date_time(date_text)

        # Get description
        desc_elem = item.find(["p", "div"], {"class": lambda c: c and "description" in str(c).lower()}) or \
                   item.find("p")
        description = desc_elem.get_text(strip=True)[:500] if desc_elem else None

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=self.location,
            address=self.address,
            url=url,
            source=self.SOURCE_NAME,
            description=description,
            category=self._categorize(name, description),
            latitude=self.latitude,
            longitude=self.longitude,
        )

    def _parse_calendar_link(self, link):
        """Parse a calendar link into an Event object."""
        url = link.get("href", "")
        if not url or "event" not in url.lower():
            return None

        if not url.startswith("http"):
            url = self.base_url + url

        name = link.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        return Event(
            name=name,
            date=datetime.now(),
            location=self.location,
            address=self.address,
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name, None),
            latitude=self.latitude,
            longitude=self.longitude,
        )

    def _parse_date_time(self, date_text: str):
        """Parse date and time from text."""
        date = datetime.now()
        time_str = None

        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', date_text)
        if time_match:
            time_str = time_match.group(1).strip()

        formats = [
            "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y",
            "%A, %B %d, %Y", "%a, %b %d, %Y",
            "%A, %B %d", "%a, %b %d",
            "%d %B %Y", "%d %b %Y",
        ]

        date_only = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?', '', date_text).strip()

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_only.strip(), fmt)
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                    if parsed < datetime.now():
                        parsed = parsed.replace(year=datetime.now().year + 1)
                return parsed, time_str
            except ValueError:
                continue

        return date, time_str

    def _categorize(self, name: str, description: str = None) -> List[str]:
        """Assign categories - ISBCC events are primarily Middle Eastern/Islamic."""
        text = f"{name} {description or ''}".lower()
        categories = ["Middle Eastern"]

        if any(x in text for x in ["eid", "ramadan", "iftar", "prayer", "quran", "islamic", "jummah", "khutbah"]):
            categories.append("Religious")
        if any(x in text for x in ["festival", "celebration", "mela"]):
            categories.append("Cultural Festival")
        if any(x in text for x in ["food", "dinner", "lunch", "cooking", "iftar"]):
            categories.append("Food & Markets")
        if any(x in text for x in ["talk", "lecture", "seminar", "discussion", "halaqah"]):
            categories.append("Talks & Lectures")
        if any(x in text for x in ["youth", "kids", "children", "family"]):
            categories.append("Community")
        if any(x in text for x in ["class", "learn", "arabic", "quran"]):
            categories.append("Talks & Lectures")

        return categories
