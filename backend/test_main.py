from fastapi.testclient import TestClient
from main import app  # Imports your FastAPI instance from main.py

# Initialize the TestClient
client = TestClient(app)

# ==========================================
# TEST CASE 1: Root Endpoint Availability
# ==========================================


def test_read_root():
    """Test if the API gateway is up and routing correctly."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()[
        "message"] == "Multi-Agent Financial Analysis System API"
    assert "endpoints" in response.json()

# ==========================================
# TEST CASE 2: Health Check & Environment
# ==========================================


def test_health_check():
    """Test if the server is healthy and Gemini API key is configured."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    # Proves the environment variables (.env) are loaded properly
    assert data["gemini_configured"] is True

# ==========================================
# TEST CASE 3: Agent Error Handling (Invalid Ticker)
# ==========================================


def test_analyze_invalid_ticker():
    """
    Test the LangGraph Agent's ability to catch a fake ticker,
    skip the analysis, and return a clean 404 error.
    """
    # Send a deliberately fake ticker
    payload = {"ticker": "FAKE_XYZ_123"}
    response = client.post("/analyze", json=payload)

    # We expect a 404 Not Found, not a 500 Server Crash
    assert response.status_code == 404

    # Check if the UI gets the correct error message from the Researcher Agent
    error_detail = response.json()["detail"]
    assert "Invalid ticker symbol" in error_detail
