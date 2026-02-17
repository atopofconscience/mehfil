"""Scraper for Meetup.com events using Playwright."""

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


class MeetupScraper(BaseScraper):
    """Scrapes Meetup.com for South Asian and Middle Eastern events in Boston."""

    SOURCE_NAME = "Meetup"

    # Known community groups to scrape directly
    COMMUNITY_GROUPS = [
        "boston-indian-professionals",
        "boston-desi-social",
        "boston-bollywood",
        "boston-south-asian-professionals",
        "boston-young-indian-professionals",
        "persian-boston",
        "boston-arab-community",
        "boston-middle-eastern",
        "boston-cultural-events",
    ]

    def __init__(self):
        self.base_url = "https://www.meetup.com"

    def scrape(self) -> List[Event]:
        """Scrape Meetup for community events using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not installed, skipping Meetup")
            return []

        all_events = []
        seen_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            # Try scraping the Boston events category page
            try:
                events = self._scrape_boston_events(page)
                for event in events:
                    if event.url not in seen_urls:
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception as e:
                print(f"  Error scraping Meetup Boston: {e}")

            # Also try known community groups
            for group in self.COMMUNITY_GROUPS:
                try:
                    events = self._scrape_group(page, group)
                    for event in events:
                        if event.url not in seen_urls:
                            seen_urls.add(event.url)
                            all_events.append(event)
                except Exception as e:
                    continue  # Groups may not exist

            browser.close()

        return all_events

    def _scrape_boston_events(self, page) -> List[Event]:
        """Scrape Boston events from Meetup."""
        events = []

        # Try the Boston city page
        url = f"{self.base_url}/cities/us/ma/boston/"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find event links
        event_links = soup.find_all("a", href=lambda h: h and "/events/" in h)

        for link in event_links[:20]:
            try:
                event = self._parse_event_link(link)
                if event and self._is_relevant(event):
                    events.append(event)
            except Exception:
                continue

        return events

    def _scrape_group(self, page, group_slug: str) -> List[Event]:
        """Scrape events from a specific Meetup group."""
        events = []

        url = f"{self.base_url}/{group_slug}/events/"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        # Check if page loaded successfully (not a 404)
        if "Page not found" in page.content() or "404" in page.title():
            return events

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find event cards
        event_cards = soup.find_all("div", {"class": lambda c: c and "eventCard" in str(c)}) or \
                      soup.find_all("a", href=lambda h: h and "/events/" in h and group_slug in h)

        for card in event_cards[:10]:
            try:
                event = self._parse_event_card(card, group_slug)
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event_link(self, link):
        """Parse an event link into an Event object."""
        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        name = link.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        return Event(
            name=name,
            date=datetime.now(),
            location="Boston, MA",
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name, ""),
        )

    def _parse_event_card(self, card, group_slug: str):
        """Parse an event card into an Event object."""
        if card.name == "a":
            link = card
        else:
            link = card.find("a", href=True)

        if not link:
            return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        # Get title
        title_elem = card.find(["h2", "h3", "span"]) if card.name != "a" else None
        name = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

        if not name or len(name) < 5:
            return None

        # Clean up
        name = re.sub(r'\s+', ' ', name).strip()

        # Get date/time if available
        date_elem = card.find("time")
        date = datetime.now()
        time_str = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            date, time_str = self._parse_date_time(date_text)

        # Determine category from group slug
        categories = self._categorize(name, group_slug)

        return Event(
            name=name,
            date=date,
            time=time_str,
            location="Boston, MA",
            url=url,
            source=self.SOURCE_NAME,
            category=categories,
        )

    def _is_relevant(self, event: Event) -> bool:
        """Check if event is relevant to our communities."""
        text = f"{event.name}".lower()
        return any(kw in text for kw in SOUTH_ASIAN_KEYWORDS + MIDDLE_EASTERN_KEYWORDS)

    def _parse_date_time(self, date_text: str):
        """Parse date and time from text."""
        date = datetime.now()
        time_str = None

        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', date_text)
        if time_match:
            time_str = time_match.group(1).strip()

        formats = [
            "%a, %b %d", "%B %d, %Y", "%b %d, %Y",
            "%A, %B %d", "%m/%d/%Y", "%b %d",
            "%a, %b %d, %Y",
        ]

        date_only = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?', '', date_text).strip()
        date_only = re.sub(r'\s+', ' ', date_only).strip(' ,·•-')

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_only, fmt)
                date = parsed.replace(year=datetime.now().year)
                if date < datetime.now():
                    date = date.replace(year=datetime.now().year + 1)
                break
            except ValueError:
                continue

        return date, time_str

    def _categorize(self, name: str, context: str) -> List[str]:
        """Assign categories based on event content."""
        text = f"{name} {context}".lower()
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
