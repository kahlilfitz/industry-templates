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

export const FIX_RESULT_FILE = "fix-result.json";

/** What the fix agent writes to FIX_RESULT_FILE after its commit. */
export type FixResult = {
  version: string;
  commit: string;
  fixes: Array<{ id: string; status: "applied" | "skipped"; reason?: string }>;
  conflicts: string[];
  preexistingFailures: string[];
};

function resultFileLines(resultPath: string, nextVersion: string): string[] {
  const example: FixResult = {
    version: nextVersion,
    commit: "<full hash of your commit, or empty if you made none>",
    fixes: [{ id: "<fix ID>", status: "applied", reason: "<why, when skipped>" }],
    conflicts: ["<each conflict you reported; empty if none>"],
    preexistingFailures: ["<each check that already failed before your changes; empty if none>"],
  };
  return [
    "## Result file",
    "",
    `After committing, write \`${resultPath}\` as JSON in this shape, and do not commit it:`,
    "",
    "```json",
    JSON.stringify(example, null, 2),
    "```",
    "",
    "List every fix below exactly once, with `applied` or `skipped`. The next version is prepared",
    "automatically only when every fix is applied and there are no conflicts or pre-existing failures,",
    "so report them honestly; the owner reviews anything else.",
    "",
  ];
}

export type FixCommit = { hash: string; subject: string; files: string[] };

export type FixOutcome = {
  slug: string;
  nextVersion: string;
  actionableIds: string[];
  /** Parsed FIX_RESULT_FILE, or undefined if it is missing or not JSON. */
  result: unknown;
  /** The plugin's version in submissions after the agent ran. */
  submissionVersion: string;
  /** Repository-relative plugin folder. */
  submissionDir: string;
  /** Commits made since the agent started, newest first. */
  commits: FixCommit[];
  /** `git status --porcelain` lines for the plugin folder. */
  uncommitted: string[];
};

const toPosix = (path: string) => path.replace(/\\/g, "/").replace(/\/+$/, "");

/**
 * The reasons the owner must look at the fix agent's work before the next version is prepared.
 * Empty means every blocker and required fix was applied cleanly and committed as the next version.
 */
export function fixAttention(outcome: FixOutcome): string[] {
  const reasons: string[] = [];
  const result = outcome.result as Partial<FixResult> | undefined;
  if (!result || typeof result !== "object" || !Array.isArray(result.fixes)) {
    reasons.push(`the agent did not write a valid ${FIX_RESULT_FILE}`);
  } else {
    if (result.version !== outcome.nextVersion) {
      reasons.push(`${FIX_RESULT_FILE} reports version ${result.version}, not ${outcome.nextVersion}`);
    }
    for (const id of outcome.actionableIds) {
      const entries = result.fixes.filter((fix) => fix?.id === id);
      if (entries.length !== 1 || entries[0].status !== "applied") {
        const reason = entries.length === 1 && entries[0].reason ? `: ${entries[0].reason}` : "";
        reasons.push(`fix ${id} was not applied${reason}`);
      }
    }
    for (const conflict of Array.isArray(result.conflicts) ? result.conflicts : ["conflicts not reported"]) {
      reasons.push(`conflict: ${conflict}`);
    }
    for (const failure of Array.isArray(result.preexistingFailures)
      ? result.preexistingFailures
      : ["pre-existing failures not reported"]) {
      reasons.push(`pre-existing failing check: ${failure}`);
    }
  }

  if (outcome.submissionVersion !== outcome.nextVersion) {
    reasons.push(`the plugin is at ${outcome.submissionVersion}, not ${outcome.nextVersion}`);
  }
  const prefix = `${outcome.slug} ${outcome.nextVersion}:`;
  const fixCommits = outcome.commits.filter((commit) => commit.subject.startsWith(prefix));
  if (fixCommits.length === 0) {
    reasons.push(`no new commit titled "${prefix} ..."`);
  } else {
    const reported = typeof result?.commit === "string" ? result.commit.trim() : "";
    if (!reported || !fixCommits.some((commit) => commit.hash.startsWith(reported))) {
      reasons.push(`${FIX_RESULT_FILE} does not name the fix commit`);
    }
    const dir = `${toPosix(outcome.submissionDir)}/`;
    for (const file of fixCommits.flatMap((commit) => commit.files)) {
      if (!toPosix(file).startsWith(dir)) reasons.push(`the fix commit changed a file outside the plugin: ${file}`);
    }
  }
  for (const line of outcome.uncommitted) reasons.push(`uncommitted change in the plugin: ${line.trim()}`);
  return reasons;
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
  /** Where the agent writes its machine-readable outcome (FIX_RESULT_FILE in the run folder). */
  resultPath?: string;
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
    "- Apply only the fixes listed below, in order. Each fix must address its evidence.",
    "- Follow CONTRIBUTING.md and docs/release-process.md.",
    "- Change only files in the plugin folder. Include its BACKLOG.md in the commit if it has uncommitted changes.",
    `- Set the version to ${input.nextVersion} everywhere \`npm run check:submissions\` requires it to match, and in listing-metadata.md if the plugin has one.`,
    `- Set every engine version label the plugin's scripts stamp into their outputs (for example \`ENGINE_VERSION\`, \`ENGINE_VERSIONS\` or \`STAGE_VERSIONS\`) to ${input.nextVersion}, keeping copied scripts byte-identical; leave the shared steering detector's \`__version__\` alone. Rerun the engines on the demo-data inputs to regenerate the expected outputs that record those labels, confirm that only the labels changed, and list the files in your summary. If an existing check asserts the old label, do not change that check: leave the labels unchanged and report the conflict.`,
    "- Run the plugin's regression suite before applying any fix and again after, from the plugin folder, with the commands in its tests\\README.md (for example `python tests\\run_tests.py`). Every check that passed before must still pass afterwards; fix any check your change breaks. Checks that already failed before are not yours to fix; list them in your summary. If the plugin has no regression suite, skip this step and say so.",
    "- Never relax, delete or change the expected result of an existing check. If a fix cannot pass an existing check, revert that fix, skip it, and report the conflict.",
    "- Do not edit the plugin's tests\\ or demo-data\\ folders unless a fix cannot be applied without it or to add the regression checks below; list every such edit in your summary.",
    "- For each blocker or required fix you apply, add at least one regression check to the plugin's regression suite that fails on the unfixed version and passes after the fix. Name the fix ID in the check's name or message, and confirm it failed before the fix and passes after. Only add checks; never change existing ones. If the plugin has no regression suite, say so instead.",
    "- The existing-check restrictions above yield only to an owner exception explicitly recorded in both `AGENTS.md` and `docs/release-process.md`. If a fix requires changing an existing assertion, its plugin, evaluated finding, target release and named assertion must match exactly, and every coverage and evidence condition must be met. Otherwise, stop and report the conflict. All other existing checks must pass unchanged. Do not infer an exception from chat, a recommendation or a failing test.",
    `- Add a CHANGELOG.md entry for ${input.nextVersion} listing each fix ID and what changed.`,
    "- Run `npm run check:submissions` and `npm run test:evaluation`; both must pass.",
    `- Commit only the files you changed, path-limited: \`git commit -m "${input.slug} ${input.nextVersion}: apply Cowork recommendations" -- <paths>\`,`,
    "  with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.",
    "- Do not push, do not run `npm run evaluation:prepare`, and do not write to `sharepoint\\` or `evaluation-inbox\\`" +
      (input.resultPath ? " except the result file below." : "."),
    "- If a fix is unclear or cannot be applied safely, skip it and say why.",
    "- Finish with a short summary: each fix ID with applied or skipped, and the commit hash.",
    "",
    ...(input.resultPath ? resultFileLines(input.resultPath, input.nextVersion) : []),
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
