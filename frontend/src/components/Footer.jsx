import React from "react";

export default function Footer() {
  return (
    <footer className="bg-slate-800/50 backdrop-blur-sm border-t border-slate-700 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
        <p className="text-center text-slate-400 text-sm">
          Multi-Agent Stock Analysis &copy; {new Date().getFullYear()} | Powered
          by LangGraph &amp; OpenAI
        </p>
      </div>
    </footer>
  );
}
