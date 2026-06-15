import { describe, expect, it } from "vitest";

import {
  formatEducationHeadline,
  groupProjectsByExperience,
  normalizeEducation,
  partitionSkillsForJd,
} from "@/lib/profile-display";
import type { CandidateScore } from "@/lib/types";

const baseScore: CandidateScore = {
  overall_score: 80,
  recommendation: "proceed",
  confidence: 0.8,
  sub_scores: {
    required_skills: 80,
    preferred_skills: 70,
    experience_relevance: 75,
    project_depth: 70,
    ai_engineering_maturity: 72,
    communication_clarity: 78,
  },
  match_reasons: [
    "具备生产级 FastAPI 与 LangGraph 编排经验",
    "熟悉 Pydantic 结构化输出与 Langfuse 可观测性",
    "Python 后端年限满足岗位要求",
  ],
  risk_flags: [],
  evidence_refs: [],
  claim_verifications: [],
  requirement_results: [
    {
      requirement_id: "MH1",
      display_label: "至少 3 年专业 Python 后端工程经验",
      kind: "must_have",
      met: true,
      weight: 12,
    },
    {
      requirement_id: "MH2",
      display_label: "具备 FastAPI 生产经验",
      kind: "must_have",
      met: true,
      weight: 10,
    },
    {
      requirement_id: "MH3",
      display_label: "多步 LLM 工作流编排实战经验",
      kind: "must_have",
      met: true,
      weight: 12,
    },
  ],
  injection_detected: false,
};

describe("partitionSkillsForJd", () => {
  it("prioritizes JD-relevant skills and caps primary list", () => {
    const skills = [
      "Python",
      "FastAPI",
      "LangGraph",
      "CSS",
      "jQuery",
      "Pydantic",
      "WordPress",
      "Milvus",
      "Redis",
      "BM25",
    ];
    const { primary, secondary } = partitionSkillsForJd(skills, baseScore, 4);

    expect(primary).toEqual(["Python", "FastAPI", "LangGraph", "Pydantic"]);
    expect(secondary).toContain("CSS");
    expect(secondary).toContain("jQuery");
  });
});

describe("normalizeEducation", () => {
  it("parses legacy plain-text education", () => {
    const items = normalizeEducation(["浙江大学 计算机科学 学士，2019"]);
    expect(items[0]?.school).toContain("浙江大学");
  });

  it("parses kv-style education dumps", () => {
    const raw =
      "school: 南京理工大学, degree: 硕士, major: 计算机科学与技术, start_date: 2021-09, end_date: 2025-06, gpa: NA, highlights: ['国家奖学金']";
    const items = normalizeEducation([raw]);
    expect(items[0]).toMatchObject({
      school: "南京理工大学",
      degree: "硕士",
      major: "计算机科学与技术",
      start_date: "2021-09",
      end_date: "2025-06",
      highlights: ["国家奖学金"],
    });
    expect(formatEducationHeadline(items[0]!)).toBe("硕士 · 计算机科学与技术");
  });
});

describe("groupProjectsByExperience", () => {
  it("uses explicit project ownership when present", () => {
    const groups = groupProjectsByExperience(
      [
        {
          name: "智能客服",
          description: "搭建多语言智能客服 Agent",
          source_work_experience: "A 公司 · 运营主管（2025）",
          technologies: ["LLM"],
        },
      ],
      [],
    );

    expect(groups).toHaveLength(1);
    expect(groups[0]?.label).toBe("A 公司 · 运营主管（2025）");
  });

  it("infers project ownership from matching work highlights", () => {
    const groups = groupProjectsByExperience(
      [
        {
          name: "TikTok Shop北美矩阵搭建",
          description: "负责北美区 TikTok Shop 账号从 0 到 1 的搭建",
          technologies: ["TikTok Shop"],
          quantified_claims: ["半年内粉丝突破 50W", "单月 GMV 稳定在 150 万美金以上"],
        },
      ],
      [
        {
          title: "跨境电商运营主管",
          company: "某头部出海 DTC 品牌公司",
          duration: "2025.06 – 至今",
          highlights: [
            "负责北美区 TikTok Shop 账号从0到1搭建，半年粉丝突破50W，单月GMV稳定在150万美金以上",
          ],
        },
      ],
    );

    expect(groups[0]?.label).toBe(
      "某头部出海 DTC 品牌公司 · 跨境电商运营主管（2025.06 – 至今）",
    );
  });
});
