"""
Technical-indicator calculations.

Function:
    calculate_technical_indicators – SMA-50, RSI-14, trend, support/resistance.
"""

from typing import Any, Dict

import pandas as pd


def calculate_technical_indicators(price_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute common technical indicators from OHLCV price history.

    Computed indicators:
    * **SMA-50** – 50-period Simple Moving Average of the closing price.
    * **RSI-14** – 14-period Relative Strength Index (rolling-mean smoothing).
    * **Trend**  – ``'Bullish'`` / ``'Bearish'`` / ``'Insufficient data'``.
    * **Support / Resistance** – lowest low / highest high of the last 20 sessions.

    Args:
        price_data: Dict as returned by :func:`~services.stock_data.fetch_stock_data`.
                    Must contain the key ``'historical_data'``.

    Returns:
        Dict with keys: ``sma_50``, ``rsi_14``, ``trend``, ``trend_strength``,
        ``rsi_signal``, ``support_level``, ``resistance_level``.

    Raises:
        Exception: On any DataFrame construction or calculation failure.
    """
    try:
        df = pd.DataFrame(price_data["historical_data"])
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        # SMA-50
        df["SMA_50"] = df["Close"].rolling(window=50).mean()

        # RSI-14 (Wilder via rolling mean)
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df["RSI_14"] = 100 - (100 / (1 + gain / loss))

        latest = df.iloc[-1]
        sma_50 = latest["SMA_50"]
        current_price = latest["Close"]
        rsi = latest["RSI_14"]

        # Trend
        if pd.notna(sma_50):
            trend = "Bullish" if current_price > sma_50 else "Bearish"
            trend_strength = abs((current_price / sma_50 - 1) * 100)
        else:
            trend, trend_strength = "Insufficient data", 0.0

        # RSI signal
        if pd.notna(rsi):
            if rsi > 70:
                rsi_signal = "Overbought"
            elif rsi < 30:
                rsi_signal = "Oversold"
            else:
                rsi_signal = "Neutral"
        else:
            rsi_signal = "Insufficient data"
            rsi = None

        return {
            "sma_50": float(sma_50) if pd.notna(sma_50) else None,
            "rsi_14": float(rsi) if rsi is not None and pd.notna(rsi) else None,
            "trend": trend,
            "trend_strength": float(trend_strength),
            "rsi_signal": rsi_signal,
            "support_level": float(df["Low"].tail(20).min()),
            "resistance_level": float(df["High"].tail(20).max()),
        }
    except Exception as e:
        raise Exception(f"Error calculating technical indicators: {str(e)}")
