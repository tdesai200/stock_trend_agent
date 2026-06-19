from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests
from requests.exceptions import SSLError
import yfinance as yf

from src.config import DEFAULT_CONFIG
from src.news_filter import NewsCache, filter_articles_with_claude, get_company_info

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except Exception:  # pragma: no cover - optional dependency fallback
    SentimentIntensityAnalyzer = None


POSITIVE_KEYWORDS = (
    "beat",
    "beats",
    "growth",
    "strong",
    "surge",
    "record",
    "upgrade",
    "outperform",
    "partnership",
    "buyback",
)

NEGATIVE_KEYWORDS = (
    "miss",
    "misses",
    "weak",
    "downgrade",
    "lawsuit",
    "probe",
    "decline",
    "warning",
    "recall",
    "cuts",
)

RECENT_NEWS_FALLBACK_DAYS = 15


@dataclass(frozen=True)
class NewsAgentResult:
    sentiment: str
    confidence_delta: float
    trusted_item_count: int
    status: str
    headlines: list[str]
    reasons: list[str]
    source_counts: dict[str, int]


def _extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


def _source_label(provider_domain: str) -> str:
    domain = provider_domain.lower()
    if "yahoo" in domain:
        return "Yahoo Finance"
    if "cnbc" in domain:
        return "CNBC"
    if "reuters" in domain:
        return "Reuters"
    if "marketwatch" in domain or "dowjones" in domain:
        return "MarketWatch"
    if "bloomberg" in domain:
        return "Bloomberg"
    if "wsj" in domain:
        return "WSJ"
    return domain or "Unknown"


def _count_sources(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for content in items:
        provider = content.get("provider", {})
        provider_url = provider.get("url", "")
        provider_domain = _extract_domain(provider_url) if provider_url else ""
        label = _source_label(provider_domain)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _normalize_news_item(title: str, summary: str, link: str, provider_url: str) -> dict:
    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "description": summary.strip(),
        "canonicalUrl": link.strip(),
        "provider": {
            "url": provider_url.strip(),
        },
        "pubDate": datetime.utcnow().isoformat(),
    }


def _extract_rss_items(feed_url: str, timeout_seconds: int = 8) -> list[dict]:
    allow_insecure_ssl = os.getenv("NEWS_ALLOW_INSECURE_SSL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    try:
        response = requests.get(feed_url, timeout=timeout_seconds, headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 403:
            print(
                f"[WARNING] RSS feed blocked with 403 for {feed_url}. "
                "Provider may reject automated RSS requests from this network."
            )
            return []
        print(f"[WARNING] RSS fetch failed for {feed_url}: {exc}")
        return []
    except SSLError as exc:
        if not allow_insecure_ssl:
            print(
                f"[WARNING] RSS SSL validation failed for {feed_url}. "
                "Skipping this feed. Set NEWS_ALLOW_INSECURE_SSL=true only if you trust your network."
            )
            return []

        try:
            response = requests.get(feed_url, timeout=timeout_seconds, verify=False)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            print(f"[WARNING] RSS fetched with SSL verification disabled for {feed_url}")
        except Exception as retry_exc:
            print(f"[WARNING] RSS fetch failed for {feed_url} after insecure retry: {retry_exc}")
            return []
    except Exception as exc:
        print(f"[WARNING] RSS fetch failed for {feed_url}: {exc}")
        return []

    items: list[dict] = []
    channel = root.find("channel")
    if channel is None:
        return items

    feed_provider_domain = _extract_domain(feed_url)
    feed_provider_url = f"https://{feed_provider_domain}" if feed_provider_domain else feed_url

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        summary = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()

        if not title or not link:
            continue

        # Prefer article-link domain as provider so trust filtering reflects the actual publisher.
        link_domain = _extract_domain(link)
        provider_url = f"https://{link_domain}" if link_domain else feed_provider_url

        items.append(_normalize_news_item(title=title, summary=summary, link=link, provider_url=provider_url))

    return items


def _is_article_about_symbol(symbol: str, company_name: str, content: dict) -> bool:
    title = (content.get("title") or "").lower()
    summary = ((content.get("summary") or content.get("description") or "")).lower()
    text = f"{title} {summary}"

    symbol_lower = symbol.lower()
    company_tokens = [token.lower() for token in company_name.split() if len(token) > 2]

    # Strong ticker patterns: $TSLA, (TSLA), or standalone TSLA token.
    ticker_patterns = [f"${symbol_lower}", f"({symbol_lower})", f" {symbol_lower} "]
    if any(pattern in f" {text} " for pattern in ticker_patterns):
        return True

    # Company-name token overlap (requires at least one significant token hit).
    if any(token in text for token in company_tokens[:4]):
        return True

    return False


def _fetch_external_news(symbol: str, company_name: str) -> list[dict]:
    if not DEFAULT_CONFIG.external_news_enabled:
        return []

    external_items: list[dict] = []
    for feed_url in DEFAULT_CONFIG.external_news_rss_feeds:
        external_items.extend(_extract_rss_items(feed_url))

    filtered = [item for item in external_items if _is_article_about_symbol(symbol, company_name, item)]
    return filtered


def _score_text(text: str) -> int:
    lowered = text.lower()
    positive_hits = sum(keyword in lowered for keyword in POSITIVE_KEYWORDS)
    negative_hits = sum(keyword in lowered for keyword in NEGATIVE_KEYWORDS)
    return positive_hits - negative_hits


def _score_text_nlp(text: str) -> float | None:
    if SentimentIntensityAnalyzer is None:
        return None

    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    return float(scores.get("compound", 0.0))


def _build_news_result(items: list[dict], reason_prefix: str) -> NewsAgentResult:
    source_counts = _count_sources(items)

    lexical_score = 0
    nlp_scores: list[float] = []
    headlines = []
    for content in items:
        title = content.get("title", "")
        summary = content.get("summary") or content.get("description") or ""
        headlines.append(title)
        combined_text = f"{title} {summary}".strip()
        lexical_score += _score_text(combined_text)

        nlp_score = _score_text_nlp(combined_text)
        if nlp_score is not None:
            nlp_scores.append(nlp_score)

    if nlp_scores:
        avg_nlp = sum(nlp_scores) / len(nlp_scores)

        if avg_nlp >= 0.10:
            return NewsAgentResult(
                sentiment="positive",
                confidence_delta=0.06,
                trusted_item_count=len(items),
                status="trusted_news_available",
                headlines=headlines,
                reasons=[f"{reason_prefix}_nlp_positive"],
                source_counts=source_counts,
            )

        if avg_nlp <= -0.10:
            return NewsAgentResult(
                sentiment="negative",
                confidence_delta=-0.14,
                trusted_item_count=len(items),
                status="trusted_news_available",
                headlines=headlines,
                reasons=[f"{reason_prefix}_nlp_negative"],
                source_counts=source_counts,
            )

        return NewsAgentResult(
            sentiment="neutral",
            confidence_delta=0.0,
            trusted_item_count=len(items),
            status="trusted_news_available",
            headlines=headlines,
            reasons=[f"{reason_prefix}_nlp_neutral"],
            source_counts=source_counts,
        )

    if lexical_score > 0:
        return NewsAgentResult(
            sentiment="positive",
            confidence_delta=0.05,
            trusted_item_count=len(items),
            status="trusted_news_available",
            headlines=headlines,
            reasons=[f"{reason_prefix}_lexical_positive"],
            source_counts=source_counts,
        )

    if lexical_score < 0:
        return NewsAgentResult(
            sentiment="negative",
            confidence_delta=-0.12,
            trusted_item_count=len(items),
            status="trusted_news_available",
            headlines=headlines,
            reasons=[f"{reason_prefix}_lexical_negative"],
            source_counts=source_counts,
        )

    return NewsAgentResult(
        sentiment="neutral",
        confidence_delta=0.0,
        trusted_item_count=len(items),
        status="trusted_news_available",
        headlines=headlines,
        reasons=[f"{reason_prefix}_lexical_neutral"],
        source_counts=source_counts,
    )


def fetch_company_news(
    symbol: str,
    source: str,
    trusted_provider_domains: tuple[str, ...],
    max_items: int = 5,
    use_claude_filter: bool = True,
) -> NewsAgentResult:
    recent_cached_items = NewsCache().get_recent(symbol, max_age_days=RECENT_NEWS_FALLBACK_DAYS)
    recent_cached_items = [
        content
        for content in recent_cached_items
        if _extract_domain((content.get("provider") or {}).get("url", "")) in trusted_provider_domains
    ][:max_items]

    if source != "yfinance":
        raise ValueError(f"Untrusted or unsupported news source={source}")

    try:
        ticker_obj = yf.Ticker(symbol)
        raw_news = ticker_obj.news or []
    except Exception:
        if recent_cached_items:
            return _build_news_result(recent_cached_items, "cached_recent_company_news")

        return NewsAgentResult(
            sentiment="unknown",
            confidence_delta=0.0,
            trusted_item_count=0,
            status="no_trusted_news",
            headlines=[],
            reasons=["company_news_fetch_failed"],
            source_counts={},
        )

    company_name, _sector = get_company_info(symbol)
    external_news = _fetch_external_news(symbol=symbol, company_name=company_name)

    # Normalize yfinance payload to same content structure as external RSS items.
    normalized_yf_content: list[dict] = []
    for item in raw_news:
        content = item.get("content", {})
        if content:
            normalized_yf_content.append(content)

    # Merge source streams (yfinance + external RSS) before trust/domain filtering.
    merged_items = normalized_yf_content + external_news
    trusted_items = []

    for content in merged_items:
        provider = content.get("provider", {})
        provider_url = provider.get("url", "")
        provider_domain = _extract_domain(provider_url) if provider_url else ""

        if provider_domain not in trusted_provider_domains:
            continue

        trusted_items.append(content)

        if len(trusted_items) >= max_items:
            break

    if not trusted_items:
        if recent_cached_items:
            return _build_news_result(recent_cached_items, "cached_recent_company_news")

        return NewsAgentResult(
            sentiment="unknown",
            confidence_delta=0.0,
            trusted_item_count=0,
            status="no_trusted_news",
            headlines=[],
            reasons=["no_trusted_company_news_items"],
            source_counts={},
        )

    # Apply Claude relevance filter if enabled
    if use_claude_filter:
        try:
            company_name, sector = get_company_info(symbol)
            filtered_items, filter_status = filter_articles_with_claude(
                ticker=symbol,
                company_name=company_name,
                sector=sector,
                raw_articles=trusted_items,
                use_cache=True,
            )
            # Log filter status for debugging
            if filter_status != "cache_hit":
                print(f"[INFO] {symbol} news filter: {filter_status}")

            if filter_status == "claude_no_relevant_articles":
                return NewsAgentResult(
                    sentiment="unknown",
                    confidence_delta=0.0,
                    trusted_item_count=0,
                    status="no_relevant_news",
                    headlines=[],
                    reasons=["no_relevant_company_news_items"],
                    source_counts={},
                )

            trusted_items = filtered_items
        except Exception as e:
            print(f"[WARNING] Claude filtering failed for {symbol}, using all trusted articles: {e}")
            # Continue with unfiltered trusted items

    if not trusted_items:
        return NewsAgentResult(
            sentiment="unknown",
            confidence_delta=0.0,
            trusted_item_count=0,
            status="no_relevant_news",
            headlines=[],
            reasons=["no_relevant_company_news_items"],
            source_counts={},
        )

    return _build_news_result(trusted_items, "trusted_company_news")