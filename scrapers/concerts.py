"""Scrapers for concert/music platforms - Bandsintown, Dice, Songkick."""

import re
import requests
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class BandsintownScraper(BaseScraper):
    """Scrapes Bandsintown for concerts by South Asian and Middle Eastern artists."""

    SOURCE_NAME = "Bandsintown"

    # Artists popular with South Asian/Middle Eastern audiences
    ARTISTS = [
        "arijit-singh",
        "ar-rahman",
        "shreya-ghoshal",
        "atif-aslam",
        "sonu-nigam",
        "neha-kakkar",
        "badshah",
        "diljit-dosanjh",
        "ap-dhillon",
        "karan-aujla",
        "sidhu-moose-wala",
        "guru-randhawa",
        "b-praak",
        "harrdy-sandhu",
        "jubin-nautiyal",
        "armaan-malik",
        "darshan-raval",
        # Comedy
        "hasan-minhaj",
        "russell-peters",
        "vir-das",
        # Middle Eastern
        "fairuz",
        "nancy-ajram",
        "amr-diab",
    ]

    def __init__(self):
        self.base_url = "https://www.bandsintown.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Bandsintown for relevant concerts."""
        all_events = []
        seen_urls = set()

        for artist in self.ARTISTS:
            try:
                events = self._get_artist_events(artist)
                for event in events:
                    if event.url not in seen_urls and self._is_boston_area(event):
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception as e:
                continue

        return all_events

    def _get_artist_events(self, artist_slug: str) -> List[Event]:
        """Get events for a specific artist."""
        url = f"{self.base_url}/a/{artist_slug}"

        response = requests.get(url, headers=self.headers, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        # Find event listings
        event_items = soup.find_all("div", {"class": lambda c: c and "event" in str(c).lower()}) or \
                      soup.find_all("a", href=lambda h: h and "/e/" in str(h))

        artist_name = artist_slug.replace("-", " ").title()

        for item in event_items[:5]:
            try:
                event = self._parse_event(item, artist_name)
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event(self, item, artist_name: str):
        """Parse an event item."""
        link = item.find("a", href=True) if item.name != "a" else item
        if not link:
            return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        # Get venue/location
        venue_elem = item.find(["span", "div"], {"class": lambda c: c and "venue" in str(c).lower()})
        location = venue_elem.get_text(strip=True) if venue_elem else ""

        # Get date
        date_elem = item.find(["time", "span"], {"class": lambda c: c and "date" in str(c).lower()})
        date = datetime.now()
        time_str = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            date, time_str = self._parse_date_time(date_text)

        return Event(
            name=f"{artist_name} Live in Boston",
            date=date,
            time=time_str,
            location=location or "Boston, MA",
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(artist_name),
        )

    def _is_boston_area(self, event: Event) -> bool:
        """Check if event is in Boston area."""
        if not event.location:
            return False
        location_lower = event.location.lower()
        boston_areas = ["boston", "cambridge", "somerville", "brookline", "worcester",
                        "providence", "massachusetts", " ma"]
        return any(area in location_lower for area in boston_areas)

    def _parse_date_time(self, date_text: str):
        """Parse date and time."""
        date = datetime.now()
        time_str = None

        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', date_text, re.IGNORECASE)
        if time_match:
            time_str = time_match.group(1)

        formats = ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%a, %b %d"]
        date_only = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM)?', '', date_text, flags=re.IGNORECASE).strip()

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_only.strip(' ,'), fmt)
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed, time_str
            except ValueError:
                continue

        return date, time_str

    def _categorize(self, artist_name: str) -> List[str]:
        """Categorize based on artist."""
        text = artist_name.lower()
        categories = ["Music & Dance"]

        if any(kw in text for kw in ["minhaj", "peters", "das", "ansari"]):
            categories = ["Comedy"]

        if any(kw in text for kw in SOUTH_ASIAN_KEYWORDS):
            categories.append("South Asian")
        elif any(kw in text for kw in ["fairuz", "nancy", "amr", "arabic"]):
            categories.append("Middle Eastern")
        else:
            # Default South Asian for most artists in our list
            categories.append("South Asian")

        return categories


class DiceScraper(BaseScraper):
    """Scrapes Dice.fm for music events in Boston."""

    SOURCE_NAME = "Dice"

    SEARCH_TERMS = [
        "indian",
        "bollywood",
        "bhangra",
        "desi",
        "arabic",
        "persian",
        "middle eastern",
    ]

    def __init__(self):
        self.base_url = "https://dice.fm"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Dice for relevant events."""
        if not PLAYWRIGHT_AVAILABLE:
            return self._scrape_with_requests()

        all_events = []
        seen_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                # Scrape Boston events page
                page.goto(f"{self.base_url}/city/boston", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                events = self._parse_events(soup)
                for event in events:
                    if event.url not in seen_urls and self._is_relevant(event):
                        seen_urls.add(event.url)
                        all_events.append(event)

            except Exception as e:
                print(f"  Error scraping Dice: {e}")

            browser.close()

        return all_events

    def _scrape_with_requests(self) -> List[Event]:
        """Fallback scraping with requests."""
        events = []

        try:
            response = requests.get(f"{self.base_url}/city/boston", headers=self.headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                events = self._parse_events(soup)
                events = [e for e in events if self._is_relevant(e)]
        except Exception:
            pass

        return events

    def _parse_events(self, soup: BeautifulSoup) -> List[Event]:
        """Parse events from page."""
        events = []

        event_cards = soup.find_all("a", href=lambda h: h and "/event/" in str(h))

        for card in event_cards[:20]:
            try:
                url = card.get("href", "")
                if not url.startswith("http"):
                    url = self.base_url + url

                name = card.get_text(strip=True)
                if not name or len(name) < 5:
                    continue

                events.append(Event(
                    name=name[:100],
                    date=datetime.now(),
                    location="Boston, MA",
                    url=url,
                    source=self.SOURCE_NAME,
                    category=self._categorize(name),
                ))
            except Exception:
                continue

        return events

    def _is_relevant(self, event: Event) -> bool:
        """Check if event is relevant."""
        text = event.name.lower()
        return any(kw in text for kw in SOUTH_ASIAN_KEYWORDS + MIDDLE_EASTERN_KEYWORDS)

    def _categorize(self, name: str) -> List[str]:
        """Categorize event."""
        text = name.lower()
        categories = ["Music & Dance"]

        if any(kw in text for kw in SOUTH_ASIAN_KEYWORDS):
            categories.append("South Asian")
        if any(kw in text for kw in MIDDLE_EASTERN_KEYWORDS):
            categories.append("Middle Eastern")

        return categories
