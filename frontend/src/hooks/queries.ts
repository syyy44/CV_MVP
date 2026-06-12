import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RunStatusResponse } from "@/lib/types";

const POLL_MS = 2000;

function isActive(status: string | undefined): boolean {
  return status === "queued" || status === "running";
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 15000,
    retry: 0,
  });
}

export function useRun(runId: string | null) {
  return useQuery<RunStatusResponse>({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId as string),
    enabled: Boolean(runId),
    refetchInterval: (query) =>
      isActive(query.state.data?.run.status) ? POLL_MS : false,
  });
}

export function useEvents(runId: string | null, active: boolean) {
  return useQuery({
    queryKey: ["events", runId],
    queryFn: () => api.getEvents(runId as string),
    enabled: Boolean(runId),
    refetchInterval: active ? POLL_MS : false,
  });
}

export function useEvals(enabled: boolean) {
  return useQuery({
    queryKey: ["evals"],
    queryFn: () => api.getEvals(),
    enabled,
    retry: 0,
  });
}

export function useAuditExport(runId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["audit-export", runId],
    queryFn: () => api.getAuditExport(runId as string),
    enabled: Boolean(runId) && enabled,
    retry: 0,
  });
}

export function useInterviewPreview(candidateId: string | null) {
  return useQuery({
    queryKey: ["interview-preview", candidateId],
    queryFn: () => api.getInterviewPreview(candidateId as string),
    enabled: Boolean(candidateId),
    retry: 0,
  });
}

export function useStartRun(onStarted: (runId: string) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      mode: "replay" | "live";
      jd?: File | null;
      resumes?: File[];
    }) => api.startRun(input.mode, { jd: input.jd, resumes: input.resumes }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["run", data.run_id] });
      onStarted(data.run_id);
    },
  });
}
