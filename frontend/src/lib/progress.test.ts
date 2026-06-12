import { describe, expect, it } from "vitest";

import { buildProgressSnapshot, eventLabel } from "@/lib/progress";

function ts(minute: number, second = 0): string {
  return new Date(Date.UTC(2026, 5, 11, 12, minute, second)).toISOString();
}

describe("buildProgressSnapshot", () => {
  it("reports a pending rubric LLM call", () => {
    const snapshot = buildProgressSnapshot({
      run: { status: "running", started_at: ts(0), created_at: ts(0) },
      documents: [{ source_type: "resume", filename: "a.pdf" }],
      candidates: [],
      events: [
        {
          id: 1,
          event_type: "document_parsed",
          node_name: "ingest_files",
          timestamp: ts(0, 5),
        },
        {
          id: 2,
          event_type: "llm_call_started",
          node_name: "extract_jd_rubric",
          timestamp: ts(0, 10),
        },
      ],
      now: new Date(Date.UTC(2026, 5, 11, 12, 0, 40)),
    });
    expect(snapshot.pending_llm).toBe(true);
    expect(snapshot.headline).toContain("LLM");
    expect(snapshot.progress).toBeGreaterThan(0);
  });

  it("marks a candidate as in-flight and surfaces the name", () => {
    const candidateId = "cand-1";
    const snapshot = buildProgressSnapshot({
      run: { status: "running", started_at: ts(0), created_at: ts(0) },
      documents: [{ source_type: "resume", filename: "strong.pdf" }],
      candidates: [],
      events: [
        {
          id: 1,
          event_type: "rubric_extracted",
          node_name: "extract_jd_rubric",
          timestamp: ts(1),
        },
        {
          id: 2,
          event_type: "llm_call_started",
          node_name: "score_candidate",
          candidate_id: candidateId,
          timestamp: ts(2),
          metadata: { candidate_name: "沈洋" },
        },
        {
          id: 3,
          event_type: "candidate_profile_extracted",
          node_name: "extract_candidate_profile",
          candidate_id: candidateId,
          timestamp: ts(1, 30),
          metadata: { candidate_name: "沈洋" },
        },
      ],
      now: new Date(Date.UTC(2026, 5, 11, 12, 2, 30)),
    });
    expect(snapshot.pending_llm).toBe(true);
    expect(snapshot.headline).toContain("沈洋");
    expect(snapshot.candidate_rows[0].label).toBe("沈洋");
  });

  it("rolls up after rubric completion with no candidates done", () => {
    const snapshot = buildProgressSnapshot({
      run: { status: "running", started_at: ts(0), created_at: ts(0) },
      documents: [{ source_type: "resume", filename: "a.pdf" }],
      candidates: [],
      events: [
        {
          id: 1,
          event_type: "rubric_extracted",
          node_name: "extract_jd_rubric",
          timestamp: ts(1),
        },
      ],
      now: new Date(Date.UTC(2026, 5, 11, 12, 1, 10)),
    });
    expect(snapshot.pending_llm).toBe(false);
    expect(snapshot.completed_count).toBe(0);
  });
});

describe("eventLabel", () => {
  it("appends the validation error detail", () => {
    const label = eventLabel({
      event_type: "schema_validation_failed",
      node_name: "score_candidate",
      candidate_id: "cand-1",
      metadata: {
        errors: ["证据引用行号无效：line_no=99 不存在（有效范围 1 至 20）。"],
      },
    });
    expect(label).toContain("输出校验失败");
    expect(label).toContain("证据引用");
  });
});
