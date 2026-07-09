from shortube.discovery.sources.hacker_news import HackerNewsSource
from shortube.discovery.sources.reddit import RedditSource
from shortube.discovery.sources.rss import RSSSource
from shortube.discovery.sources.web_scraper import WebScraperSource
from shortube.discovery.sources.youtube_search import YouTubeSearchSource

ALL_SOURCES = {
    "hacker_news": HackerNewsSource,
    "reddit": RedditSource,
    "rss": RSSSource,
    "web_scraper": WebScraperSource,
    "youtube_search": YouTubeSearchSource,
}

__all__ = [
    "ALL_SOURCES",
    "HackerNewsSource",
    "RedditSource",
    "RSSSource",
    "WebScraperSource",
    "YouTubeSearchSource",
]
