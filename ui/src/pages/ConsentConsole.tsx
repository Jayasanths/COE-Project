import { Link, useParams } from "react-router-dom";
import { useConsent } from "../hooks/useApi";
import { EmptyState, ErrorState, Loading } from "../components/Primitives";
import { categoryLabel, formatDate, type ConsentRow } from "../lib/api";

/**
 * Page 3 — consent console (read-only).
 *
 * Active status comes from the API, which computes it with the same
 * `is_active` check the policy engine uses. Re-deriving it in the browser from
 * the raw dates would let the console and the engine disagree about whether a
 * record is live, and the console would be the more convincing of the two —
 * it looks like the source of truth even though it is a view.
 */

function StatusPill({ record }: { record: ConsentRow }) {
  if (record.active) {
    return (
      <span className="inline-flex rounded border border-shown/40 bg-shown/5 px-2 py-0.5 font-mono text-micro uppercase tracking-wider text-shown">
        Active
      </span>
    );
  }

  const reason = !record.granted
    ? "Declined"
    : record.revoked_at
      ? "Revoked"
      : record.expires_at
        ? "Expired"
        : "Inactive";

  return (
    <span className="inline-flex rounded border border-withheld/40 bg-withheld/5 px-2 py-0.5 font-mono text-micro uppercase tracking-wider text-withheld">
      {reason}
    </span>
  );
}

export default function ConsentConsole() {
  const { clientId } = useParams<{ clientId: string }>();
  const { data, isLoading, error } = useConsent(clientId);

  if (isLoading) return <Loading what="consent records" />;
  if (error) return <ErrorState error={error} what="the consent records" />;

  const consents = data?.consents ?? [];
  const activeCount = consents.filter((record) => record.active).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label-micro">Consent console</p>
          <h1 className="text-xl font-semibold tracking-tight">
            <span className="font-mono">{clientId}</span>
            {data?.pseudonym && <span className="text-muted"> · {data.pseudonym}</span>}
          </h1>
        </div>
        <Link to={`/brief/${clientId}`} className="pb-1 text-sm text-clinical hover:underline">
          Back to brief
        </Link>
      </div>

      <p className="text-sm text-muted">
        {activeCount} of {consents.length} records are currently active. Records are read-only
        here — consent is captured and withdrawn with the client, not in this interface.
      </p>

      {consents.length === 0 ? (
        <div className="card p-6">
          <EmptyState>
            No consent records on file for this client. With no records, every sensitivity
            category defaults to withheld.
          </EmptyState>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Consent records for client {clientId}</caption>
            <thead>
              <tr className="border-b border-rule bg-paper/60 text-left">
                <th scope="col" className="label-micro px-4 py-2.5">Category</th>
                <th scope="col" className="label-micro px-4 py-2.5">Role</th>
                <th scope="col" className="label-micro px-4 py-2.5">Purpose</th>
                <th scope="col" className="label-micro px-4 py-2.5">Granted</th>
                <th scope="col" className="label-micro px-4 py-2.5">Expires</th>
                <th scope="col" className="label-micro px-4 py-2.5">Revoked</th>
                <th scope="col" className="label-micro px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {consents.map((record, index) => (
                <tr
                  key={`${record.category}-${record.recipient_role}-${index}`}
                  className="border-b border-rule last:border-0"
                >
                  <td className="px-4 py-2.5 font-medium">{categoryLabel(record.category)}</td>
                  <td className="px-4 py-2.5">{categoryLabel(record.recipient_role)}</td>
                  <td className="px-4 py-2.5 font-mono text-micro uppercase text-muted">
                    {record.purpose}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-muted">
                    {record.granted ? formatDate(record.granted_at) : "Declined"}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-muted">
                    {record.expires_at ? formatDate(record.expires_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-muted">
                    {record.revoked_at ? formatDate(record.revoked_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusPill record={record} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-sm text-muted">
        Consent is granted per topic, per role and per purpose. A record covering the
        psychiatrist does not permit disclosure to the counsellor, and revocation applies to
        every brief generated from that point on.
      </p>
    </div>
  );
}
