import type { ReactNode } from "react";
import { categoryLabel } from "../lib/api";

/* ── Loading and error states ─────────────────────────────────────────────
 *
 * Both are written in the interface's voice and say what to do next. A
 * clinician who hits an error thirty seconds before a session needs to know
 * whether to wait or to go and find the paper file, and "Something went wrong"
 * answers neither.
 */

export function Loading({ what }: { what: string }) {
  return (
    <div className="card p-6">
      <p className="label-micro">Loading {what}</p>
    </div>
  );
}

export function ErrorState({ error, what }: { error: unknown; what: string }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="banner border-l-escalate">
      <p className="label-micro text-escalate">Could not load {what}</p>
      <p className="mt-1 text-sm">{message}</p>
      <p className="mt-2 text-sm text-muted">
        Check the API is running on port 8000. If it is, complete a paper handover
        before the session rather than proceeding without one.
      </p>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

/* ── Tier badge ───────────────────────────────────────────────────────────
 *
 * The tier is shown on every brief, not only degraded ones. A reader who only
 * ever sees a badge when something is wrong learns to ignore it; a reader who
 * always sees it learns to read it.
 */

const TIER_STYLES: Record<number, string> = {
  1: "border-clinical text-clinical",
  2: "border-muted text-muted",
  3: "border-withheld text-withheld",
  4: "border-escalate text-escalate",
};

export function TierBadge({ tier, label }: { tier: number; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-micro uppercase tracking-wider ${
        TIER_STYLES[tier] ?? TIER_STYLES[2]
      }`}
      title={label}
    >
      <span className="font-semibold">T{tier}</span>
      <span className="hidden sm:inline">{label.replace(/\s*\(tier \d\)$/, "")}</span>
    </span>
  );
}

/* ── Disclosure ledger ────────────────────────────────────────────────────
 *
 * Every sensitivity category that appeared in the notes, with its state, in one
 * strip above the summary.
 *
 * This exists because the harm this system addresses is not disclosure — it is
 * a brief that *looks complete*. Prose cannot convey absence: a reader has no
 * way to notice that trauma history is missing from three paragraphs. The
 * ledger makes the shape of the disclosure visible before the text is read, so
 * "there is something here I have not been told" is the first thing seen rather
 * than something inferred later, if at all.
 */

type LedgerState = "shown" | "withheld" | "flagged";

const LEDGER_STYLES: Record<LedgerState, string> = {
  shown: "border-shown/40 bg-shown/5 text-shown",
  withheld: "border-withheld/40 bg-withheld/5 text-withheld",
  flagged: "border-escalate/50 bg-escalate/5 text-escalate",
};

const LEDGER_GLYPH: Record<LedgerState, string> = {
  shown: "●",
  withheld: "○",
  flagged: "▲",
};

const LEDGER_TITLE: Record<LedgerState, string> = {
  shown: "Disclosed under active consent",
  withheld: "Withheld — content not shown",
  flagged: "Withheld, but safety-relevant — escalation raised",
};

export function DisclosureLedger({
  permitted,
  withheld,
  safetyFlagged,
}: {
  permitted: string[];
  withheld: string[];
  safetyFlagged: string[];
}) {
  const entries: { category: string; state: LedgerState }[] = [
    ...permitted.map((c) => ({ category: c, state: "shown" as const })),
    ...withheld.map((c) => ({
      category: c,
      state: safetyFlagged.includes(c) ? ("flagged" as const) : ("withheld" as const),
    })),
  ].sort((a, b) => a.category.localeCompare(b.category));

  if (entries.length === 0) {
    return (
      <div className="card p-4">
        <p className="label-micro">Disclosure ledger</p>
        <p className="mt-2 text-sm text-muted">
          No sensitivity-tagged content in the last three sessions.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="label-micro">Disclosure ledger</p>
        <p className="font-mono text-micro text-muted">
          {permitted.length} shown &middot; {withheld.length} withheld
        </p>
      </div>

      <ul className="mt-3 flex flex-wrap gap-1.5">
        {entries.map(({ category, state }) => (
          <li key={`${category}-${state}`}>
            <span
              className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-micro uppercase tracking-wider ${LEDGER_STYLES[state]}`}
              title={LEDGER_TITLE[state]}
            >
              <span aria-hidden="true">{LEDGER_GLYPH[state]}</span>
              {categoryLabel(category)}
              <span className="sr-only"> — {LEDGER_TITLE[state]}</span>
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 border-t border-rule pt-2 font-mono text-micro text-muted">
        ● disclosed &nbsp; ○ withheld &nbsp; ▲ withheld, safety-relevant
      </p>
    </div>
  );
}

/* ── Banners ─────────────────────────────────────────────────────────────── */

export function Banner({
  tone,
  title,
  children,
}: {
  tone: "withheld" | "escalate" | "clinical";
  title: string;
  children: ReactNode;
}) {
  const border =
    tone === "escalate"
      ? "border-l-escalate"
      : tone === "withheld"
        ? "border-l-withheld"
        : "border-l-clinical";
  const text =
    tone === "escalate" ? "text-escalate" : tone === "withheld" ? "text-withheld" : "text-clinical";

  return (
    <section className={`banner ${border}`} role={tone === "escalate" ? "alert" : undefined}>
      <p className={`label-micro ${text}`}>{title}</p>
      <div className="mt-1.5 space-y-1.5 text-sm">{children}</div>
    </section>
  );
}
