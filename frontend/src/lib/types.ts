// TS mirror of app/models/contracts.py, events.py, export.py and api/schemas.py.
// Kept intentionally close to the Pydantic shapes so the API response maps 1:1.

export type ParseStatus =
  | "parsed"
  | "unsupported_file_type"
  | "parse_failed"
  | "empty_text"
  | "encrypted_pdf"
  | "scanned_pdf_requires_text_upload"
  | "candidate_parse_failed";

export type RunStatus = "queued" | "running" | "completed" | "needs_review" | "failed";
export type RunMode = "live" | "replay" | "eval";
export type Recommendation = "proceed" | "hold" | "reject";
export type SourceType = "jd" | "resume";
export type Difficulty = "junior" | "mid" | "senior" | "expert";
export type OffsetStatus = "verified" | "approximate" | "unavailable";
export type ValidationStatus = "valid" | "repaired" | "failed";

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
}

export interface CandidateSubScores {
  required_skills: number;
  preferred_skills: number;
  experience_relevance: number;
  project_depth: number;
  ai_engineering_maturity: number;
  communication_clarity: number;
}

export interface CandidateScore {
  overall_score: number;
  recommendation: Recommendation;
  confidence: number;
  sub_scores: CandidateSubScores;
  match_reasons: string[];
  risk_flags: string[];
  evidence_refs: EvidenceSpan[];
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
  technologies: string[];
}

export interface CandidateProfile {
  candidate_name: string;
  summary: string;
  skills: string[];
  work_experiences: WorkExperience[];
  projects: ProjectItem[];
  education: string[];
  certifications: string[];
  evidence_spans: EvidenceSpan[];
  missing_or_ambiguous_claims: string[];
}

export interface InterviewQuestion {
  question: string;
  competency: string;
  difficulty: Difficulty;
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

export interface CandidateRunResult {
  candidate_id: string;
  candidate_name?: string | null;
  status: "completed" | "needs_review" | "failed";
  dossier?: Dossier | null;
  errors: string[];
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

export interface RunCreateResponse {
  run_id: string;
  status: string;
  existing: boolean;
}

export interface HealthResponse {
  status: string;
  mode: string;
  version: string;
  langfuse_enabled: boolean;
  langfuse_verified: boolean;
}

export interface InterviewPreviewResponse {
  candidate_id: string;
  candidate_name: string;
  interviewer_persona: string;
  opening_question: string;
  focus_areas: string[];
  source: string;
}

export type DecisionEventType =
  | "document_parsed"
  | "rubric_extracted"
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
  | "human_override_recorded";

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
