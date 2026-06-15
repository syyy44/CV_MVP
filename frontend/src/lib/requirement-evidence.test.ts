import { describe, expect, it } from "vitest";

import { requirementEvidenceStatus } from "@/lib/requirement-evidence";
import type { RequirementResult } from "@/lib/types";

const metReq: RequirementResult = {
  requirement_id: "MH1",
  display_label: "熟悉短视频平台生态",
  kind: "must_have",
  met: true,
  weight: 10,
};

const unmetReq: RequirementResult = {
  ...metReq,
  met: false,
};

describe("requirementEvidenceStatus", () => {
  it("flags met requirements without resume citations", () => {
    const status = requirementEvidenceStatus(metReq, [], []);
    expect(status.metLabel).toBe("满足（缺简历引用）");
    expect(status.tone).toBe("hold");
    expect(status.resumeGap).toBe(true);
    expect(status.reason).toContain("未绑定可引用的简历行");
  });

  it("keeps proceed tone when resume evidence exists", () => {
    const status = requirementEvidenceStatus(
      metReq,
      [
        {
          document_id: "d1",
          document_hash: "h1",
          source_type: "resume",
          snippet: "运营过小红书与抖音账号",
          offset_status: "verified",
          requirement_id: "MH1",
        },
      ],
      [],
    );
    expect(status.metLabel).toBe("满足");
    expect(status.tone).toBe("proceed");
    expect(status.reason).toContain("已找到可引用的简历证据");
  });

  it("uses penalty explanations when present", () => {
    const status = requirementEvidenceStatus(metReq, [], [
      {
        kind: "missing_must_have",
        points: 10,
        requirement_id: "MH1",
        explanation: "简历未体现平台运营经历。",
      },
    ]);
    expect(status.reason).toBe("简历未体现平台运营经历。");
  });

  it("describes unmet requirements", () => {
    const status = requirementEvidenceStatus(unmetReq, [], []);
    expect(status.metLabel).toBe("未满足");
    expect(status.tone).toBe("reject");
  });
});
