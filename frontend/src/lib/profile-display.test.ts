import { describe, expect, it } from "vitest";

import {
  extractProfileOverview,
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

describe("extractProfileOverview", () => {
  it("keeps only the overview before detailed highlights", () => {
    const summary =
      "候选人小宋，2026年计算机硕士应届，拥有4段AI核心业务实战经验。最突出的可验证亮点包括：" +
      "1) 在头部互联网平台通过LoRA微调将准确率从65%提升至88%；" +
      "2) 在自动驾驶企业利用Transformer融合多模态数据使mAP提升5.2%。" +
      "待面试重点核实：1) 3.85/4.0的绩点精确口径；2) 多模态融合中Transformer的具体架构。";

    expect(extractProfileOverview(summary)).toBe(
      "候选人小宋，2026年计算机硕士应届，拥有4段AI核心业务实战经验。",
    );
  });

  it("handles alternate highlight and verification markers", () => {
    const summary =
      "候选人小文，某985/211高校计算机本科在读，预计2026年毕业，兼具后端开发与算法研究多段实习经历。" +
      "亮点包括：在自动驾驶独角兽实习期间，基于LoRA微调Llama-3，显存占用降低60%；" +
      "在互联网大厂通过Redis与消息队列优化高并发秒杀接口，QPS提升3倍；" +
      "带领团队完成AIGC营销实战，客流量提升50%。" +
      "面试需核实：多项指标缺失基线数据（如Recall@5、准确率提升等），个人贡献与团队成果边界不清。";

    expect(extractProfileOverview(summary)).toBe(
      "候选人小文，某985/211高校计算机本科在读，预计2026年毕业，兼具后端开发与算法研究多段实习经历。",
    );
  });

  it("returns plain summaries unchanged", () => {
    expect(extractProfileOverview("高级后端工程师，拥有 6 年专业 Python 经验。")).toBe(
      "高级后端工程师，拥有 6 年专业 Python 经验。",
    );
  });
});

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
