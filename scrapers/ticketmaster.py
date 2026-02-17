"""Scraper for Ticketmaster events."""

import re
import requests
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class TicketmasterScraper(BaseScraper):
    """Scrapes Ticketmaster for South Asian and Middle Eastern concerts/shows in Boston."""

    SOURCE_NAME = "Ticketmaster"

    # Artists and search terms popular with South Asian/Middle Eastern audiences
    SEARCH_TERMS = [
        # South Asian artists/terms
        "arijit singh",
        "ar rahman",
        "shreya ghoshal",
        "atif aslam",
        "neha kakkar",
        "badshah",
        "diljit dosanjh",
        "ap dhillon",
        "karan aujla",
        "bollywood",
        "indian",
        "desi",
        "bhangra",
        "punjabi",
        # Middle Eastern artists/terms
        "arabic",
        "persian",
        "lebanese",
        "belly dance",
        # Comedy
        "hasan minhaj",
        "russell peters",
        "vir das",
        "aziz ansari",
        # Cultural
        "qawwali",
        "ghazal",
        "sufi",
    ]

    def __init__(self):
        self.base_url = "https://www.ticketmaster.com"
        self.search_url = "https://www.ticketmaster.com/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Ticketmaster for community events."""
        all_events = []
        seen_urls = set()

        for term in self.SEARCH_TERMS:
            try:
                events = self._search_term(term)
                for event in events:
                    if event.url not in seen_urls:
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception as e:
                print(f"  Error scraping Ticketmaster for '{term}': {e}")

        return all_events

    def _search_term(self, term: str) -> List[Event]:
        """Search for a specific term on Ticketmaster."""
        # Use the discovery API endpoint format
        search_url = f"{self.search_url}?q={term.replace(' ', '+')}&loc=Boston%2C+MA"

        response = requests.get(search_url, headers=self.headers, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        # Find event cards
        event_cards = soup.find_all("div", {"class": lambda c: c and "event" in str(c).lower()}) or \
                      soup.find_all("a", {"class": lambda c: c and "event" in str(c).lower()}) or \
                      soup.find_all("li", {"class": lambda c: c and "result" in str(c).lower()})

        for card in event_cards[:10]:
            try:
                event = self._parse_event_card(card, term)
                if event and self._is_boston_area(event):
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event_card(self, card, search_term: str):
        """Parse an event card into an Event object."""
        link = card.find("a", href=True) if card.name != "a" else card
        if not link:
            return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        # Get title
        title_elem = card.find(["h2", "h3", "span"], {"class": lambda c: c and "title" in str(c).lower()}) or \
                     card.find(["h2", "h3"])
        name = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

        if not name or len(name) < 3:
            return None

        # Get date
        date_elem = card.find(["time", "span", "div"], {"class": lambda c: c and "date" in str(c).lower()})
        date = datetime.now()
        time_str = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            date, time_str = self._parse_date_time(date_text)

        # Get venue/location
        venue_elem = card.find(["span", "div"], {"class": lambda c: c and ("venue" in str(c).lower() or "location" in str(c).lower())})
        location = venue_elem.get_text(strip=True) if venue_elem else "Boston, MA"

        # Get price
        price_elem = card.find(["span", "div"], {"class": lambda c: c and "price" in str(c).lower()})
        price = None
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            match = re.search(r'\$[\d,]+(?:\.\d{2})?', price_text)
            if match:
                price = match.group(0)

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            price=price,
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name, search_term),
        )

    def _is_boston_area(self, event: Event) -> bool:
        """Check if event is in Boston area."""
        if not event.location:
            return True
        location_lower = event.location.lower()
        boston_areas = ["boston", "cambridge", "somerville", "brookline", "newton",
                        "quincy", "medford", "malden", "everett", "chelsea", "ma"]
        return any(area in location_lower for area in boston_areas)

    def _parse_date_time(self, date_text: str):
        """Parse date and time from text."""
        date = datetime.now()
        time_str = None

        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', date_text)
        if time_match:
            time_str = time_match.group(1).strip()

        formats = [
            "%a, %b %d, %Y", "%B %d, %Y", "%b %d, %Y",
            "%m/%d/%Y", "%a %b %d", "%b %d",
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

    def _categorize(self, name: str, search_term: str) -> List[str]:
        """Assign categories based on event content."""
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

        # Default to Music & Dance for Ticketmaster
        if not categories:
            categories = ["Music & Dance"]

        return categories
