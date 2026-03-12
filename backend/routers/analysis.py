"""
Stock analysis routes: /analyze, /history, and /download.
"""

import os
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage

from core.database import history_collection
from core.security import get_current_user
from models.analysis import AnalysisRequest, AnalysisResponse, StockDataPoint
from services.pdf_generator import generate_pdf_report
from services.workflow import agent_workflow

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(
    request: AnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run the full multi-agent analysis pipeline for a given ticker.

    Executes the Researcher → Analyst → Team Lead LangGraph workflow, then
    generates a PDF report and persists the analysis to MongoDB.

    Args:
        request:      :class:`~models.analysis.AnalysisRequest` with the ticker.
        current_user: Injected by :func:`~core.security.get_current_user`.

    Returns:
        :class:`~models.analysis.AnalysisResponse`.

    Raises:
        HTTPException(404): Invalid ticker symbol.
        HTTPException(500): Any other pipeline failure.
    """
    ticker = request.ticker.upper()

    try:
        initial_state = {
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
            "ticker_validation_error": None,
        }

        final_state = agent_workflow.invoke(initial_state)

        if final_state.get("ticker_validation_error"):
            raise HTTPException(
                status_code=404,
                detail=final_state.get("errors", ["Invalid ticker symbol"])[0],
            )

        if final_state.get("errors") and not final_state.get("final_report"):
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {'; '.join(final_state['errors'])}",
            )

        # Detect silent data-fetch failure: researcher errors ran but left
        # stock_price_data empty, producing an N/A-filled LLM report.
        if final_state.get("stock_price_data") is None and final_state.get("errors"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Unable to fetch market data for "
                    f"'{ticker}'. "
                    f"Detail: {'; '.join(final_state['errors'])}"
                ),
            )

        # Build OHLCV list for charting
        stock_data_list: list[StockDataPoint] = []
        if final_state.get("stock_price_data"):
            for record in final_state["stock_price_data"]["historical_data"][-60:]:
                stock_data_list.append(
                    StockDataPoint(
                        date=(
                            record["Date"].strftime("%Y-%m-%d")
                            if isinstance(record["Date"], datetime)
                            else str(record["Date"])
                        ),
                        open=float(record["Open"]),
                        high=float(record["High"]),
                        low=float(record["Low"]),
                        close=float(record["Close"]),
                        volume=int(record["Volume"]),
                    )
                )

        # Generate PDF
        pdf_status = "Success"
        pdf_path = None
        try:
            pdf_path = generate_pdf_report(
                ticker,
                final_state.get("final_report", ""),
                final_state.get("stock_price_data") or {},
                final_state.get("fundamentals") or {},
                final_state.get("technical_analysis") or {},
            )
        except Exception as e:
            pdf_status = f"Failed: {e}"

        # Persist to history
        history_collection.insert_one(
            {
                "user_id": str(current_user["_id"]),
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "summary_report": final_state.get("final_report", ""),
                "pdf_path": pdf_path,
                "pdf_status": pdf_status,
            }
        )

        return AnalysisResponse(
            summary_report=final_state.get(
                "final_report", "Report generation failed"),
            stock_data=stock_data_list,
            pdf_status=pdf_status,
            pdf_path=pdf_path,
            ticker=ticker,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {e}\n{traceback.format_exc()}",
        )


@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    """Return the 50 most-recent analyses for the authenticated user.

    Args:
        current_user: Injected by :func:`~core.security.get_current_user`.

    Returns:
        List of history documents (``_id`` serialised as string).
    """
    history = list(
        history_collection.find({"user_id": str(current_user["_id"])})
        .sort("timestamp", -1)
        .limit(50)
    )
    for item in history:
        item["_id"] = str(item["_id"])
    return history


@router.delete("/history/{item_id}")
async def delete_history_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a single history entry belonging to the authenticated user.

    Args:
        item_id:      The ``_id`` string of the history document.
        current_user: Injected by :func:`~core.security.get_current_user`.

    Returns:
        ``{"message": "Deleted"}`` on success.

    Raises:
        HTTPException(404): If the document is not found or does not belong to this user.
    """
    from bson import ObjectId

    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid history item ID")

    result = history_collection.delete_one(
        {"_id": oid, "user_id": str(current_user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="History item not found")

    return {"message": "Deleted"}


@router.get("/download/{filename:path}")
async def download_pdf(filename: str):
    """Serve a previously generated PDF report.

    Accepts an optional ``reports/`` prefix so both ``reports/foo.pdf``
    and ``foo.pdf`` work as *filename*.

    Args:
        filename: Filename or relative path of the PDF.

    Returns:
        :class:`~fastapi.responses.FileResponse` (``application/pdf``).

    Raises:
        HTTPException(404): If the file does not exist.
    """
    if filename.startswith("reports/"):
        filename = filename.replace("reports/", "", 1)

    filepath = os.path.join("reports", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=os.path.basename(filename),
    )
