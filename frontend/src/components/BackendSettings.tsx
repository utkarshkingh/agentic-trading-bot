"use client";

import { useEffect, useState } from "react";

import { getBackendUrl, setBackendUrl } from "@/lib/config";

/**
 * Lets the user point the app at a different backend at runtime. On desktop
 * this stays at the bundled localhost sidecar; on Android the user sets it to
 * their PC's LAN address (e.g. http://192.168.1.20:8000) or a hosted backend.
 * Saving persists the value and reloads so the agent reconnects.
 */
export function BackendSettings() {
  const [url, setUrl] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUrl(getBackendUrl());
  }, []);

  const handleSave = () => {
    setBackendUrl(url);
    setSaved(true);
    setTimeout(() => window.location.reload(), 400);
  };

  return (
    <div className="mt-6">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Backend</p>
      <input
        value={url}
        onChange={(e) => { setUrl(e.target.value); setSaved(false); }}
        placeholder="http://localhost:8000"
        className="w-full rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
        spellCheck={false}
      />
      <button
        onClick={handleSave}
        className="mt-1.5 w-full rounded-lg bg-slate-700 px-2 py-1 text-xs font-semibold text-slate-200 hover:bg-slate-600"
      >
        {saved ? "Saved — reloading…" : "Save & reconnect"}
      </button>
      <p className="mt-1 text-[10px] leading-tight text-slate-500">
        On mobile, set this to your PC&apos;s LAN address (e.g. http://192.168.x.x:8000).
      </p>
    </div>
  );
}
