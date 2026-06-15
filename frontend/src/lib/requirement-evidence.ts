import type { EvidenceSpan, RequirementResult, ScorePenaltyExplanation } from "@/lib/types";

export type RequirementEvidenceTone = "proceed" | "hold" | "reject";

export interface RequirementEvidenceStatus {
  metLabel: string;
  tone: RequirementEvidenceTone;
  reason: string;
  resumeGap: boolean;
}

export function requirementEvidenceStatus(
  req: RequirementResult,
  resumeRefs: EvidenceSpan[],
  penalties: ScorePenaltyExplanation[],
): RequirementEvidenceStatus {
  const penaltyReasons = penalties
    .filter((penalty) => penalty.requirement_id === req.requirement_id)
    .map((penalty) => penalty.explanation);

  if (penaltyReasons.length > 0) {
    return {
      metLabel: req.met ? "满足" : "未满足",
      tone: req.met ? "proceed" : "reject",
      reason: penaltyReasons.join("；"),
      resumeGap: req.met && resumeRefs.length === 0,
    };
  }

  if (!req.met) {
    return {
      metLabel: "未满足",
      tone: "reject",
      reason: "未找到足够证据支撑该必备项。",
      resumeGap: false,
    };
  }

  if (resumeRefs.length === 0) {
    return {
      metLabel: "满足（缺简历引用）",
      tone: "hold",
      reason:
        "模型判定为满足，但匹配依据中未绑定可引用的简历行；建议结合「匹配依据」或面试追问核实。",
      resumeGap: true,
    };
  }

  return {
    metLabel: "满足",
    tone: "proceed",
    reason: "已找到可引用的简历证据支撑该必备项。",
    resumeGap: false,
  };
}
