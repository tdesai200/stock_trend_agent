"""Claude-based news relevance filter with caching and fallback guardrails."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

import anthropic


_STATUS_PROBE_CACHE: dict[str, object] = {
    "checked_at": 0.0,
    "reachable": False,
    "error": "",
}
_STATUS_PROBE_TTL_SECONDS = int(os.getenv("CLAUDE_STATUS_PROBE_TTL_SECONDS", "300"))


def _get_anthropic_api_key() -> str:
    """Read Anthropic API key from the runtime environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if len(api_key) >= 2 and api_key[0] == api_key[-1] and api_key[0] in {"'", '"'}:
        api_key = api_key[1:-1].strip()
    return api_key


class NewsFilterGuardrails:
    """Guardrails for Claude-based news filtering."""

    RELEVANCE_THRESHOLD = float(os.getenv("NEWS_FILTER_RELEVANCE_THRESHOLD", "0.7"))
    MAX_ARTICLES_INPUT = int(os.getenv("NEWS_FILTER_MAX_ARTICLES_INPUT", "10"))
    MAX_ARTICLES_OUTPUT = int(os.getenv("NEWS_FILTER_MAX_ARTICLES_OUTPUT", "5"))
    CACHE_TTL_HOURS = int(os.getenv("NEWS_FILTER_CACHE_TTL_HOURS", "24"))
    TIMEOUT_SECONDS = int(os.getenv("NEWS_FILTER_TIMEOUT_SECONDS", "30"))
    FALLBACK_ON_ERROR = True
    ANTHROPIC_MODEL_PRIMARY = os.getenv("ANTHROPIC_MODEL", "")
    ANTHROPIC_MODEL_FALLBACKS = (
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "claude-fable-5",
        "claude-opus-4-8",
    )
    MODEL_DISCOVERY_LIMIT = int(os.getenv("ANTHROPIC_MODEL_DISCOVERY_LIMIT", "20"))
    MODEL_FAMILY_PREFERENCE = tuple(
        token.strip().lower()
        for token in os.getenv("ANTHROPIC_MODEL_FAMILY_PREFERENCE", "haiku,sonnet,fable,opus").split(",")
        if token.strip()
    )


class NewsCache:
    """Persistent JSON cache for filtered news with TTL."""

    def __init__(self, cache_path: str = "data/news_cache.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache from JSON file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save cache to JSON file."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._cache, f, indent=2, default=str)
        except Exception as e:
            print(f"[WARNING] Could not save news cache: {e}")

    def get(self, ticker: str) -> Optional[dict]:
        """Get cached filtered articles for ticker if fresh."""
        if ticker not in self._cache:
            return None

        cached_entry = self._cache[ticker]
        timestamp = cached_entry.get("timestamp")
        if not timestamp:
            return None

        cached_time = datetime.fromisoformat(timestamp)
        now = datetime.now()
        age_hours = (now - cached_time).total_seconds() / 3600

        if age_hours > NewsFilterGuardrails.CACHE_TTL_HOURS:
            # Cache expired; remove it
            del self._cache[ticker]
            self._save_cache()
            return None

        return cached_entry.get("articles")

    def get_recent(self, ticker: str, max_age_days: int) -> list[dict]:
        """Get cached articles whose pubDate is within the requested recent window."""
        cached_entry = self._cache.get(ticker, {})
        cached_articles = cached_entry.get("articles", [])
        if not cached_articles:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        recent_articles: list[dict] = []

        for article in cached_articles:
            raw_pub_date = str(article.get("pubDate") or "").strip()
            if not raw_pub_date:
                continue

            normalized_pub_date = raw_pub_date[:-1] + "+00:00" if raw_pub_date.endswith("Z") else raw_pub_date
            try:
                published_at = datetime.fromisoformat(normalized_pub_date)
            except ValueError:
                continue

            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            else:
                published_at = published_at.astimezone(timezone.utc)

            if published_at >= cutoff:
                recent_articles.append(article)

        return recent_articles

    def set(self, ticker: str, articles: list[dict]) -> None:
        """Store filtered articles in cache."""
        self._cache[ticker] = {
            "timestamp": datetime.now().isoformat(),
            "articles": articles,
        }
        self._save_cache()


def _build_claude_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    raw_articles: list[dict],
) -> str:
    """Build few-shot prompt for Claude to filter articles."""
    articles_text = "\n".join(
        [
            f"{i+1}. Headline: {art['title']}\n   Summary: {art.get('summary', '')}"
            for i, art in enumerate(raw_articles[:NewsFilterGuardrails.MAX_ARTICLES_INPUT])
        ]
    )

    return f"""You are a financial news relevance expert. Your task is to identify which news articles are relevant to a specific company's stock.

Given:
- Ticker: {ticker}
- Company: {company_name}
- Sector: {sector}

Rate each article's relevance (0.0 to 1.0) to this company's stock performance and fundamentals:
- 0.9-1.0: Direct company-specific news (earnings, product launch, CEO change, regulatory)
- 0.6-0.8: Relevant sector/industry trends affecting this company
- 0.3-0.5: Tangential (supply chain, macro, competitor news)
- 0.0-0.2: Unrelated (other companies, general market news)

Articles to evaluate:
{articles_text}

Respond ONLY with valid JSON (no markdown, no explanation):
[
  {{"headline_index": 1, "title": "...", "relevance_score": 0.95, "reason": "..."}},
  {{"headline_index": 2, "title": "...", "relevance_score": 0.4, "reason": "..."}}
]

Filter to only articles with relevance_score >= {NewsFilterGuardrails.RELEVANCE_THRESHOLD}.
If no articles meet the threshold, return an empty array [].
"""


def _discover_model_candidates(client: anthropic.Anthropic) -> list[str]:
    model_candidates: list[str] = []

    configured_primary = NewsFilterGuardrails.ANTHROPIC_MODEL_PRIMARY.strip()
    if configured_primary:
        model_candidates.append(configured_primary)

    discovered_ids: list[str] = []
    try:
        page = client.models.list(limit=NewsFilterGuardrails.MODEL_DISCOVERY_LIMIT)
        for model_info in page.data:
            model_id = str(getattr(model_info, "id", "")).strip()
            if model_id:
                discovered_ids.append(model_id)
    except Exception as exc:
        print(f"[WARNING] Could not discover Anthropic models dynamically: {exc}")

    if discovered_ids:
        for family in NewsFilterGuardrails.MODEL_FAMILY_PREFERENCE:
            for model_id in discovered_ids:
                lowered = model_id.lower()
                if family in lowered and model_id not in model_candidates:
                    model_candidates.append(model_id)

        for model_id in discovered_ids:
            if model_id not in model_candidates:
                model_candidates.append(model_id)

    for fallback_model in NewsFilterGuardrails.ANTHROPIC_MODEL_FALLBACKS:
        if fallback_model not in model_candidates:
            model_candidates.append(fallback_model)

    return model_candidates


def _extract_json_payload(text: str) -> str | None:
    """Extract a JSON array/object payload from mixed text output."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    # Handle markdown code fences first.
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    # Try to find a top-level JSON array.
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]

    # Fall back to top-level JSON object if array is absent.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]

    return None


def _parse_filtered_response(response_text: str) -> list[dict] | None:
    """Parse model response into list[dict], returning None if not parseable."""
    payload = _extract_json_payload(response_text)
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        # Support wrappers like {"items": [...]} from some model responses.
        items = parsed.get("items")
        if isinstance(items, list):
            return items

    return None


def filter_articles_with_claude(
    ticker: str,
    company_name: str,
    sector: str,
    raw_articles: list[dict],
    use_cache: bool = True,
) -> tuple[list[dict], str]:
    """
    Filter articles using Claude for relevance.

    Returns:
        (filtered_articles, status)
        status: "claude_filtered" | "cache_hit" | "claude_failed_valdier_fallback" | "no_articles"
    """
    cache = NewsCache()

    # Try cache first
    if use_cache:
        cached = cache.get(ticker)
        if cached is not None:
            return cached, "cache_hit"

    if not raw_articles:
        return [], "no_articles"

    # Call Claude
    api_key = _get_anthropic_api_key()
    if not api_key:
        return raw_articles, "claude_failed_no_api_key"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_claude_prompt(ticker, company_name, sector, raw_articles)

        # Discover available models for this account and try preferred families first.
        model_candidates = _discover_model_candidates(client)

        message = None
        active_model = None
        last_api_error: Exception | None = None

        for model_name in model_candidates:
            try:
                message = client.messages.create(
                    model=model_name,
                    max_tokens=1024,
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                    timeout=NewsFilterGuardrails.TIMEOUT_SECONDS,
                )
                active_model = model_name
                break
            except anthropic.APIStatusError as e:
                last_api_error = e
                error_text = str(e).lower()
                if "not_found_error" in error_text or "model" in error_text:
                    continue
                raise

        if message is None:
            if last_api_error is not None:
                print(
                    f"[WARNING] Claude model unavailable for {ticker}. Tried: {model_candidates}. Last error: {last_api_error}"
                )
                return raw_articles, "claude_failed_model_not_found"
            return raw_articles, "claude_failed_api_error"

        if active_model is not None:
            print(f"[INFO] {ticker} Claude model used: {active_model}")

        response_text = message.content[0].text.strip()
        parsed = _parse_filtered_response(response_text)

        if parsed is None:
            # One repair pass: ask the same model to output strict JSON only.
            repair_prompt = (
                "Convert the following content into strict JSON only. "
                "Output ONLY a JSON array of objects with keys: "
                "headline_index, title, relevance_score, reason.\n\n"
                f"CONTENT:\n{response_text}"
            )
            repair_message = client.messages.create(
                model=active_model or model_candidates[0],
                max_tokens=1024,
                messages=[{"role": "user", "content": repair_prompt}],
                timeout=NewsFilterGuardrails.TIMEOUT_SECONDS,
            )
            repair_text = repair_message.content[0].text.strip()
            parsed = _parse_filtered_response(repair_text)

        if parsed is None:
            preview = (response_text or "")[:180].replace("\n", " ")
            print(f"[WARNING] Claude returned malformed JSON for {ticker}. Preview: {preview}")
            return raw_articles, "claude_failed_malformed_json"

        # Map back to original articles
        filtered = []
        for item in parsed:
            idx = item.get("headline_index", -1)
            if 1 <= idx <= len(raw_articles):
                article = raw_articles[idx - 1]
                filtered.append(article)

        if not filtered:
            # Strict mode: do not fall back to all articles when none are relevant.
            return [], "claude_no_relevant_articles"

        # Limit to max output
        filtered = filtered[: NewsFilterGuardrails.MAX_ARTICLES_OUTPUT]

        # Cache the result
        cache.set(ticker, filtered)

        return filtered, "claude_filtered"

    except anthropic.APIConnectionError as e:
        print(f"[WARNING] Claude API connection failed for {ticker}: {e}")
        return raw_articles, "claude_failed_connection"
    except anthropic.APIStatusError as e:
        print(f"[WARNING] Claude API error for {ticker}: {e}")
        return raw_articles, "claude_failed_api_error"
    except anthropic.APITimeoutError as e:
        print(f"[WARNING] Claude API timeout for {ticker}: {e}")
        return raw_articles, "claude_failed_timeout"
    except Exception as e:
        print(f"[WARNING] Unexpected error in Claude filtering for {ticker}: {e}")
        return raw_articles, "claude_failed_unexpected_error"


def get_company_info(symbol: str) -> tuple[str, str]:
    """
    Fetch company name and sector from yfinance for Claude context.

    Returns:
        (company_name, sector)
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        name = info.get("longName", symbol)
        sector = info.get("sector", "Unknown")
        return name, sector
    except Exception as e:
        print(f"[WARNING] Could not fetch company info for {symbol}: {e}")
        return symbol, "Unknown"


def get_claude_status() -> dict:
    """
    Get Claude filter status for dashboard display.
    
    Returns:
        {
            "claude_available": bool,
            "api_key_present": bool,
            "cached_tickers": int,
            "cache_sizes": {ticker: article_count},
            "cache_ages": {ticker: hours_old},
            "status_message": str
        }
    """
    api_key = _get_anthropic_api_key()
    api_key_present = bool(api_key and len(api_key) > 0)

    claude_reachable = False
    claude_error = ""

    # Validate reachability/auth once per TTL so status is truthful but not noisy.
    now_ts = time.time()
    cache_age = now_ts - float(_STATUS_PROBE_CACHE.get("checked_at", 0.0) or 0.0)
    if api_key_present and cache_age <= _STATUS_PROBE_TTL_SECONDS:
        claude_reachable = bool(_STATUS_PROBE_CACHE.get("reachable", False))
        claude_error = str(_STATUS_PROBE_CACHE.get("error", "") or "")
    elif api_key_present:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client.models.list(limit=1)
            claude_reachable = True
            claude_error = ""
        except anthropic.APIConnectionError as exc:
            claude_reachable = False
            claude_error = f"connection_failed: {exc}"
        except anthropic.APIStatusError as exc:
            claude_reachable = False
            status_code = getattr(exc, "status_code", "unknown")
            claude_error = f"api_status_{status_code}: {exc}"
        except Exception as exc:
            claude_reachable = False
            claude_error = f"unexpected_error: {exc}"

        _STATUS_PROBE_CACHE["checked_at"] = now_ts
        _STATUS_PROBE_CACHE["reachable"] = claude_reachable
        _STATUS_PROBE_CACHE["error"] = claude_error
    
    cache = NewsCache()
    cached_tickers = len(cache._cache)
    cache_sizes = {}
    cache_ages = {}
    
    now = datetime.now()
    for ticker, entry in cache._cache.items():
        articles = entry.get("articles", [])
        cache_sizes[ticker] = len(articles)
        
        timestamp_str = entry.get("timestamp")
        if timestamp_str:
            try:
                cached_time = datetime.fromisoformat(timestamp_str)
                age_hours = (now - cached_time).total_seconds() / 3600
                cache_ages[ticker] = round(age_hours, 1)
            except Exception:
                cache_ages[ticker] = -1
    
    # Determine status message
    if api_key_present and claude_reachable:
        if cached_tickers > 0:
            oldest_age = max(cache_ages.values()) if cache_ages else 0
            status_msg = f"✅ Claude Active | {cached_tickers} ticker(s) cached | Oldest: {oldest_age:.1f}h"
        else:
            status_msg = "✅ Claude Active | Cache empty (will populate on first analysis)"
    elif api_key_present:
        if "api_status_401" in claude_error:
            status_msg = (
                "⚠️ Claude Unavailable (invalid API key) | Update ANTHROPIC_API_KEY "
                "in Render Environment or local .env | Fallback: VADER only"
            )
        else:
            status_msg = "⚠️ Claude Unavailable (API unreachable) | Check network/firewall/proxy | Fallback: VADER only"

        if claude_error:
            preview = claude_error.replace("\n", " ")[:140]
            status_msg = f"{status_msg} | {preview}"
    else:
        status_msg = "⚠️ Claude Unavailable (missing API key) | Fallback: VADER only"
    
    return {
        "claude_available": bool(api_key_present and claude_reachable),
        "api_key_present": api_key_present,
        "api_reachable": claude_reachable,
        "api_error": claude_error,
        "cached_tickers": cached_tickers,
        "cache_sizes": cache_sizes,
        "cache_ages": cache_ages,
        "status_message": status_msg,
    }
