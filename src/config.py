from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class AppConfig:
    symbols: List[str]
    market_data_source: str = "yfinance"
    trusted_data_sources: tuple[str, ...] = ("yfinance",)
    news_data_source: str = "yfinance"
    macro_news_data_source: str = "yfinance"
    earnings_data_source: str = "yfinance"
    fundamentals_data_source: str = "yfinance"
    trusted_news_provider_domains: tuple[str, ...] = (
        "finance.yahoo.com",
        "reuters.com",
        "reutersagency.com",
        "bloomberg.com",
        "wsj.com",
        "cnbc.com",
        "marketwatch.com",
        "feeds.content.dowjones.io",
    )
    external_news_enabled: bool = True
    external_news_rss_feeds: tuple[str, ...] = (
        "https://www.cnbc.com/id/15839069/device/rss/rss.html",
        "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    )
    required_decision_domains: tuple[str, ...] = (
        "technicals",
        "macro_news",
        "earnings",
        "fundamentals",
        "company_news",
    )
    enforce_full_decision_context: bool = False
    chat_enabled: bool = True
    max_questions_per_session: int = 10
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")


DEFAULT_CONFIG = AppConfig(
    symbols=["AAPL", "MSFT", "NVDA", "AMZN", "MU"],
)
