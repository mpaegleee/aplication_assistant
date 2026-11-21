export const factCategories = {
  experience: "Experiência profissional",
  education: "Formação",
  course: "Cursos e certificações",
  skill: "Competências e idiomas",
  other: "Outras qualificações",
} as const;
export type FactCategory = keyof typeof factCategories;
export type Fact = {
  id: string;
  text: string;
  evidence: string;
  source: "pdf" | "manual";
  category?: FactCategory;
};
export type Profile = {
  name: string;
  email: string;
  phone: string;
  city: string;
  linkedin_url: string;
  areas: string[];
  excluded_areas: string[];
  roles: string[];
  modalities: string[];
  contracts: string[];
  locations: string[];
  minimum_salary: number;
  facts: Fact[];
  confirmed: boolean;
  answers: { question: string; answer: string }[];
};
export type Criterion = {
  grade: number;
  weight: number;
  fact_ids: string[];
  job_quote: string;
  reason: string;
};
export type Analysis = {
  score: number | null;
  confidence: number | null;
  criteria?: Record<string, Criterion>;
  blocks: string[];
  gaps?: string;
  resume_fact_ids?: string[];
};
export type JobInput = {
  published_at?: string;
  valid_until?: string;
  country?: "BR" | "unknown";
  title: string;
  company: string;
  url: string;
  description: string;
  area: string;
  area_reviewed: boolean;
  modality: string;
  contract: string;
  location: string;
  salary: number | null;
  recipient: string;
  source: string;
  application_url?: string;
  email_subject?: string;
  instructions_reviewed?: boolean;
};
export type Job = JobInput & {
  id: string;
  status: string;
  created_at: string;
  analysis: Analysis | null;
  approved: boolean;
  sent_at?: string;
  email_eligible: boolean;
  destination?: string;
  pending_reason?: string;
  browser_confirmed?: boolean;
  archived?: boolean;
  pending_code?: string;
  origins?: { url: string; platform: string; source: string }[];
};
export type Settings = {
  search_platforms: string[];
  allowed_destinations: string[];
  browser_search_queries: string[];
  linkedin_posts_enabled: boolean;
  experimental_portal_submission: boolean;
  share_with_enabled_portals: boolean;
  auto_classify_areas: boolean;
  run_time_limit_minutes: number;
  mode: "manual" | "review" | "automatic";
  threshold: number;
  minimum_confidence: number;
  daily_limit: number;
  ai_daily_limit: number;
  max_jobs_per_run: number;
  max_job_age_days: 7 | 15 | 30;
  include_undated_jobs: boolean;
  interval_seconds: number;
  paused: boolean;
  schedule_enabled: boolean;
  weekdays: number[];
  time: string;
  timezone: string;
  ai_url: string;
  ai_model: string;
  ai_key: string;
  ai_consent: boolean;
  ai_key_configured?: boolean;
  allowed_domains: string[];
  sources: {
    name: string;
    url: string;
    enabled: boolean;
    kind?: "feed" | "company" | "greenhouse" | "lever";
    board?: string;
  }[];
  smtp_host: string;
  smtp_port: number;
  smtp_security: string;
  smtp_user: string;
  smtp_password: string;
  smtp_password_configured?: boolean;
  smtp_from: string;
  email_enabled: boolean;
  imap_enabled: boolean;
  imap_host: string;
  imap_port: number;
  imap_user: string;
  imap_password: string;
  imap_password_configured?: boolean;
  imap_folder: string;
  imap_poll_minutes: number;
  imap_max_messages: number;
  auto_followup: boolean;
};
export type Followup = {
  id: string;
  subject: string;
  from: string;
  excerpt: string;
  candidates: string[];
  suggested_status: string;
  confirmed: boolean;
  method?: string;
};
export type AppState = {
  worklist: {
    items: {
      job_id: string;
      score: number;
      confidence: number;
      destination: string;
      automatic_available: boolean;
      destination_enabled: boolean;
    }[];
    summary: {
      eligible: number;
      stale: number;
      blocked: number;
      below_threshold: number;
      archived: number;
      outside_window?: number;
    };
  };
  profile: Profile;
  settings: Settings;
  jobs: Job[];
  areas: string[];
  events: { job_id: string; message: string; at: string }[];
  runs: {
    id: string;
    status: string;
    started_at: string;
    action?: "collect" | "apply";
    consolidated?: number;
    found?: number;
    skipped_age?: number;
    eligible?: number;
    pending?: number;
    duplicates?: number;
    sources?: {
      name: string;
      platform: string;
      found: number;
      new: number;
      duplicates: number;
      status: string;
    }[];
    items?: {
      job_id: string;
      stage: string;
      result: string;
      destination?: string;
    }[];
    imported: number;
    analyzed: number;
    sent: number;
    errors: string[];
  }[];
  followups: Followup[];
  running: boolean;
  configured_sources?: string[];
  pdf_imported: boolean;
  pdf_filename?: string | null;
  connectors: {
    id: string;
    name: string;
    discovery: boolean;
    submission: boolean;
    experimental?: boolean;
    reason: string;
  }[];
  metrics: {
    days: number;
    applied: number;
    smtp_accepted: number;
    browser_confirmed: number;
    reported_manual: number;
    responses: number;
    current: Record<string, number>;
    pending: number;
    by_destination: Record<string, number>;
  };
  mail_status: {
    last_checked_at?: string;
    error?: string;
    imported?: number;
    updated?: number;
  };
};

export type AIProvider = {
  id: string;
  name: string;
  url: string;
  local: boolean;
  help: string;
  docs: string;
};
export type AIModel = { id: string; name: string };

export function editableJob(job: Job): JobInput {
  const keys = [
    "title",
    "company",
    "url",
    "description",
    "area",
    "area_reviewed",
    "modality",
    "contract",
    "location",
    "salary",
    "recipient",
    "source",
    "country",
    "application_url",
    "email_subject",
    "instructions_reviewed",
  ] as const;
  return Object.fromEntries(keys.map((key) => [key, job[key]])) as JobInput;
}
export function editableSettings(settings: Settings) {
  return Object.fromEntries(
    Object.entries(settings).filter(([key]) => !key.endsWith("_configured")),
  );
}
