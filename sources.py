from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSource:
    name: str
    url: str
    language: str
    category: str
    trust_score: float = 1.0
    enabled: bool = True


RSS_SOURCES: list[NewsSource] = [
    NewsSource("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "en", "ai", 0.88),
    NewsSource("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "en", "ai", 0.82),
    NewsSource("MIT Technology Review", "https://www.technologyreview.com/feed/", "en", "technology", 0.92),
    NewsSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "en", "technology", 0.86, enabled=False),
    NewsSource("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "en", "ai", 0.82),
    NewsSource("Wired", "https://www.wired.com/feed/rss", "en", "technology", 0.9),
    NewsSource("The Decoder", "https://the-decoder.com/feed/", "en", "ai", 0.88),
    NewsSource("TensorFeed", "https://tensorfeed.ai/feed.xml", "en", "ai", 0.78, enabled=False),
    NewsSource("Planet AI", "https://www.planet-ai.net/rss.xml", "en", "ai", 0.76, enabled=False),
    NewsSource("OnAI", "https://onai2.com/rss.xml", "en", "ai", 0.76, enabled=False),
    NewsSource("InfoQ AI", "https://feed.infoq.com/artificial_intelligence/news", "en", "ai", 0.82, enabled=False),
    NewsSource("Google AI Blog", "https://blog.google/technology/ai/rss/", "en", "ai", 0.92),
    NewsSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "en", "ai", 0.86, enabled=False),
    NewsSource("Product Hunt", "https://www.producthunt.com/feed", "en", "ai", 0.78, enabled=False),
    NewsSource("Smashing Magazine", "https://www.smashingmagazine.com/feed/", "en", "web_design", 0.86, enabled=False),
    NewsSource("UX Collective", "https://uxdesign.cc/feed", "en", "web_design", 0.58, enabled=False),
    NewsSource("Webflow Blog", "https://webflow.com/blog/rss.xml", "en", "web_design", 0.82, enabled=False),
    NewsSource("CSS-Tricks", "https://css-tricks.com/feed/", "en", "frontend", 0.82, enabled=False),
    NewsSource("Simon Willison", "https://simonwillison.net/atom/everything/", "en", "ai", 0.84, enabled=False),
    NewsSource("A List Apart", "https://alistapart.com/main/feed/", "en", "web_design", 0.82, enabled=False),
    NewsSource("Search Engine Land", "https://searchengineland.com/feed", "en", "marketing", 0.72, enabled=False),
    NewsSource("Search Engine Journal", "https://www.searchenginejournal.com/feed/", "en", "marketing", 0.82, enabled=False),
    NewsSource("Marketing AI Institute", "https://www.marketingaiinstitute.com/blog/rss.xml", "en", "marketing_ai", 0.84, enabled=False),
    NewsSource("HubSpot Marketing", "https://blog.hubspot.com/marketing/rss.xml", "en", "marketing", 0.78, enabled=False),
    NewsSource("IEEE Spectrum Robotics", "https://spectrum.ieee.org/rss/robotics/fulltext", "en", "robotics", 0.9, enabled=False),
    NewsSource("ScienceDaily Robotics", "https://www.sciencedaily.com/rss/computers_math/robotics.xml", "en", "robotics", 0.68, enabled=False),
    NewsSource("MarkTechPost", "https://www.marktechpost.com/feed/", "en", "ai", 0.62, enabled=False),
    NewsSource("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "en", "ai", 0.95),
    NewsSource("OpenAI Blog", "https://openai.com/news/rss.xml", "en", "ai", 0.96),
    NewsSource("Anthropic News", "https://www.anthropic.com/news/rss.xml", "en", "ai", 0.94),
    NewsSource("NVIDIA Blog", "https://blogs.nvidia.com/feed/", "en", "technology", 0.88),
    NewsSource("Heise Online", "https://www.heise.de/rss/heise-atom.xml", "de", "technology", 0.84, enabled=False),
    NewsSource("Golem.de", "https://rss.golem.de/rss.php?feed=RSS2.0", "de", "technology", 0.82, enabled=False),
    NewsSource("t3n", "https://t3n.de/feed/", "de", "technology", 0.78, enabled=False),
    NewsSource("OMR", "https://omr.com/de/feed", "de", "marketing", 0.8, enabled=False),
    NewsSource("ComputerBase", "https://www.computerbase.de/rss/news.xml", "de", "technology", 0.8, enabled=False),
    NewsSource("Habr AI", "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/", "ru", "ai", 0.78, enabled=False),
    NewsSource("Habr Robotics", "https://habr.com/ru/rss/hubs/robotics/articles/", "ru", "robotics", 0.76, enabled=False),
    NewsSource("3DNews", "https://3dnews.ru/news/rss/", "ru", "technology", 0.76, enabled=False),
    NewsSource("iXBT", "https://www.ixbt.com/export/news.rss", "ru", "technology", 0.72, enabled=False),
    NewsSource("N+1", "https://nplus1.ru/rss", "ru", "science_tech", 0.82, enabled=False),
    NewsSource("vc.ru", "https://vc.ru/rss/all", "ru", "technology", 0.68, enabled=False),
    # Chinese and Hebrew RSS feeds can be added here later without changing main.py.
    # Example:
    # NewsSource("Example Chinese AI Feed", "https://example.com/rss", "zh", "ai", 0.7, enabled=False),
    # NewsSource("Example Hebrew Tech Feed", "https://example.com/rss", "he", "technology", 0.7, enabled=False),
]


def get_sources(enabled_only: bool = True) -> list[NewsSource]:
    if enabled_only:
        return [source for source in RSS_SOURCES if source.enabled]
    return list(RSS_SOURCES)
