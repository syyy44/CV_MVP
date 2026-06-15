"""1v1 candidate comparison.

Facts are reused from each already-computed dossier; relative verdicts are
regenerated against the shared run rubric (same JD) by an LLM in a single
context, with a deterministic head-to-head core as both the structural guard
and the graceful fallback when the LLM is unavailable (e.g. replay mode without
a fixture). Absolute per-candidate scores are kept only as a labelled reference
anchor — never as the head-to-head verdict.
"""

from __future__ import annotations

import hashlib
import json

from app.core.config import get_settings
from app.core.errors import (
    CandidateNotCompletedError,
    CandidateNotFoundError,
    CompareNotComparableError,
)
from app.core.logging import get_logger
from app.ledger.events import LedgerRecorder
from app.llm.client import LiveLLMProvider
from app.llm.prompts import COMPARE_CANDIDATES
from app.llm.structured import generate_structured
from app.models.contracts import (
    CandidateComparison,
    CandidateScore,
    CompareDifferentiator,
    CompareSide,
    CompareVerdict,
    DecisionDossier,
    DimensionComparison,
    EvaluationWeights,
    MustHaveFaceOff,
    ScenarioFit,
    ScoreExplanation,
    VerificationFocus,
)
from app.models.drafts import CandidateComparisonDraft
from app.observability.tracing import Tracer
from app.replay.provider import ReplayProvider
from app.storage import repository
from app.workflows.context import MetricsCollector, WorkflowContext

log = get_logger(__name__)

DIMENSION_KEYS: tuple[str, ...] = (
    "required_skills",
    "preferred_skills",
    "experience_relevance",
    "project_depth",
    "ai_engineering_maturity",
    "communication_clarity",
)

DIMENSION_LABELS: dict[str, str] = {
    "required_skills": "必备技能",
    "preferred_skills": "加分技能",
    "experience_relevance": "经历相关性",
    "project_depth": "项目深度",
    "ai_engineering_maturity": "AI 工程成熟度",
    "communication_clarity": "表达清晰度",
}

_BAND_SHORT = {"strong": "强", "adequate": "中", "weak": "弱", "absent": "缺"}

_CACHE: dict[str, CandidateComparison] = {}


# ---- small helpers --------------------------------------------------------------


def _band_from_score(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "adequate"
    if score >= 30:
        return "weak"
    return "absent"


def _margin(delta: int) -> str:
    a = abs(delta)
    if a >= 20:
        return "decisive"
    if a >= 10:
        return "clear"
    if a >= 4:
        return "slight"
    return "even"


def _winner(delta: int, margin: str) -> str:
    if margin == "even":
        return "tie"
    return "a" if delta > 0 else "b"


def _explanation(score: CandidateScore) -> ScoreExplanation:
    return score.score_explanation or ScoreExplanation()


def _weights(dossier: DecisionDossier) -> dict[str, float]:
    defaults = EvaluationWeights().model_dump()
    dims = {d.key: d.weight for d in _explanation(dossier.score).dimensions}
    return {k: float(dims.get(k, defaults[k])) for k in DIMENSION_KEYS}


def _dossier_hash(dossier: DecisionDossier) -> str:
    return hashlib.sha256(dossier.model_dump_json().encode("utf-8")).hexdigest()[:12]


# ---- reference assembly (deterministic, reused facts) ---------------------------


def _dimension_refs(
    a: DecisionDossier, b: DecisionDossier
) -> list[DimensionComparison]:
    a_exp = {d.key: d for d in _explanation(a.score).dimensions}
    b_exp = {d.key: d for d in _explanation(b.score).dimensions}
    a_w = _weights(a)
    a_sub = a.score.sub_scores.model_dump()
    b_sub = b.score.sub_scores.model_dump()

    out: list[DimensionComparison] = []
    for key in DIMENSION_KEYS:
        a_sc = int(a_sub[key])
        b_sc = int(b_sub[key])
        delta = a_sc - b_sc
        margin = _margin(delta)
        out.append(
            DimensionComparison(
                key=key,
                label=DIMENSION_LABELS[key],
                weight=a_w[key],
                a_score_ref=a_sc,
                b_score_ref=b_sc,
                a_band=a_exp[key].band if key in a_exp else _band_from_score(a_sc),
                b_band=b_exp[key].band if key in b_exp else _band_from_score(b_sc),
                winner=_winner(delta, margin),
                margin=margin,
                rationale="",
                a_basis=a_exp[key].rationale if key in a_exp else "",
                b_basis=b_exp[key].rationale if key in b_exp else "",
            )
        )
    return out


def _must_have_faceoff(
    a: DecisionDossier, b: DecisionDossier
) -> list[MustHaveFaceOff]:
    a_map = {r.requirement_id: r for r in a.score.requirement_results}
    b_map = {r.requirement_id: r for r in b.score.requirement_results}
    ids = list(a_map) + [rid for rid in b_map if rid not in a_map]
    out: list[MustHaveFaceOff] = []
    for rid in ids:
        ref = a_map.get(rid) or b_map[rid]
        out.append(
            MustHaveFaceOff(
                requirement_id=rid,
                display_label=ref.display_label,
                a_met=a_map[rid].met if rid in a_map else False,
                b_met=b_map[rid].met if rid in b_map else False,
            )
        )
    return out


def _side(dossier: DecisionDossier) -> CompareSide:
    s = dossier.score
    return CompareSide(
        candidate_id=dossier.candidate_id,
        candidate_name=dossier.candidate_name,
        overall_score_ref=s.overall_score,
        recommendation_ref=s.recommendation,
        confidence_ref=s.confidence,
    )


def _role_context(run_id: str) -> tuple[str, str]:
    docs = repository.get_documents(run_id)
    jd = next((d for d in docs if d["source_type"] == "jd"), None)
    text = (jd or {}).get("text", "") or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    role_title = lines[0][:40] if lines else ""
    return role_title, text[:1200]


def _candidate_card(dossier: DecisionDossier) -> dict:
    p = dossier.candidate_profile
    s = dossier.score
    sub = s.sub_scores.model_dump()
    return {
        "name": dossier.candidate_name,
        "summary": p.summary,
        "skills": p.skills,
        "projects": [
            {
                "name": pr.name,
                "role": pr.role_in_project,
                "quantified_claims": pr.quantified_claims,
                "tech_decisions": pr.tech_decisions,
            }
            for pr in p.projects[:5]
        ],
        "independent_dimension_scores(先验,仅参考)": {
            DIMENSION_LABELS[k]: {"score": int(sub[k]), "band": _band_from_score(int(sub[k]))}
            for k in DIMENSION_KEYS
        },
        "claim_checks": [
            {"claim": c.claim, "credibility": c.credibility, "reason": c.reason}
            for c in s.claim_verifications[:6]
        ],
        "risk_flags": s.risk_flags,
        "ambiguities": p.missing_or_ambiguous_claims[:6],
        "must_have_met": {r.display_label: r.met for r in s.requirement_results},
        "independent_recommendation(先验)": s.recommendation,
    }


def _shared_anchor(
    role_title: str, jd_excerpt: str, dossier: DecisionDossier, faceoff: list[MustHaveFaceOff]
) -> str:
    weights = _weights(dossier)
    lines = [f"岗位：{role_title or '（未命名岗位）'}", "", "必备项满足对照（A vs B）："]
    for mh in faceoff:
        lines.append(
            f"- {mh.display_label}：A {'满足' if mh.a_met else '未满足'}，"
            f"B {'满足' if mh.b_met else '未满足'}"
        )
    lines.append("")
    lines.append(
        "维度权重：" + "，".join(f"{DIMENSION_LABELS[k]} {weights[k]:.2f}" for k in DIMENSION_KEYS)
    )
    if jd_excerpt:
        lines.extend(["", "JD 摘要：", jd_excerpt])
    return "\n".join(lines)


# ---- deterministic comparison (fallback + structural core) ----------------------


def _deterministic_relative(
    a: DecisionDossier,
    b: DecisionDossier,
    dimensions: list[DimensionComparison],
    faceoff: list[MustHaveFaceOff],
) -> dict:
    a_name, b_name = a.candidate_name, b.candidate_name

    for dim in dimensions:
        a_label = _BAND_SHORT[dim.a_band]
        b_label = _BAND_SHORT[dim.b_band]
        dim.rationale = (
            f"{a_name} {a_label} / {b_name} {b_label}"
            f"（{dim.a_score_ref} vs {dim.b_score_ref}）"
        )

    ranked = sorted(
        dimensions,
        key=lambda d: abs(d.a_score_ref - d.b_score_ref) * d.weight,
        reverse=True,
    )
    differentiators = [
        CompareDifferentiator(
            favors=dim.winner,  # type: ignore[arg-type]
            dimension=dim.key,
            text=(
                f"{(a_name if dim.winner == 'a' else b_name)}在{dim.label}上更强"
                f"（{dim.a_score_ref} vs {dim.b_score_ref}）"
            ),
        )
        for dim in ranked
        if dim.winner != "tie"
    ][:4]

    a_skills = {sk.lower() for sk in a.candidate_profile.skills}
    b_skills = {sk.lower() for sk in b.candidate_profile.skills}

    def _strengths(side: str, dossier: DecisionDossier, other_skills: set[str]) -> list[str]:
        out = [
            f"{dossier.candidate_name}在{d.label}更扎实"
            for d in dimensions
            if d.winner == side and d.margin in ("decisive", "clear")
        ]
        unique = [
            sk
            for sk in dossier.candidate_profile.skills
            if sk.lower() not in other_skills
        ][:3]
        if unique:
            out.append("独有技能：" + "、".join(unique))
        return out[:4]

    a_strengths = _strengths("a", a, b_skills)
    b_strengths = _strengths("b", b, a_skills)

    scenario: list[ScenarioFit] = []
    a_lead = next((d for d in ranked if d.winner == "a"), None)
    b_lead = next((d for d in ranked if d.winner == "b"), None)
    if a_lead:
        scenario.append(ScenarioFit(prefer="a", when=f"更看重{a_lead.label}时"))
    if b_lead:
        scenario.append(ScenarioFit(prefer="b", when=f"更看重{b_lead.label}时"))

    def _verify(dossier: DecisionDossier) -> list[VerificationFocus]:
        out: list[VerificationFocus] = []
        for c in dossier.score.claim_verifications:
            if c.credibility in ("needs_probing", "suspicious"):
                out.append(
                    VerificationFocus(
                        item=f"{dossier.candidate_name}：{c.verification_hint}",
                        why_it_matters=c.reason,
                        could_flip=c.credibility == "suspicious",
                    )
                )
        return out[:2]

    verification = (_verify(a) + _verify(b))[:3]
    for mh in faceoff:
        if mh.a_met != mh.b_met and len(verification) < 3:
            loser = b.candidate_name if mh.a_met else a.candidate_name
            verification.append(
                VerificationFocus(
                    item=f"核实 {loser} 是否真的不满足「{mh.display_label}」",
                    why_it_matters="必备项不对称是首要决胜因子。",
                    could_flip=True,
                )
            )

    return {
        "dimensions": dimensions,
        "differentiators": differentiators,
        "a_unique_strengths": a_strengths,
        "b_unique_strengths": b_strengths,
        "a_risks": a.score.risk_flags[:3],
        "b_risks": b.score.risk_flags[:3],
        "scenario_fit": scenario,
        "verification_focus": verification,
        "verdict": _deterministic_verdict(a, b, faceoff),
    }


def _deterministic_verdict(
    a: DecisionDossier, b: DecisionDossier, faceoff: list[MustHaveFaceOff]
) -> CompareVerdict:
    da, db = a.score.overall_score, b.score.overall_score
    a_met = sum(1 for mh in faceoff if mh.a_met)
    b_met = sum(1 for mh in faceoff if mh.b_met)
    delta = da - db
    a_name, b_name = a.candidate_name, b.candidate_name

    if abs(delta) >= 8:
        pick = "a" if delta > 0 else "b"
        winner_met, loser_met = (a_met, b_met) if pick == "a" else (b_met, a_met)
        confidence = "clear" if winner_met >= loser_met else "leaning"
    elif a_met != b_met:
        pick = "a" if a_met > b_met else "b"
        confidence = "leaning"
    else:
        pick = "either"
        confidence = "too_close"

    name = a_name if pick == "a" else b_name
    if confidence == "too_close":
        headline = "势均力敌，建议通过面试进一步区分"
        rationale = (
            f"{a_name} 与 {b_name} 总分与必备项覆盖接近"
            f"（{da} vs {db}），现有证据不足以拉开差距。"
        )
        tie_breaker = ""
    else:
        headline = f"{name} 相对更合适"
        rationale = (
            f"{name} 在总分（{da} vs {db}）或必备项覆盖（{a_met} vs {b_met}）上占优。"
        )
        tie_breaker = "必备项覆盖更全" if a_met != b_met and abs(delta) < 8 else "综合分更高"

    return CompareVerdict(
        pick=pick,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        headline=headline,
        rationale=rationale,
        tie_breaker=tie_breaker,
        would_change_if="若核实清单中的存疑项被证实或证伪，结论可能调整。",
    )


# ---- LLM enrichment -------------------------------------------------------------


def _run_llm(
    run_id: str,
    a: DecisionDossier,
    b: DecisionDossier,
    shared_anchor: str,
) -> CandidateComparisonDraft:
    settings = get_settings()
    if settings.llm_api_key:
        provider: object = LiveLLMProvider(settings)
    else:
        provider = ReplayProvider(settings)
    ctx = WorkflowContext(
        run_id=run_id,
        mode=settings.demo_mode,
        settings=settings,
        provider=provider,
        ledger=LedgerRecorder(run_id),
        tracer=Tracer(settings),
        metrics=MetricsCollector(),
    )
    draft, _meta = generate_structured(
        ctx,
        COMPARE_CANDIDATES,
        CandidateComparisonDraft,
        {
            "shared_anchor": shared_anchor,
            "a_name": a.candidate_name,
            "b_name": b.candidate_name,
            "a_card": json.dumps(_candidate_card(a), ensure_ascii=False),
            "b_card": json.dumps(_candidate_card(b), ensure_ascii=False),
        },
        node_name="compare_candidates",
    )
    ctx.tracer.flush()
    return draft


def _merge_llm(
    draft: CandidateComparisonDraft,
    dimensions: list[DimensionComparison],
) -> dict:
    verdicts = {dv.key: dv for dv in draft.dimension_verdicts}
    for dim in dimensions:
        dv = verdicts.get(dim.key)
        if dv is not None:
            dim.winner = dv.winner
            dim.margin = dv.margin
            dim.rationale = dv.rationale
        elif not dim.rationale:
            dim.rationale = (
                f"{dim.a_score_ref} vs {dim.b_score_ref}"
            )

    return {
        "dimensions": dimensions,
        "differentiators": [
            CompareDifferentiator(favors=d.favors, dimension=None, text=d.text)
            for d in draft.differentiators
        ],
        "a_unique_strengths": draft.a_unique_strengths,
        "b_unique_strengths": draft.b_unique_strengths,
        "a_risks": draft.a_risks,
        "b_risks": draft.b_risks,
        "scenario_fit": [
            ScenarioFit(prefer=s.prefer, when=s.when) for s in draft.scenario_fit
        ],
        "verification_focus": [
            VerificationFocus(
                item=v.item, why_it_matters=v.why_it_matters, could_flip=v.could_flip
            )
            for v in draft.verification_focus
        ],
        "verdict": CompareVerdict(
            pick=draft.pick,
            confidence=draft.confidence,
            headline=draft.headline,
            rationale=draft.rationale,
            tie_breaker=draft.tie_breaker,
            would_change_if=draft.would_change_if,
        ),
    }


# ---- structural reconciliation (hard rules win) ---------------------------------


def _reconcile(comp: CandidateComparison, a: DecisionDossier, b: DecisionDossier) -> None:
    a_rej = a.score.recommendation == "reject"
    b_rej = b.score.recommendation == "reject"
    if not (a_rej or b_rej):
        return
    if a_rej and b_rej:
        comp.verdict.pick = "neither"
        comp.verdict.confidence = "clear"
        comp.verdict.headline = "双方均不建议推进"
        comp.verdict.rationale = "两位候选人均触发拒绝（一票否决或低于阈值）。"
        comp.verdict.overridden_by_rule = "双方均为拒绝"
        return
    winner_side = "b" if a_rej else "a"
    loser_name = a.candidate_name if a_rej else b.candidate_name
    winner_name = b.candidate_name if a_rej else a.candidate_name
    comp.verdict.pick = winner_side  # type: ignore[assignment]
    comp.verdict.confidence = "clear"
    comp.verdict.headline = f"{winner_name} 胜出：对方触发拒绝条件"
    comp.verdict.rationale = (
        f"{loser_name} 触发拒绝（一票否决或低于阈值），结构性出局；"
        f"因此推荐 {winner_name}。"
    )
    comp.verdict.overridden_by_rule = f"{loser_name} 触发拒绝条件"


# ---- public entry ---------------------------------------------------------------


def build_comparison(candidate_a_id: str, candidate_b_id: str) -> CandidateComparison:
    found_a = repository.get_candidate(candidate_a_id)
    if found_a is None:
        raise CandidateNotFoundError(f"未找到候选人：{candidate_a_id}")
    found_b = repository.get_candidate(candidate_b_id)
    if found_b is None:
        raise CandidateNotFoundError(f"未找到候选人：{candidate_b_id}")

    run_a, res_a = found_a
    run_b, res_b = found_b
    if run_a != run_b:
        raise CompareNotComparableError(
            "两位候选人来自不同的运行（不同 JD），缺少共同评判标准，无法对比。"
        )
    if not isinstance(res_a.dossier, DecisionDossier):
        raise CandidateNotCompletedError(f"候选人尚未完成分析：{candidate_a_id}")
    if not isinstance(res_b.dossier, DecisionDossier):
        raise CandidateNotCompletedError(f"候选人尚未完成分析：{candidate_b_id}")

    a_doss, b_doss = res_a.dossier, res_b.dossier
    cache_key = ":".join(
        [
            run_a,
            candidate_a_id,
            candidate_b_id,
            _dossier_hash(a_doss),
            _dossier_hash(b_doss),
            COMPARE_CANDIDATES.version,
        ]
    )
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    dimensions = _dimension_refs(a_doss, b_doss)
    faceoff = _must_have_faceoff(a_doss, b_doss)
    role_title, jd_excerpt = _role_context(run_a)
    shared_anchor = _shared_anchor(role_title, jd_excerpt, a_doss, faceoff)

    generated_with = "llm"
    try:
        draft = _run_llm(run_a, a_doss, b_doss, shared_anchor)
        parts = _merge_llm(draft, dimensions)
    except Exception as exc:  # never hard-fail the feature
        log.warning("compare LLM unavailable, using deterministic fallback: %s", exc)
        generated_with = "deterministic"
        parts = _deterministic_relative(a_doss, b_doss, dimensions, faceoff)

    comparison = CandidateComparison(
        run_id=run_a,
        role_title=role_title,
        generated_with=generated_with,  # type: ignore[arg-type]
        a=_side(a_doss),
        b=_side(b_doss),
        verdict=parts["verdict"],
        differentiators=parts["differentiators"],
        dimensions=parts["dimensions"],
        must_haves=faceoff,
        a_unique_strengths=parts["a_unique_strengths"],
        b_unique_strengths=parts["b_unique_strengths"],
        a_risks=parts["a_risks"],
        b_risks=parts["b_risks"],
        scenario_fit=parts["scenario_fit"],
        verification_focus=parts["verification_focus"],
    )
    _reconcile(comparison, a_doss, b_doss)

    _CACHE[cache_key] = comparison
    return comparison
