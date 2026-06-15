import type {
  AuditExport,
  CandidateComparison,
  CandidateNote,
  DecisionEvent,
  EvalResultSummary,
  HealthResponse,
  HumanOverride,
  InterviewScriptResponse,
  Recommendation,
  RunCreateResponse,
  RunListItem,
  RunStatusResponse,
  TestDataManifest,
} from "@/lib/types";

export class ApiError extends Error {
  code: string;
  httpStatus: number;

  constructor(code: string, message: string, httpStatus: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.httpStatus = httpStatus;
  }

  get display(): string {
    return `${this.code}: ${this.message}`;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    const detail = body?.error;
    if (detail?.code) {
      return new ApiError(detail.code, detail.message ?? "", response.status);
    }
  } catch {
    /* fall through to a plain HTTP error */
  }
  return new ApiError("http_error", `HTTP ${response.status}`, response.status);
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

async function sendJson<T>(
  path: string,
  method: "POST" | "PATCH",
  body: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export const api = {
  health(): Promise<HealthResponse> {
    return getJson<HealthResponse>("/health");
  },

  getRun(runId: string): Promise<RunStatusResponse> {
    return getJson<RunStatusResponse>(`/api/runs/${runId}`);
  },

  listRuns(limit = 30): Promise<RunListItem[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    return getJson<RunListItem[]>(`/api/runs?${params.toString()}`);
  },

  getEvents(runId: string): Promise<DecisionEvent[]> {
    return getJson<DecisionEvent[]>(`/api/runs/${runId}/events`);
  },

  getComparison(
    runId: string,
    aId: string,
    bId: string,
  ): Promise<CandidateComparison> {
    const params = new URLSearchParams({ a: aId, b: bId });
    return getJson<CandidateComparison>(
      `/api/runs/${runId}/compare?${params.toString()}`,
    );
  },

  getEvals(): Promise<EvalResultSummary[]> {
    return getJson<EvalResultSummary[]>("/api/evals");
  },

  getInterviewScript(candidateId: string): Promise<InterviewScriptResponse> {
    return getJson<InterviewScriptResponse>(
      `/api/candidates/${candidateId}/interview-script`,
    );
  },

  getNotes(candidateId: string): Promise<CandidateNote[]> {
    return getJson<CandidateNote[]>(`/api/candidates/${candidateId}/notes`);
  },

  addNote(
    candidateId: string,
    body: string,
    author: string,
  ): Promise<CandidateNote> {
    return sendJson<CandidateNote>(
      `/api/candidates/${candidateId}/notes`,
      "POST",
      { body, author },
    );
  },

  patchDecision(
    candidateId: string,
    recommendation: Recommendation,
    rationale: string,
  ): Promise<HumanOverride> {
    return sendJson<HumanOverride>(
      `/api/candidates/${candidateId}/decision`,
      "PATCH",
      { recommendation, rationale },
    );
  },

  // audit-export returns a typed envelope on 409/422 too; the caller decides.
  async getAuditExport(runId: string): Promise<AuditExport> {
    return getJson<AuditExport>(`/api/runs/${runId}/audit-export`);
  },

  auditExportUrl(runId: string): string {
    return `/api/runs/${runId}/audit-export`;
  },

  getTestDataManifest(): Promise<TestDataManifest> {
    return getJson<TestDataManifest>("/api/test-data");
  },

  async startRun(
    mode: "replay" | "live",
    options: {
      jd?: File | null;
      jdText?: string;
      resumes?: File[];
      source?: "upload" | "test";
    } = {},
  ): Promise<RunCreateResponse> {
    const form = new FormData();
    form.append("idempotency_key", crypto.randomUUID());
    if (options.jd) form.append("jd", options.jd, options.jd.name);
    else if (options.jdText) form.append("jd_text", options.jdText);
    for (const resume of options.resumes ?? []) {
      form.append("resumes", resume, resume.name);
    }
    const params = new URLSearchParams({ mode });
    if (options.source) params.set("source", options.source);
    const response = await fetch(`/api/runs?${params.toString()}`, {
      method: "POST",
      body: form,
    });
    if (!response.ok && response.status !== 202) {
      throw await parseError(response);
    }
    return (await response.json()) as RunCreateResponse;
  },
};
