import type { AppState } from "./types";

export function linkedinSearchUrl(state: AppState) {
  const url = new URL("https://www.linkedin.com/jobs/search/");
  const term =
    state.settings.browser_search_queries[0]?.trim() ||
    state.profile.roles[0]?.trim();
  if (term) url.searchParams.set("keywords", term);
  url.searchParams.set("location", "Brasil");
  url.searchParams.set("f_TPR", `r${state.settings.max_job_age_days * 86400}`);
  return url.href;
}
