import React from "react";
import ReactMarkdown from "react-markdown";
import { downloadPDF } from "../api/client";

const mdComponents = {
  h1: ({ ...props }) => (
    <h1 className="text-3xl font-bold text-white mb-4 mt-6" {...props} />
  ),
  h2: ({ ...props }) => (
    <h2 className="text-2xl font-semibold text-blue-300 mb-3 mt-5" {...props} />
  ),
  h3: ({ ...props }) => (
    <h3 className="text-xl font-medium text-slate-200 mb-2 mt-4" {...props} />
  ),
  p: ({ ...props }) => (
    <p className="text-slate-300 mb-3 leading-relaxed" {...props} />
  ),
  ul: ({ ...props }) => (
    <ul
      className="list-disc list-inside text-slate-300 mb-3 space-y-1"
      {...props}
    />
  ),
  ol: ({ ...props }) => (
    <ol
      className="list-decimal list-inside text-slate-300 mb-3 space-y-1"
      {...props}
    />
  ),
  li: ({ ...props }) => <li className="text-slate-300" {...props} />,
  strong: ({ ...props }) => (
    <strong className="font-semibold text-white" {...props} />
  ),
  code: ({ ...props }) => (
    <code
      className="bg-slate-900 px-2 py-1 rounded text-blue-300 text-sm"
      {...props}
    />
  ),
};

/**
 * Renders the markdown report and an optional PDF download button.
 * @param {{ summaryReport: string, pdfStatus: string, pdfPath: string|null }} props
 */
export default function AnalysisReport({ summaryReport, pdfStatus, pdfPath }) {
  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl shadow-2xl p-8 border border-slate-700">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold text-white">Analysis Report</h2>

        {pdfStatus === "Success" && pdfPath && (
          <button
            onClick={() => downloadPDF(pdfPath)}
            className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 flex items-center space-x-2"
          >
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
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <span>Download PDF</span>
          </button>
        )}
      </div>

      <div className="prose prose-invert prose-slate max-w-none">
        <ReactMarkdown components={mdComponents}>{summaryReport}</ReactMarkdown>
      </div>

      {pdfStatus !== "Success" && (
        <div className="mt-4 p-3 bg-yellow-900/30 border border-yellow-700 rounded-lg">
          <p className="text-yellow-200 text-sm">PDF Generation: {pdfStatus}</p>
        </div>
      )}
    </div>
  );
}
