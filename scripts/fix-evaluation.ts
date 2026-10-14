/**
 * `npm run evaluation:fix -- --slug <slug>`: act on an archived Cowork evaluation.
 *
 * Reads the suggested-fixes table in the archived recommendations.html, records advisory items in
 * `submissions\<industry>\<slug>\BACKLOG.md`, writes a fix brief for the blocker and required items
 * to `evaluation-inbox\<slug>\<version>\fix-brief.md`, and starts a Copilot CLI agent on it. The
 * agent bumps the version, applies the fixes, runs the checks, commits locally and stops for review.
 * `--dry-run` writes the brief and backlog without starting the agent.
 */
import { spawnSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  ROOT,
  EvaluationRun,
  FixStatus,
  VERDICT_REPORT,
  assertNonEmptyFile,
  findSubmission,
  parseArgs,
  readRun,
  relativeToRoot,
  requiredArg,
  resolveInputPath,
} from "./evaluation-workflow.js";
import {
  copilotArgs,
  isActionable,
  nextPatchVersion,
  parseRecommendations,
  renderBacklogSection,
  renderFixBrief,
} from "./recommendations.js";

function recommendationsPath(run: EvaluationRun, override: string | undefined): string {
  if (override) return resolveInputPath(override);
  for (const folder of [run.archiveDestination, run.reportSource]) {
    if (folder && existsSync(join(folder, VERDICT_REPORT))) return join(folder, VERDICT_REPORT);
  }
  throw new Error(`no archived ${VERDICT_REPORT} found; run evaluation:archive first or pass --report`);
}

function main(): void {
  const args = parseArgs(process.argv.slice(2), new Set(["dry-run"]));
  const slug = requiredArg(args, "slug");
  const submission = findSubmission(slug);
  const version = args.get("version")?.trim() || submission.version;
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const dryRun = args.has("dry-run");

  const { path: runPath, run } = readRun(inboxRoot, slug, version);
  if (run.status !== "archived") {
    throw new Error(`the ${slug} ${version} evaluation is ${run.status}, not archived; archive its reports first`);
  }
  if (submission.version !== version) {
    throw new Error(
      `${slug} is already at ${submission.version} in submissions; the ${version} recommendations were applied or superseded`,
    );
  }

  const reportPath = recommendationsPath(run, args.get("report"));
  assertNonEmptyFile(reportPath, VERDICT_REPORT);
  const fixes = parseRecommendations(readFileSync(reportPath, "utf8"));
  const actionable = fixes.filter(isActionable);
  const advisory = fixes.length - actionable.length;

  const save = (status: FixStatus, extra: Partial<EvaluationRun> = {}) =>
    writeFileSync(
      runPath,
      `${JSON.stringify({ ...run, ...extra, fixStatus: status, fixUpdatedAt: new Date().toISOString() }, null, 2)}\n`,
      "utf8",
    );

  const backlogPath = join(submission.dir, "BACKLOG.md");
  if (advisory > 0) {
    const section = renderBacklogSection(run.coworkTaskName, version, fixes);
    const existing = existsSync(backlogPath) ? readFileSync(backlogPath, "utf8") : "";
    if (!existing.includes(section.split("\n")[0])) {
      const header = existing ? "" : `# ${submission.displayName} backlog\n\nAdvisory items from Cowork evaluations.\n\n`;
      appendFileSync(backlogPath, `${header}${existing && !existing.endsWith("\n\n") ? "\n" : ""}${section}`, "utf8");
      console.log(`Recorded ${advisory} advisory item(s) in ${relativeToRoot(backlogPath)}.`);
    }
  }

  console.log(`${VERDICT_REPORT}: ${actionable.length} blocker/required fix(es), ${advisory} advisory.`);
  if (actionable.length === 0) {
    save("nothing-to-fix");
    console.log("Nothing for the fix agent to do. Next: the two-tester human spot check (docs/release-process.md).");
    return;
  }

  const nextVersion = nextPatchVersion(version);
  const briefPath = join(inboxRoot, slug, version, "fix-brief.md");
  writeFileSync(
    briefPath,
    renderFixBrief({
      slug,
      displayName: submission.displayName,
      version,
      nextVersion,
      submissionDir: relativeToRoot(submission.dir),
      verdict: run.automatedVerdict ?? "unknown",
      reportPath,
      fixes,
      backlogPath: relativeToRoot(backlogPath),
      advisoryCount: advisory,
    }),
    "utf8",
  );
  save("brief-written", { fixBrief: briefPath, fixVersion: nextVersion });
  console.log(`Fix brief: ${briefPath}`);

  const command = copilotArgs(briefPath, args.get("model"));
  if (dryRun) {
    console.log("Dry run: the fix agent was not started. To start it:");
    console.log(`  copilot ${command.map((arg) => (/[\s()]/.test(arg) ? `"${arg}"` : arg)).join(" ")}`);
    return;
  }

  console.log(`Starting the Copilot CLI fix agent for ${slug} ${version} -> ${nextVersion}...`);
  const result = spawnSync("copilot", command, { cwd: ROOT, stdio: "inherit" });
  const ok = !result.error && result.status === 0;
  save(ok ? "agent-finished" : "agent-failed", { fixBrief: briefPath, fixVersion: nextVersion });
  if (!ok) {
    throw new Error(
      `the fix agent did not finish (${result.error ? result.error.message : `exit code ${result.status}`}); ` +
        `the brief is at ${briefPath}`,
    );
  }
  console.log("");
  console.log(`Fix agent finished. Review its commit (git --no-pager log -1 --stat), then prepare ${nextVersion}:`);
  console.log(`  npm run evaluation:prepare -- --slug ${slug}`);
}

try {
  main();
} catch (error) {
  console.error(`Evaluation fix step failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
