import { describe, expect, it } from "vitest";

import { formatScriptMarkdown } from "@/lib/interview-script";
import type {
  InterviewQuestion,
  InterviewScriptResponse,
  ScriptQuestion,
} from "@/lib/types";

function q(
  question: string,
  difficulty: InterviewQuestion["difficulty"],
  redFlags: string[] = [],
  archetype: InterviewQuestion["archetype"] = "depth_probe",
  targetClaim = "",
  probes: string[] = [],
): InterviewQuestion {
  return {
    question,
    archetype,
    target_claim: targetClaim,
    competency: "能力",
    difficulty,
    follow_up_probes: probes,
    scoring_criteria: ["要点一", "要点二"],
    good_answer_signals: ["信号"],
    red_flags: redFlags,
  };
}

function sq(index: number, question: InterviewQuestion, minutes: number): ScriptQuestion {
  return { index, question, suggested_minutes: minutes };
}

function makeScript(
  overrides: Partial<InterviewScriptResponse> = {},
): InterviewScriptResponse {
  return {
    candidate_id: "c1",
    candidate_name: "测试",
    recommendation: "proceed",
    overall_score: 80,
    confidence: 0.9,
    confidence_band: "high",
    script_rule_version: "v3",
    suggested_duration_min: 31,
    must_ask: [
      sq(
        1,
        q(
          "senior q",
          "senior",
          ["r1"],
          "metric_validation",
          "成功率提升至 81.9%",
          ["baseline 是什么？", "评估集多大？"],
        ),
        8,
      ),
    ],
    follow_ups: [
      {
        question: "follow 1",
        ambiguity: "amb",
        what_to_listen_for: "listen",
        evidence_refs: [
          {
            document_id: "d",
            document_hash: "h",
            source_type: "resume",
            snippet: "证据片段",
            offset_status: "verified",
          },
        ],
      },
    ],
    optional: [sq(2, q("junior q", "junior"), 5)],
    verification_checklist: [],
    pass_criteria: "核实关键风险后可调整推荐结论。",
    ...overrides,
  };
}

describe("formatScriptMarkdown", () => {
  it("renders the §6.6 template header and sections", () => {
    const md = formatScriptMarkdown(makeScript());
    expect(md).toContain("# 面试脚本 — 测试");
    expect(md).toContain("岗位：本次筛选 · 推荐：通过 · 分数：80");
    expect(md).toContain("置信：高");
    expect(md).toContain("## 必问");
    expect(md).toContain("[口径核查 · 高级] senior q");
    expect(md).toContain("- 针对声明：成功率提升至 81.9%");
    expect(md).toContain("- 追问1：baseline 是什么？");
    expect(md).toContain("- 追问2：评估集多大？");
    expect(md).toContain("- 真做过的信号：信号");
    expect(md).toContain("- 背诵信号：r1");
    expect(md).toContain("- 建议时长：8 分钟");
    expect(md).toContain("## 模糊点追问");
    expect(md).toContain("（依据：证据片段）");
    expect(md).toContain("## 选问（时间充裕）");
    expect(md).toContain("[技术深挖] junior q");
    expect(md).not.toContain("## 待核实");
  });

  it("appends the verification section for hold candidates", () => {
    const md = formatScriptMarkdown(
      makeScript({
        recommendation: "hold",
        confidence_band: "medium",
        verification_checklist: [
          { item: "请说明异常指令来源", reason: "injection", evidence_refs: [] },
          { item: "follow 1", reason: "follow_up", evidence_refs: [] },
        ],
        pass_criteria:
          "若以上 2 条核实均有可信、可核对简历或项目的答复，可将推荐调整为「通过」；否则维持「待定」。",
      }),
    );
    expect(md).toContain("置信：中");
    expect(md).toContain("## 待核实（通过前）");
    expect(md).toContain("1. 请说明异常指令来源");
    expect(md).toContain("2. follow 1");
    expect(md).toContain("判定：若以上 2 条核实均有可信、可核对简历或项目的答复");
  });

  it("strips trailing periods before joining clauses", () => {
    const md = formatScriptMarkdown(
      makeScript({
        must_ask: [
          sq(
            1,
            {
              ...q("senior q", "senior"),
              good_answer_signals: ["能说出具体字段名。", "展示过工作记录表。"],
              red_flags: ["只复述框架名词。", "说不清口径定义。"],
              scoring_criteria: ["说明统计方式。", "能提供部门产出量。"],
            },
            8,
          ),
        ],
      }),
    );
    expect(md).toContain(
      "- 真做过的信号：能说出具体字段名；展示过工作记录表",
    );
    expect(md).toContain("- 背诵信号：只复述框架名词；说不清口径定义");
    expect(md).toContain("- 要点：说明统计方式；能提供部门产出量");
    expect(md).not.toContain("。；");
  });
});
