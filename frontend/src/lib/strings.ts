// zh-CN product copy shared by the React views.
// Icons are intentionally NOT embedded here (emoji-free UI); semantic SVG icons
// are rendered by components instead.

import type {
  ClaimCredibility,
  Difficulty,
  QuestionArchetype,
  Recommendation,
  RunStatus,
} from "@/lib/types";

export const PAGE_TITLE = "智能招聘助手";
export const APP_TITLE = "智能招聘助手";
export const APP_TAGLINE = "筛选 · 排名 · 面试准备";
export const MAIN_TITLE = "候选人筛选与面试准备";
export const MAIN_CAPTION =
  "上传 JD 与简历，几分钟拿到排名和可直接带进会议室的面试脚本。每条结论都附简历原文。";

export const RECOMMENDATION_LABELS: Record<Recommendation, string> = {
  proceed: "通过",
  hold: "待定",
  reject: "拒绝",
};

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  junior: "初级",
  mid: "中级",
  senior: "高级",
  expert: "专家",
};

// 深度面试题型（与 GENERATE_INTERVIEW_PACK prompt 的 archetype contract 对齐）。
export const ARCHETYPE_LABELS: Record<QuestionArchetype, string> = {
  experience_probe: "经历复原",
  metric_validation: "口径核查",
  depth_probe: "技术深挖",
  failure_review: "失败复盘",
  scenario_design: "场景设计",
  jd_fit: "岗位迁移",
};

export const CLAIM_CREDIBILITY_LABELS: Record<ClaimCredibility, string> = {
  well_supported: "证据充分",
  plausible: "基本可信",
  needs_probing: "需追问口径",
  suspicious: "存疑",
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  needs_review: "待人工复核",
  failed: "失败",
};

export const S = {
  apiUnreachable: (url: string) =>
    `无法连接 API（${url}），请先运行 make demo 启动服务。`,
  replayMode: "回放模式 — 使用内置演示数据，无需 LLM 密钥。",
  liveMode: "实时模式 — OpenAI 兼容端点（当前演示环境使用 DeepSeek v4 Pro）。",

  sidebarDemoHeader: "一键演示",
  loadDemoButton: "加载演示案例",
  loadDemoHelp: "一份 JD + 三份合成简历：强匹配、弱匹配、prompt 注入尝试。",

  sidebarLiveHeader: "实时筛选（你的文件）",
  loadTestDataButton: "加载测试简历",
  loadTestDataHelp: "从 data/test 一键填入 JD 与本地测试简历。",
  runTestLiveButton: "一键实时测试",
  jdUploader: "职位描述（PDF / DOCX / TXT）",
  jdUploadTab: "上传文件",
  jdPasteTab: "粘贴文字",
  jdPastePlaceholder: "将职位描述粘贴到此处…",
  resumeUploader: "简历（1-5 份，每份最大 5MB）",
  runLiveButton: "开始实时筛选",
  uploadContract:
    "上传约定：1 份 JD + 最多 5 份简历，PDF/DOCX/TXT，每份 5MB。文件保存在本地 SQLite；原始文本不会进入审计导出。",

  historyHeader: "历史记录",
  historyCaption: "本地 SQLite 中保存的筛选运行，点击可重新打开排名与面试脚本。",
  historyEmpty: "暂无历史记录。完成一次演示或实时筛选后会显示在这里。",
  historyOpen: "打开",
  historyJdUnknown: "（未命名 JD）",
  historyResumeCount: (count: number) => `${count} 份简历`,
  historyTopCandidate: (name: string, score: number) => `${name} · ${score} 分`,

  emptyRun: "上传 JD 与简历进行实时筛选，或使用本地测试简历快速验证流程。",

  runBadgeReplay: "回放",
  runBadgeLive: "实时",

  progressQueued: "任务已提交，等待后台启动…",
  progressParsingDocs: "正在解析上传文档…",
  progressRubric: "正在从职位描述提取评分标准…",
  progressLlmWait: (step: string) =>
    `正在调用 LLM：${step}（通常需 30 秒–4 分钟）`,
  progressWaiting: (done: number, total: number) =>
    `已完成 ${done}/${total} 位候选人，继续处理下一位…`,
  progressAggregating: "所有候选人已处理，正在汇总结果…",
  progressStepIngest: "解析上传文件",
  progressStepRubric: "提取职位标准",
  progressElapsed: (minutes: number, seconds: number) =>
    `已运行 ${minutes} 分 ${String(seconds).padStart(2, "0")} 秒`,
  progressLastEvent: (seconds: number) => `最新事件 ${seconds} 秒前`,
  progressLlmIdle:
    "LLM 仍在响应中，请稍候（长简历或网络较慢时可能等待数分钟）",
  progressAutoRefresh: "每 1 秒自动刷新",
  progressCandidatesHeader: "候选人进度",
  progressActivityHeader: "实时活动",
  progressStatusLabel: "运行中",
  progressMetricDone: "已完成",
  progressMetricTotal: "简历数",
  progressMetricEvents: "事件数",
  progressMetricElapsed: "耗时",
  activityColTime: "时间",
  activityColEvent: "活动",
  activityColLatency: "延迟(ms)",
  runInProgressCaption: "后台运行写入决策事件时，本面板会持续更新。",

  runFailed: (detail: string) => `运行失败：${detail}`,
  unknownError: "未知错误",

  tabBoard: "候选看板",
  tabPrep: "面试准备",

  boardHeader: (n: number) => `本次筛选 · ${n} 名候选人`,
  boardCaption: "按匹配分数排序。用右侧按钮进入面试准备。",
  boardRiskCount: (n: number) => `${n} 风险`,
  boardVerifyCount: (n: number) => `${n} 待核实`,
  chipAll: "全部",
  showReason: "查看原因",
  hideReason: "收起",

  compareTitle: "对比",
  compareSelected: (n: number) => `已选 ${n} 人`,
  compareOpen: "进入对比",
  compareClose: "关闭",
  compareRiskRow: "风险",
  compareVerifyRow: "待核实",
  compareNoRisk: "—",

  prepTabScript: "面试脚本",
  prepTabScore: "评分依据",
  prepTabProfile: "候选人画像",
  copyScript: "复制脚本",
  scriptCopied: "已复制",
  scriptCopiedToast: "面试脚本已复制，可粘贴到笔记或飞书文档。",
  scriptMustAsk: "必问",
  scriptFollowUps: (n: number) => `模糊点追问（${n} 条）`,
  scriptOptional: (n: number) => `选问（${n} 题，时间充裕再问）`,
  scriptMinutes: (n: number) => `${n} 分钟`,
  scriptKeyPoints: "要点：",
  scriptDurationHint: (min: number, must: number, follow: number) =>
    `建议面试约 ${min} 分钟 · 必问 ${must} 题 · 追问 ${follow} 条`,

  holdWhyTitle: "为什么待定",
  holdVerifyTitle: (n: number) => `通过前建议核实（${n} 条）`,

  scriptLoading: "正在生成面试脚本…",
  scriptError: "面试脚本加载失败，请稍后重试。",

  // 必备要求覆盖（UX-014：用 display_label，不暴露 MH 编号）。
  requirementCoverageTitle: "必备要求覆盖",
  requirementCoverageHint: "点击任一必备项展开 JD 要求、满足时的简历引用与判断原因",
  reqMet: "满足",
  reqUnmet: "未满足",

  // 面后笔记（P2）。
  notesTitle: "面后笔记",
  notesEmpty: "还没有笔记。面试后可在此记录结论与依据。",
  notesPlaceholder: "记录面试中的关键回答、印象与结论…",
  notesAdd: "添加笔记",
  notesAdding: "保存中…",
  notesAuthorDefault: "面试官",
  notesAt: (time: string) => time,

  // 人工改推荐（P2）。
  overrideBadge: "已改判",
  changeDecisionTitle: "调整推荐结论",
  changeDecisionHint: "面试后如需修改推荐，将记录到决策台账（原始模型结论保留）。",
  decisionCurrent: (label: string) => `当前推荐：${label}`,
  decisionModelRec: (label: string) => `模型原始推荐：${label}`,
  decisionRationalePlaceholder: "改判依据（必填）…",
  decisionSavedRationaleTitle: "已记录的改判依据",
  decisionOverrideMeta: (actor: string, time: string) => `${actor} · ${time}`,
  decisionSubmit: "记录改判",
  decisionSubmitting: "记录中…",
  decisionRecordedToast: "推荐结论已更新并写入决策台账。",
  overrideBy: (actor: string, label: string) => `${actor} 已改判为「${label}」`,

  recommendationShort: (rec: Recommendation) => RECOMMENDATION_LABELS[rec],
  confidenceBandLabel: (band: "high" | "medium" | "low") =>
    band === "high" ? "置信：高" : band === "medium" ? "置信：中" : "置信：低",
  // Hover copy per docs/V2_UI_PROPOSAL.md §5.2.
  confidenceHover: (band: "high" | "medium" | "low") =>
    band === "high"
      ? "各维度评分一致、证据充分，可直接安排面试。"
      : band === "medium"
        ? "部分维度证据偏弱或有待核实点，建议先看追问再定。"
        : "评分冲突或证据不足，建议 hold 或缩短面试以核实为主。",
  scoreExplanationShort: "分数由多项维度综合得出；下方可查看评分依据与原文引用。",

  noCandidates: "本次运行没有候选人。",
  noDossiers: "本次运行没有可用档案。",
  needsReview: (message: string) => `需要人工复核：${message}`,
  validationFailedDefault: "校验失败",
  needsReviewBadge: "需复核",
  failedBadge: "失败",

  scoreLabel: "匹配分数",
  recommendationLabel: "推荐结论",
  confidenceLabel: "评分置信度",
  scoreExplanation:
    "总分由校验后的子分项确定性计算；模型仅提供证据与分析。",
  scoreDecisionSummary: "决策摘要",
  scorePrimaryReasons: "关键原因",
  scorePositiveSignals: "匹配亮点",
  scoreMustVerify: "必须核查",
  scoreRulesTitle: "评分规则",
  scoreRulesCopy:
    "最终分数由固定权重与扣分规则计算；同一份结构化分析会得到相同总分。LLM 只负责抽取证据和逐维度判断。",
  scoreThresholdCopy:
    "通过：≥75 且置信≥0.70；拒绝：<60、置信<0.50 或命中一票否决；其余待定。",
  scoreFormulaTitle: "分数构成",
  scoreFormulaCopy:
    "基础分 = 六个维度按权重加权；缺失必备项扣 8-15 分，重大无支撑声明每条扣 5 分，一票否决封顶 59。",
  scoreBandStrong: "强匹配",
  scoreBandAdequate: "可接受",
  scoreBandWeak: "弱匹配",
  scoreBandAbsent: "缺失",
  scoreConclusionTitle: "核心结论",
  scoreStrengths: "核心优势",
  scoreConcerns: "短板与风险",
  scoreInterviewFocus: "面试追问重点",
  scoreDimensionRationaleShow: "展开各维度评分依据",
  scoreDimensionRationaleHide: "收起各维度评分依据",
  scoreClaimDetailToggle: (n: number) => `完整声明核查（${n} 条）`,
  scoreEvidenceToggle: (n: number) => `必备项覆盖与证据台账（${n} 条引用）`,
  scoreFinalLabel: "最终分",
  scoreBaseLabel: "加权基础分",
  scorePenaltyLabel: "扣分",
  scoreNoStrengths: "暂无足够明确的匹配亮点。",
  scoreNoConcerns: "未发现明确阻断项。",
  scoreNoVerify: "没有额外的高优先级核查项。",
  whyThisScore: "评分理由",
  subScoreHeader: "维度得分",
  evidenceLedger: (n: number) => `证据台账（${n} 条引用）`,
  riskFlags: "风险标记",
  requirementTag: (id: string) => ` · 要求 ${id}`,
  confidenceFmt: (value: number) => `置信度 ${value.toFixed(2)}`,

  profileHeader: "候选人画像",
  profileSummary: "概述",
  profileSkills: "技能",
  profileSkillsJdRelevant: "JD 相关技能",
  profileSkillsOther: (n: number) => `其他技能（${n}）`,
  profileExperience: "工作经历",
  profileProjects: "项目",
  profileEducation: "教育",
  profileCertifications: "证书",

  interviewPack: (n: number) => `面试题包（${n} 题）`,
  scoringCriteria: "评分标准：",
  goodSignals: "优秀回答信号：",
  redFlagsLabel: "警示信号：",
  followUps: (n: number) => `模糊点追问（${n} 条）`,
  ambiguityLabel: "模糊点：",
  listenFor: "关注信号：",

  // 深度面试题（v7）。
  targetClaimLabel: "针对简历声明：",
  probeChainLabel: (n: number) => `递进追问（${n} 条，答得越顺越往深问）`,
  authenticSignals: "真做过的信号：",
  recitedSignals: "背诵/包装信号：",

  // 声明核查（评分依据页）。
  claimVerificationTitle: (n: number) => `简历声明核查（${n} 条）`,
  claimVerificationCaption:
    "简历是「声明的集合」而非「事实的集合」：以下关键声明的可信度评级与面试验证方式。",
  claimHowToVerify: "面试验证：",

  // 候选人画像：项目深挖锚点。
  profileProjectExperienceLabel: "归属经历：",
  profileProjectCount: (n: number) => `${n} 个项目`,
  profileRoleLabel: "职责边界：",
  profileClaimsLabel: "量化声明",
  profileTechDecisionsLabel: "技术选型",

  candidateSelect: "候选人",
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  document_parsed: "文档解析完成",
  rubric_extracted: "职位标准已生成",
  llm_call_started: "开始 LLM 调用",
  candidate_profile_extracted: "候选人档案已提取",
  candidate_started: "开始处理候选人",
  schema_validation_failed: "输出校验失败",
  repair_attempted: "尝试修复输出",
  repair_succeeded: "修复成功",
  repair_failed: "修复失败",
  score_component_computed: "评分子项已计算",
  recommendation_derived: "推荐结论已生成",
  questions_generated: "面试题已生成",
  dossier_completed: "决策档案已完成",
  human_override_recorded: "人工覆盖已记录",
};

export const NODE_LABELS: Record<string, string> = {
  ingest_files: "文件入库",
  extract_jd_rubric: "提取职位标准",
  extract_candidate_profile: "提取候选人档案",
  score_candidate: "匹配评分",
  generate_interview_pack: "生成面试题包",
  assemble_dossier: "汇总决策档案",
};

export const CANDIDATE_STAGE_LABELS: Record<string, string> = {
  queued: "排队中",
  profile: "提取档案",
  score: "匹配评分",
  interview: "生成面试题",
  assemble: "汇总档案",
  done: "已完成",
  failed: "处理失败",
};

export const SUB_SCORE_LABELS: Record<string, string> = {
  required_skills: "必备技能",
  preferred_skills: "加分技能",
  experience_relevance: "经历相关性",
  project_depth: "项目深度",
  ai_engineering_maturity: "AI 工程成熟度",
  communication_clarity: "表达清晰度",
};
