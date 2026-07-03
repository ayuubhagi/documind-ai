import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchBillingConfig,
  fetchUsage,
  getToken,
  openBillingPortal,
  startCheckout,
} from "../services/api";
import type { BillingConfig, UsageSummary } from "../types";

const FREE_FEATURES = ["1 document", "10 questions per day", "Cited answers", "Sample document"];
const PRO_FEATURES = [
  "Unlimited questions",
  "Up to 50 documents",
  "Search across all documents",
  "Priority speed",
];

export default function Pricing() {
  const isAuthed = Boolean(getToken());
  const [config, setConfig] = useState<BillingConfig | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchBillingConfig().then(setConfig).catch(() => setConfig(null));
    if (isAuthed) void fetchUsage().then(setUsage).catch(() => undefined);
  }, [isAuthed]);

  const price = config ? (config.pro_price_cents / 100).toFixed(2) : "6.99";
  const isPro = usage?.plan === "pro";

  const handleUpgrade = async () => {
    setError(null);
    setBusy(true);
    try {
      await startCheckout();
    } catch {
      setError("Couldn't start checkout. Please try again in a moment.");
      setBusy(false);
    }
  };

  const handleManage = async () => {
    setBusy(true);
    try {
      await openBillingPortal();
    } catch {
      setError("Couldn't open the billing portal. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link to="/" className="font-display text-2xl font-bold text-brand-400">
          DocuMind <span className="text-xs uppercase tracking-widest text-slate-500">AI</span>
        </Link>
        <Link to={isAuthed ? "/dashboard" : "/login"} className="btn-secondary">
          {isAuthed ? "Open app" : "Sign in"}
        </Link>
      </header>

      <section className="mx-auto max-w-3xl px-6 py-12 text-center">
        <h1 className="font-display text-4xl font-bold">Simple pricing</h1>
        <p className="mt-3 text-slate-400">Start free. Upgrade when you hit the limits.</p>

        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          <div className="card p-8 text-left">
            <h2 className="text-lg font-semibold">Free</h2>
            <p className="mt-2 font-display text-4xl font-bold">$0</p>
            <ul className="mt-6 space-y-3 text-sm text-slate-300">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <span className="text-slate-500">✓</span> {f}
                </li>
              ))}
            </ul>
            {!isAuthed && (
              <Link to="/register" className="btn-secondary mt-8 block w-full text-center">
                Get started
              </Link>
            )}
            {isAuthed && !isPro && (
              <p className="mt-8 text-center text-sm text-slate-500">Your current plan</p>
            )}
          </div>

          <div className="card border-brand-500/40 p-8 text-left ring-1 ring-brand-500/20">
            <h2 className="text-lg font-semibold text-brand-400">Pro</h2>
            <p className="mt-2 font-display text-4xl font-bold">
              ${price}
              <span className="text-base font-normal text-slate-400">/month</span>
            </p>
            <ul className="mt-6 space-y-3 text-sm text-slate-300">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <span className="text-brand-400">✓</span> {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <button className="btn-secondary mt-8 w-full" disabled={busy} onClick={() => void handleManage()}>
                Manage subscription
              </button>
            ) : isAuthed ? (
              <button
                className="btn-primary mt-8 w-full"
                disabled={busy || !config?.enabled}
                onClick={() => void handleUpgrade()}
              >
                {busy ? "Redirecting…" : config?.enabled ? "Upgrade to Pro" : "Coming soon"}
              </button>
            ) : (
              <Link to="/register" className="btn-primary mt-8 block w-full text-center">
                Start free, upgrade anytime
              </Link>
            )}
          </div>
        </div>

        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
        <p className="mt-8 text-xs text-slate-500">
          Payments handled by Stripe. Cancel anytime from the billing portal.
        </p>
      </section>
    </div>
  );
}
