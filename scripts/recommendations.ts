/**
 * Reads the suggested-fixes table in a Cowork recommendations.html and turns it into a fix brief
 * for the Copilot CLI fix agent. Pure functions only; scripts/fix-evaluation.ts does the I/O.
 */
import { htmlToText } from "./evaluation-workflow.js";

export type Severity = "blocker" | "required" | "advisory";

export type Recommendation = {
  id: string;
  severity: Severity;
  target: string;
  evidence: string;
  change: string;
};

const COLUMNS = {
  severity: /severity|priority/i,
  id: /^(?:id|#|ref(?:erence)?|fix id)$/i,
  evidence: /evidence|finding|observ/i,
  change: /suggest|change|fix|recommend|action/i,
  target: /skill|file|component|area|target/i,
} as const;

type Column = keyof typeof COLUMNS;

function cells(rowHtml: string): string[] {
  return [...rowHtml.matchAll(/<t[hd]\b[^>]*>([\s\S]*?)<\/t[hd]>/gi)].map((match) => htmlToText(match[1]));
}

function mapHeader(header: string[]): Partial<Record<Column, number>> {
  const map: Partial<Record<Column, number>> = {};
  header.forEach((label, index) => {
    const column = (Object.keys(COLUMNS) as Column[]).find(
      (name) => map[name] === undefined && COLUMNS[name].test(label.trim()),
    );
    if (column) map[column] = index;
  });
  return map;
}

export function normalizeSeverity(raw: string): Severity | undefined {
  const value = raw.toLowerCase();
  if (/\b(?:blocker|blocking|hard[\s-]?stop|critical)\b/.test(value)) return "blocker";
  if (/\b(?:required|must|high|medium)\b/.test(value)) return "required";
  if (/\b(?:advisory|optional|nice[\s-]to[\s-]have|low|suggestion)\b/.test(value)) return "advisory";
  return undefined;
}

/**
 * The suggested fixes from the first table whose header has Severity and Suggested change columns.
 * Rows without a recognisable severity (for example "Nothing to fix") are skipped.
 */
export function parseRecommendations(html: string): Recommendation[] {
  for (const table of html.matchAll(/<table\b[\s\S]*?<\/table>/gi)) {
    const rows = [...table[0].matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)].map((row) => cells(row[1]));
    const headerIndex = rows.findIndex((row) => row.length > 0);
    if (headerIndex < 0) continue;
    const columns = mapHeader(rows[headerIndex]);
    if (columns.severity === undefined || columns.change === undefined) continue;

    const fixes: Recommendation[] = [];
    for (const row of rows.slice(headerIndex + 1)) {
      const severity = normalizeSeverity(row[columns.severity] ?? "");
      if (!severity) continue;
      const pick = (column: Column) => (columns[column] === undefined ? "" : (row[columns[column]!] ?? "").trim());
      fixes.push({
        id: pick("id") || `R${fixes.length + 1}`,
        severity,
        target: pick("target"),
        evidence: pick("evidence"),
        change: pick("change"),
      });
    }
    return fixes;
  }
  throw new Error(
    "recommendations.html has no suggested-fixes table with Severity and Suggested change columns",
  );
}

export function isActionable(fix: Recommendation): boolean {
  return fix.severity !== "advisory";
}

/** 1.0.6 -> 1.0.7; the last numeric segment is incremented. */
export function nextPatchVersion(version: string): string {
  const match = version.match(/^(.*?)(\d+)$/);
  if (!match) throw new Error(`cannot bump version ${version}: it does not end in a number`);
  return `${match[1]}${Number(match[2]) + 1}`;
}

function fixLines(fix: Recommendation): string[] {
  return [
    `### ${fix.id} (${fix.severity})${fix.target ? `: ${fix.target}` : ""}`,
    "",
    `- Evidence: ${fix.evidence || "(not stated)"}`,
    `- Suggested change: ${fix.change || "(not stated)"}`,
    "",
  ];
}

export type BriefInput = {
  slug: string;
  displayName: string;
  version: string;
  nextVersion: string;
  submissionDir: string;
  verdict: string;
  reportPath: string;
  fixes: Recommendation[];
  backlogPath: string;
  advisoryCount: number;
};

export function renderFixBrief(input: BriefInput): string {
  const actionable = input.fixes.filter(isActionable);
  return [
    `# Fix brief: ${input.displayName} (${input.slug}) ${input.version} -> ${input.nextVersion}`,
    "",
    `Cowork evaluated ${input.slug} ${input.version} with the automated verdict **${input.verdict}**.`,
    `Source: ${input.reportPath}`,
    `Plugin folder: ${input.submissionDir}`,
    "",
    "## Rules",
    "",
    "- Do not invoke skills; work from this brief and the repository.",
    "- Apply only the fixes listed below, in order. Each fix must address its evidence.",
    "- Follow CONTRIBUTING.md and docs/release-process.md.",
    "- Change only files in the plugin folder. Include its BACKLOG.md in the commit if it has uncommitted changes.",
    `- Set the version to ${input.nextVersion} everywhere \`npm run check:submissions\` requires it to match.`,
    `- Add a CHANGELOG.md entry for ${input.nextVersion} listing each fix ID and what changed.`,
    "- Run `npm run check:submissions` and `npm run test:evaluation`; both must pass.",
    `- Commit only the files you changed, path-limited: \`git commit -m "${input.slug} ${input.nextVersion}: apply Cowork recommendations" -- <paths>\`,`,
    "  with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.",
    "- Do not push, do not run `npm run evaluation:prepare`, and do not write to `sharepoint\\` or `evaluation-inbox\\`.",
    "- If a fix is unclear or cannot be applied safely, skip it and say why.",
    "- Finish with a short summary: each fix ID with applied or skipped, and the commit hash.",
    "",
    `## Fixes to apply (${actionable.length})`,
    "",
    ...actionable.flatMap(fixLines),
    input.advisoryCount > 0
      ? `Advisory items (${input.advisoryCount}) were recorded in ${input.backlogPath}; do not apply them.`
      : "There are no advisory items.",
    "",
  ].join("\n");
}

/** Non-interactive Copilot CLI arguments that hand the brief to a fix agent. It may not push. */
export function copilotArgs(briefPath: string, model?: string): string[] {
  return [
    "-p",
    `Read the fix brief at ${briefPath} and carry it out exactly. Stop when it is done.`,
    "--allow-all-tools",
    "--deny-tool=shell(git push)",
    "--no-ask-user",
    ...(model ? ["--model", model] : []),
  ];
}

/** A BACKLOG.md section for the advisory items of one evaluation run. */
export function renderBacklogSection(runLabel: string, version: string, fixes: Recommendation[]): string {
  const advisory = fixes.filter((fix) => !isActionable(fix));
  return [
    `## ${version} evaluation (${runLabel})`,
    "",
    ...advisory.flatMap((fix) => [
      `- [ ] **${fix.id}**${fix.target ? ` (${fix.target})` : ""}: ${fix.change || "(no change stated)"}`,
      `  - Evidence: ${fix.evidence || "(not stated)"}`,
    ]),
    "",
  ].join("\n");
}
