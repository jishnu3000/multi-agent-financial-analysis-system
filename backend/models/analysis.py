"""Pydantic models for the stock analysis endpoints."""

from typing import List, Optional
from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Request body for ``POST /analyze``."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL)")


class StockDataPoint(BaseModel):
    """Single OHLCV candle returned to the frontend for charting."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AnalysisResponse(BaseModel):
    """Response body returned by ``POST /analyze``.

    Attributes:
        summary_report: Full markdown text of the analyst report.
        stock_data:     OHLCV data points for the last 60 trading days.
        pdf_status:     ``'Success'`` or an error message.
        pdf_path:       Relative path to the generated PDF, or ``None``.
        ticker:         Normalised (upper-case) ticker symbol.
    """

    summary_report: str
    stock_data: List[StockDataPoint]
    pdf_status: str
    pdf_path: Optional[str] = None
    ticker: str
