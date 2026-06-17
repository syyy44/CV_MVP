// TS mirror of app/models/contracts.py, events.py, export.py and api/schemas.py.
// Kept intentionally close to the Pydantic shapes so the API response maps 1:1.

export type ParseStatus =
  | "pending_ingest"
  | "parsed"
  | "unsupported_file_type"
  | "parse_failed"
  | "empty_text"
  | "encrypted_pdf"
  | "scanned_pdf_requires_text_upload"
  | "candidate_parse_failed";

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "needs_review"
  | "failed"
  | "cancelled";
export type RunMode = "live" | "replay" | "eval";
export type Recommendation = "proceed" | "hold" | "reject";
export type SourceType = "jd" | "resume";
export type Difficulty = "junior" | "mid" | "senior" | "expert";
export type OffsetStatus = "verified" | "approximate" | "unavailable";
export type ValidationStatus = "valid" | "repaired" | "failed";

export interface EvidenceContextLine {
  line_no: number;
  text: string;
  is_focus: boolean;
}

export interface EvidenceSpan {
  document_id: string;
  document_hash: string;
  source_type: SourceType;
  snippet: string;
  page_number?: number | null;
  section?: string | null;
  line_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  offset_status: OffsetStatus;
  requirement_id?: string | null;
  context_lines?: EvidenceContextLine[];
}

export interface CandidateSubScores {
  required_skills: number;
  preferred_skills: number;
  experience_relevance: number;
  project_depth: number;
  ai_engineering_maturity: number;
  communication_clarity: number;
}

export type ConfidenceBand = "high" | "medium" | "low";

export interface RequirementResult {
  requirement_id: string;
  display_label: string;
  kind: "must_have";
  met: boolean;
  weight: number;
  jd_evidence_refs?: EvidenceSpan[];
}

export type ClaimCredibility =
  | "well_supported"
  | "plausible"
  | "needs_probing"
  | "suspicious";

export interface ClaimVerification {
  claim: string;
  credibility: ClaimCredibility;
  reason: string;
  verification_hint: string;
  evidence_refs: EvidenceSpan[];
}

export type ScoreDimensionKey = keyof CandidateSubScores;

export type ScoreBand = "strong" | "adequate" | "weak" | "absent";

export interface ScoreDimensionExplanation {
  key: ScoreDimensionKey;
  score: number;
  band: ScoreBand;
  weight: number;
  weighted_points: number;
  rationale: string;
}

export interface ScorePenaltyExplanation {
  kind: string;
  points: number;
  explanation: string;
  requirement_id?: string | null;
}

export interface ScoreBreakdownExplanation {
  base_score: number;
  penalties: ScorePenaltyExplanation[];
  capped_by_deal_breaker: boolean;
  final_score: number;
  recommendation_rule: string;
}

export interface ScoreExplanation {
  verdict_summary?: string;
  fit_reasons?: string[];
  gap_reasons?: string[];
  verification_priorities?: string[];
  confidence_rationale?: string;
  dimensions?: ScoreDimensionExplanation[];
  breakdown?: ScoreBreakdownExplanation | null;
}

export interface CandidateScore {
  overall_score: number;
  recommendation: Recommendation;
  confidence: number;
  sub_scores: CandidateSubScores;
  match_reasons: string[];
  risk_flags: string[];
  evidence_refs: EvidenceSpan[];
  requirement_results: RequirementResult[];
  claim_verifications: ClaimVerification[];
  score_explanation?: ScoreExplanation;
  injection_detected: boolean;
}

export interface WorkExperience {
  title: string;
  company: string;
  duration: string;
  highlights: string[];
}

export interface ProjectItem {
  name: string;
  description: string;
  source_work_experience?: string;
  technologies: string[];
  role_in_project?: string;
  quantified_claims?: string[];
  tech_decisions?: string[];
}

export interface EducationItem {
  school: string;
  degree?: string;
  major?: string;
  start_date?: string;
  end_date?: string;
  gpa?: string | null;
  highlights?: string[];
}

export interface CandidateProfile {
  candidate_name: string;
  summary: string;
  skills: string[];
  work_experiences: WorkExperience[];
  projects: ProjectItem[];
  education: EducationItem[];
  certifications: string[];
  evidence_spans: EvidenceSpan[];
  missing_or_ambiguous_claims: string[];
}

export type QuestionArchetype =
  | "experience_probe"
  | "metric_validation"
  | "depth_probe"
  | "failure_review"
  | "scenario_design"
  | "jd_fit";

export interface InterviewQuestion {
  question: string;
  archetype: QuestionArchetype;
  target_claim: string;
  competency: string;
  difficulty: Difficulty;
  follow_up_probes: string[];
  scoring_criteria: string[];
  good_answer_signals: string[];
  red_flags: string[];
}

export interface FollowUpQuestion {
  question: string;
  ambiguity: string;
  what_to_listen_for: string;
  evidence_refs: EvidenceSpan[];
}

export interface ValidationSummary {
  schema_name: string;
  node_name: string;
  candidate_id?: string | null;
  status: ValidationStatus;
  error_count: number;
  repair_attempts: number;
  messages: string[];
}

export interface DecisionDossier {
  status: "completed";
  candidate_id: string;
  candidate_name: string;
  candidate_profile: CandidateProfile;
  score: CandidateScore;
  questions: InterviewQuestion[];
  follow_ups: FollowUpQuestion[];
  validation_summaries: ValidationSummary[];
  trace_url?: string | null;
}

export interface NeedsReviewDossier {
  status: "needs_review";
  candidate_id: string;
  candidate_name?: string | null;
  partial_profile?: CandidateProfile | null;
  partial_sub_scores?: CandidateSubScores | null;
  validation_summaries: ValidationSummary[];
  repair_attempt_count: number;
  missing_fields: string[];
  reviewer_message: string;
  trace_url?: string | null;
}

export type Dossier = DecisionDossier | NeedsReviewDossier;

export interface HumanOverride {
  recommendation: Recommendation;
  rationale: string;
  actor: string;
  at: string;
}

export interface CandidateNote {
  id?: number | null;
  candidate_id: string;
  run_id: string;
  body: string;
  author: string;
  created_at: string;
}

export interface CandidateRunResult {
  candidate_id: string;
  candidate_name?: string | null;
  status: "completed" | "needs_review" | "failed";
  dossier?: Dossier | null;
  errors: string[];
  decision_summary?: string | null;
  risk_count: number;
  verification_count: number;
  confidence_band?: ConfidenceBand | null;
  human_override?: HumanOverride | null;
}

export type SelectionReason =
  | "claim_probe"
  | "must_have_gap"
  | "dimension_gap"
  | "scenario_coverage"
  | "difficulty_fill";
export type VerificationReason =
  | "injection"
  | "claim_probe"
  | "must_have_gap"
  | "follow_up";

export interface ScriptQuestion {
  index: number;
  question: InterviewQuestion;
  suggested_minutes: number;
  selection_reason?: SelectionReason | null;
}

export interface VerificationItem {
  item: string;
  reason: VerificationReason;
  evidence_refs: EvidenceSpan[];
}

export interface InterviewScriptResponse {
  candidate_id: string;
  candidate_name: string;
  recommendation: Recommendation;
  overall_score: number;
  confidence: number;
  confidence_band: ConfidenceBand;
  script_rule_version: "v3";
  suggested_duration_min: number;
  must_ask: ScriptQuestion[];
  follow_ups: FollowUpQuestion[];
  optional: ScriptQuestion[];
  verification_checklist: VerificationItem[];
  pass_criteria: string;
}

export interface RunMetrics {
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_estimate_usd: number;
  duration_s: number;
}

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  mode: RunMode;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  metrics?: RunMetrics | null;
}

export interface DocumentSummary {
  document_id: string;
  run_id: string;
  source_type: SourceType;
  filename: string;
  parse_status: ParseStatus;
  document_hash?: string | null;
  char_count: number;
  preview: string;
}

export interface RunStatusResponse {
  run: RunSummary;
  candidates: CandidateRunResult[];
  documents: DocumentSummary[];
}

export interface RunListItem {
  run: RunSummary;
  jd_filename?: string | null;
  resume_count: number;
  candidate_count: number;
  top_candidate_name?: string | null;
  top_score?: number | null;
}

export interface RunCreateResponse {
  run_id: string;
  status: string;
  existing: boolean;
}

export interface TestDataFile {
  filename: string;
  url: string;
}

export interface TestDataManifest {
  jd: TestDataFile;
  resumes: TestDataFile[];
}

export interface HealthResponse {
  status: string;
  mode: string;
  version: string;
  langfuse_enabled: boolean;
  langfuse_verified: boolean;
}

export type DecisionEventType =
  | "document_parsed"
  | "rubric_extracted"
  | "candidate_started"
  | "llm_call_started"
  | "candidate_profile_extracted"
  | "schema_validation_failed"
  | "repair_attempted"
  | "repair_succeeded"
  | "repair_failed"
  | "score_component_computed"
  | "recommendation_derived"
  | "questions_generated"
  | "dossier_completed"
  | "human_override_recorded"
  | "note_added";

export interface DecisionEvent {
  id?: number | null;
  run_id: string;
  candidate_id?: string | null;
  event_type: DecisionEventType;
  timestamp: string;
  actor: "system" | "human";
  node_name: string;
  model?: string | null;
  prompt_name?: string | null;
  prompt_version?: string | null;
  input_hash?: string | null;
  output_hash?: string | null;
  schema_name?: string | null;
  validation_status?: ValidationStatus | null;
  repair_attempt?: number | null;
  latency_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  metadata?: Record<string, unknown>;
}

export interface RepairAttemptSummary {
  candidate_id?: string | null;
  node_name: string;
  schema_name?: string | null;
  attempt: number;
  outcome: "repaired" | "failed" | "attempted";
  error_excerpt: string;
}

export interface EvalResultSummary {
  run_id?: string | null;
  scope: "run" | "suite";
  name: string;
  status: "pass" | "fail" | "skipped";
  value?: number | null;
  details: string;
  ts?: string | null;
}

export interface TraceRef {
  candidate_id?: string | null;
  node_name?: string | null;
  trace_id: string;
  url?: string | null;
}

export interface AuditExport {
  schema_version: "audit-export.v1";
  generated_at: string;
  run: RunSummary;
  documents: DocumentSummary[];
  candidate_dossiers: Dossier[];
  decision_events: DecisionEvent[];
  validation_summaries: ValidationSummary[];
  repair_attempts: RepairAttemptSummary[];
  run_eval_results: EvalResultSummary[];
  suite_eval_summary: EvalResultSummary[];
  eval_results: EvalResultSummary[];
  trace_refs: TraceRef[];
  export_status: "complete" | "partial";
  warnings: string[];
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export function isCompletedDossier(d: Dossier | null | undefined): d is DecisionDossier {
  return d?.status === "completed";
}

// ---- 1v1 comparison (compare.v1) -------------------------------------------

export type CompareMargin = "decisive" | "clear" | "slight" | "even";
export type ComparePick = "a" | "b" | "either" | "neither";
export type CompareConfidence = "clear" | "leaning" | "too_close";
export type CompareWinner = "a" | "b" | "tie";
export type CompareSideRef = "a" | "b";

export interface CompareSide {
  candidate_id: string;
  candidate_name: string;
  overall_score_ref: number;
  recommendation_ref: Recommendation;
  confidence_ref: number;
}

export interface DimensionComparison {
  key: ScoreDimensionKey;
  label: string;
  weight: number;
  a_score_ref: number;
  b_score_ref: number;
  a_band: ScoreBand;
  b_band: ScoreBand;
  winner: CompareWinner;
  margin: CompareMargin;
  rationale: string;
  a_basis: string;
  b_basis: string;
}

export interface MustHaveFaceOff {
  requirement_id: string;
  display_label: string;
  a_met: boolean;
  b_met: boolean;
}

export interface CompareDifferentiator {
  favors: CompareSideRef;
  dimension?: ScoreDimensionKey | null;
  text: string;
}

export interface ScenarioFit {
  prefer: CompareSideRef;
  when: string;
}

export interface VerificationFocus {
  item: string;
  why_it_matters: string;
  could_flip: boolean;
}

export interface CompareVerdict {
  pick: ComparePick;
  confidence: CompareConfidence;
  headline: string;
  rationale: string;
  tie_breaker: string;
  would_change_if: string;
  overridden_by_rule: string;
}

export interface CandidateComparison {
  schema_version: "compare.v1";
  run_id: string;
  role_title: string;
  generated_with: "llm" | "deterministic";
  a: CompareSide;
  b: CompareSide;
  verdict: CompareVerdict;
  differentiators: CompareDifferentiator[];
  dimensions: DimensionComparison[];
  must_haves: MustHaveFaceOff[];
  a_unique_strengths: string[];
  b_unique_strengths: string[];
  a_risks: string[];
  b_risks: string[];
  scenario_fit: ScenarioFit[];
  verification_focus: VerificationFocus[];
}
