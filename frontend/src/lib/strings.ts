// zh-CN copy, ported 1:1 from ui/strings.py and app/locale/zh_CN.py.
// Icons are intentionally NOT embedded here (emoji-free UI); semantic SVG icons
// are rendered by components instead.

import type { Difficulty, Recommendation, RunStatus } from "@/lib/types";

export const PAGE_TITLE = "智能招聘助手";
export const APP_TITLE = "智能招聘助手";
export const MAIN_TITLE = "候选人决策档案";
export const MAIN_CAPTION =
  "证据驱动的筛选：每项评分均有原文引用支撑，经过 schema 校验、有界修复，并生成可导出的决策台账。";

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

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  needs_review: "待人工复核",
  failed: "失败",
};

export const VALIDATION_STATUS_LABELS: Record<string, string> = {
  valid: "有效",
  repaired: "已修复",
  failed: "失败",
};

export const S = {
  apiUnreachable: (url: string) =>
    `无法连接 API（${url}），请先运行 make demo 启动服务。`,
  replayMode: "回放模式 — 使用内置演示数据，无需 LLM 密钥。",
  liveMode: "实时模式 — OpenAI 兼容端点（默认 Qwen qwen-plus）。",
  langfuseEnabled: "已启用",
  langfuseFallback: "本地回退（决策台账 + 日志）",
  langfuseCaption: (label: string) => `Langfuse：${label}`,

  sidebarDemoHeader: "一键演示",
  loadDemoButton: "加载演示案例",
  loadDemoHelp: "一份 JD + 三份合成简历：强匹配、弱匹配、prompt 注入尝试。",

  sidebarLiveHeader: "实时筛选（你的文件）",
  jdUploader: "职位描述（PDF / DOCX / TXT）",
  resumeUploader: "简历（1-5 份，每份最大 5MB）",
  runLiveButton: "开始实时筛选",
  uploadContract:
    "上传约定：1 份 JD + 最多 5 份简历，PDF/DOCX/TXT，每份 5MB。文件保存在本地 SQLite；原始文本不会进入审计导出。",

  emptyRun: "点击「加载演示案例」体验一键演示，或上传 JD 与简历进行实时筛选。",

  runBadgeReplay: "回放",
  runBadgeLive: "实时",

  progressQueued: "任务已提交，等待后台启动…",
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
  progressAutoRefresh: "每 2 秒自动刷新",
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

  tabRanking: "排名",
  tabDossier: "档案",
  tabObservability: "可观测性",
  tabAudit: "审计导出",

  noCandidates: "本次运行没有候选人。",
  noDossiers: "本次运行没有可用档案。",
  needsReview: (message: string) => `需要人工复核：${message}`,
  validationFailedDefault: "校验失败",
  needsReviewBadge: "待复核",
  failedBadge: "失败",

  scoreLabel: "匹配分数",
  recommendationLabel: "推荐结论",
  confidenceLabel: "模型置信度",
  scoreExplanation:
    "总分由校验后的子分项确定性计算；模型仅提供证据与分析。",
  whyThisScore: "评分理由",
  subScoreHeader: "维度得分",
  evidenceLedger: (n: number) => `证据台账（${n} 条引用）`,
  riskFlags: "风险标记",
  requirementTag: (id: string) => ` · 要求 ${id}`,
  confidenceFmt: (value: number) => `置信度 ${value.toFixed(2)}`,

  profileHeader: "候选人画像",
  profileSummary: "概述",
  profileSkills: "技能",
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

  interviewPreviewTitle: "场景 B 预览（轻量）",
  interviewPreviewCaption:
    "非完整多轮面试官；这是基于已完成候选人决策档案的文档化扩展路径。",
  personaLabel: "面试官人设：",
  openingLabel: "开场问题：",
  focusLabel: "关注重点：",
  previewUnavailable: (detail: string) => `面试预览不可用：${detail}`,

  candidateSelect: "候选人",

  obsLlmCalls: "LLM 调用",
  obsInputTokens: "输入 token",
  obsOutputTokens: "输出 token",
  obsCost: "费用估算（USD）",
  obsDuration: "耗时（秒）",
  obsReplayNote: "回放模式不调用实时模型，因此 token 为 0。",
  decisionLedger: (n: number) => `决策台账（${n} 条事件）`,
  evalResults: "最新评测结果（make eval）",
  noEvalResults: "尚无评测结果 — 运行 make eval 填充本面板。",

  ledgerColTs: "时间",
  ledgerColEvent: "事件",
  ledgerColCandidate: "候选人",
  ledgerColNode: "节点",
  ledgerColActor: "执行方",
  ledgerColModel: "模型",
  ledgerColPrompt: "Prompt",
  ledgerColLatency: "延迟(ms)",
  ledgerColValidation: "校验",

  evalColCheck: "检查项",
  evalColStatus: "状态",
  evalColValue: "数值",
  evalColDetails: "详情",

  validationProvenance: "校验与溯源",
  validationRow: (
    node: string,
    schema: string,
    status: string,
    repairs: number,
  ) => `${node} · ${schema} · ${status} · 修复次数=${repairs}`,
  langfuseTrace: "打开 Langfuse 追踪",
  langfuseDisabled: "Langfuse 未启用 — 决策台账与本地日志为审计来源。",

  exportStatus: "导出状态",
  exportEvents: "决策事件",
  exportDossiers: "档案",
  exportRepairs: "修复尝试",
  downloadAudit: "下载审计 JSON（audit-export.v1）",
  exportUnavailable: (detail: string) => `审计导出不可用：${detail}`,
  auditRedaction:
    "脱敏说明：仅包含哈希、引用片段与元数据 — 原始文档文本与服务商凭证不会进入导出。",
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  document_parsed: "文档解析完成",
  rubric_extracted: "职位标准已生成",
  llm_call_started: "开始 LLM 调用",
  candidate_profile_extracted: "候选人档案已提取",
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
};

export const SUB_SCORE_LABELS: Record<string, string> = {
  required_skills: "必备技能",
  preferred_skills: "加分技能",
  experience_relevance: "经历相关性",
  project_depth: "项目深度",
  ai_engineering_maturity: "AI 工程成熟度",
  communication_clarity: "表达清晰度",
};
