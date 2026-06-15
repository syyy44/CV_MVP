// Markdown formatting only. The script itself (v3 claim-first selection,
// checklist, timings) is built by the backend —
// `GET /api/candidates/{id}/interview-script` — per docs/V2_UI_PROPOSAL.md §6.1.
// No selection logic lives in the client.

import { ARCHETYPE_LABELS, DIFFICULTY_LABELS, S } from "@/lib/strings";
import type { InterviewScriptResponse, ScriptQuestion } from "@/lib/types";
import { joinZhClauses } from "@/lib/utils";

function pushQuestionBlock(lines: string[], item: ScriptQuestion): void {
  const q = item.question;
  const archetype = q.archetype ? `${ARCHETYPE_LABELS[q.archetype]} · ` : "";
  lines.push(
    `${item.index}. [${archetype}${DIFFICULTY_LABELS[q.difficulty]}] ${q.question}`,
  );
  if (q.target_claim) {
    lines.push(`   - 针对声明：${q.target_claim}`);
  }
  if (q.follow_up_probes && q.follow_up_probes.length > 0) {
    q.follow_up_probes.forEach((probe, i) => {
      lines.push(`   - 追问${i + 1}：${probe}`);
    });
  }
  if (q.scoring_criteria.length > 0) {
    lines.push(`   - 要点：${joinZhClauses(q.scoring_criteria.slice(0, 2))}`);
  }
  if (q.good_answer_signals.length > 0) {
    lines.push(`   - 真做过的信号：${joinZhClauses(q.good_answer_signals)}`);
  }
  if (q.red_flags.length > 0) {
    lines.push(`   - 背诵信号：${joinZhClauses(q.red_flags)}`);
  }
  lines.push(`   - 建议时长：${item.suggested_minutes} 分钟`);
}

// Fixed template per docs/V2_UI_PROPOSAL.md §6.6. No internal ids / trace ids.
export function formatScriptMarkdown(script: InterviewScriptResponse): string {
  const lines: string[] = [
    `# 面试脚本 — ${script.candidate_name}`,
    `岗位：本次筛选 · 推荐：${S.recommendationShort(script.recommendation)} · 分数：${script.overall_score}`,
    `置信：${S.confidenceBandLabel(script.confidence_band).replace("置信：", "")} · 建议时长：~${script.suggested_duration_min} 分钟`,
    "",
    "## 必问",
  ];

  for (const item of script.must_ask) {
    pushQuestionBlock(lines, item);
  }

  if (script.follow_ups.length > 0) {
    lines.push("", "## 模糊点追问");
    for (const followUp of script.follow_ups) {
      const evidence =
        followUp.evidence_refs[0]?.snippet?.slice(0, 40) ?? followUp.ambiguity;
      lines.push(`- ${followUp.question}（依据：${evidence}）`);
    }
  }

  if (script.optional.length > 0) {
    lines.push("", "## 选问（时间充裕）");
    for (const item of script.optional) {
      const q = item.question;
      const archetype = q.archetype ? `[${ARCHETYPE_LABELS[q.archetype]}] ` : "";
      lines.push(`- ${archetype}${q.question}`);
      if (q.follow_up_probes && q.follow_up_probes.length > 0) {
        lines.push(`  - 追问：${joinZhClauses(q.follow_up_probes)}`);
      }
    }
  }

  if (script.recommendation === "hold" && script.verification_checklist.length > 0) {
    lines.push("", "## 待核实（通过前）");
    script.verification_checklist.forEach((item, i) => {
      lines.push(`${i + 1}. ${item.item}`);
    });
    lines.push(`判定：${script.pass_criteria}`);
  }

  return lines.join("\n");
}
