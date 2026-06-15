import { ChevronDown, UserRound } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/Badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/Collapsible";
import {
  extractProfileOverview,
  formatEducationHeadline,
  formatEducationPeriod,
  groupProjectsByExperience,
  normalizeEducation,
  partitionSkillsForJd,
} from "@/lib/profile-display";
import { S } from "@/lib/strings";
import type { DecisionDossier, ProjectItem } from "@/lib/types";

interface CandidateProfilePanelProps {
  dossier: DecisionDossier;
}

function ProfileSectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80">
      {children}
    </div>
  );
}

function ProfileSummaryBlock({ summary }: { summary: string }) {
  const overview = React.useMemo(() => extractProfileOverview(summary), [summary]);

  return (
    <div className="border-b border-border/60 pb-4">
      <ProfileSectionLabel>{S.profileSummary}</ProfileSectionLabel>
      <p className="max-w-4xl text-sm leading-[1.75] text-foreground/80">
        {overview}
      </p>
    </div>
  );
}

export function CandidateProfilePanel({ dossier }: CandidateProfilePanelProps) {
  const profile = dossier.candidate_profile;
  const { primary, secondary } = partitionSkillsForJd(profile.skills, dossier.score);
  const [showSecondarySkills, setShowSecondarySkills] = React.useState(false);
  const education = normalizeEducation(profile.education);
  const projectGroups = groupProjectsByExperience(
    profile.projects,
    profile.work_experiences,
  );

  return (
    <Collapsible defaultOpen>
      <CollapsibleTrigger className="group flex w-full cursor-pointer items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm font-medium shadow-xs transition-colors hover:border-primary/40 hover:bg-muted/40">
        <span className="flex items-center gap-2">
          <UserRound className="size-4 text-primary" />
          {S.profileHeader}
        </span>
        <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
        <div className="mt-2 space-y-5 rounded-lg border border-border/70 bg-card p-5 shadow-xs">
          <ProfileSummaryBlock summary={profile.summary} />
          {education.length > 0 ? (
            <div>
              <ProfileSectionLabel>{S.profileEducation}</ProfileSectionLabel>
              <ul className="space-y-2">
                {education.map((edu, i) => {
                  const headline = formatEducationHeadline(edu);
                  const period = formatEducationPeriod(
                    edu.start_date ?? "",
                    edu.end_date ?? "",
                  );
                  return (
                    <li
                      key={`${edu.school}-${i}`}
                      className="rounded-md border border-border bg-muted/40 px-3 py-2"
                    >
                      <div className="text-sm font-semibold text-foreground">{edu.school}</div>
                      {headline ? (
                        <div className="mt-0.5 text-sm text-foreground/75">{headline}</div>
                      ) : null}
                      {period ? (
                        <div className="mt-0.5 text-xs text-muted-foreground">{period}</div>
                      ) : null}
                      {edu.gpa ? (
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          GPA {edu.gpa}
                        </div>
                      ) : null}
                      {edu.highlights && edu.highlights.length > 0 ? (
                        <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs text-muted-foreground">
                          {edu.highlights.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {primary.length > 0 ? (
            <div>
              <ProfileSectionLabel>{S.profileSkillsJdRelevant}</ProfileSectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {primary.map((skill) => (
                  <Badge key={skill} variant="default">
                    {skill}
                  </Badge>
                ))}
              </div>
              {secondary.length > 0 ? (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setShowSecondarySkills((open) => !open)}
                    className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {showSecondarySkills
                      ? "收起"
                      : S.profileSkillsOther(secondary.length)}
                  </button>
                  {showSecondarySkills ? (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {secondary.map((skill) => (
                        <Badge key={skill} variant="outline">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
          {profile.work_experiences.length > 0 ? (
            <div>
              <ProfileSectionLabel>{S.profileExperience}</ProfileSectionLabel>
              <ul className="space-y-1.5">
                {profile.work_experiences.map((exp, i) => (
                  <li key={i} className="text-sm leading-snug">
                    <span className="font-semibold text-foreground">{exp.title}</span>
                    <span className="text-foreground/80"> · {exp.company}</span>{" "}
                    <span className="text-xs text-muted-foreground">({exp.duration})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {profile.projects.length > 0 ? (
            <div>
              <ProfileSectionLabel>{S.profileProjects}</ProfileSectionLabel>
              <div className="space-y-4">
                {projectGroups.map((group) => (
                  <section
                    key={group.key}
                    className="relative border-l border-border/60 pl-4"
                  >
                    <span className="absolute -left-[5px] top-1.5 size-2.5 rounded-full border border-primary/60 bg-card shadow-[0_0_0_3px_hsl(var(--card))]" />
                    <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <h4 className="text-sm font-semibold text-foreground">
                        {group.label}
                      </h4>
                      <span className="text-xs text-muted-foreground">
                        {S.profileProjectCount(group.projects.length)}
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {group.projects.map((proj, i) => (
                        <ProjectCard project={proj} key={`${proj.name}-${i}`} />
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function ProjectCard({ project }: { project: ProjectItem }) {
  return (
    <li className="rounded-lg border border-border bg-muted/40 px-3 py-2.5">
      <div className="space-y-1">
        <div className="text-sm font-medium text-foreground">{project.name}</div>
        <p className="text-xs leading-relaxed text-foreground/75">
          {project.description}
        </p>
      </div>
      {project.role_in_project ? (
        <div className="mt-1.5 text-xs text-muted-foreground">
          {S.profileRoleLabel}
          {project.role_in_project}
        </div>
      ) : null}
      {project.quantified_claims && project.quantified_claims.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {project.quantified_claims.map((claim) => (
            <li
              key={claim}
              className="flex gap-1.5 text-xs leading-relaxed text-foreground/70"
            >
              <span className="mt-[0.55em] size-1.5 shrink-0 rounded-full bg-primary/70" />
              <span>{claim}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {project.tech_decisions && project.tech_decisions.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {project.tech_decisions.map((tech) => (
            <Badge key={tech} variant="outline">
              {tech}
            </Badge>
          ))}
        </div>
      ) : null}
    </li>
  );
}
