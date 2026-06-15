import { describe, expect, it } from "vitest";

import { buildSearch, parseNav } from "@/lib/url-state";

describe("parseNav", () => {
  it("defaults to board with no params", () => {
    expect(parseNav("")).toEqual({ run: null, tab: "board", candidate: null });
  });

  it("parses run, prep tab, and candidate", () => {
    expect(parseNav("?run=abc&tab=prep&candidate=wei")).toEqual({
      run: "abc",
      tab: "prep",
      candidate: "wei",
    });
  });

  it("falls back to board for unknown tab values", () => {
    expect(parseNav("?tab=compare").tab).toBe("board");
    expect(parseNav("?tab=audit").tab).toBe("board");
  });
});

describe("buildSearch", () => {
  it("returns empty string for default state", () => {
    expect(buildSearch({ run: null, tab: "board", candidate: null })).toBe("");
  });

  it("omits tab=board and candidate on board", () => {
    expect(buildSearch({ run: "abc", tab: "board", candidate: "wei" })).toBe("?run=abc");
  });

  it("round-trips prep deep link", () => {
    const nav = { run: "abc", tab: "prep" as const, candidate: "wei" };
    expect(parseNav(buildSearch(nav))).toEqual(nav);
  });
});
