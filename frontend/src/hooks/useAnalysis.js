import { useState, useCallback } from "react";
import { analyzeStock } from "../api/client";

/**
 * Encapsulates the full analyze → result lifecycle.
 * Returns state and the trigger function so pages stay clean.
 */
export function useAnalysis() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const analyze = useCallback(async (ticker) => {
    if (!ticker.trim()) {
      setError("Please enter a ticker symbol");
      return;
    }

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const result = await analyzeStock(ticker.toUpperCase());
      setData(result);
    } catch (err) {
      let msg = err.message || "Analysis failed. Please try again.";
      if (err.status === 404 && !msg.includes("Invalid ticker")) {
        msg = `Invalid ticker symbol '${ticker.toUpperCase()}'. Please check and try again.`;
      } else if (err.status === 401) {
        msg = "Session expired. Please log in again.";
      } else if (err.status === 500) {
        msg = `Server error: ${msg}`;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { loading, error, data, analyze, reset };
}
