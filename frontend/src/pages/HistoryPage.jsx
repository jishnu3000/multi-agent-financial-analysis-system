import React, { useState, useEffect } from "react";
import { fetchHistory, deleteHistoryItem } from "../api/client";
import HistoryPanel from "../components/HistoryPanel";

export default function HistoryPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchHistory();
        if (!cancelled) setItems(data);
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load history");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1">
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl shadow-2xl p-8 border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-white">
            Analysis History
          </h2>
          {!loading && !error && items.length > 0 && (
            <span className="text-slate-400 text-sm">
              {items.length} report{items.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        <HistoryPanel
          items={items}
          loading={loading}
          error={error}
          onDelete={async (id) => {
            await deleteHistoryItem(id);
            setItems((prev) => prev.filter((item) => item._id !== id));
          }}
        />
      </div>
    </main>
  );
}
