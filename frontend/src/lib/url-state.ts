// URL deep-link state per docs/V2_UI_PROPOSAL.md §3.3.
// Params: run, tab (board|prep), candidate (prep only).

export type MainTab = "board" | "prep";

export interface NavState {
  run: string | null;
  tab: MainTab;
  candidate: string | null;
}

export function parseNav(search: string): NavState {
  const params = new URLSearchParams(search);
  const tab: MainTab = params.get("tab") === "prep" ? "prep" : "board";
  return {
    run: params.get("run"),
    tab,
    candidate: params.get("candidate"),
  };
}

/** Builds the query string; omits defaults so board URLs stay short. */
export function buildSearch(nav: NavState): string {
  const params = new URLSearchParams();
  if (nav.run) params.set("run", nav.run);
  if (nav.tab !== "board") params.set("tab", nav.tab);
  if (nav.tab === "prep" && nav.candidate) params.set("candidate", nav.candidate);
  const search = params.toString();
  return search ? `?${search}` : "";
}
