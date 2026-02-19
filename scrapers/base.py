"""Base scraper class that all scrapers inherit from."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Event:
    """Represents a community event."""
    name: str
    date: datetime
    url: str
    source: str
    location: Optional[str] = None      # Venue name
    address: Optional[str] = None       # Full address
    time: Optional[str] = None          # Start time (e.g., "7:00 PM")
    price: Optional[str] = None         # "Free" or "$20" etc.
    description: Optional[str] = None
    category: Optional[List[str]] = None
    latitude: Optional[float] = None    # For map display
    longitude: Optional[float] = None   # For map display


# Expanded keywords for relevance filtering
SOUTH_ASIAN_KEYWORDS = [
    "south asian", "indian", "pakistani", "bengali", "desi", "nepali", "sri lankan",
    "bangladeshi", "afghan", "tamil", "punjabi", "gujarati", "marathi", "telugu",
    "bollywood", "bhangra", "garba", "dandiya", "kathak", "bharatanatyam",
    "holi", "diwali", "navratri", "durga puja", "ganesh", "onam", "pongal", "baisakhi",
    "biryani", "samosa", "chai", "tandoori", "naan", "curry", "masala", "thali",
    "mehndi", "henna", "rangoli", "sari", "saree", "kurta", "salwar",
    "cricket", "kabaddi", "carrom",
]

MIDDLE_EASTERN_KEYWORDS = [
    "middle eastern", "arab", "persian", "iranian", "lebanese", "syrian", "palestinian",
    "egyptian", "moroccan", "turkish", "afghan", "iraqi", "jordanian", "yemeni",
    "eid", "ramadan", "iftar", "nowruz", "norooz",
    "mosque", "masjid", "islamic", "muslim",
    "halal", "falafel", "hummus", "shawarma", "kebab", "kabob", "baklava", "tahini",
    "belly dance", "dabke", "oud", "arabic music",
    "hookah", "shisha", "arabic calligraphy",
]

CATEGORY_KEYWORDS = {
    "Arts & Crafts": ["art", "craft", "painting", "pottery", "calligraphy", "drawing", "sculpture", "gallery", "exhibition", "workshop"],
    "Food & Markets": ["food", "cuisine", "cooking", "restaurant", "market", "bazaar", "tasting", "culinary", "chef", "dining"],
    "Theater & Film": ["theater", "theatre", "film", "movie", "cinema", "play", "drama", "screening", "documentary"],
    "Comedy": ["comedy", "standup", "stand-up", "comedian", "improv", "open mic", "laugh"],
    "Coffee & Chai": ["coffee", "chai", "tea", "cafe", "café", "coffeehouse"],
    "Sports & Outdoors": ["sports", "cricket", "soccer", "basketball", "hiking", "outdoor", "fitness", "yoga", "run", "marathon", "kabaddi"],
    "Music & Dance": ["music", "dance", "concert", "performance", "dj", "live music", "recital", "bhangra", "bollywood", "classical", "qawwali"],
    "Talks & Lectures": ["talk", "lecture", "seminar", "discussion", "panel", "speaker", "conversation", "symposium", "conference", "ama", "fireside"],
    "Cultural Festival": ["festival", "mela", "celebration", "holi", "diwali", "eid", "navratri", "nowruz", "cultural"],
    "Religious": ["religious", "spiritual", "prayer", "temple", "mosque", "church", "meditation", "puja", "namaz"],
    "Career & Tech": ["career", "professional", "intern", "startup", "entrepreneur", "tech", "coding", "aws", "cloud", "ai", "machine learning", "job", "hiring", "resume"],
    "Community": ["community", "meetup", "networking", "social", "gathering"],
}


class BaseScraper(ABC):
    """Base class for all event scrapers."""

    SOURCE_NAME = "Unknown"

    @abstractmethod
    def scrape(self) -> List[Event]:
        """Scrape events and return a list of Event objects."""
        pass
