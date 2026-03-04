import React, { useState } from "react";
import { useAnalysis } from "../hooks/useAnalysis";
import StockChart from "../components/StockChart";
import AnalysisReport from "../components/AnalysisReport";
import LoadingState from "../components/LoadingState";
import ErrorMessage from "../components/ErrorMessage";

export default function DashboardPage() {
  const [ticker, setTicker] = useState("");
  const { loading, error, data, analyze, reset } = useAnalysis();

  const handleSubmit = (e) => {
    e.preventDefault();
    analyze(ticker);
  };

  const handleTickerChange = (e) => {
    setTicker(e.target.value.toUpperCase());
    if (error) reset();
  };

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1">
      {/* Input Card */}
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl shadow-2xl p-8 mb-8 border border-slate-700">
        <h2 className="text-2xl font-semibold text-white mb-6">
          Stock Analysis
        </h2>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col sm:flex-row gap-4"
        >
          <div className="flex-1">
            <label
              htmlFor="ticker"
              className="block text-sm font-medium text-slate-300 mb-2"
            >
              Ticker Symbol
            </label>
            <input
              id="ticker"
              type="text"
              value={ticker}
              onChange={handleTickerChange}
              placeholder="e.g., AAPL, GOOGL, TSLA"
              className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              disabled={loading}
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading || !ticker.trim()}
              className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin h-5 w-5"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Analyzing…
                </>
              ) : (
                <>
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                    />
                  </svg>
                  Generate Report
                </>
              )}
            </button>
          </div>
        </form>

        <ErrorMessage message={error} onDismiss={reset} />
        {loading && <LoadingState />}
      </div>

      {/* Results */}
      {data && (
        <div className="space-y-8">
          <StockChart ticker={data.ticker} stockData={data.stock_data} />
          <AnalysisReport
            summaryReport={data.summary_report}
            pdfStatus={data.pdf_status}
            pdfPath={data.pdf_path}
          />
        </div>
      )}
    </main>
  );
}
