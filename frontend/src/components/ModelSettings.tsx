"use client";

import { useEffect, useState } from "react";

import { getBackendUrl } from "@/lib/config";

/**
 * Lets the user pick any LiteLLM model and paste that vendor's API key from
 * inside the app — no .env editing. The key is sent to the backend (which makes
 * the LLM calls) and never echoed back; the form only shows whether one is set.
 */
export function ModelSettings() {
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch(`${getBackendUrl()}config`)
      .then((r) => r.json())
      .then((d) => {
        setModel(d.model ?? "");
        setApiBase(d.api_base ?? "");
        setHasKey(Boolean(d.has_api_key));
      })
      .catch(() => setStatus("Backend not reachable"));
  }, []);

  const save = async () => {
    setStatus("Saving…");
    try {
      const body: Record<string, string> = { model, api_base: apiBase };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      const res = await fetch(`${getBackendUrl()}config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      const d = await res.json();
      setHasKey(Boolean(d.has_api_key));
      setApiKey("");
      setStatus("Saved ✓");
    } catch {
      setStatus("Save failed");
    }
  };

  const field = "w-full rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500";

  return (
    <div className="mt-6">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Model</p>

      <input
        value={model}
        onChange={(e) => { setModel(e.target.value); setStatus(""); }}
        placeholder="openrouter/anthropic/claude-sonnet-4-6"
        className={field}
        spellCheck={false}
      />

      <input
        type="password"
        value={apiKey}
        onChange={(e) => { setApiKey(e.target.value); setStatus(""); }}
        placeholder={hasKey ? "API key set — leave blank to keep" : "Paste any vendor API key"}
        className={`${field} mt-1.5`}
        spellCheck={false}
        autoComplete="off"
      />

      <input
        value={apiBase}
        onChange={(e) => { setApiBase(e.target.value); setStatus(""); }}
        placeholder="API base (optional, e.g. Ollama)"
        className={`${field} mt-1.5`}
        spellCheck={false}
      />

      <button
        onClick={save}
        className="mt-1.5 w-full rounded-lg bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-500"
      >
        {status || "Save model & key"}
      </button>

      <p className="mt-1 text-[10px] leading-tight text-slate-500">
        Any LiteLLM model works: <code>openai/gpt-4.1</code>, <code>gemini/gemini-2.5-pro</code>,
        <code> ollama/llama3</code>. One key field — routed to the right vendor automatically.
      </p>
    </div>
  );
}
