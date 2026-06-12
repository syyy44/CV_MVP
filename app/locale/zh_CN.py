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


def interview_preview_requires_dossier() -> str:
    return "面试预览需要已完成的候选人决策档案"


def unexpected_server_error() -> str:
    return "服务器发生意外错误"


def demo_manifest_not_found(path: str) -> str:
    return f"未找到演示清单 {path}，请重新克隆仓库"


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
    return "必须上传职位描述（JD）文件"


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


def band_score_mismatch(dimension: str, band: str, score: int) -> str:
    return f"维度「{dimension}」的 band={band} 与 score={score} 区间不一致"


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
UNNAMED_PROJECT = "未命名项目"
NO_PROJECT_DESCRIPTION = "未提供项目描述"

# --- Redaction -----------------------------------------------------------------

EMAIL_REDACTED = "[邮箱已脱敏]"
PHONE_REDACTED = "[电话已脱敏]"
ADDRESS_REDACTED = "[地址已脱敏]"

# --- Interview preview ---------------------------------------------------------

FOCUS_RECOMMENDATION = "推荐"
FOCUS_SCORE = "分数"
