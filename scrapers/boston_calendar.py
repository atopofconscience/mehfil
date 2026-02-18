"""Scraper for The Boston Calendar using Playwright."""

import re
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class BostonCalendarScraper(BaseScraper):
    """Scrapes The Boston Calendar for community events."""

    SOURCE_NAME = "Boston Calendar"

    # Use expanded keywords from base
    KEYWORDS = SOUTH_ASIAN_KEYWORDS + MIDDLE_EASTERN_KEYWORDS

    SEARCH_TERMS = [
        "indian", "middle eastern", "cultural", "south asian", "persian", "arabic",
        "painting", "art class", "pottery", "dance class", "crafts", "workshop",
        "cooking class", "mosaic", "calligraphy", "yoga", "meditation", "world music"
    ]

    def __init__(self):
        self.base_url = "https://www.thebostoncalendar.com"

    def scrape(self) -> list[Event]:
        """Scrape The Boston Calendar using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not available, skipping Boston Calendar")
            return []

        all_events = []
        seen_urls = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # Scrape main events page
                try:
                    events = self._scrape_main_page(page)
                    for event in events:
                        if event.url not in seen_urls:
                            seen_urls.add(event.url)
                            all_events.append(event)
                except Exception as e:
                    print(f"  Error scraping main page: {e}")

                # Search for specific terms
                for keyword in self.SEARCH_TERMS:
                    try:
                        events = self._search(page, keyword)
                        for event in events:
                            if event.url not in seen_urls:
                                seen_urls.add(event.url)
                                all_events.append(event)
                    except Exception:
                        pass

                browser.close()
        except Exception as e:
            print(f"  Playwright error: {e}")

        return all_events

    def _scrape_main_page(self, page) -> list[Event]:
        """Scrape the main events listing page."""
        page.goto(f"{self.base_url}/events", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_event_list(soup, page)

    def _search(self, page, query: str) -> list[Event]:
        """Search for events with a specific query."""
        search_url = f"{self.base_url}/events?search={query}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_event_list(soup, page)

    def _parse_event_list(self, soup: BeautifulSoup, page) -> list[Event]:
        """Parse a page of events."""
        events = []

        # Find event items - Boston Calendar uses li.event
        event_items = soup.find_all("li", {"class": "event"})

        for item in event_items:
            try:
                event = self._parse_event_item(item)
                if event and self._is_relevant(event):
                    # Fetch detail page for relevant events
                    event = self._enrich_event_details(event, page)
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event_item(self, item):
        """Parse an event item into an Event object."""
        # Skip pinned listings
        if item.find("i", class_="fa-thumbtack") or "pinned" in str(item).lower():
            return None

        h3 = item.find("h3")
        if not h3:
            return None

        link = h3.find("a", href=True)
        if not link:
            return None

        detail_url = link.get("href", "")
        if not detail_url.startswith("http"):
            detail_url = self.base_url + detail_url

        name = link.get_text(strip=True)
        if not name:
            return None

        # Skip list/guide articles
        skip_patterns = ["best ", "top ", "things to do", "guide to", "where to"]
        if any(p in name.lower() for p in skip_patterns):
            return None

        time_elem = item.find("p", {"class": "time"})
        if not time_elem:
            return None

        date_text = time_elem.get_text(strip=True)
        date, time_str = self._parse_date_time(date_text)

        # Skip past events
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if date < today and date.date() != today.date():
            return None

        location_elem = item.find("p", {"class": "location"})
        location = location_elem.get_text(strip=True) if location_elem else "Boston, MA"

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            url=detail_url,
            source=self.SOURCE_NAME,
            description=None,
            category=self._categorize(name, None),
        )

    def _enrich_event_details(self, event: Event, page) -> Event:
        """Fetch detail page to get actual event URL, price, and time."""
        try:
            page.goto(event.url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Extract time
            starting_time = soup.find("span", id="starting_time")
            if starting_time:
                time_text = starting_time.get_text(strip=True)
                time_match = re.search(r'(\d{1,2}:\d{2})([ap])', time_text, re.IGNORECASE)
                if time_match and not event.time:
                    hour_min = time_match.group(1)
                    ampm = time_match.group(2).lower()
                    event.time = f"{hour_min} {'PM' if ampm == 'p' else 'AM'}"

            # Extract event website and price
            for b_tag in soup.find_all("b"):
                label = b_tag.get_text(strip=True).lower()

                if "event website" in label:
                    parent_p = b_tag.find_parent("p")
                    if parent_p:
                        link = parent_p.find("a", href=True)
                        if link:
                            href = link.get("href", "")
                            if href and "thebostoncalendar.com" not in href:
                                event.url = href

                if "admission" in label:
                    parent_p = b_tag.find_parent("p")
                    if parent_p:
                        full_text = parent_p.get_text(strip=True)
                        if ":" in full_text:
                            price_text = full_text.split(":", 1)[1].strip()
                            price_text = " ".join(price_text.split())[:50]
                            if price_text:
                                if "free" in price_text.lower():
                                    event.price = "Free"
                                else:
                                    event.price = re.sub(r'<[^>]+>', '', price_text)

            # Get description
            desc_elem = soup.find("div", id="event_description")
            if desc_elem:
                event.description = desc_elem.get_text(strip=True)[:500]
                event.category = self._categorize(event.name, event.description)

        except Exception:
            pass

        return event

    def _parse_date_time(self, date_text: str) -> tuple:
        """Parse date and time from text."""
        date = datetime.now()
        time_str = None

        time_match = re.search(r'(\d{1,2}:\d{2})([ap]m?)', date_text, re.IGNORECASE)
        if time_match:
            hour_min = time_match.group(1)
            ampm = time_match.group(2).lower()
            time_str = f"{hour_min} {'PM' if ampm.startswith('p') else 'AM'}"

        date_only = re.sub(r'\d{1,2}:\d{2}[ap]m?', '', date_text, flags=re.IGNORECASE).strip()

        formats = [
            "%A, %b %d, %Y", "%A, %B %d, %Y", "%a, %b %d, %Y",
            "%B %d, %Y", "%b %d, %Y", "%A, %b %d", "%a, %b %d",
        ]

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

        return datetime.now(), time_str

    def _is_relevant(self, event: Event) -> bool:
        """Check if an event is relevant."""
        text_to_check = f"{event.name} {event.description or ''}".lower()

        if any(keyword in text_to_check for keyword in self.KEYWORDS):
            return True

        general_keywords = [
            "painting", "pottery", "art class", "workshop", "dance class", "crafts",
            "drawing", "mosaic", "calligraphy", "cultural", "world music", "cooking class",
            "yoga", "meditation", "mindfulness", "gallery", "exhibition"
        ]
        return any(keyword in text_to_check for keyword in general_keywords)

    def _categorize(self, name: str, description=None) -> list[str]:
        """Categorize an event based on its content."""
        text = f"{name} {description or ''}".lower()
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
