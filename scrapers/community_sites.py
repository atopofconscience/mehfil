"""Scrapers for community-specific event sites - Sulekha, Google Events, Facebook."""

import re
import json
import requests
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class SulekhaScraper(BaseScraper):
    """Scrapes Sulekha for Indian community events in Boston using structured data."""

    SOURCE_NAME = "Sulekha"

    def __init__(self):
        self.base_url = "https://events.sulekha.com"
        self.boston_url = "https://events.sulekha.com/boston-ma"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Sulekha for Boston area events using JSON-LD structured data."""
        events = []
        seen_urls = set()

        try:
            response = requests.get(self.boston_url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return events

            soup = BeautifulSoup(response.text, "html.parser")

            # Find JSON-LD structured data - this has accurate dates!
            json_ld_scripts = soup.find_all("script", {"type": "application/ld+json"})

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    # Handle both single event and array of events
                    if isinstance(data, list):
                        for item in data:
                            event = self._parse_json_ld(item)
                            if event and event.url not in seen_urls:
                                seen_urls.add(event.url)
                                events.append(event)
                    elif isinstance(data, dict) and data.get("@type") == "Event":
                        event = self._parse_json_ld(data)
                        if event and event.url not in seen_urls:
                            seen_urls.add(event.url)
                            events.append(event)
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"  Error scraping Sulekha: {e}")

        return events

    def _parse_json_ld(self, data: dict) -> Event:
        """Parse JSON-LD event data into Event object."""
        if data.get("@type") != "Event":
            return None

        name = data.get("name", "")
        if not name:
            return None

        url = data.get("url", "")

        # Parse date from ISO format (e.g., "2026-02-20T21:00:00-05:00")
        start_date_str = data.get("startDate", "")
        date = datetime.now()
        time_str = None

        if start_date_str:
            try:
                # Parse ISO format date
                if "T" in start_date_str:
                    dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    date = dt.replace(tzinfo=None)
                    time_str = dt.strftime("%I:%M %p").lstrip("0")
                else:
                    date = datetime.fromisoformat(start_date_str)
            except ValueError:
                pass

        # Get location
        location_data = data.get("location", {})
        location = location_data.get("name", "Boston, MA") if isinstance(location_data, dict) else "Boston, MA"

        # Get address
        address = None
        if isinstance(location_data, dict):
            addr = location_data.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress", ""),
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                    addr.get("postalCode", ""),
                ]
                address = ", ".join(p for p in parts if p)

        # Get coordinates
        lat = None
        lng = None
        if isinstance(location_data, dict):
            geo = location_data.get("geo", {})
            if isinstance(geo, dict):
                lat = geo.get("latitude")
                lng = geo.get("longitude")

        # Get price
        price = None
        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price_val = offers.get("price")
            currency = offers.get("priceCurrency", "USD")
            if price_val:
                price = f"${price_val}" if currency == "USD" else f"{price_val} {currency}"

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            address=address,
            price=price,
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name),
            latitude=float(lat) if lat else None,
            longitude=float(lng) if lng else None,
        )

    def _categorize(self, name: str) -> List[str]:
        """Categorize event - Sulekha is primarily South Asian."""
        text = name.lower()
        categories = ["South Asian"]

        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                if cat not in categories:
                    categories.append(cat)

        return categories


class GoogleEventsScraper(BaseScraper):
    """Scrapes Google Events/Search for community events in Boston."""

    SOURCE_NAME = "Google Events"

    SEARCH_QUERIES = [
        "indian events boston",
        "south asian events boston",
        "bollywood events boston",
        "desi events boston",
        "middle eastern events boston",
        "persian events boston",
        "arabic events boston",
        "holi boston",
        "diwali boston",
        "eid boston",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Google for event results."""
        all_events = []
        seen_urls = set()

        for query in self.SEARCH_QUERIES:
            try:
                events = self._search_query(query)
                for event in events:
                    if event.url not in seen_urls:
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception:
                continue

        return all_events

    def _search_query(self, query: str) -> List[Event]:
        """Search Google for events."""
        # Use Google search with events filter
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&ibp=htl;events"

        response = requests.get(search_url, headers=self.headers, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        # Find event cards in Google's event results
        event_divs = soup.find_all("div", {"data-hveid": True})

        for div in event_divs[:10]:
            try:
                # Look for event-like content
                title_elem = div.find(["h3", "div"], {"role": "heading"})
                if not title_elem:
                    continue

                name = title_elem.get_text(strip=True)
                if not name or len(name) < 5:
                    continue

                # Try to find a link
                link = div.find("a", href=True)
                url = link.get("href", "") if link else ""

                # Try to find date
                date_elem = div.find(["span", "div"], string=re.compile(r'\d{1,2}'))
                date = datetime.now()

                events.append(Event(
                    name=name,
                    date=date,
                    location="Boston, MA",
                    url=url,
                    source=self.SOURCE_NAME,
                    category=self._categorize(name, query),
                ))
            except Exception:
                continue

        return events

    def _categorize(self, name: str, query: str) -> List[str]:
        """Categorize event."""
        text = f"{name} {query}".lower()
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


class FacebookEventsScraper(BaseScraper):
    """
    Facebook Events scraper using Graph API.

    To use this scraper:
    1. Create a Facebook App at https://developers.facebook.com/
    2. Get an access token with user_events permission
    3. Set FACEBOOK_ACCESS_TOKEN in your .env file
    """

    SOURCE_NAME = "Facebook Events"

    def __init__(self):
        import os
        self.access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.graph_url = "https://graph.facebook.com/v18.0"

    def scrape(self) -> List[Event]:
        """Scrape Facebook Events using Graph API."""
        if not self.access_token:
            # Silently skip if no token configured
            return []

        all_events = []
        seen_urls = set()

        # Search for events
        search_terms = ["indian boston", "south asian boston", "desi boston",
                       "middle eastern boston", "persian boston"]

        for term in search_terms:
            try:
                events = self._search_events(term)
                for event in events:
                    if event.url not in seen_urls:
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception as e:
                print(f"  Facebook API error: {e}")
                continue

        return all_events

    def _search_events(self, query: str) -> List[Event]:
        """Search for events using Graph API."""
        url = f"{self.graph_url}/search"
        params = {
            "type": "event",
            "q": query,
            "fields": "id,name,start_time,end_time,place,description,cover,ticket_uri",
            "access_token": self.access_token,
            "limit": 20,
        }

        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return []

        data = response.json()
        events = []

        for item in data.get("data", []):
            try:
                event = self._parse_event(item)
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event(self, data: dict) -> Event:
        """Parse Facebook event data."""
        name = data.get("name", "")
        if not name:
            return None

        event_id = data.get("id")
        url = f"https://www.facebook.com/events/{event_id}" if event_id else ""

        # Parse date
        start_time = data.get("start_time", "")
        date = datetime.now()
        time_str = None

        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                date = dt.replace(tzinfo=None)
                time_str = dt.strftime("%I:%M %p").lstrip("0")
            except ValueError:
                pass

        # Get location
        place = data.get("place", {})
        location = place.get("name", "Boston, MA") if place else "Boston, MA"

        # Get coordinates
        lat = None
        lng = None
        if place and "location" in place:
            loc = place["location"]
            lat = loc.get("latitude")
            lng = loc.get("longitude")

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            url=url,
            source=self.SOURCE_NAME,
            description=data.get("description", "")[:500],
            category=self._categorize(name, data.get("description", "")),
            latitude=lat,
            longitude=lng,
        )

    def _categorize(self, name: str, description: str) -> List[str]:
        """Categorize event."""
        text = f"{name} {description}".lower()
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


class BrownPaperTicketsScraper(BaseScraper):
    """Scrapes Brown Paper Tickets for cultural events."""

    SOURCE_NAME = "Brown Paper Tickets"

    SEARCH_TERMS = ["indian", "bollywood", "south asian", "desi", "middle eastern", "persian"]

    def __init__(self):
        self.base_url = "https://www.brownpapertickets.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> List[Event]:
        """Scrape Brown Paper Tickets for relevant events."""
        all_events = []
        seen_urls = set()

        for term in self.SEARCH_TERMS:
            try:
                events = self._search_term(term)
                for event in events:
                    if event.url not in seen_urls and self._is_boston_area(event):
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception:
                continue

        return all_events

    def _search_term(self, term: str) -> List[Event]:
        """Search for events with a term."""
        search_url = f"{self.base_url}/search?q={term.replace(' ', '+')}"

        response = requests.get(search_url, headers=self.headers, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        event_items = soup.find_all("div", {"class": lambda c: c and "event" in str(c).lower()}) or \
                      soup.find_all("a", href=lambda h: h and "/event/" in str(h))

        for item in event_items[:10]:
            try:
                event = self._parse_event(item, term)
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_event(self, item, search_term: str):
        """Parse an event item."""
        link = item.find("a", href=True) if item.name != "a" else item
        if not link:
            return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = self.base_url + url

        name = link.get_text(strip=True)
        if not name or len(name) < 5:
            title_elem = item.find(["h2", "h3", "h4"])
            name = title_elem.get_text(strip=True) if title_elem else ""

        if not name:
            return None

        location_elem = item.find(["span", "div"], {"class": lambda c: c and "location" in str(c).lower()})
        location = location_elem.get_text(strip=True) if location_elem else ""

        return Event(
            name=name,
            date=datetime.now(),
            location=location or "Boston area",
            url=url,
            source=self.SOURCE_NAME,
            category=self._categorize(name, search_term),
        )

    def _is_boston_area(self, event: Event) -> bool:
        """Check if in Boston area."""
        if not event.location:
            return True
        location_lower = event.location.lower()
        boston_areas = ["boston", "cambridge", "massachusetts", " ma", "somerville", "brookline"]
        return any(area in location_lower for area in boston_areas) or not event.location

    def _categorize(self, name: str, search_term: str) -> List[str]:
        """Categorize event."""
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

        return categories if categories else ["Community"]
