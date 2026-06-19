"""Chat agent for answering user questions about stock analysis context.

Provides domain-specific Q&A grounded in the current analysis of a symbol,
focusing on macro tone, risk adjustment, technical signals, and decision criteria.
Uses Claude if available, gracefully degrades if API is unavailable.
"""

import os
from dataclasses import dataclass
from typing import Literal, Optional

try:
    from anthropic import Anthropic, APIConnectionError, APIStatusError
except ImportError:
    Anthropic = None
    APIConnectionError = None
    APIStatusError = None


@dataclass
class ChatResponse:
    """Response from chat agent."""

    success: bool
    message: str
    is_on_topic: bool = True
    question_count_remaining: int = 0


# Cache for detected model
_DETECTED_MODEL = None
_API_STATUS_CHECKED = False
_API_STATUS_WORKING = False


def check_api_health() -> bool:
    """Quick check if Claude API is accessible. Returns True if working, False otherwise."""
    global _API_STATUS_CHECKED, _API_STATUS_WORKING
    
    # Return cached status if already checked
    if _API_STATUS_CHECKED:
        return _API_STATUS_WORKING
    
    client = get_claude_client()
    if not client:
        _API_STATUS_CHECKED = True
        _API_STATUS_WORKING = False
        return False
    
    try:
        # Try to detect model as a cheap health check
        _detect_available_model(client)
        _API_STATUS_WORKING = True
        _API_STATUS_CHECKED = True
        print("[INFO] Claude API health check: OK")
        return True
    except Exception as e:
        print(f"[WARNING] Claude API health check failed: {e}")
        _API_STATUS_WORKING = False
        _API_STATUS_CHECKED = True
        return False



def get_claude_client() -> Optional[Anthropic]:
    """Get Claude client if API key is available."""
    if not Anthropic:
        return None
    
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    
    try:
        return Anthropic(api_key=api_key)
    except Exception as e:
        print(f"[WARNING] Failed to create Anthropic client: {e}")
        return None


def _detect_available_model(client: Anthropic) -> str:
    """Detect an available Claude model from your account."""
    global _DETECTED_MODEL
    
    # Return cached model if already detected
    if _DETECTED_MODEL:
        return _DETECTED_MODEL
    
    # Preferred models in order of preference
    preferred_models = [
        "claude-3-5-sonnet-20250514",  # Latest Claude 3.5 Sonnet
        "claude-3-5-sonnet-20241022",  # Previous Claude 3.5 Sonnet
        "claude-3-sonnet-20250229",    # Claude 3 Sonnet
        "claude-opus-4-1-20250805",    # Claude Opus
        "claude-3-opus-20250219",      # Claude 3 Opus
        "claude-3-haiku-20250307",     # Claude 3 Haiku (lightweight)
    ]
    
    # Try to list models from API
    try:
        # Most recent Anthropic SDK method
        if hasattr(client, 'models') and hasattr(client.models, 'list'):
            models_response = client.models.list()
            available_ids = {model.id for model in models_response.data if hasattr(model, 'id')}
            
            # Find first preferred model that's available
            for preferred in preferred_models:
                if preferred in available_ids:
                    _DETECTED_MODEL = preferred
                    print(f"[INFO] Detected available model: {preferred}")
                    return preferred
    except Exception as e:
        print(f"[DEBUG] Could not list models from API: {e}")
        pass
    
    # Fallback: try making minimal test requests with each model
    for model in preferred_models:
        try:
            test_response = client.messages.create(
                model=model,
                max_tokens=5,
                system="Respond with just 'ok'",
                messages=[{"role": "user", "content": "ok"}],
                timeout=5,
            )
            _DETECTED_MODEL = model
            print(f"[INFO] Confirmed available model via test call: {model}")
            return model
        except Exception as e:
            debug_msg = str(e).lower()
            if "not found" in debug_msg or "invalid" in debug_msg:
                # Model doesn't exist, skip it
                continue
            elif "connection" in debug_msg or "timeout" in debug_msg:
                # Network issue, might be temporary
                print(f"[DEBUG] Connection issue during model detection: {e}")
                continue
            elif "401" in str(e) or "unauthorized" in debug_msg:
                # Auth issue, no point trying other models
                print(f"[WARNING] Authentication failed during model detection: {e}")
                raise
            else:
                print(f"[DEBUG] Model test failed for {model}: {e}")
                continue
    
    # If nothing worked, default to latest (will fail gracefully in answer_question)
    # This preserves the original behavior of defaulting to latest model
    print(f"[WARNING] No Claude model could be confirmed. Defaulting to {preferred_models[0]}")
    _DETECTED_MODEL = preferred_models[0]
    return _DETECTED_MODEL


def _is_general_question(question: str) -> bool:
    """Check if question is about general concepts vs. specific analysis."""
    question_lower = question.lower()
    
    # Specific analysis questions (require stock context)
    specific_keywords = {
        "this stock", "my stock", "aapl", "msft", "nvda", "amzn",
        "current", "right now", "today", "my analysis", "your analysis",
        "the decision", "the trend", "confidence", "rsi value",
    }
    
    if any(kw in question_lower for kw in specific_keywords):
        return False
    
    return True


def _detect_question_mode(
    question: str,
    symbol: str | None,
) -> Literal["analysis_context", "general_ticker", "general_concept"]:
    """Route the question based on whether the user wants page analysis or general ticker info."""
    question_lower = (question or "").lower()
    symbol_lower = (symbol or "").lower()

    general_ticker_phrases = {
        "general info",
        "company info",
        "company overview",
        "what do they do",
        "tell me about",
        "about the company",
        "about this company",
    }

    general_ticker_terms = {
        "business model",
        "sector",
        "industry",
        "competitor",
        "competitors",
        "overview",
        "profile",
        "background",
        "company",
        "business",
    }

    analysis_keywords = {
        "analysis",
        "decision",
        "confidence",
        "trend",
        "rsi",
        "atr",
        "signal",
        "macro tone",
        "news sentiment",
        "earnings",
        "fundamentals",
        "why buy",
        "why sell",
        "why hold",
        "reduce risk",
        "main page",
        "current page",
        "current analysis",
        "this analysis",
        "the metrics",
    }

    if symbol and any(keyword in question_lower for keyword in analysis_keywords):
        return "analysis_context"

    if any(phrase in question_lower for phrase in general_ticker_phrases):
        return "general_ticker"

    if any(term in question_lower for term in general_ticker_terms):
        if symbol or symbol_lower in question_lower:
            return "general_ticker"

    if symbol_lower and symbol_lower in question_lower and any(
        phrase in question_lower
        for phrase in ("tell me about", "general info", "overview", "profile", "company")
    ):
        return "general_ticker"

    if symbol:
        return "analysis_context"

    return "general_concept"


def _is_on_topic(question: str) -> bool:
    """Quick check if question is about stock analysis, macro, risk, technicals."""
    return bool((question or "").strip())


def answer_question(
    question: str,
    symbol: str = None,
    final_decision: str = None,
    confidence: float = None,
    trend: str = None,
    rsi_14: float = None,
    technical_signal: str = None,
    criteria_summary: str = None,
    macro_tone: str = None,
    macro_summary: str = None,
    news_sentiment: str = None,
    earnings_summary: str = None,
    fundamentals_summary: str = None,
    questions_asked: int = 0,
    max_questions: int = 10,
) -> ChatResponse:
    """
    Answer a user question about stock analysis or general concepts.
    
    Args:
        question: User's question
        symbol: Stock ticker (optional, only needed for specific analysis questions)
        final_decision: Current decision (e.g., "Buy", "Hold", "Reduce Risk")
        confidence: Confidence score [0.0, 1.0]
        trend: Trend state ("Uptrend", "Downtrend", "Neutral")
        rsi_14: RSI indicator value
        technical_signal: Technical interpretation
        criteria_summary: Detailed criteria text
        macro_tone: Macro signal tone ("Supportive", "Risk-Off", "Neutral", "Unavailable")
        macro_summary: Macro signal details
        news_sentiment: News sentiment summary
        earnings_summary: Earnings context
        fundamentals_summary: Fundamentals context
        questions_asked: Number of questions already asked this session
        max_questions: Maximum questions allowed per session
    
    Returns:
        ChatResponse with success, message, and metadata
    """
    
    # Check question limit
    if questions_asked >= max_questions:
        return ChatResponse(
            success=False,
            message=f"Question limit reached ({max_questions} per session). Please refresh to continue.",
            is_on_topic=True,
            question_count_remaining=0,
        )
    
    # Check if question is on-topic
    if not _is_on_topic(question):
        return ChatResponse(
            success=False,
            message=(
                "I focus on questions about stock analysis, macro conditions, risk factors, "
                "and the metrics shown in your analysis. Please ask about those topics!"
            ),
            is_on_topic=False,
            question_count_remaining=max_questions - questions_asked - 1,
        )
    
    question_mode = _detect_question_mode(question=question, symbol=symbol)
    is_general = question_mode != "analysis_context"
    
    # Try to get Claude client
    client = get_claude_client()
    if not client:
        return ChatResponse(
            success=False,
            message=(
                "Claude API is not available. Please add ANTHROPIC_API_KEY to your .env file "
                "and restart the app to enable AI-powered explanations."
            ),
            is_on_topic=True,
            question_count_remaining=max_questions - questions_asked - 1,
        )
    
    # Prepare system prompt based on question type
    if question_mode == "general_concept":
        system_prompt = """You are a knowledgeable stock analysis tutor. Help users understand key concepts:
- Macro economic signals and sentiment tones
- Technical indicators (RSI, ATR, momentum, trends)
- Risk adjustment and volatility
- Confidence scoring and decision criteria
- News sentiment impact on analysis
- Earnings and fundamental signals

Keep responses SHORT and educational (2-3 sentences for definitions, one paragraph max).
Use simple language. Avoid overly technical jargon.
Focus on 'why it matters' not exhaustive details.
If the user mentions a ticker or stock symbol, give a best-effort explanation even if the full page context is missing."""
        
        context_str = ""  # No specific analysis context

    elif question_mode == "general_ticker":
        system_prompt = f"""You are a knowledgeable equity research assistant. The user is asking for GENERAL information about ticker {symbol or 'the ticker they mentioned'}, not just the current dashboard analysis.

Answer with a company or ticker overview first: what the business does, what sector or industry it sits in, and what investors usually watch for this name.
If current dashboard context exists, you may mention it briefly at the end as separate context, but do not make it the main answer unless the user asks about the live analysis.

Keep responses concise, clear, and practical. This is analytical support, not financial advice."""
        context_str = (
            f"Current page context for {symbol}:\n"
            f"- Decision: {final_decision}\n"
            f"- Confidence: {confidence:.2f} (0.0-1.0 scale)\n"
            f"- Trend: {trend}\n"
            f"- RSI(14): {rsi_14:.2f}\n"
            f"- Technical Signal: {technical_signal}\n"
            f"- Macro Tone: {macro_tone}\n"
            f"- News Sentiment: {news_sentiment}"
        ).strip() if symbol and confidence is not None and rsi_14 is not None else ""
    
    else:
        # Specific question with stock context - we have current analysis data
        context_str = f"""
Current Analysis Context for {symbol}:
- Decision: {final_decision}
- Confidence: {confidence:.2f} (0.0-1.0 scale)
- Trend: {trend}
- RSI(14): {rsi_14:.2f}
- Technical Signal: {technical_signal}
- Macro Tone: {macro_tone}
- News Sentiment: {news_sentiment}

Detailed Criteria:
{criteria_summary}

Macro Signal Details:
{macro_summary}

Earnings Context:
{earnings_summary}

Fundamentals Context:
{fundamentals_summary}
""".strip()
        
        system_prompt = f"""You are a knowledgeable stock analysis assistant helping interpret the CURRENT analysis of {symbol}.

You have detailed analysis data below for {symbol}. Answer questions about this analysis, explain what the metrics mean, and help users understand the decision and confidence level.

Key points to remember:
- You have CURRENT, specific data for {symbol} (shown below)
- Always reference the metrics and analysis provided
- Be specific to THIS company, not generic
- Help users understand why the decision was made
- Explain the impact of each signal (technical, macro, news, earnings, fundamentals)

Be clear, educational, and concise (2-4 sentences for quick questions, up to a paragraph for deeper explanations).
Remind users this is analytical support, not financial advice."""
    
    try:
        # Detect available model on first use
        detected_model = _detect_available_model(client)
        
        response = client.messages.create(
            model=detected_model,
            max_tokens=400 if is_general else 500,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"{f'Analysis Context:{chr(10)}{context_str}{chr(10)}{chr(10)}' if context_str else ''}User Question: {question}",
                }
            ],
        )
        
        answer = response.content[0].text if response.content else "No response generated."
        
        return ChatResponse(
            success=True,
            message=answer,
            is_on_topic=True,
            question_count_remaining=max_questions - questions_asked - 1,
        )
    
    except Exception as exc:
        error_msg = str(exc).lower()
        
        # Provide more specific error messages
        if "connection" in error_msg or "network" in error_msg:
            user_msg = (
                "Network connection error. Please check your internet connection and try again. "
                "If the issue persists, the API service may be temporarily unavailable."
            )
        elif "401" in error_msg or "authentication" in error_msg or "unauthorized" in error_msg:
            user_msg = (
                "API authentication failed. Please verify that your ANTHROPIC_API_KEY in .env is correct "
                "and restart the app."
            )
        elif "429" in error_msg or "rate" in error_msg:
            user_msg = "API rate limit reached. Please wait a moment and try again."
        elif "model" in error_msg or "not found" in error_msg:
            user_msg = (
                "The selected Claude model is not available in your account. "
                "Please check your Anthropic account or try updating the ANTHROPIC_MODEL setting."
            )
        else:
            user_msg = f"Claude API error: {str(exc)}"
        
        return ChatResponse(
            success=False,
            message=user_msg,
            is_on_topic=True,
            question_count_remaining=max_questions - questions_asked - 1,
        )


# Example questions for the UI
EXAMPLE_QUESTIONS = [
    "What does RSI mean and why is it important?",
    "What is macro tone and how does it affect my investment?",
    "What's the difference between Bullish and Bearish trends?",
    "How does volatility (ATR) affect my risk adjustment?",
    "What does confidence score tell me about a decision?",
    "Why is having multiple signals important in analysis?",
]
