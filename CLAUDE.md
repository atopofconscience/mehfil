# Boston Community Events Aggregator

A website that aggregates events relevant to South Asian and Middle Eastern communities in the Boston area using web scraping.

## Project Overview

- **Goal**: Find and display relevant cultural, community, and social events
- **Method**: Web scraping → Notion database → Web dashboard with map
- **Status**: Fully functional with 6 scrapers and interactive dashboard

## Tech Stack

- Python 3.11+
- BeautifulSoup for scraping
- Notion API for database
- Leaflet.js for interactive map
- GitHub Actions for scheduled runs

## Event Sources

- **Eventbrite** - Search-based scraping for community events
- **Boston Calendar** - Keyword-filtered local events
- **AllEvents.in** - Cultural and community events
- **Meetup** - Community group events (requires JavaScript rendering)
- **ISBCC** - Islamic Society of Boston Cultural Center events
- **University Events** - MIT, Harvard, BU, Northeastern calendars

## Event Categories

- South Asian
- Middle Eastern
- Arts & Crafts
- Food & Markets
- Theater & Film
- Comedy
- Coffee & Chai
- Sports & Outdoors
- Music & Dance
- Talks & Lectures
- Cultural Festival
- Religious
- Community

## Project Structure

```
boston-community-events/
├── main.py                  # Entry point - runs all scrapers
├── notion_db.py             # Notion API wrapper
├── setup_notion_db.py       # Configure Notion database properties
├── export_events.py         # Export events to JSON for dashboard
├── geocode_events.py        # Add map coordinates to events
├── serve_dashboard.py       # Local HTTP server for dashboard
├── scrapers/
│   ├── __init__.py          # Package exports
│   ├── base.py              # Base scraper class + keywords
│   ├── eventbrite.py        # Eventbrite scraper
│   ├── boston_calendar.py   # Boston Calendar scraper
│   ├── allevents.py         # AllEvents.in scraper
│   ├── meetup.py            # Meetup scraper
│   ├── isbcc.py             # ISBCC scraper
│   └── universities.py      # University events scraper
├── dashboard/
│   ├── index.html           # Interactive web dashboard
│   └── events.json          # Exported events data
├── .github/workflows/
│   └── scrape.yml           # Daily scraper action
├── .env.example             # Template for env vars
├── .gitignore
└── requirements.txt
```

## Quick Start

1. Copy `.env.example` to `.env` and add your Notion credentials
2. Run `pip install -r requirements.txt`
3. Run `python setup_notion_db.py` (first time only)
4. Run `python main.py` to scrape events
5. Run `python export_events.py` to export to JSON
6. Run `python geocode_events.py` to add map coordinates
7. Run `python serve_dashboard.py` and open http://localhost:8000

## Dashboard Features

- **Interactive Map**: Events plotted on a Leaflet map of Boston
- **Category Filters**: Filter by South Asian, Middle Eastern, Food, etc.
- **Price Filter**: Show free or paid events
- **Search**: Full-text search across event names and descriptions
- **Responsive**: Works on desktop and mobile

## Environment Variables

- `NOTION_TOKEN` - Notion integration token (secret)
- `NOTION_DATABASE_ID` - Target database ID

## Adding New Scrapers

1. Create a new file in `scrapers/` that extends `BaseScraper`
2. Implement the `scrape()` method returning `List[Event]`
3. Import and add to `scrapers/__init__.py`
4. Add to the scrapers list in `main.py`

## Relevance Filtering

Keywords are defined in `scrapers/base.py`:
- `SOUTH_ASIAN_KEYWORDS` - 35+ terms for South Asian events
- `MIDDLE_EASTERN_KEYWORDS` - 30+ terms for Middle Eastern events
- `CATEGORY_KEYWORDS` - Terms for each event category
