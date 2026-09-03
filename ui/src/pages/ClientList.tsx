import { Link } from "react-router-dom";
import { useClients } from "../hooks/useApi";
import { ErrorState, Loading, EmptyState } from "../components/Primitives";
import { formatDate } from "../lib/api";

/**
 * Page 1 — client list.
 *
 * Sorted server-side by red flags, then open high-priority actions. The list a
 * clinician sees first should be ordered by what will hurt someone soonest,
 * not alphabetically by pseudonym.
 */
export default function ClientList() {
  const { data, isLoading, error } = useClients();

  if (isLoading) return <Loading what="clients" />;
  if (error) return <ErrorState error={error} what="the client list" />;

  const clients = data?.clients ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Clients awaiting handover</h1>
        <p className="label-micro">{clients.length} on file</p>
      </div>

      {clients.length === 0 ? (
        <div className="card p-6">
          <EmptyState>
            No clients loaded. Run <code className="font-mono">make data</code> to generate the
            synthetic set, then restart the API.
          </EmptyState>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Clients awaiting handover, most urgent first
            </caption>
            <thead>
              <tr className="border-b border-rule bg-paper/60 text-left">
                <th scope="col" className="label-micro px-4 py-2.5">Client</th>
                <th scope="col" className="label-micro px-4 py-2.5">Pseudonym</th>
                <th scope="col" className="label-micro px-4 py-2.5">Discharged</th>
                <th scope="col" className="label-micro px-4 py-2.5 text-right">High priority</th>
                <th scope="col" className="label-micro px-4 py-2.5 text-right">Red flags</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr
                  key={client.client_id}
                  className="border-b border-rule last:border-0 hover:bg-paper/70"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/brief/${client.client_id}`}
                      className="font-mono font-medium text-clinical hover:underline"
                    >
                      {client.client_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">{client.pseudonym}</td>
                  <td className="px-4 py-2.5 font-mono text-muted">
                    {formatDate(client.discharge_date)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {client.open_high_priority || <span className="text-muted">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {client.red_flags > 0 ? (
                      <span className="font-semibold text-escalate">{client.red_flags}</span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-sm text-muted">
        Red flags are high-priority actions more than seven days overdue. They appear on every
        brief until they are resolved or reassigned.
      </p>
    </div>
  );
}
