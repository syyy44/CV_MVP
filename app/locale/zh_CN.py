"""产品面向用户的中文文案。"""

from __future__ import annotations

RECOMMENDATION_LABELS = {
    "proceed": "通过",
    "hold": "待定",
    "reject": "拒绝",
}

DIFFICULTY_LABELS = {
    "junior": "初级",
    "mid": "中级",
    "senior": "高级",
    "expert": "专家",
}

RUN_STATUS_LABELS = {
    "queued": "排队中",
    "running": "运行中",
    "completed": "已完成",
    "needs_review": "待人工复核",
    "failed": "失败",
}

VALIDATION_STATUS_LABELS = {
    "valid": "有效",
    "repaired": "已修复",
    "failed": "失败",
}

# --- API / workflow errors -----------------------------------------------------

def unsupported_file_type(filename: str) -> str:
    return f"「{filename}」：仅支持 PDF、DOCX、TXT 格式"


def file_too_large(filename: str, max_mb: int) -> str:
    return f"「{filename}」超过 {max_mb}MB 大小限制"


def file_empty(filename: str) -> str:
    return f"「{filename}」为空文件"


def replay_rejects_uploads() -> str:
    return (
        "回放模式使用内置演示数据，请勿上传文件"
        "（如需使用自己的文档，请切换到 live 模式）"
    )


def run_not_found(run_id: str) -> str:
    return f"未找到运行 {run_id}"


def candidate_not_found(candidate_id: str) -> str:
    return f"未找到候选人 {candidate_id}"


def candidate_not_completed(candidate_id: str) -> str:
    return f"候选人 {candidate_id} 尚未完成评估，暂无面试脚本"


def note_added_note(author: str) -> str:
    return f"{author} 添加了面后笔记"


def decision_override_note(from_rec: str, to_rec: str) -> str:
    from_label = RECOMMENDATION_LABELS.get(from_rec, from_rec)
    to_label = RECOMMENDATION_LABELS.get(to_rec, to_rec)
    return f"人工将推荐从「{from_label}」改为「{to_label}」"


def unexpected_server_error() -> str:
    return "服务器发生意外错误"


def demo_manifest_not_found(path: str) -> str:
    return f"未找到演示清单 {path}，请重新克隆仓库"


def test_data_dir_missing(path: str) -> str:
    return f"测试数据目录不存在：{path}"


def test_data_manifest_invalid(path: str) -> str:
    return f"测试数据 manifest 无效：{path}"


def test_data_files_missing(paths: str) -> str:
    return f"测试数据文件缺失：{paths}"


def test_data_auto_discover_failed(path: str) -> str:
    return f"无法自动识别测试数据（需 1 份 JD txt + 至少 1 份简历）：{path}"


def test_data_file_not_allowed(filename: str) -> str:
    return f"不允许访问测试文件：{filename}"


def test_data_file_not_found(filename: str) -> str:
    return f"测试文件不存在：{filename}"


def test_data_rejects_uploads() -> str:
    return "source=test 时不应同时上传文件"


def demo_jd_fixture_missing(path: str) -> str:
    return f"缺少演示 JD 数据：{path}"


def demo_resume_fixture_missing(path: str) -> str:
    return f"缺少演示简历数据：{path}"


def live_requires_api_key() -> str:
    return "实时模式需要配置 LLM_API_KEY；请在 .env 中设置或改用 replay 模式"


def live_requires_api_key_extended() -> str:
    return (
        "实时模式需要 LLM_API_KEY（DashScope/OpenAI 兼容密钥）；"
        "请在 .env 中设置或切换 DEMO_MODE=replay"
    )


def jd_required() -> str:
    return "必须提供职位描述（上传文件或粘贴文字）"


def jd_upload_and_text_conflict() -> str:
    return "职位描述不能同时上传文件并粘贴文字，请只选一种方式"


def resume_required() -> str:
    return "至少需要上传一份简历"


def too_many_resumes(max_resumes: int, got: int) -> str:
    return f"每次运行最多 {max_resumes} 份简历（当前 {got} 份）"


def run_has_no_jd() -> str:
    return "该运行没有 JD 文档"


def unexpected_error(exc: str) -> str:
    return f"意外错误：{exc}"


def llm_provider_custom_requires_config() -> str:
    return "LLM_PROVIDER=custom 需要同时设置 OPENAI_BASE_URL 和 MODEL_NAME"


def llm_timeout(seconds: float) -> str:
    display = int(seconds) if seconds == int(seconds) else seconds
    return (
        f"LLM 调用超时（{display} 秒）。"
        "可在 .env 中增大 LLM_TIMEOUT_SECONDS，或稍后重试。"
    )


def llm_connection_failed(exc: str) -> str:
    return f"LLM 连接失败：{exc}"


def llm_rate_limit() -> str:
    return "LLM 服务返回 429 限流"


def llm_provider_error(exc: str) -> str:
    return f"LLM 服务错误：{exc}"


def llm_no_content() -> str:
    return "LLM 未返回可用内容"


def replay_fixture_missing(key: str, searched: str) -> str:
    return (
        f"未找到回放数据「{key}.json」（已搜索：{searched}）；"
        "请重新克隆仓库或重新生成 fixture"
    )


def replay_without_fixture_key() -> str:
    return "回放调用缺少 fixture_key"


def export_run_not_found(run_id: str) -> str:
    return f"未找到运行 {run_id}"


def export_run_still_running(run_id: str, status: str) -> str:
    return f"运行 {run_id} 状态为 {status}；仅 completed 或 needs_review 可导出"


def export_run_failed(run_id: str) -> str:
    return f"运行 {run_id} 已失败，无法导出"


def export_no_events(run_id: str) -> str:
    return f"运行 {run_id} 没有可导出的决策事件"


def export_no_dossiers(run_id: str) -> str:
    return f"运行 {run_id} 没有可导出的档案"


def export_candidate_needs_review(candidate_id: str, errors: str) -> str:
    return f"候选人 {candidate_id} 需要人工复核：{errors}"


def export_candidate_failed(candidate_id: str, errors: str) -> str:
    return f"候选人 {candidate_id} 处理失败：{errors}"


def orphaned_run_recovered() -> str:
    return "启动时恢复了孤立运行；请创建新的运行"


# --- Parsing / nodes -----------------------------------------------------------

def jd_parse_failed(filename: str, status: str) -> str:
    return f"JD「{filename}」无法解析（状态：{status}），运行无法继续"


def resume_not_usable(filename: str, status: str) -> str:
    return f"简历「{filename}」不可用（解析状态：{status}）"


def output_failed_validation() -> str:
    return "输出未通过校验"


def candidate_processing_failed() -> str:
    return "候选人处理失败"


def dossier_assembled_note() -> str:
    return "档案已由校验通过的产物组装完成"


def demo_override_note() -> str:
    return "演示复核员在检查 prompt 注入风险标记后确认了推荐结论"


# --- Evidence / validation -----------------------------------------------------

def evidence_source_missing(source_type: str) -> str:
    return f"证据引用了不存在的来源类型「{source_type}」"


def evidence_line_not_found(source_type: str, line_no: int, valid_max: int) -> str:
    if valid_max <= 0:
        return (
            f"证据引用行号无效：{source_type} 来源没有可引用的编号行，"
            f"无法引用 line_no={line_no}。"
        )
    return (
        f"证据引用行号无效：source_type={source_type} 的 line_no={line_no} 不存在"
        f"（有效范围 1 至 {valid_max}）。请改用带编号原文中真实存在的行号。"
    )


def match_reasons_need_three_quotes() -> str:
    return "match_reasons 必须引用至少 3 条不同的证据原文"


def missing_must_have_unknown_id(requirement_id: str) -> str:
    return f"missing_must_haves 引用了未知要求编号「{requirement_id}」"


def met_requirement_missing_resume_evidence(requirement_id: str) -> str:
    return (
        f"必备项「{requirement_id}」未列入 missing_must_haves，"
        f"但 match_reasons 中缺少带 requirement_id 的简历引用；"
        f"请为该项补充 resume 证据或将其加入 missing_must_haves。"
    )


def band_score_mismatch(dimension: str, band: str, score: int) -> str:
    return f"维度「{dimension}」的 band={band} 与 score={score} 区间不一致"


_GROUNDING_LABELS = {
    "match_reasons": "match_reasons",
    "claim_verifications": "claim_verifications",
    "follow_ups": "follow_ups",
}


def evidence_irrelevant(label: str, index: int, claim: str, relevance: float) -> str:
    field = _GROUNDING_LABELS.get(label, label)
    excerpt = claim if len(claim) <= 40 else f"{claim[:40]}…"
    return (
        f"{field}[{index}]「{excerpt}」所引用的原文与该结论几乎无关"
        f"（最高相关度 {relevance:.2f}）。请改引「带编号原文」中真正支撑该结论的行号，"
        "或删除该条；引用必须是直接支撑结论的那一行。"
    )


def quantified_claim_number_unsupported(
    project_name: str, claim: str, numbers: list[str]
) -> str:
    nums = "、".join(numbers)
    where = f"项目「{project_name}」" if project_name else "项目"
    excerpt = claim if len(claim) <= 40 else f"{claim[:40]}…"
    return (
        f"{where} quantified_claims「{excerpt}」中的数字 {nums} 未在简历原文中出现。"
        "量化声明必须逐字摘自简历，请改用简历中真实存在的数字，或删除该声明。"
    )


def claim_number_unsupported(claim: str, numbers: list[str]) -> str:
    nums = "、".join(numbers)
    excerpt = claim if len(claim) <= 40 else f"{claim[:40]}…"
    return (
        f"claim_verifications 声明「{excerpt}」中的数字 {nums} 在 JD 与简历原文中均未出现，"
        "疑似编造。请仅核查简历中真实存在的声明与数字。"
    )


def archetype_quota_unmet(archetype: str, minimum: int, actual: int) -> str:
    return (
        f"题型配比不达标：archetype={archetype} 至少需要 {minimum} 题，当前只有 {actual} 题。"
        "请调整 questions 的题型分布。"
    )


def question_needs_probe_chain(index: int, count: int) -> str:
    return (
        f"questions[{index}] 的 follow_up_probes 只有 {count} 条；"
        "每道主题目必须带 2-4 条递进追问链。"
    )


def question_needs_target_claim(index: int, archetype: str) -> str:
    return (
        f"questions[{index}]（archetype={archetype}）缺少 target_claim；"
        "复原/口径/深挖/复盘类题目必须锚定简历中的具体声明原文。"
    )


def anchor_claim_not_covered(claim: str) -> str:
    excerpt = claim if len(claim) <= 60 else f"{claim[:60]}…"
    return (
        f"高优先级声明「{excerpt}」没有被任何 questions.target_claim 覆盖；"
        "needs_probing/suspicious 声明必须至少对应一道面试题。"
    )


def no_json_in_output() -> str:
    return "模型输出中未找到 JSON 对象"


def repair_exhausted(schema_name: str, attempts: int, problems: str) -> str:
    return f"{schema_name} 在 {attempts} 次尝试后仍未通过校验：{problems}"


def evaluation_weights_must_sum(total: float) -> str:
    return f"评分权重之和必须为 1.0，当前为 {total}"


# --- Coercion fallbacks --------------------------------------------------------

UNKNOWN_TITLE = "未知职位"
UNKNOWN_COMPANY = "未知公司"
UNKNOWN_DURATION = "未知时段"
UNKNOWN_SCHOOL = "未知院校"
UNNAMED_PROJECT = "未命名项目"
NO_PROJECT_DESCRIPTION = "未提供项目描述"

# --- Redaction -----------------------------------------------------------------

EMAIL_REDACTED = "[邮箱已脱敏]"
PHONE_REDACTED = "[电话已脱敏]"
ADDRESS_REDACTED = "[地址已脱敏]"
