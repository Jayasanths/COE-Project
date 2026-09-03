import { useQuery } from "@tanstack/react-query";
import { api, type RecipientRole } from "../lib/api";

export function useClients() {
  return useQuery({
    queryKey: ["clients"],
    queryFn: api.listClients,
    refetchInterval: 30000,
  });
}

export function useBrief(
  clientId: string | undefined,
  role: RecipientRole,
  tier?: number | null,
) {
  return useQuery({
    queryKey: ["brief", clientId, role, tier],
    queryFn: () => api.getBrief(clientId!, role, tier),
    enabled: Boolean(clientId),
  });
}

export function useConsent(clientId: string | undefined) {
  return useQuery({
    queryKey: ["consent", clientId],
    queryFn: () => api.getConsent(clientId!),
    enabled: Boolean(clientId),
  });
}
