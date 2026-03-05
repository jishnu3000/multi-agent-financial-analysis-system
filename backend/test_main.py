"""
Test suite for the Multi-Agent Financial Analysis System API.

Each test case targets a distinct layer of the application:
  1. Root endpoint – routing and response schema.
  2. Health check  – environment / configuration reporting.
  3. Input validation – Pydantic rejects a malformed /register payload.
  4. Auth guard     – protected routes reject requests with no JWT token.
  5. File serving   – /download returns 404 for a non-existent PDF.

The five tests above require no live database, no LLM, and no external
network calls, so they run reliably in any CI environment.

Run with:
    pytest test_main.py -v
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ==========================================
# TEST CASE 1: Root Endpoint Schema
# ==========================================

def test_root_endpoint_schema():
    """
    GET /  →  200
    Verifies that the gateway is reachable and that the response carries
    the expected API metadata: a message string, a version field, and an
    endpoints dictionary containing all six documented routes.
    """
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Multi-Agent Financial Analysis System API"
    assert data["version"] == "1.0.0"

    expected_keys = {"register", "login",
                     "analyze", "history", "download", "health"}
    assert expected_keys == set(data["endpoints"].keys()), (
        f"Unexpected endpoint keys: {set(data['endpoints'].keys())}"
    )


# ==========================================
# TEST CASE 2: Health Check Response Fields
# ==========================================

def test_health_check_response_fields():
    """
    GET /health  →  200
    Confirms all three mandatory fields are present with the correct types:
      • status             must equal "healthy"
      • timestamp          must be a non-empty string (ISO-8601 datetime)
      • gemini_configured  must be a boolean (True when GOOGLE_API_KEY is set)
    """
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert isinstance(data["timestamp"], str) and data["timestamp"], (
        "timestamp must be a non-empty ISO-8601 string"
    )
    assert isinstance(data["gemini_configured"], bool), (
        "gemini_configured must be a boolean"
    )


# ==========================================
# TEST CASE 3: Registration Input Validation
# ==========================================

def test_register_rejects_short_username():
    """
    POST /register  →  422  (Pydantic validation error)
    The UserCreate schema enforces username min_length=3 and
    password min_length=6.  Sending a 2-character username must be
    rejected before the request ever reaches the database layer.
    """
    payload = {"username": "ab", "password": "securepassword"}
    response = client.post("/register", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for short username, got {response.status_code}"
    )

    # FastAPI wraps Pydantic errors in a 'detail' list
    errors = response.json()["detail"]
    assert isinstance(errors, list) and len(errors) > 0, (
        "Response should contain a non-empty validation error list"
    )


# ==========================================
# TEST CASE 4: Protected Route Auth Guard
# ==========================================

def test_history_endpoint_requires_authentication():
    """
    GET /history  →  401  (no Authorization header supplied)
    The /history route depends on get_current_user which uses
    OAuth2PasswordBearer.  Without a valid Bearer token the dependency
    raises HTTP 401 before any database interaction occurs.
    """
    response = client.get("/history")

    assert response.status_code == 401, (
        f"Expected 401 Unauthorised, got {response.status_code}"
    )

    data = response.json()
    assert "detail" in data, "401 response must include a 'detail' field"


# ==========================================
# TEST CASE 5: PDF Download – File Not Found
# ==========================================

def test_download_nonexistent_pdf_returns_404():
    """
    GET /download/<filename>  →  404
    The /download route checks os.path.exists before serving the file.
    A deliberately random filename must trigger a 404 Not Found without
    raising an unhandled server error (500).
    """
    response = client.get("/download/this_report_does_not_exist_xyz.pdf")

    assert response.status_code == 404, (
        f"Expected 404 for missing PDF, got {response.status_code}"
    )

    data = response.json()
    assert data.get("detail") == "PDF not found", (
        f"Expected detail 'PDF not found', got: {data.get('detail')}"
    )
