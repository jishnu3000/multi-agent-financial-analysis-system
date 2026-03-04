import React from "react";
import { downloadPDF } from "../api/client";

/**
 * Displays a condensed list of past analysis records.
 * @param {{ items: Array, loading: boolean, error: string|null }} props
 */
export default function HistoryPanel({ items, loading, error }) {
  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="flex space-x-2">
          {[0, 150, 300].map((d) => (
            <div
              key={d}
              className="w-3 h-3 bg-blue-500 rounded-full animate-bounce"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-900/40 border border-red-700 rounded-lg text-red-200 text-sm">
        {error}
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <p className="text-slate-400 text-center py-12">
        No analyses yet. Head to the Dashboard to run your first report.
      </p>
    );
  }

  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li
          key={item._id}
          className="bg-slate-900/60 border border-slate-700 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <span className="text-lg font-bold text-white">
                {item.ticker}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  item.pdf_status === "Success"
                    ? "bg-green-900/60 text-green-300"
                    : "bg-yellow-900/60 text-yellow-300"
                }`}
              >
                {item.pdf_status === "Success" ? "PDF ready" : "No PDF"}
              </span>
            </div>
            <p className="text-slate-400 text-sm">
              {new Date(item.timestamp).toLocaleString()}
            </p>
            {item.summary_report && (
              <p className="text-slate-300 text-sm mt-2 line-clamp-2">
                {item.summary_report.replace(/[#*`]/g, "").slice(0, 180)}…
              </p>
            )}
          </div>

          {item.pdf_status === "Success" && item.pdf_path && (
            <button
              onClick={() => downloadPDF(item.pdf_path)}
              className="flex-shrink-0 px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm font-semibold rounded-lg transition flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Download PDF
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
