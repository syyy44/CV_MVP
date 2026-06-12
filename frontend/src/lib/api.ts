import type {
  AuditExport,
  DecisionEvent,
  EvalResultSummary,
  HealthResponse,
  InterviewPreviewResponse,
  RunCreateResponse,
  RunStatusResponse,
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

export const api = {
  health(): Promise<HealthResponse> {
    return getJson<HealthResponse>("/health");
  },

  getRun(runId: string): Promise<RunStatusResponse> {
    return getJson<RunStatusResponse>(`/api/runs/${runId}`);
  },

  getEvents(runId: string): Promise<DecisionEvent[]> {
    return getJson<DecisionEvent[]>(`/api/runs/${runId}/events`);
  },

  getEvals(): Promise<EvalResultSummary[]> {
    return getJson<EvalResultSummary[]>("/api/evals");
  },

  getInterviewPreview(candidateId: string): Promise<InterviewPreviewResponse> {
    return getJson<InterviewPreviewResponse>(
      `/api/candidates/${candidateId}/interview/preview`,
    );
  },

  // audit-export returns a typed envelope on 409/422 too; the caller decides.
  async getAuditExport(runId: string): Promise<AuditExport> {
    return getJson<AuditExport>(`/api/runs/${runId}/audit-export`);
  },

  auditExportUrl(runId: string): string {
    return `/api/runs/${runId}/audit-export`;
  },

  async startRun(
    mode: "replay" | "live",
    options: { jd?: File | null; resumes?: File[] } = {},
  ): Promise<RunCreateResponse> {
    const form = new FormData();
    form.append("idempotency_key", crypto.randomUUID());
    if (options.jd) form.append("jd", options.jd, options.jd.name);
    for (const resume of options.resumes ?? []) {
      form.append("resumes", resume, resume.name);
    }
    const response = await fetch(`/api/runs?mode=${mode}`, {
      method: "POST",
      body: form,
    });
    if (!response.ok && response.status !== 202) {
      throw await parseError(response);
    }
    return (await response.json()) as RunCreateResponse;
  },
};
