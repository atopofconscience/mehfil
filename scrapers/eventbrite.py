"""Scraper for Eventbrite events using JSON-LD structured data."""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class EventbriteScraper(BaseScraper):
    """Scrapes Eventbrite for South Asian and Middle Eastern events in Boston."""

    SOURCE_NAME = "Eventbrite"

    # Community-specific search terms (internal use)
    COMMUNITY_SEARCH_TERMS = [
        "indian",
        "south-asian",
        "pakistani",
        "bengali",
        "desi",
        "middle-eastern",
        "arab",
        "persian",
        "bollywood",
        "holi",
        "diwali",
        "eid",
        "iftar",
        "nowruz",
    ]

    # General interest search terms
    GENERAL_SEARCH_TERMS = [
        "painting-class",
        "art-workshop",
        "pottery",
        "dance-class",
        "crafts",
        "drawing",
        "mosaic",
        "calligraphy",
        "cultural",
        "world-music",
        "international",
        "asian",
        "global-cuisine",
        "cooking-class",
        "meditation",
        "yoga",
        "mindfulness",
    ]

    SEARCH_TERMS = COMMUNITY_SEARCH_TERMS + GENERAL_SEARCH_TERMS

    def __init__(self):
        self.base_url = "https://www.eventbrite.com/d/ma--boston"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def scrape(self) -> List[Event]:
        """Scrape Eventbrite using JSON-LD structured data."""
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
                print(f"  Error scraping Eventbrite for '{term}': {e}")

        return all_events

    def _search_term(self, term: str) -> List[Event]:
        """Search for a specific term on Eventbrite."""
        search_url = f"{self.base_url}/{term}/"
        response = requests.get(search_url, headers=self.headers, timeout=15)

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        # Extract JSON-LD structured data
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string)

                # Handle itemList format
                if isinstance(data, dict) and "itemListElement" in data:
                    for item in data["itemListElement"]:
                        event_data = item.get("item", {})
                        if event_data.get("@type") == "Event":
                            event = self._parse_json_ld(event_data, term)
                            if event:
                                # Fetch individual event page to get accurate time
                                event = self._enrich_with_time(event)
                                events.append(event)

                # Handle single event
                elif isinstance(data, dict) and data.get("@type") == "Event":
                    event = self._parse_json_ld(data, term)
                    if event:
                        events.append(event)

            except json.JSONDecodeError:
                continue

        return events

    def _enrich_with_time(self, event: Event) -> Event:
        """Fetch individual event page to get accurate time."""
        if event.time:  # Already has time
            return event

        try:
            response = requests.get(event.url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return event

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for JSON-LD with full datetime
            # Eventbrite uses various @type values: Event, EducationEvent, MusicEvent, etc.
            event_types = ["Event", "EducationEvent", "MusicEvent", "SocialEvent", "BusinessEvent", "SportsEvent"]

            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") in event_types:
                        start_date_str = data.get("startDate", "")
                        if "T" in start_date_str:
                            dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                            event.time = dt.strftime("%I:%M %p").lstrip("0")
                            break
                except (json.JSONDecodeError, ValueError):
                    continue

        except Exception:
            pass  # Keep event without time

        return event

    def _parse_json_ld(self, data: dict, search_term: str) -> Event:
        """Parse JSON-LD event data into Event object."""
        name = data.get("name", "")
        if not name:
            return None

        url = data.get("url", "")

        # Parse date
        start_date_str = data.get("startDate", "")
        date = datetime.now()
        time_str = None

        if start_date_str:
            try:
                if "T" in start_date_str:
                    dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    date = dt.replace(tzinfo=None)
                    time_str = dt.strftime("%I:%M %p").lstrip("0")
                else:
                    date = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Get location
        location_data = data.get("location", {})
        location = location_data.get("name", "Boston, MA") if isinstance(location_data, dict) else "Boston, MA"

        # Get address and coordinates
        address = None
        lat = None
        lng = None

        if isinstance(location_data, dict):
            addr = location_data.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress", ""),
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                ]
                address = ", ".join(p for p in parts if p)

            geo = location_data.get("geo", {})
            if isinstance(geo, dict):
                lat = geo.get("latitude")
                lng = geo.get("longitude")
                if lat:
                    lat = float(lat)
                if lng:
                    lng = float(lng)

        # Get description
        description = data.get("description", "")[:500] if data.get("description") else None

        # Get price from offers
        price = None
        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price_val = offers.get("price")
            price_currency = offers.get("priceCurrency", "USD")
            if price_val is not None:
                if price_val == 0 or str(price_val) == "0":
                    price = "Free"
                else:
                    price = f"${price_val}" if price_currency == "USD" else f"{price_val} {price_currency}"
            # Check lowPrice/highPrice for range
            low = offers.get("lowPrice")
            high = offers.get("highPrice")
            if low is not None and high is not None:
                if low == 0 and high == 0:
                    price = "Free"
                elif low == 0:
                    price = f"Free - ${high}"
                else:
                    price = f"${low} - ${high}"
            elif low is not None:
                price = f"From ${low}" if low > 0 else "Free"
        elif isinstance(offers, list) and len(offers) > 0:
            # Multiple ticket types - get price range
            prices = []
            for offer in offers:
                if isinstance(offer, dict):
                    p = offer.get("price")
                    if p is not None:
                        prices.append(float(p))
            if prices:
                min_p, max_p = min(prices), max(prices)
                if min_p == 0 and max_p == 0:
                    price = "Free"
                elif min_p == 0:
                    price = f"Free - ${max_p:.0f}"
                elif min_p == max_p:
                    price = f"${min_p:.0f}"
                else:
                    price = f"${min_p:.0f} - ${max_p:.0f}"

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            address=address,
            url=url,
            price=price,
            source=self.SOURCE_NAME,
            description=description,
            category=self._categorize(name, search_term),
            latitude=lat,
            longitude=lng,
        )

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

        return categories if categories else ["Community"]
