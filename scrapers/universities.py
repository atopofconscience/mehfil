"""Scrapers for Boston area university events using Playwright."""

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


class UniversityEventsScraper(BaseScraper):
    """Scrapes university event calendars for South Asian and Middle Eastern events."""

    SOURCE_NAME = "University Events"

    # University event calendar URLs and their configurations
    UNIVERSITIES = {
        "MIT Events": {
            "url": "https://calendar.mit.edu/search/events?search={term}",
            "base": "https://calendar.mit.edu",
            "location": "MIT Campus, Cambridge, MA",
            "lat": 42.3601,
            "lng": -71.0942,
        },
        "Harvard Events": {
            "url": "https://calendar.college.harvard.edu/search/events?search={term}",
            "base": "https://calendar.college.harvard.edu",
            "location": "Harvard University, Cambridge, MA",
            "lat": 42.3770,
            "lng": -71.1167,
        },
        "BU Events": {
            "url": "https://www.bu.edu/calendar/?s={term}",
            "base": "https://www.bu.edu",
            "location": "Boston University, Boston, MA",
            "lat": 42.3505,
            "lng": -71.1054,
        },
        "Northeastern Events": {
            "url": "https://calendar.northeastern.edu/search/events?search={term}",
            "base": "https://calendar.northeastern.edu",
            "location": "Northeastern University, Boston, MA",
            "lat": 42.3398,
            "lng": -71.0892,
        },
    }

    SEARCH_TERMS = [
        "indian",
        "south asian",
        "desi",
        "bollywood",
        "middle eastern",
        "arab",
        "persian",
        "islamic",
        "cultural",
    ]

    RELEVANCE_KEYWORDS = SOUTH_ASIAN_KEYWORDS + MIDDLE_EASTERN_KEYWORDS

    def scrape(self) -> List[Event]:
        """Scrape university calendars for events using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not installed, skipping University Events")
            return []

        all_events = []
        seen_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = context.new_page()

            for uni_name, uni_info in self.UNIVERSITIES.items():
                try:
                    events = self._scrape_university(page, uni_name, uni_info)
                    for event in events:
                        if event.url not in seen_urls:
                            seen_urls.add(event.url)
                            all_events.append(event)
                except Exception as e:
                    print(f"  Error scraping {uni_name}: {e}")

            browser.close()

        return all_events

    def _scrape_university(self, page, uni_name: str, uni_info: dict) -> List[Event]:
        """Scrape a single university's event calendar."""
        events = []

        for term in self.SEARCH_TERMS:
            try:
                search_url = uni_info['url'].format(term=term.replace(' ', '%20'))
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Scroll to load dynamic content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                event_items = self._find_event_items(soup)

                for item in event_items[:10]:
                    event = self._parse_event_item(item, uni_name, uni_info)
                    if event and self._is_relevant(event):
                        events.append(event)

            except Exception:
                continue

        return events

    def _find_event_items(self, soup: BeautifulSoup):
        """Find event items in the page."""
        # Try various common patterns used by university calendars
        selectors = [
            ("div", "em-card"),
            ("div", "event-card"),
            ("article", "event"),
            ("div", "event"),
            ("li", "event"),
            ("div", "vevent"),
            ("a", "event"),
        ]

        for tag, class_pattern in selectors:
            items = soup.find_all(tag, {"class": lambda c: c and class_pattern in str(c).lower()})
            if items:
                return items

        # Fallback: find any article or div with event-related content
        items = soup.find_all("article")
        if items:
            return items

        return []

    def _parse_event_item(self, item, uni_name: str, uni_info: dict):
        """Parse an event item into an Event object."""
        link = item.find("a", href=True)
        if not link:
            if item.name == "a" and item.get("href"):
                link = item
            else:
                return None

        url = link.get("href", "")
        if not url.startswith("http"):
            url = uni_info["base"] + url

        # Get title
        title_elem = item.find(["h2", "h3", "h4"]) or \
                     item.find("span", {"class": lambda c: c and "title" in str(c).lower()}) or \
                     link
        name = title_elem.get_text(strip=True) if title_elem else ""

        if not name or len(name) < 5:
            return None

        # Clean up name
        name = re.sub(r'\s+', ' ', name).strip()

        # Get date
        date_elem = item.find("time") or \
                    item.find(["span", "div", "p"], {"class": lambda c: c and "date" in str(c).lower()})
        date = datetime.now()
        time_str = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            date, time_str = self._parse_date_time(date_text)

        # Get location - use university default if not found
        location_elem = item.find(["span", "div", "p"], {"class": lambda c: c and "location" in str(c).lower()})
        location = location_elem.get_text(strip=True) if location_elem else uni_info["location"]

        # Get description
        desc_elem = item.find(["p", "div"], {"class": lambda c: c and "description" in str(c).lower()})
        description = desc_elem.get_text(strip=True)[:500] if desc_elem else None

        return Event(
            name=name,
            date=date,
            time=time_str,
            location=location,
            url=url,
            source=uni_name,
            description=description,
            category=self._categorize(name, description),
            latitude=uni_info["lat"],
            longitude=uni_info["lng"],
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
            "%A, %B %d, %Y", "%A, %B %d",
            "%a, %b %d", "%d %b %Y",
            "%a, %b %d, %Y",
        ]

        date_only = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?', '', date_text).strip()
        date_only = re.sub(r'\s+', ' ', date_only).strip(' ,·•-')

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

    def _is_relevant(self, event: Event) -> bool:
        """Check if an event is relevant to our communities."""
        text = f"{event.name} {event.description or ''}".lower()
        return any(keyword in text for keyword in self.RELEVANCE_KEYWORDS)

    def _categorize(self, name: str, description: str = None) -> List[str]:
        """Assign categories based on event content."""
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
