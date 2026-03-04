"""
Multi-Agent Financial Analysis System
Backend API with LangGraph Agent Orchestration

This module implements a multi-agent financial analysis pipeline using LangGraph
for orchestration and Google Gemini as the underlying LLM. Three specialised
agents collaborate in sequence:

  1. Researcher Agent  - fetches stock price data, fundamentals, and news.
  2. Analyst Agent     - computes technical indicators (SMA-50, RSI-14, etc.).
  3. Team Lead Agent   - synthesises all data into a final markdown report via LLM.

The resulting report is exposed through a FastAPI REST interface and can be
exported as a PDF using ReportLab.

Environment variables required:
    GOOGLE_API_KEY: API key for Google Generative AI (Gemini).

Usage:
    uvicorn main:app --reload
    # or
    python main.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, TypedDict, Annotated
import os
from datetime import datetime, timedelta
import json
import traceback

# LangGraph & LangChain
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Data Tools
import yfinance as yf
import pandas as pd
import numpy as np
from ddgs import DDGS

# PDF Generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

# Environment
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURATION ====================

app = FastAPI(
    title="Multi-Agent Financial Analysis System",
    description="Multi-Agent Stock Analysis System",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini LLM Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
    max_output_tokens=2048
)

# ==================== DATA MODELS ====================


class AnalysisRequest(BaseModel):
    """Request body for the /analyze endpoint."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL)")


class StockDataPoint(BaseModel):
    """Represents a single OHLCV candle returned to the frontend for charting."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AnalysisResponse(BaseModel):
    """Response body returned by the /analyze endpoint.

    Attributes:
        summary_report: Full markdown text of the analyst report.
        stock_data:     List of OHLCV data points for the last 60 trading days.
        pdf_status:     'Success' or an error message describing why PDF generation
                        failed.
        pdf_path:       Relative path to the generated PDF file, or None if the PDF
                        could not be created.
        ticker:         The normalised (upper-case) ticker symbol that was analysed.
    """

    summary_report: str
    stock_data: List[StockDataPoint]
    pdf_status: str
    pdf_path: Optional[str] = None
    ticker: str

# ==================== AGENT STATE ====================


class AgentState(TypedDict):
    """Shared mutable state object threaded through every node in the LangGraph workflow.

    Each agent reads from and writes to this dictionary.  Fields are grouped by
    the agent that is responsible for populating them.

    Attributes:
        ticker:                  Upper-case stock ticker symbol (e.g. 'AAPL').
        messages:                Running log of LangChain message objects used
                                 to trace agent activity.

        stock_price_data:        Raw OHLCV history and derived metrics returned
                                 by :func:`fetch_stock_data`.
        fundamentals:            Key financial ratios and company metadata
                                 returned by :func:`fetch_fundamentals`.
        news_articles:           List of recent news snippets from DuckDuckGo.
        research_summary:        Human-readable markdown string summarising the
                                 data collected by the Researcher Agent.

        technical_analysis:      Dictionary of computed technical indicators
                                 (SMA-50, RSI-14, support/resistance) from the
                                 Analyst Agent.
        analyst_summary:         Human-readable markdown string summarising the
                                 technical analysis.

        final_report:            Full markdown report generated by the Team Lead
                                 Agent via the Gemini LLM.

        errors:                  Accumulated list of error messages from any
                                 agent.  Non-empty does not necessarily halt the
                                 pipeline; check ``ticker_validation_error`` for
                                 hard failures.
        ticker_validation_error: Set to ``True`` by the Researcher Agent when
                                 the supplied ticker symbol is invalid.  All
                                 downstream agents skip processing if this flag
                                 is set.
    """

    ticker: str
    messages: List[Any]

    # Researcher outputs
    stock_price_data: Optional[Dict[str, Any]]
    fundamentals: Optional[Dict[str, Any]]
    news_articles: Optional[List[Dict[str, str]]]
    research_summary: Optional[str]

    # Analyst outputs
    technical_analysis: Optional[Dict[str, Any]]
    analyst_summary: Optional[str]

    # Team Lead outputs
    final_report: Optional[str]

    # Error handling
    errors: List[str]
    ticker_validation_error: Optional[bool]

# ==================== TOOL FUNCTIONS ====================


def fetch_stock_data(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """Fetch OHLCV price history and summary statistics for a stock.

    Uses *yfinance* to download historical market data and validates that the
    ticker symbol is recognised before returning results.

    Args:
        ticker: Stock ticker symbol (e.g. ``'AAPL'``, ``'TSLA'``).
        period: Lookback window accepted by yfinance (e.g. ``'1mo'``, ``'6mo'``,
                ``'1y'``). Defaults to ``'6mo'``.

    Returns:
        A dictionary containing:
            - ``ticker``          (str)  – normalised ticker symbol.
            - ``current_price``   (float) – most recent closing price.
            - ``previous_close``  (float | None) – previous day's close.
            - ``price_change``    (float) – absolute change vs. previous close.
            - ``price_change_pct``(float) – percentage change vs. previous close.
            - ``volume``          (int)  – latest day's trading volume.
            - ``high_52w``        (float) – 52-week high.
            - ``low_52w``         (float) – 52-week low.
            - ``historical_data`` (list[dict]) – full OHLCV records as
              ``orient='records'`` dicts from pandas.

    Raises:
        ValueError: If the ticker symbol is not recognised by yfinance (empty
                    history or missing ``symbol`` in the info dict).
        Exception:  For any other network or parsing error.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            raise ValueError(
                f"Invalid ticker symbol '{ticker}'. Please check the ticker and try again.")

        # Additional validation: check if ticker info is available
        info = stock.info
        if not info or 'symbol' not in info:
            raise ValueError(
                f"Invalid ticker symbol '{ticker}'. Please check the ticker and try again.")

        # Convert to serializable format
        data = {
            "ticker": ticker,
            "current_price": float(hist['Close'].iloc[-1]),
            "previous_close": float(hist['Close'].iloc[-2]) if len(hist) > 1 else None,
            "price_change": float(hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) if len(hist) > 1 else 0,
            "price_change_pct": float((hist['Close'].iloc[-1] / hist['Close'].iloc[-2] - 1) * 100) if len(hist) > 1 else 0,
            "volume": int(hist['Volume'].iloc[-1]),
            "high_52w": float(hist['High'].max()),
            "low_52w": float(hist['Low'].min()),
            "historical_data": hist.reset_index().to_dict(orient='records')
        }

        return data
    except ValueError:
        # Re-raise ValueError for ticker validation
        raise
    except Exception as e:
        raise Exception(f"Error fetching stock data: {str(e)}")


def fetch_fundamentals(ticker: str) -> Dict[str, Any]:
    """Fetch key fundamental metrics and company metadata for a stock.

    Retrieves company information from the yfinance ``Ticker.info`` dictionary
    and validates that a meaningful response was received.

    Args:
        ticker: Stock ticker symbol (e.g. ``'AAPL'``).

    Returns:
        A dictionary containing fields such as:
            - ``company_name``  (str)   – full company name.
            - ``sector``        (str)   – GICS sector or ``'N/A'``.
            - ``industry``      (str)   – industry group or ``'N/A'``.
            - ``market_cap``    (int | None)   – market capitalisation.
            - ``pe_ratio``      (float | None) – trailing P/E ratio.
            - ``forward_pe``    (float | None) – forward P/E ratio.
            - ``price_to_book`` (float | None) – price-to-book ratio.
            - ``dividend_yield``(float | None) – annual dividend yield.
            - ``beta``          (float | None) – beta versus the market.
            - ``52w_high``      (float | None) – 52-week high price.
            - ``52w_low``       (float | None) – 52-week low price.
            - ``avg_volume``    (int | None)   – 30-day average volume.
            - ``description``   (str)   – first 500 characters of the business
              summary.

    Raises:
        ValueError: If the ticker is invalid (no data or fewer than 5 info
                    fields returned by yfinance).
        Exception:  For any other network or parsing error.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Validate that we got valid data
        if not info or len(info) < 5 or 'symbol' not in info:
            raise ValueError(
                f"Invalid ticker symbol '{ticker}'. Please check the ticker and try again.")

        fundamentals = {
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
            "description": info.get("longBusinessSummary", "")[:500]
        }

        return fundamentals
    except ValueError:
        # Re-raise ValueError for ticker validation
        raise
    except Exception as e:
        raise Exception(f"Error fetching fundamentals: {str(e)}")


def fetch_news(ticker: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fetch recent news headlines related to a stock via DuckDuckGo.

    Performs a news search for the query ``"<ticker> stock news"`` and returns
    a normalised list of article summaries.  Failures are silently swallowed and
    an empty list is returned so that a news outage never blocks the pipeline.

    Args:
        ticker:      Stock ticker symbol used to build the search query.
        max_results: Maximum number of news articles to retrieve. Defaults to 5.

    Returns:
        A list of dictionaries, each containing:
            - ``title``   (str) – article headline.
            - ``source``  (str) – publication or domain name.
            - ``url``     (str) – direct link to the article.
            - ``date``    (str) – publication date string as returned by DDGS.
            - ``snippet`` (str) – up to 200 characters of the article body.

        Returns an empty list if the search fails or yields no results.
    """
    try:
        query = f"{ticker} stock news"
        results = []

        with DDGS() as ddgs:
            news_results = ddgs.news(query, max_results=max_results)
            for article in news_results:
                results.append({
                    "title": article.get("title", ""),
                    "source": article.get("source", ""),
                    "url": article.get("url", ""),
                    "date": article.get("date", ""),
                    "snippet": article.get("body", "")[:200]
                })

        return results
    except Exception as e:
        # Return empty list if search fails
        return []


def calculate_technical_indicators(price_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute common technical indicators from OHLCV price history.

    Calculates the following indicators on the ``historical_data`` embedded in
    *price_data* (as produced by :func:`fetch_stock_data`):

    * **SMA-50** – 50-period Simple Moving Average of the closing price.
    * **RSI-14** – 14-period Relative Strength Index (Wilder smoothing via
      rolling mean).
    * **Trend**  – ``'Bullish'`` when the latest close is above SMA-50,
      ``'Bearish'`` otherwise.
    * **Support / Resistance** – lowest low and highest high of the most
      recent 20 trading sessions.

    Args:
        price_data: Dictionary as returned by :func:`fetch_stock_data`.
                    Must contain the key ``'historical_data'``.

    Returns:
        A dictionary containing:
            - ``sma_50``           (float | None) – 50-day SMA value.
            - ``rsi_14``           (float | None) – latest RSI value (0-100).
            - ``trend``            (str)   – ``'Bullish'``, ``'Bearish'``, or
              ``'Insufficient data'``.
            - ``trend_strength``   (float) – absolute % deviation of price
              from SMA-50.
            - ``rsi_signal``       (str)   – ``'Overbought'`` (RSI > 70),
              ``'Oversold'`` (RSI < 30), ``'Neutral'``, or
              ``'Insufficient data'``.
            - ``support_level``    (float) – 20-session low.
            - ``resistance_level`` (float) – 20-session high.

    Raises:
        Exception: If the DataFrame cannot be constructed or a calculation
                   fails unexpectedly.
    """
    try:
        df = pd.DataFrame(price_data['historical_data'])
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')

        # SMA-50
        df['SMA_50'] = df['Close'].rolling(window=50).mean()

        # RSI-14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # Get latest values
        latest = df.iloc[-1]

        # Trend analysis
        sma_50 = latest['SMA_50']
        current_price = latest['Close']

        if pd.notna(sma_50):
            trend = "Bullish" if current_price > sma_50 else "Bearish"
            trend_strength = abs((current_price / sma_50 - 1) * 100)
        else:
            trend = "Insufficient data"
            trend_strength = 0

        # RSI interpretation
        rsi = latest['RSI_14']
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
            "rsi_14": float(rsi) if pd.notna(rsi) else None,
            "trend": trend,
            "trend_strength": float(trend_strength),
            "rsi_signal": rsi_signal,
            "support_level": float(df['Low'].tail(20).min()),
            "resistance_level": float(df['High'].tail(20).max())
        }
    except Exception as e:
        raise Exception(f"Error calculating technical indicators: {str(e)}")

# ==================== AGENT NODES ====================


def researcher_agent(state: AgentState) -> AgentState:
    """LangGraph node: collect raw market data for the requested ticker.

    Responsibilities:
        * Fetch OHLCV price history via :func:`fetch_stock_data`.
        * Fetch fundamental metrics via :func:`fetch_fundamentals`.
        * Fetch recent news headlines via :func:`fetch_news`.
        * Compose a brief markdown ``research_summary`` from the collected data.

    On a ``ValueError`` (invalid ticker), the node sets
    ``state['ticker_validation_error'] = True`` so that downstream agents
    skip processing and the API can return a 404 response.

    Args:
        state: Current :class:`AgentState`.  Reads ``ticker``.

    Returns:
        Updated :class:`AgentState` with ``stock_price_data``, ``fundamentals``,
        ``news_articles``, and ``research_summary`` populated (or
        ``ticker_validation_error`` set on failure).
    """
    ticker = state["ticker"]
    errors = state.get("errors", [])

    try:
        # Fetch stock price data
        stock_data = fetch_stock_data(ticker)
        state["stock_price_data"] = stock_data

        # Fetch fundamentals
        fundamentals = fetch_fundamentals(ticker)
        state["fundamentals"] = fundamentals

        # Fetch news
        news = fetch_news(ticker)
        state["news_articles"] = news

        # Create research summary
        summary = f"""
## Research Data Collected for {ticker}

**Company:** {fundamentals['company_name']}
**Sector:** {fundamentals['sector']} | **Industry:** {fundamentals['industry']}

**Current Price:** ${stock_data['current_price']:.2f}
**Price Change:** ${stock_data['price_change']:.2f} ({stock_data['price_change_pct']:.2f}%)
**52-Week Range:** ${stock_data['low_52w']:.2f} - ${stock_data['high_52w']:.2f}

**Fundamentals:**
- Market Cap: ${fundamentals['market_cap']:,} if fundamentals['market_cap'] else 'N/A'
- P/E Ratio: {fundamentals['pe_ratio']:.2f} if fundamentals['pe_ratio'] else 'N/A'
- Beta: {fundamentals['beta']:.2f} if fundamentals['beta'] else 'N/A'

**Recent News Headlines:**
{chr(10).join([f"- {article['title']}" for article in news[:3]])}
"""

        state["research_summary"] = summary.strip()
        state["messages"].append(
            AIMessage(content=f"Research completed for {ticker}"))

    except ValueError as e:
        # Store ticker validation error
        error_msg = str(e)
        errors.append(error_msg)
        state["errors"] = errors
        state["ticker_validation_error"] = True
        state["messages"].append(AIMessage(content=error_msg))
    except Exception as e:
        error_msg = f"Researcher Agent Error: {str(e)}"
        errors.append(error_msg)
        state["errors"] = errors
        state["messages"].append(AIMessage(content=error_msg))

    return state


def analyst_agent(state: AgentState) -> AgentState:
    """LangGraph node: derive technical indicators from collected price data.

    Responsibilities:
        * Invoke :func:`calculate_technical_indicators` on the price history
          stored in ``state['stock_price_data']``.
        * Compose a brief markdown ``analyst_summary`` from the results.

    This node is a no-op when ``state['ticker_validation_error']`` is ``True``
    (i.e. the Researcher Agent encountered an invalid ticker).

    Args:
        state: Current :class:`AgentState`.  Reads ``stock_price_data``.

    Returns:
        Updated :class:`AgentState` with ``technical_analysis`` and
        ``analyst_summary`` populated (or an error appended to ``errors``).
    """
    errors = state.get("errors", [])

    # Skip if ticker validation failed
    if state.get("ticker_validation_error"):
        return state

    try:
        if not state.get("stock_price_data"):
            raise ValueError("No stock price data available for analysis")

        # Calculate technical indicators
        technical = calculate_technical_indicators(state["stock_price_data"])
        state["technical_analysis"] = technical

        # Create analyst summary
        summary = f"""
## Technical Analysis

**Trend Analysis:**
- 50-Day SMA: ${technical['sma_50']:.2f} if technical['sma_50'] else 'Insufficient data'
- Current Trend: {technical['trend']} (Strength: {technical['trend_strength']:.2f}%)

**Momentum Indicators:**
- RSI (14): {technical['rsi_14']:.2f} if technical['rsi_14'] else 'Insufficient data' - {technical['rsi_signal']}

**Support/Resistance:**
- Support Level: ${technical['support_level']:.2f}
- Resistance Level: ${technical['resistance_level']:.2f}
"""

        state["analyst_summary"] = summary.strip()
        state["messages"].append(
            AIMessage(content="Technical analysis completed"))

    except Exception as e:
        error_msg = f"Analyst Agent Error: {str(e)}"
        errors.append(error_msg)
        state["errors"] = errors
        state["messages"].append(AIMessage(content=error_msg))

    return state


def team_lead_agent(state: AgentState) -> AgentState:
    """LangGraph node: synthesise all collected data into a final analyst report.

    Responsibilities:
        * Build a structured prompt incorporating the research summary,
          technical analysis summary, and recent news snippets.
        * Invoke the Gemini LLM to produce a professional multi-section
          markdown report.
        * Store the result in ``state['final_report']``.

    If the LLM call fails, a plain-text fallback report is generated from the
    raw summaries so that the pipeline always returns *something* to the caller.

    This node is a no-op when ``state['ticker_validation_error']`` is ``True``.

    Args:
        state: Current :class:`AgentState`.  Reads ``research_summary``,
               ``analyst_summary``, ``fundamentals``, ``technical_analysis``,
               and ``news_articles``.

    Returns:
        Updated :class:`AgentState` with ``final_report`` populated.
    """
    ticker = state["ticker"]
    errors = state.get("errors", [])

    # Skip if ticker validation failed
    if state.get("ticker_validation_error"):
        return state

    try:
        # Gather all information
        research = state.get("research_summary", "No research data available")
        analysis = state.get(
            "analyst_summary", "No technical analysis available")
        fundamentals = state.get("fundamentals", {})
        technical = state.get("technical_analysis", {})
        news = state.get("news_articles", [])

        # Use LLM to create comprehensive report
        prompt = f"""You are a senior financial analyst creating a comprehensive stock analysis report.

Based on the following data, create a professional, well-structured markdown report for {ticker}:

{research}

{analysis}

News Articles:
{chr(10).join([f"- {article['title']}: {article['snippet']}" for article in news[:5]])}

Create a report with these sections:
1. Executive Summary (brief overview)
2. Company Overview
3. Price Performance & Fundamentals
4. Technical Analysis
5. Recent News & Market Sentiment
6. Risk Factors
7. Conclusion

Be objective, data-driven, and professional. Use the actual numbers provided.
"""

        messages = [
            SystemMessage(content="You are an expert financial analyst."),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        final_report = response.content

        state["final_report"] = final_report
        state["messages"].append(AIMessage(content="Final report generated"))

    except Exception as e:
        error_msg = f"Team Lead Agent Error: {str(e)}"
        errors.append(error_msg)
        state["errors"] = errors

        # Create fallback report
        fallback_report = f"""# Stock Analysis Report: {ticker}

## Error Notice
An error occurred during report generation: {error_msg}

## Available Data
{state.get('research_summary', 'No data available')}
{state.get('analyst_summary', 'No data available')}
"""
        state["final_report"] = fallback_report
        state["messages"].append(
            AIMessage(content="Fallback report generated"))

    return state

# ==================== LANGGRAPH WORKFLOW ====================


def create_agent_workflow():
    """Build and compile the LangGraph multi-agent workflow.

    Defines a linear directed graph:

        researcher  →  analyst  →  team_lead  →  END

    Each node is a Python function conforming to the
    ``(AgentState) -> AgentState`` signature.  The compiled graph accepts an
    initial :class:`AgentState` dictionary and returns the final state after all
    nodes have executed.

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready to be invoked with
        ``graph.invoke(initial_state)``.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("team_lead", team_lead_agent)

    # Define edges (sequential flow)
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "team_lead")
    workflow.add_edge("team_lead", END)

    return workflow.compile()


# Initialize workflow
agent_workflow = create_agent_workflow()

# ==================== PDF GENERATION ====================


def generate_pdf_report(ticker: str, report_content: str, stock_data: Dict) -> str:
    """Render the markdown analyst report as a PDF file using ReportLab.

    Converts the markdown-formatted *report_content* string into a
    ReportLab ``Platypus`` document.  The following markdown constructs are
    handled:

    * ``# / ## / ###`` headings → ``Heading1 / Heading2 / Heading3`` styles.
    * ``**bold**`` inline markup → ``<b>`` tags.
    * ``- `` / ``* `` list items → bullet-prefixed Normal paragraphs.
    * Plain text → Normal style paragraphs.

    Special XML characters (``&``, ``<``, ``>``, ``"``, ``'``) in all text
    content are escaped before being passed to ReportLab to prevent parse
    errors.

    The output file is saved to the ``reports/`` sub-directory (created
    automatically if absent) with the naming convention::

        stock_report_<TICKER>_<YYYYMMDD_HHMMSS>.pdf

    Args:
        ticker:         Upper-case ticker symbol, used in the filename.
        report_content: Full markdown text of the analyst report.
        stock_data:     Raw stock data dictionary (currently unused but
                        reserved for future chart embedding).

    Returns:
        Relative path to the generated PDF file (e.g.
        ``'reports/stock_report_AAPL_20260303_120000.pdf'``).

    Raises:
        Exception: If ReportLab fails to build the PDF for any reason.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_report_{ticker}_{timestamp}.pdf"
        filepath = os.path.join("reports", filename)

        # Create reports directory if it doesn't exist
        os.makedirs("reports", exist_ok=True)

        # Create PDF
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        story.append(
            Paragraph(f"Multi-Agent Financial Analysis System Report: {ticker}", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Timestamp
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        # Helper function to escape XML/HTML special characters
        def escape_text(text: str) -> str:
            """Escape special characters for ReportLab Paragraph"""
            return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&apos;'))

        # Convert markdown to PDF paragraphs (simplified)
        lines = report_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1 * inch))
                continue

            if line.startswith('# '):
                text = escape_text(line.replace('# ', ''))
                story.append(Paragraph(text, styles['Heading1']))
            elif line.startswith('## '):
                text = escape_text(line.replace('## ', ''))
                story.append(Paragraph(text, styles['Heading2']))
            elif line.startswith('### '):
                text = escape_text(line.replace('### ', ''))
                story.append(Paragraph(text, styles['Heading3']))
            elif '**' in line:
                # Handle bold text
                parts = line.split('**')
                formatted = ''
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # Odd indices are bold
                        formatted += f'<b>{escape_text(part)}</b>'
                    else:
                        formatted += escape_text(part)
                story.append(Paragraph(formatted, styles['Normal']))
            elif line.startswith('- ') or line.startswith('* '):
                # Bullet points
                text = escape_text(line[2:])
                story.append(Paragraph(f'• {text}', styles['Normal']))
            else:
                text = escape_text(line)
                story.append(Paragraph(text, styles['Normal']))

            story.append(Spacer(1, 0.1 * inch))

        # Build PDF
        doc.build(story)

        return filepath

    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")

# ==================== API ENDPOINTS ====================


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """Run the full multi-agent analysis pipeline for a given stock ticker.

    Initialises a fresh :class:`AgentState`, invokes the compiled LangGraph
    workflow (Researcher → Analyst → Team Lead), and packages the results into
    an :class:`AnalysisResponse`.  A PDF report is also generated as a
    side-effect.

    Args:
        request: :class:`AnalysisRequest` containing the ticker symbol.

    Returns:
        :class:`AnalysisResponse` with the markdown report, the last 60 days
        of OHLCV data, PDF generation status, and the PDF download path.

    Raises:
        HTTPException(404): When the ticker symbol is not recognised.
        HTTPException(500): When the pipeline fails without producing a report.
    """
    ticker = request.ticker.upper()

    try:
        # Initialize state
        initial_state: AgentState = {
            "ticker": ticker,
            "messages": [HumanMessage(content=f"Analyze stock: {ticker}")],
            "stock_price_data": None,
            "fundamentals": None,
            "news_articles": None,
            "research_summary": None,
            "technical_analysis": None,
            "analyst_summary": None,
            "final_report": None,
            "errors": [],
            "ticker_validation_error": None
        }

        # Run agent workflow
        final_state = agent_workflow.invoke(initial_state)

        # Check for ticker validation error first
        if final_state.get("ticker_validation_error"):
            error_message = final_state.get(
                "errors", ["Invalid ticker symbol"])[0]
            raise HTTPException(
                status_code=404,
                detail=error_message
            )

        # Check for critical errors
        if final_state.get("errors") and not final_state.get("final_report"):
            error_message = '; '.join(final_state['errors'])
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {error_message}"
            )

        # Prepare stock data for charting
        stock_data_list = []
        if final_state.get("stock_price_data"):
            historical = final_state["stock_price_data"]["historical_data"]
            for record in historical[-60:]:  # Last 60 days
                stock_data_list.append(StockDataPoint(
                    date=record['Date'].strftime(
                        '%Y-%m-%d') if isinstance(record['Date'], datetime) else str(record['Date']),
                    open=float(record['Open']),
                    high=float(record['High']),
                    low=float(record['Low']),
                    close=float(record['Close']),
                    volume=int(record['Volume'])
                ))

        # Generate PDF
        pdf_status = "Success"
        pdf_path = None
        try:
            pdf_path = generate_pdf_report(
                ticker,
                final_state.get("final_report", ""),
                final_state.get("stock_price_data", {})
            )
        except Exception as e:
            pdf_status = f"Failed: {str(e)}"

        return AnalysisResponse(
            summary_report=final_state.get(
                "final_report", "Report generation failed"),
            stock_data=stock_data_list,
            pdf_status=pdf_status,
            pdf_path=pdf_path,
            ticker=ticker
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        )


@app.get("/download/{filename:path}")
async def download_pdf(filename: str):
    """Serve a previously generated PDF report as a file download.

    Accepts an optional ``reports/`` path prefix in *filename* and strips it
    before resolving the absolute path, so both ``'reports/foo.pdf'`` and
    ``'foo.pdf'`` are valid.

    Args:
        filename: Filename (or relative path) of the PDF to download.

    Returns:
        :class:`~fastapi.responses.FileResponse` with
        ``Content-Type: application/pdf``.

    Raises:
        HTTPException(404): If the requested file does not exist on disk.
    """
    # Remove 'reports/' prefix if present
    if filename.startswith("reports/"):
        filename = filename.replace("reports/", "", 1)

    filepath = os.path.join("reports", filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=os.path.basename(filename)
    )


@app.get("/health")
async def health_check():
    """Return service health status.

    Useful for load-balancer probes and uptime monitoring.  Reports whether a
    Google API key has been configured without exposing the key itself.

    Returns:
        JSON object with ``status``, current ``timestamp``, and
        ``gemini_configured`` boolean.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "gemini_configured": bool(GOOGLE_API_KEY)
    }


@app.get("/")
async def root():
    """Return basic API metadata and available endpoint listing.

    Returns:
        JSON object describing the service name, version, and endpoint paths.
    """
    return {
        "message": "Multi-Agent Financial Analysis System API",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/analyze (POST)",
            "download": "/download/{filename} (GET)",
            "health": "/health (GET)"
        }
    }

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
