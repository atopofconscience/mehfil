"""Scraper for The Boston Calendar."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, Event, SOUTH_ASIAN_KEYWORDS, MIDDLE_EASTERN_KEYWORDS, CATEGORY_KEYWORDS


class BostonCalendarScraper(BaseScraper):
    """Scrapes The Boston Calendar for community events."""

    SOURCE_NAME = "Boston Calendar"

    # Use expanded keywords from base
    KEYWORDS = SOUTH_ASIAN_KEYWORDS + MIDDLE_EASTERN_KEYWORDS

    def __init__(self):
        self.base_url = "https://www.thebostoncalendar.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def scrape(self) -> list[Event]:
        """Scrape The Boston Calendar for relevant events."""
        all_events = []
        seen_urls = set()

        # Scrape the main events page and filter for relevant events
        try:
            events = self._scrape_main_page()
            for event in events:
                if event.url not in seen_urls:
                    seen_urls.add(event.url)
                    all_events.append(event)
        except Exception as e:
            print(f"Error scraping Boston Calendar main page: {e}")

        # Also try searching for specific terms - community and general interest
        for keyword in [
            "indian", "middle eastern", "cultural", "south asian", "persian", "arabic",
            "painting", "art class", "pottery", "dance class", "crafts", "workshop",
            "cooking class", "mosaic", "calligraphy", "yoga", "meditation", "world music"
        ]:
            try:
                events = self._search(keyword)
                for event in events:
                    if event.url not in seen_urls:
                        seen_urls.add(event.url)
                        all_events.append(event)
            except Exception as e:
                pass  # Silent fail for search

        return all_events

    def _scrape_main_page(self) -> list[Event]:
        """Scrape the main events listing page."""
        response = requests.get(f"{self.base_url}/events", headers=self.headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        return self._parse_event_list(soup)

    def _search(self, query: str) -> list[Event]:
        """Search for events with a specific query."""
        search_url = f"{self.base_url}/events?search={query}"
        response = requests.get(search_url, headers=self.headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        return self._parse_event_list(soup)

    def _parse_event_list(self, soup: BeautifulSoup) -> list[Event]:
        """Parse a page of events."""
        events = []

        # Find event items - Boston Calendar uses li.event
        event_items = soup.find_all("li", {"class": "event"})

        for item in event_items:
            try:
                event = self._parse_event_item(item)
                if event and self._is_relevant(event):
                    # Only fetch detail page for relevant events (to get price & actual URL)
                    event = self._enrich_event_details(event)
                    events.append(event)
            except Exception as e:
                continue

        return events

    def _parse_event_item(self, item):
        """Parse an event item into an Event object."""
        # Skip pinned listings (they're not real events with dates)
        if item.find("i", class_="fa-thumbtack") or "pinned" in str(item).lower():
            return None

        # Find link in h3
        h3 = item.find("h3")
        if not h3:
            return None

        link = h3.find("a", href=True)
        if not link:
            return None

        detail_url = link.get("href", "")
        if not detail_url.startswith("http"):
            detail_url = self.base_url + detail_url

        # Get title from link text
        name = link.get_text(strip=True)
        if not name:
            return None

        # Skip list/guide articles (not actual events)
        skip_patterns = ["best ", "top ", "things to do", "guide to", "where to"]
        if any(p in name.lower() for p in skip_patterns):
            return None

        # Get date/time from p.time - format: "Sunday, Jan 01, 2023 7:00p"
        time_elem = item.find("p", {"class": "time"})

        # Skip if no date element - these are likely featured listings
        if not time_elem:
            return None

        date_text = time_elem.get_text(strip=True)
        date, time_str = self._parse_date_time(date_text)

        # Skip if date couldn't be parsed or is in the past
        if date <= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            # Check if it's actually today
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if date.date() != today.date():
                return None

        # Get location from p.location
        location_elem = item.find("p", {"class": "location"})
        location = location_elem.get_text(strip=True) if location_elem else "Boston, MA"

        # Create event with Boston Calendar URL first (will be enriched later)
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

    def _enrich_event_details(self, event: Event) -> Event:
        """Fetch detail page to get actual event URL and admission price."""
        event_url, price, description = self._get_event_details(event.url)

        # Update event with enriched data
        if event_url:
            event.url = event_url
        if price:
            event.price = price
        if description:
            event.description = description
            # Re-categorize with description
            event.category = self._categorize(event.name, description)

        return event

    def _get_event_details(self, detail_url: str) -> tuple:
        """Fetch event detail page to get actual event website and admission price."""
        event_url = None
        price = None
        description = None

        try:
            response = requests.get(detail_url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return event_url, price, description

            soup = BeautifulSoup(response.text, "html.parser")

            # Boston Calendar structure: <p><b>Event website:</b><br/> followed by <a href>
            # Find all <b> tags and look for the labels
            for b_tag in soup.find_all("b"):
                label = b_tag.get_text(strip=True).lower()

                # Event website
                if "event website" in label:
                    parent_p = b_tag.find_parent("p")
                    if parent_p:
                        link = parent_p.find("a", href=True)
                        if link:
                            href = link.get("href", "")
                            # Skip Boston Calendar internal links
                            if href and "thebostoncalendar.com" not in href:
                                event_url = href

                # Admission/Price
                if "admission" in label:
                    parent_p = b_tag.find_parent("p")
                    if parent_p:
                        # Get text after the <b> tag
                        full_text = parent_p.get_text(strip=True)
                        if ":" in full_text:
                            price_text = full_text.split(":", 1)[1].strip()
                            # Clean up - remove extra whitespace
                            price_text = " ".join(price_text.split())
                            if price_text:
                                price = price_text[:50]

            # Also look for links in description that point to ticketing sites
            if not event_url:
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    if any(site in href.lower() for site in ["eventbrite", "tickets.", "ticketmaster", "register", "signup"]):
                        if "thebostoncalendar.com" not in href:
                            event_url = href
                            break

            # Clean up price
            if price:
                price = price.replace("\n", " ").strip()
                if "free" in price.lower():
                    price = "Free"
                # Remove any trailing HTML or weird chars
                price = re.sub(r'<[^>]+>', '', price)

            # Get description from event_description div
            desc_elem = soup.find("div", id="event_description")
            if desc_elem:
                description = desc_elem.get_text(strip=True)[:500]

        except Exception as e:
            pass  # Silent fail, return what we have

        return event_url, price, description

    def _parse_date_time(self, date_text: str) -> tuple:
        """Parse date and time from text like 'Sunday, Feb 01, 2026 7:00a'."""
        date = datetime.now()
        time_str = None

        # Extract time (e.g., "7:00p", "10:30a", "7:00pm")
        time_match = re.search(r'(\d{1,2}:\d{2})([ap]m?)', date_text, re.IGNORECASE)
        if time_match:
            hour_min = time_match.group(1)
            ampm = time_match.group(2).lower()
            if ampm.startswith('p'):
                time_str = f"{hour_min} PM"
            else:
                time_str = f"{hour_min} AM"

        # Remove time portion for date parsing
        date_only = re.sub(r'\d{1,2}:\d{2}[ap]m?', '', date_text, flags=re.IGNORECASE).strip()

        # Try various date formats - Boston Calendar uses "Sunday, Feb 01, 2026"
        formats = [
            "%A, %b %d, %Y",   # Sunday, Feb 01, 2026
            "%A, %B %d, %Y",   # Sunday, February 01, 2026
            "%a, %b %d, %Y",   # Sun, Feb 01, 2026
            "%B %d, %Y",       # February 01, 2026
            "%b %d, %Y",       # Feb 01, 2026
            "%A, %b %d",       # Sunday, Feb 01 (no year)
            "%a, %b %d",       # Sun, Feb 01 (no year)
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_only.strip(), fmt)
                # If no year in format, assume current/next year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                    # If date is in past, assume next year
                    if parsed < datetime.now():
                        parsed = parsed.replace(year=datetime.now().year + 1)
                return parsed, time_str
            except ValueError:
                continue

        return datetime.now(), time_str

    def _is_relevant(self, event: Event) -> bool:
        """Check if an event is relevant - community events or arts/crafts/culture."""
        text_to_check = f"{event.name} {event.description or ''}".lower()

        # Community-specific keywords
        if any(keyword in text_to_check for keyword in self.KEYWORDS):
            return True

        # General interest keywords (arts, crafts, dance, culture)
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
