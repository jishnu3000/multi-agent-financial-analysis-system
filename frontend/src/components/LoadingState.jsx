import React from "react";

/** Animated "agents are working" loading indicator. */
export default function LoadingState() {
  return (
    <div className="mt-6 p-6 bg-slate-900/50 rounded-lg border border-slate-700">
      <div className="flex items-center justify-center space-x-4">
        <div className="flex space-x-2">
          {[0, 150, 300].map((delay) => (
            <div
              key={delay}
              className="w-3 h-3 bg-blue-500 rounded-full animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>
        <p className="text-slate-300">Agents are working…</p>
      </div>
      <div className="mt-4 space-y-1 text-sm text-slate-400 text-center">
        <p>Researcher: Fetching stock data and news…</p>
        <p>Analyst: Calculating technical indicators…</p>
        <p>Team Lead: Synthesising comprehensive report…</p>
      </div>
    </div>
  );
}
