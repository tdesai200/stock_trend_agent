from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class MacroNewsAgentResult:
    status: str
    confidence_delta: float
    reasons: list[str]
    summary: str
    item_count: int


def _extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


def _fetch_rss_items(feed_url: str, timeout_seconds: int = 8) -> list[dict]:
    try:
        response = requests.get(feed_url, timeout=timeout_seconds)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title:
            continue
        items.append({"title": title, "description": description, "link": link})

    return items


def _score_macro_item(text: str) -> float:
    lowered = text.lower()

    positive_keywords = (
        "cooling inflation",
        "inflation falls",
        "rate cut",
        "soft landing",
        "gdp growth",
        "jobs growth",
        "productivity",
        "consumer spending rises",
    )

    negative_keywords = (
        "inflation rises",
        "rate hike",
        "recession",
        "yield inversion",
        "credit stress",
        "unemployment rises",
        "geopolitical tension",
        "oil spikes",
    )

    score = 0.0
    for phrase in positive_keywords:
        if phrase in lowered:
            score += 1.0

    for phrase in negative_keywords:
        if phrase in lowered:
            score -= 1.0

    return score


def fetch_macro_news_signal(
    source: str,
    trusted_provider_domains: tuple[str, ...],
    feed_urls: tuple[str, ...],
    max_items: int = 15,
) -> MacroNewsAgentResult:
    if source != "yfinance":
        raise ValueError(f"Untrusted or unsupported macro news source={source}")

    collected: list[dict] = []
    for feed_url in feed_urls:
        for item in _fetch_rss_items(feed_url):
            link_domain = _extract_domain(item.get("link", ""))
            if link_domain and link_domain not in trusted_provider_domains:
                continue
            collected.append(item)
            if len(collected) >= max_items:
                break
        if len(collected) >= max_items:
            break

    if not collected:
        return MacroNewsAgentResult(
            status="no_macro_news_data",
            confidence_delta=0.0,
            reasons=["no_macro_news_context"],
            summary="No trusted macro-news context available",
            item_count=0,
        )

    total_score = 0.0
    for item in collected:
        text = f"{item.get('title', '')} {item.get('description', '')}".strip()
        total_score += _score_macro_item(text)

    avg_score = total_score / max(len(collected), 1)
    reasons: list[str] = []
    confidence_delta = 0.0

    if avg_score >= 0.6:
        confidence_delta = 0.04
        reasons.append("macro_tone_supportive")
    elif avg_score <= -0.6:
        confidence_delta = -0.06
        reasons.append("macro_tone_risk_off")
    else:
        reasons.append("macro_tone_neutral")

    return MacroNewsAgentResult(
        status="macro_news_available",
        confidence_delta=round(confidence_delta, 3),
        reasons=reasons,
        summary=f"macro_items={len(collected)}; avg_macro_score={avg_score:.2f}",
        item_count=len(collected),
    )
