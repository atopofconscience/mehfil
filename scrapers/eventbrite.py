"""Scraper for Eventbrite events using Playwright for browser automation."""

import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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

    def scrape(self) -> List[Event]:
        """Scrape Eventbrite using Playwright browser automation."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not available, skipping Eventbrite")
            return []

        all_events = []
        seen_urls = set()

        try:
            with sync_playwright() as p:
                # Launch with additional args to avoid detection
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                )
                page = context.new_page()

                # Hide webdriver property
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)

                for term in self.SEARCH_TERMS:
                    try:
                        events = self._search_term_playwright(page, term)
                        for event in events:
                            if event.url not in seen_urls:
                                seen_urls.add(event.url)
                                all_events.append(event)
                    except Exception as e:
                        print(f"    Error scraping '{term}': {e}")
                        continue

                browser.close()
        except Exception as e:
            print(f"  Playwright error: {e}")

        return all_events

    def _search_term_playwright(self, page, term: str) -> List[Event]:
        """Search for a specific term using Playwright."""
        search_url = f"{self.base_url}/{term}/"

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)  # Wait longer for dynamic content
        except Exception as e:
            print(f"    Failed to load page for '{term}': {e}")
            return []

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        events = []

        # Extract JSON-LD structured data
        scripts = soup.find_all("script", {"type": "application/ld+json"})

        if not scripts:
            # Debug: check page title to see if we got blocked
            title = soup.find("title")
            title_text = title.get_text() if title else "No title"
            if "just a moment" in title_text.lower() or "blocked" in title_text.lower():
                print(f"    Blocked by Cloudflare for '{term}'")
            return []

        for script in scripts:
            try:
                script_content = script.string or script.get_text()
                if not script_content:
                    continue

                data = json.loads(script_content)

                # Handle itemList format
                if isinstance(data, dict) and "itemListElement" in data:
                    for item in data["itemListElement"]:
                        event_data = item.get("item", {})
                        if event_data.get("@type") == "Event":
                            event = self._parse_json_ld(event_data, term)
                            if event:
                                events.append(event)

                # Handle single event
                elif isinstance(data, dict) and data.get("@type") == "Event":
                    event = self._parse_json_ld(data, term)
                    if event:
                        events.append(event)

            except json.JSONDecodeError as e:
                continue
            except Exception as e:
                continue

        return events

    def _parse_json_ld(self, data: dict, search_term: str) -> Event:
        """Parse JSON-LD event data into Event object."""
        name = data.get("name", "")
        if not name:
            return None

        url = data.get("url", "")

        # Parse date and time
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
