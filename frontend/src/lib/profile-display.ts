import type {
  CandidateScore,
  EducationItem,
  ProjectItem,
  WorkExperience,
} from "@/lib/types";

const MAX_PRIMARY_SKILLS = 8;

function normalizeToken(value: string): string {
  return value.toLowerCase().trim();
}

function skillMatchesText(skill: string, text: string): boolean {
  const skillNorm = normalizeToken(skill);
  const textNorm = normalizeToken(text);
  if (!skillNorm || !textNorm) return false;
  if (textNorm.includes(skillNorm) || skillNorm.includes(textNorm)) return true;

  const parts = skillNorm.split(/[/\s,，、+]+/).filter(Boolean);
  return parts.some((part) => part.length > 1 && textNorm.includes(part));
}

function scoreSkillRelevance(skill: string, score: CandidateScore): number {
  let points = 0;
  for (const req of score.requirement_results) {
    if (skillMatchesText(skill, req.display_label)) {
      points += req.met ? 12 : 6;
    }
  }
  for (const reason of score.match_reasons) {
    if (skillMatchesText(skill, reason)) {
      points += 4;
    }
  }
  return points;
}

export interface PartitionedSkills {
  primary: string[];
  secondary: string[];
}

export function partitionSkillsForJd(
  skills: string[],
  score: CandidateScore,
  maxPrimary = MAX_PRIMARY_SKILLS,
): PartitionedSkills {
  if (skills.length === 0) {
    return { primary: [], secondary: [] };
  }

  const ranked = skills.map((skill, index) => ({
    skill,
    index,
    relevance: scoreSkillRelevance(skill, score),
  }));
  ranked.sort((a, b) => b.relevance - a.relevance || a.index - b.index);

  const relevant = ranked.filter((item) => item.relevance > 0);
  const primaryItems =
    relevant.length > 0 ? relevant.slice(0, maxPrimary) : ranked.slice(0, maxPrimary);
  const primarySet = new Set(primaryItems.map((item) => item.skill));

  return {
    primary: primaryItems.map((item) => item.skill),
    secondary: skills.filter((skill) => !primarySet.has(skill)),
  };
}

export interface ProjectExperienceGroup {
  key: string;
  label: string;
  projects: ProjectItem[];
}

const UNASSIGNED_PROJECT_GROUP = "未归属到具体工作经历";

export function formatWorkExperienceLabel(exp: WorkExperience): string {
  const headline = [exp.company, exp.title].map((part) => part.trim()).filter(Boolean);
  const duration = exp.duration.trim();
  return `${headline.join(" · ")}${duration ? `（${duration}）` : ""}`;
}

function normalizeMatchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[\s·,，.。;；:：、()[\]（）【】《》"'“”‘’\-–—_/]+/g, "");
}

function characterOverlapRatio(source: string, target: string): number {
  const sourceChars = new Set(source);
  if (sourceChars.size === 0) return 0;
  let overlap = 0;
  for (const char of sourceChars) {
    if (target.includes(char)) overlap += 1;
  }
  return overlap / sourceChars.size;
}

function fuzzyTextScore(needle: string, haystack: string): number {
  const normalizedNeedle = normalizeMatchText(needle);
  const normalizedHaystack = normalizeMatchText(haystack);
  if (normalizedNeedle.length < 4 || normalizedHaystack.length < 4) return 0;
  if (
    normalizedHaystack.includes(normalizedNeedle) ||
    normalizedNeedle.includes(normalizedHaystack)
  ) {
    return Math.min(normalizedNeedle.length, 30);
  }
  const ratio = characterOverlapRatio(normalizedNeedle, normalizedHaystack);
  return ratio >= 0.7 ? ratio * Math.min(normalizedNeedle.length, 18) : 0;
}

function projectExperienceScore(project: ProjectItem, exp: WorkExperience): number {
  const projectFacts = [
    project.name,
    project.description,
    ...(project.quantified_claims ?? []),
    ...project.technologies,
  ];
  let score = 0;
  for (const highlight of exp.highlights) {
    for (const fact of projectFacts) {
      score += fuzzyTextScore(fact, highlight);
    }
  }
  return score;
}

function inferProjectExperienceLabel(
  project: ProjectItem,
  experiences: WorkExperience[],
): string | null {
  let best: { label: string; score: number } | null = null;
  for (const exp of experiences) {
    const score = projectExperienceScore(project, exp);
    if (!best || score > best.score) {
      best = { label: formatWorkExperienceLabel(exp), score };
    }
  }
  return best && best.score >= 8 ? best.label : null;
}

export function groupProjectsByExperience(
  projects: ProjectItem[],
  experiences: WorkExperience[],
): ProjectExperienceGroup[] {
  const groups = new Map<string, ProjectExperienceGroup>();

  for (const project of projects) {
    const explicitLabel = project.source_work_experience?.trim();
    const label =
      explicitLabel ||
      inferProjectExperienceLabel(project, experiences) ||
      UNASSIGNED_PROJECT_GROUP;

    const key = normalizeMatchText(label) || label;
    const group = groups.get(key) ?? { key, label, projects: [] };
    group.projects.push(project);
    groups.set(key, group);
  }

  return Array.from(groups.values());
}

function parseHighlights(raw: string): string[] {
  const text = raw.trim();
  if (!text) return [];
  if (text.startsWith("[") && text.endsWith("]")) {
    try {
      const parsed = JSON.parse(text.replace(/'/g, '"')) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.map(String).map((item) => item.trim()).filter(Boolean);
      }
    } catch {
      // fall through
    }
  }
  return [text];
}

function parseKvEducationString(raw: string): EducationItem {
  const text = raw.trim();
  const lower = text.toLowerCase();
  const schoolStart = lower.indexOf("school:");
  const school =
    schoolStart >= 0
      ? text
          .slice(schoolStart + "school:".length)
          .split(",", 1)[0]
          ?.trim() ?? text
      : text;

  let degree = "";
  let major = "";
  let start_date = "";
  let end_date = "";
  let gpa: string | null = null;
  let highlights: string[] = [];

  for (const part of text.split(",")) {
    const segment = part.trim();
    const segmentLower = segment.toLowerCase();
    if (segmentLower.startsWith("degree:")) {
      degree = segment.split(":", 2)[1]?.trim() ?? "";
    } else if (segmentLower.startsWith("major:")) {
      major = segment.split(":", 2)[1]?.trim() ?? "";
    } else if (segmentLower.startsWith("start_date:")) {
      start_date = segment.split(":", 2)[1]?.trim() ?? "";
    } else if (segmentLower.startsWith("end_date:")) {
      end_date = segment.split(":", 2)[1]?.trim() ?? "";
    } else if (segmentLower.startsWith("gpa:")) {
      const rawGpa = segment.split(":", 2)[1]?.trim() ?? "";
      gpa = ["na", "n/a", "none", ""].includes(rawGpa.toLowerCase()) ? null : rawGpa;
    } else if (segmentLower.startsWith("highlights:")) {
      highlights = parseHighlights(segment.split(":", 2)[1] ?? "");
    }
  }

  return {
    school: school || text,
    degree,
    major,
    start_date,
    end_date,
    gpa,
    highlights,
  };
}

export function parseEducationEntry(entry: EducationItem | string): EducationItem {
  if (typeof entry !== "string") {
    return {
      ...entry,
      gpa: entry.gpa && !["na", "n/a"].includes(entry.gpa.toLowerCase()) ? entry.gpa : null,
      highlights: entry.highlights ?? [],
    };
  }

  const text = entry.trim();
  if (!text) {
    return { school: "" };
  }
  if (text.toLowerCase().includes("school:")) {
    return parseKvEducationString(text);
  }
  return { school: text };
}

export function normalizeEducation(
  items: (EducationItem | string)[],
): EducationItem[] {
  const expanded: (EducationItem | string)[] = [];
  for (const item of items) {
    if (typeof item === "string") {
      const matches = item.match(/school:/gi);
      if (matches && matches.length > 1) {
        expanded.push(
          ...item
            .split(/(?=school:)/i)
            .map((part) => part.trim())
            .filter(Boolean),
        );
        continue;
      }
    }
    expanded.push(item);
  }

  return expanded.map(parseEducationEntry).filter((item) => item.school.trim().length > 0);
}

export function formatEducationPeriod(start: string, end: string): string | null {
  const startDate = start.trim();
  const endDate = end.trim();
  if (startDate && endDate) return `${startDate} – ${endDate}`;
  return startDate || endDate || null;
}

export function formatEducationHeadline(edu: EducationItem): string {
  const parts = [edu.degree, edu.major].map((part) => part?.trim()).filter(Boolean);
  return parts.join(" · ");
}
