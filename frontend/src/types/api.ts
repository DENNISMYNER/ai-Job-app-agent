export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface Skill { name: string; category?: string; level?: string; years?: number | null }
export interface Education { institution: string; degree: string; field_of_study: string; start_date: string; end_date: string; description: string }
export interface Employment { company: string; title: string; location: string; start_date: string; end_date: string; is_current: boolean; description: string; achievements: string[] }
export interface Certification { name: string; issuer: string; issue_date: string; expiry_date: string; credential_url: string }
export interface LanguageSkill { language: string; proficiency: string }
export interface Profile {
  id?: number; full_name: string; email: string; phone: string; location: string; country: string; headline: string; summary: string;
  portfolio_url: string; github_url: string; linkedin_url: string; salary_min: number | null; salary_max: number | null; salary_currency: string;
  employment_types: string[]; preferred_locations: string[]; work_modes: string[]; notice_period: string; available_from: string;
  verified_facts: Record<string, string>;
  education: Education[]; employment: Employment[]; skills: Skill[]; certifications: Certification[]; languages: LanguageSkill[];
}

export interface Match { score: number; recommendation: "apply" | "consider" | "skip"; explanation: string; matched_skills: string[]; missing_skills: string[]; breakdown: Record<string, number | null>; method: string }
export interface Job {
  id: number; title: string; company: string; location: string; remote_type: string; employment_type: string; experience_level: string;
  salary_min: number | null; salary_max: number | null; salary_currency: string; url: string; technologies: string[]; posted_at: string | null;
  discovered_at: string; injection_flags: string[]; dismissed: boolean; match: Match | null;
}
export interface JobDetail extends Job { description_text: string; requirements: { kind: string; text: string; skill: string }[] }
export interface JobSource { id: number; name: string; kind: string; identifier: string; enabled: boolean; config: Record<string, unknown>; last_run_at: string | null; last_status: string }

export interface CV { id: number; listing_id: number | null; parent_id: number | null; category: string; version: number; title: string; warnings: string[]; ats_keywords: string[]; method: string; pdf_path: string; docx_path: string; content: Record<string, unknown> }
export interface CoverLetter { id: number; listing_id: number | null; title: string; content: string; is_template: boolean; version: number; tone: string; method: string }
export interface DocumentFile { id: number; kind: string; filename: string; mime: string; size: number; sha256: string }
export interface SavedAnswer { id: number; question: string; answer: string; category: string; approved: boolean; sensitive: boolean; times_used: number; source: string }
export interface AnswerResult { status: "answered" | "draft" | "needs_user" | "review"; answer: string; source: string; category: string; reason: string; warnings: string[] }

export const STATUSES = ["discovered", "shortlisted", "preparing", "awaiting_approval", "applied", "interview", "assessment", "offer", "rejected", "withdrawn"] as const;
export type Status = (typeof STATUSES)[number];

export interface AppEvent { type: string; detail: string; created_at: string }
export interface Interview { id: number; application_id: number; scheduled_at: string | null; kind: string; location: string; notes: string; prep: Record<string, unknown> }
export interface Recruiter { id: number; application_id: number | null; name: string; email: string; phone: string; company: string; notes: string }
export interface Application {
  id: number; listing_id: number | null; company: string; position: string; job_url: string; status: Status; applied_at: string | null;
  cv_id: number | null; cover_letter_id: number | null; confirmation: string; follow_up_date: string | null; notes: string;
  submission_result: string; approved_at: string | null; created_at: string;
}
export interface FieldResult { field_id: string; label: string; action: string; status: string; value: string; source: string; required: boolean; filled: boolean; verified: boolean; note: string }
export interface FillReport {
  status?: "ready_for_review" | "needs_input" | "intervention_required" | "no_form_found"; reason?: string; url?: string;
  pages?: { page: number; url: string; fields: FieldResult[] }[]; missing_required?: string[]; needs_user?: string[]; review?: string[]; filled?: number;
}
export interface ApplicationDetail extends Application { fill_report: FillReport; events: AppEvent[]; interviews: Interview[]; recruiters: Recruiter[] }

export interface Dashboard {
  discovered_jobs: number; matching_jobs: number; submitted: number; awaiting_approval: number; interviews: number; rejections: number; offers: number;
  by_status: Record<string, number>; follow_ups: { id: number; company: string; position: string; date: string }[];
  recent_activity: { actor: string; action: string; message: string; at: string }[];
}
export interface AppNotification { id: number; kind: string; title: string; body: string; read: boolean; payload: Record<string, unknown>; created_at: string }
export interface Schedule { id: number; name: string; task_type: string; cron: string; params: Record<string, unknown>; enabled: boolean; last_run_at: string | null; last_status: string }
export interface EmailDraft { id: number; application_id: number | null; to_address: string; subject: string; body: string; status: string; error: string }
export interface AIStatus { reachable: boolean; models: string[]; chat_model: string; chat_model_installed: boolean; embedding_model: string; embedding_model_installed: boolean; message: string; enabled: boolean }
export interface MatchingSettings { min_apply_score: number; min_consider_score: number; weights: Record<string, number>; target_titles: string[]; excluded_keywords: string[] }
export interface AutomationSettings { require_approval: boolean; auto_submit_enabled: boolean; auto_submit_min_score: number; auto_submit_daily_limit: number; headless: boolean; notify_min_score: number }
