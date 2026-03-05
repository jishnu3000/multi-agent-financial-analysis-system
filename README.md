# Multi-Agent Financial Analysis System

An AI-powered stock analysis platform that uses a **LangGraph multi-agent pipeline** to research, analyse, and synthesise comprehensive investment reports for any publicly traded stock. Reports are rendered in the browser as formatted Markdown and can be exported as PDF.

---

## Features

- **3-Agent LangGraph Workflow**
  - **Researcher Agent** — fetches live OHLCV price data, fundamental metrics, and recent news
  - **Analyst Agent** — computes technical indicators (SMA-50, RSI-14, trend, support/resistance)
  - **Team Lead Agent** — synthesises all data into a structured Markdown report via Google Gemini
- **Interactive Price Chart** — 60-day OHLCV line chart with close, high, and low series
- **PDF Export** — professionally formatted report generated with ReportLab
- **Analysis History** — per-user archive of past reports with PDF download and delete
- **JWT Authentication** — secure register/login flow; all analysis endpoints are protected
- **Dark UI** — React + Tailwind CSS, fully responsive

---

## Tech Stack

### Backend

| Component           | Technology                                   |
| ------------------- | -------------------------------------------- |
| API Framework       | FastAPI                                      |
| Agent Orchestration | LangGraph                                    |
| LLM                 | Google Gemini 2.5 Flash Lite (via LangChain) |
| Stock Data          | yfinance                                     |
| News                | DuckDuckGo Search (ddgs)                     |
| PDF Generation      | ReportLab                                    |
| Database            | MongoDB (pymongo)                            |
| Authentication      | JWT (PyJWT) + bcrypt                         |
| Server              | Uvicorn                                      |

### Frontend

| Component          | Technology      |
| ------------------ | --------------- |
| Framework          | React 18 + Vite |
| Styling            | Tailwind CSS    |
| Routing            | React Router v7 |
| Charts             | Recharts        |
| Markdown Rendering | react-markdown  |

---

## Project Structure

```
industry-project/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── demo.py                 # Rich terminal demo
│   ├── requirements.txt
│   ├── core/
│   │   ├── config.py           # Environment-based settings
│   │   ├── database.py         # MongoDB client & collections
│   │   ├── llm.py              # Gemini LLM singleton
│   │   └── security.py         # Password hashing, JWT, auth dependency
│   ├── models/
│   │   ├── agent_state.py      # LangGraph shared state TypedDict
│   │   ├── analysis.py         # Pydantic request/response schemas
│   │   └── auth.py             # Pydantic auth schemas
│   ├── routers/
│   │   ├── analysis.py         # /analyze, /history, /download
│   │   ├── auth.py             # /register, /login
│   │   └── health.py           # /, /health
│   ├── services/
│   │   ├── workflow.py         # LangGraph agent definitions & compiled graph
│   │   ├── stock_data.py       # yfinance + DuckDuckGo data fetchers
│   │   ├── technical.py        # Technical indicator calculations
│   │   └── pdf_generator.py    # ReportLab PDF builder
│   └── reports/                # Generated PDF output (git-ignored)
└── frontend/
    ├── index.html
    ├── package.json
    └── src/
        ├── App.jsx
        ├── api/client.js       # Centralised fetch wrapper with JWT
        ├── components/         # Header, Footer, StockChart, AnalysisReport, …
        ├── context/
        │   └── AuthContext.jsx # Global auth state (localStorage)
        ├── hooks/
        │   └── useAnalysis.js  # Analyse lifecycle hook
        └── pages/              # DashboardPage, HistoryPage, LoginPage, RegisterPage
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **MongoDB** — Atlas cluster or local instance
- **Google API Key** — Gemini API key from [Google AI Studio](https://aistudio.google.com)

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd industry-project
```

### 2. Backend

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
MONGODB_URL=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/
JWT_SECRET_KEY=your_strong_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173
```

Start the backend server:

```bash
uvicorn main:app --reload
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173
```

---

## Usage

1. Open `http://localhost:5173` in your browser
2. **Register** a new account or **log in**
3. Enter a stock ticker symbol (e.g. `AAPL`, `GOOGL`, `TSLA`) on the Dashboard
4. Click **Generate Report** — the three agents will run sequentially (~30–60 seconds)
5. View the interactive price chart and AI-generated Markdown report
6. Download the PDF export using the **Download PDF** button
7. Revisit past reports from the **History** page

### Terminal Demo

A Rich-powered terminal demo is available for quick testing without the frontend:

```bash
cd backend
python demo.py
```

---

## API Endpoints

| Method   | Path                   | Auth | Description              |
| -------- | ---------------------- | ---- | ------------------------ |
| `GET`    | `/`                    | No   | API info                 |
| `GET`    | `/health`              | No   | Health check             |
| `POST`   | `/register`            | No   | Create user account      |
| `POST`   | `/login`               | No   | Obtain JWT token         |
| `POST`   | `/analyze`             | Yes  | Run multi-agent analysis |
| `GET`    | `/history`             | Yes  | Fetch analysis history   |
| `DELETE` | `/history/{id}`        | Yes  | Delete a history entry   |
| `GET`    | `/download/{filename}` | No   | Download a generated PDF |

---

## Running Tests

```bash
cd backend
pytest test_main.py -v
```

The test suite covers:

- Root endpoint availability
- Health check and environment configuration
- Invalid ticker error handling (404 vs 500)

---

## Environment Variables Reference

| Variable                      | Required | Default                 | Description                     |
| ----------------------------- | -------- | ----------------------- | ------------------------------- |
| `GOOGLE_API_KEY`              | Yes      | —                       | Gemini API key                  |
| `MONGODB_URL`                 | Yes      | —                       | MongoDB connection string       |
| `JWT_SECRET_KEY`              | Yes      | `fallback_secret_key`   | JWT signing secret              |
| `ALGORITHM`                   | No       | `HS256`                 | JWT algorithm                   |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No       | `30`                    | Token lifetime                  |
| `HOST`                        | No       | `0.0.0.0`               | Uvicorn bind host               |
| `PORT`                        | No       | `8000`                  | Uvicorn bind port               |
| `CORS_ORIGINS`                | No       | `http://localhost:5173` | Comma-separated allowed origins |
