import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useBrief } from "../hooks/useApi";
import {
  Banner,
  DisclosureLedger,
  EmptyState,
  ErrorState,
  Loading,
  TierBadge,
} from "../components/Primitives";
import { ROLES, categoryLabel, formatDate, type RecipientRole } from "../lib/api";

/**
 * Page 2 — handover brief.
 *
 * Reading order is the point of this layout. Escalations and conflicts sit
 * above the summary, because a clinician skimming with two minutes to spare
 * reads top-down and stops early. Anything that could change how they open the
 * session has to appear before the prose, not after it.
 */
export default function BriefPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [role, setRole] = useState<RecipientRole>("counsellor");
  const [showExplanation, setShowExplanation] = useState(false);

  const { data: brief, isLoading, error } = useBrief(clientId, role);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label-micro">Handover brief</p>
          <h1 className="text-xl font-semibold tracking-tight">
            <span className="font-mono">{clientId}</span>
            {brief?.pseudonym && <span className="text-muted"> · {brief.pseudonym}</span>}
          </h1>
        </div>

        <div className="flex items-end gap-3">
          <label className="block">
            <span className="label-micro mb-1 block">Recipient role</span>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as RecipientRole)}
              className="rounded border border-rule bg-card px-3 py-1.5 text-sm"
            >
              {ROLES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <Link
            to={`/consent/${clientId}`}
            className="pb-2 text-sm text-clinical hover:underline"
          >
            Consent console
          </Link>
        </div>
      </div>

      {/* Changing the role recomputes the disclosure decision entirely — it is
          not a filter over an already-loaded brief. Saying so prevents the
          reader assuming they have seen "the" brief for this client. */}
      <p className="text-sm text-muted">
        Each role sees a different brief. Consent is granted per topic, per role.
      </p>

      {isLoading && <Loading what="the brief" />}
      {error && <ErrorState error={error} what="this brief" />}

      {brief && (
        <div className="space-y-4">
          {brief.escalation_flags.length > 0 && (
            <Banner tone="escalate" title="Escalation required before session">
              {brief.escalation_flags.map((flag) => (
                <p key={flag}>{flag}</p>
              ))}
            </Banner>
          )}

          {brief.conflict_notices.length > 0 && (
            <Banner tone="escalate" title="Conflicting records">
              {brief.conflicts.map((conflict) => (
                <div key={conflict.category} className="space-y-1">
                  <p>{conflict.notice}</p>
                  <ul className="ml-4 list-disc space-y-0.5 text-muted">
                    <li>{conflict.positive_text}</li>
                    <li>{conflict.negative_text}</li>
                  </ul>
                </div>
              ))}
            </Banner>
          )}

          {brief.withheld_count > 0 && (
            <Banner tone="withheld" title="Topics withheld under client consent">
              <p>{brief.withheld_notice}</p>
              {brief.consent_missing.length > 0 && (
                <p className="text-muted">
                  No consent record on file for{" "}
                  {brief.consent_missing.map(categoryLabel).join(", ")} — nobody has asked the
                  client. This is an administrative gap, not a refusal.
                </p>
              )}
            </Banner>
          )}

          <DisclosureLedger
            permitted={brief.permitted_categories}
            withheld={brief.withheld_categories}
            safetyFlagged={brief.explanation.why_withheld
              .filter((reason) => reason.is_safety_relevant)
              .map((reason) => reason.category)}
          />

          <section className="card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="label-micro">Summary</h2>
              <div className="flex items-center gap-2">
                <TierBadge tier={brief.tier} label={brief.tier_label} />
                <span className="font-mono text-micro text-muted">
                  {brief.word_count} words
                </span>
              </div>
            </div>

            <p className="mt-3 whitespace-pre-line text-[15px] leading-relaxed">
              {brief.summary}
            </p>

            {brief.uncertainty_note && (
              <p className="mt-3 border-t border-rule pt-3 text-sm italic text-muted">
                {brief.uncertainty_note}
              </p>
            )}
          </section>

          {brief.notifications.length > 0 && (
            <Banner tone="clinical" title="Notifications">
              {brief.notifications.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </Banner>
          )}

          <section className="card overflow-hidden">
            <div className="flex items-baseline justify-between border-b border-rule px-4 py-2.5">
              <h2 className="label-micro">Open actions</h2>
              <p className="font-mono text-micro text-muted">
                carried forward regardless of consent filtering
              </p>
            </div>

            {brief.actions.length === 0 ? (
              <div className="p-4">
                <EmptyState>No open actions recorded for this client.</EmptyState>
              </div>
            ) : (
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-rule bg-paper/60 text-left">
                    <th scope="col" className="label-micro px-4 py-2">Action</th>
                    <th scope="col" className="label-micro px-4 py-2">Owner</th>
                    <th scope="col" className="label-micro px-4 py-2">Due</th>
                    <th scope="col" className="label-micro px-4 py-2">Priority</th>
                    <th scope="col" className="label-micro px-4 py-2">Escalation</th>
                  </tr>
                </thead>
                <tbody>
                  {brief.actions.map((action) => (
                    <tr key={action.action_id} className="border-b border-rule last:border-0">
                      <td className="px-4 py-2.5">{action.description}</td>
                      <td className="px-4 py-2.5">
                        {action.owner_role}
                        <span className="block font-mono text-micro text-muted">
                          {action.owner_id}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-muted">
                        {formatDate(action.due_date)}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-micro uppercase">
                        {action.priority}
                      </td>
                      <td className="px-4 py-2.5">
                        {action.escalation_level === 0 ? (
                          <span className="text-muted">—</span>
                        ) : (
                          <span
                            className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-micro uppercase tracking-wider ${
                              action.escalation_level >= 3
                                ? "border-escalate/50 bg-escalate/5 text-escalate"
                                : "border-withheld/40 bg-withheld/5 text-withheld"
                            }`}
                            title={action.escalation_note}
                          >
                            L{action.escalation_level}
                            <span>{action.days_overdue}d overdue</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card p-5">
            <h2 className="label-micro">Goals</h2>
            {brief.goals.length === 0 ? (
              <p className="mt-2">
                <EmptyState>No active goals on file.</EmptyState>
              </p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm">
                {brief.goals.map((goal) => (
                  <li key={goal} className="flex gap-2">
                    <span aria-hidden="true" className="text-muted">
                      –
                    </span>
                    {goal}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <button
              type="button"
              onClick={() => setShowExplanation((open) => !open)}
              aria-expanded={showExplanation}
              className="flex w-full items-baseline justify-between px-5 py-3 text-left"
            >
              <span className="label-micro">Why this brief looks like this</span>
              <span className="font-mono text-micro text-clinical">
                {showExplanation ? "Hide" : "Show"}
              </span>
            </button>

            {showExplanation && (
              <div className="space-y-4 border-t border-rule px-5 py-4 text-sm">
                <p className="text-muted">{brief.explanation.summary}</p>

                <div>
                  <h3 className="label-micro text-shown">Shown</h3>
                  {brief.explanation.why_shown.length === 0 ? (
                    <p className="mt-1.5">
                      <EmptyState>
                        Nothing was disclosed to this role from the tagged content.
                      </EmptyState>
                    </p>
                  ) : (
                    <ul className="mt-1.5 space-y-1">
                      {brief.explanation.why_shown.map((reason) => (
                        <li key={reason.category}>{reason.detail}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h3 className="label-micro text-withheld">Withheld</h3>
                  {brief.explanation.why_withheld.length === 0 ? (
                    <p className="mt-1.5">
                      <EmptyState>Nothing was withheld from this role.</EmptyState>
                    </p>
                  ) : (
                    <ul className="mt-1.5 space-y-1.5">
                      {brief.explanation.why_withheld.map((reason) => (
                        <li key={reason.category}>
                          <span className="font-mono text-micro uppercase tracking-wider text-withheld">
                            {categoryLabel(reason.category)}
                          </span>
                          {reason.is_safety_relevant && (
                            <span className="ml-1.5 font-mono text-micro uppercase text-escalate">
                              safety-relevant
                            </span>
                          )}
                          <span className="block text-muted">{reason.detail}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {brief.degradation_reasons.length > 0 && (
                  <div>
                    <h3 className="label-micro">Fallback</h3>
                    <ul className="mt-1.5 space-y-1 font-mono text-micro text-muted">
                      {brief.degradation_reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="border-t border-rule pt-3 font-mono text-micro text-muted">
                  generated {formatDate(brief.generated_at)} · {brief.permitted_span_count}/
                  {brief.total_spans} spans permitted · {brief.provenance.length} provenance links
                </p>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
