import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Recommendation, RunStatusResponse } from "@/lib/types";

const POLL_MS = 1000;

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

export function useRunHistory() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
    staleTime: 10_000,
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

export function useCompare(
  runId: string | null,
  aId: string | null,
  bId: string | null,
) {
  return useQuery({
    queryKey: ["compare", runId, aId, bId],
    queryFn: () => api.getComparison(runId as string, aId as string, bId as string),
    enabled: Boolean(runId && aId && bId),
    staleTime: Infinity,
    retry: 0,
  });
}

export function useInterviewScript(candidateId: string | null) {
  return useQuery({
    queryKey: ["interview-script", candidateId],
    queryFn: () => api.getInterviewScript(candidateId as string),
    enabled: Boolean(candidateId),
    staleTime: Infinity,
  });
}

export function useNotes(candidateId: string | null) {
  return useQuery({
    queryKey: ["notes", candidateId],
    queryFn: () => api.getNotes(candidateId as string),
    enabled: Boolean(candidateId),
  });
}

export function useAddNote(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { body: string; author: string }) =>
      api.addNote(candidateId, input.body, input.author),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes", candidateId] });
    },
  });
}

export function usePatchDecision(candidateId: string, runId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { recommendation: Recommendation; rationale: string }) =>
      api.patchDecision(candidateId, input.recommendation, input.rationale),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
    },
  });
}


export function useCancelRun(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.cancelRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["events", runId] });
    },
  });
}

export function useStartRun(onStarted: (runId: string) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      mode: "replay" | "live";
      jd?: File | null;
      jdText?: string;
      resumes?: File[];
      source?: "upload" | "test";
    }) =>
      api.startRun(input.mode, {
        jd: input.jd,
        jdText: input.jdText,
        resumes: input.resumes,
        source: input.source,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["run", data.run_id] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      onStarted(data.run_id);
    },
  });
}
