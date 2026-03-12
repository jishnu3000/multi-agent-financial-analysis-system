"""
Market-data fetching tools.

Functions:
    fetch_stock_data    – OHLCV price history via yfinance.
    fetch_fundamentals  – Key financial ratios via yfinance.
    fetch_news          – Recent headlines via DuckDuckGo.
"""

import time
from typing import Any, Dict, List

import yfinance as yf
from curl_cffi import requests as curl_requests
from ddgs import DDGS


def _yf_session() -> curl_requests.Session:
    """Return a curl_cffi Session that impersonates Chrome.

    yfinance 1.x requires a curl_cffi session (not a plain requests.Session).
    Passing an explicit Chrome-impersonating session ensures the TLS
    fingerprint and headers match a real browser, which is necessary to
    bypass Yahoo Finance's bot-detection both locally and on cloud hosts
    (Render, Railway, etc.) that share IP ranges with known scrapers.
    """
    return curl_requests.Session(impersonate="chrome124")


def _with_retry(fn, max_retries: int = 3):
    """Call fn(), retrying on Yahoo Finance rate-limit (429) errors.

    Uses exponential back-off: 5 s, 10 s, 20 s between attempts.
    All other exceptions are re-raised immediately.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            msg = str(e).lower()
            if any(kw in msg for kw in ("too many requests", "rate limit", "429")) and attempt < max_retries - 1:
                time.sleep(5 * (2 ** attempt))  # 5 s, 10 s, 20 s
                continue
            raise


def fetch_stock_data(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """Fetch OHLCV price history and summary statistics for a stock.

    Args:
        ticker: Stock ticker symbol (e.g. ``'AAPL'``).
        period: Lookback window (e.g. ``'6mo'``, ``'1y'``). Defaults to ``'6mo'``.

    Returns:
        Dict with keys: ``ticker``, ``current_price``, ``previous_close``,
        ``price_change``, ``price_change_pct``, ``volume``, ``high_52w``,
        ``low_52w``, ``historical_data``.

    Raises:
        ValueError: If the ticker is not recognised by yfinance.
        Exception:  For any other network or parsing error.
    """
    try:
        session = _yf_session()
        stock = yf.Ticker(ticker, session=session)

        # yfinance can return an empty DataFrame silently (no exception) when
        # Yahoo Finance rate-limits the request, so we retry on empty hist too.
        hist = None
        for attempt in range(3):
            hist = stock.history(period=period)
            if not hist.empty:
                break
            if attempt < 2:
                time.sleep(5 * (2 ** attempt))  # 5 s, 10 s

        if hist is None or hist.empty:
            raise ValueError(
                f"Invalid ticker symbol '{ticker}'. Please check the ticker and try again."
            )

        # info can be sparse in newer yfinance — don't use it for validity.
        # hist.empty is the only reliable signal for an invalid ticker.
        try:
            info = _with_retry(lambda: stock.info) or {}
        except Exception:
            info = {}

        return {
            "ticker": ticker,
            "current_price": float(hist["Close"].iloc[-1]),
            "previous_close": float(hist["Close"].iloc[-2]) if len(hist) > 1 else None,
            "price_change": (
                float(hist["Close"].iloc[-1] - hist["Close"].iloc[-2])
                if len(hist) > 1
                else 0
            ),
            "price_change_pct": (
                float((hist["Close"].iloc[-1] /
                      hist["Close"].iloc[-2] - 1) * 100)
                if len(hist) > 1
                else 0
            ),
            "volume": int(hist["Volume"].iloc[-1]),
            "high_52w": float(hist["High"].max()),
            "low_52w": float(hist["Low"].min()),
            "historical_data": hist.reset_index().to_dict(orient="records"),
        }
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Error fetching stock data: {str(e)}")


def fetch_fundamentals(ticker: str) -> Dict[str, Any]:
    """Fetch key fundamental metrics and company metadata.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Dict with keys: ``company_name``, ``sector``, ``industry``,
        ``market_cap``, ``pe_ratio``, ``forward_pe``, ``price_to_book``,
        ``dividend_yield``, ``beta``, ``52w_high``, ``52w_low``,
        ``avg_volume``, ``description``.

    Raises:
        ValueError: If the ticker is invalid (sparse or missing info dict).
        Exception:  For any other error.
    """
    try:
        stock = yf.Ticker(ticker, session=_yf_session())
        info = _with_retry(lambda: stock.info) or {}

        # An empty dict means truly invalid ticker; sparse dict is fine (newer yfinance)
        if not info:
            raise ValueError(
                f"Invalid ticker symbol '{ticker}'. Please check the ticker and try again."
            )

        return {
            "company_name": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "description": info.get("longBusinessSummary", "")[:800],
        }
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Error fetching fundamentals: {str(e)}")


def fetch_news(ticker: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fetch recent news headlines for a stock via DuckDuckGo.

    Failures are silently suppressed; an empty list is returned so that a
    news outage never blocks the analysis pipeline.

    Args:
        ticker:      Ticker symbol used to build the search query.
        max_results: Maximum number of articles to retrieve.

    Returns:
        List of dicts with keys: ``title``, ``source``, ``url``, ``date``,
        ``snippet``.  Empty list on any failure.
    """
    try:
        results = []
        with DDGS() as ddgs:
            for article in ddgs.news(f"{ticker} stock news", max_results=max_results):
                results.append(
                    {
                        "title": article.get("title", ""),
                        "source": article.get("source", ""),
                        "url": article.get("url", ""),
                        "date": article.get("date", ""),
                        "snippet": article.get("body", "")[:200],
                    }
                )
        return results
    except Exception:
        return []
