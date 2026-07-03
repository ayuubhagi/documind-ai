import { useState } from "react";
import { Link } from "react-router-dom";

import { startCheckout } from "../services/api";

/** Inline paywall card, rendered in the flow (never a blocking modal). */
export default function UpgradeCard({ reason }: { reason: string }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const handleUpgrade = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await startCheckout();
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-brand-500/40 bg-brand-500/5 p-5">
      <p className="text-sm font-medium text-slate-200">{reason}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className="btn-primary text-sm" disabled={busy} onClick={() => void handleUpgrade()}>
          {busy ? "Redirecting…" : "Upgrade to Pro — $6.99/mo"}
        </button>
        <Link to="/pricing" className="text-sm text-slate-400 hover:text-slate-200">
          See what's included
        </Link>
      </div>
      {failed && (
        <p className="mt-2 text-xs text-red-400">Checkout didn't start — please try again.</p>
      )}
    </div>
  );
}
