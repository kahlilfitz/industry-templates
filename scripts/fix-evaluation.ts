/**
 * `npm run evaluation:fix -- --slug <slug>`: act on an archived Cowork evaluation.
 *
 * Reads the suggested-fixes table in the archived recommendations.html, records advisory items in
 * `submissions\<industry>\<slug>\BACKLOG.md`, writes a fix brief for the blocker and required items
 * to `evaluation-inbox\<slug>\<version>\fix-brief.md`, and starts a Copilot CLI agent on it. The
 * agent bumps the version, applies the fixes, runs the checks, commits locally, writes
 * `fix-result.json` and stops. If every fix was applied with no conflict, the commit is the next
 * version and only plugin files changed, the next version is prepared (`evaluation:prepare`) the
 * same way as this one (queue or manual); otherwise it stops with the reasons for the owner.
 * `--dry-run` writes the brief and backlog without starting the agent; `--no-prepare` skips the
 * automatic prepare.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
  runScript,
} from "./evaluation-workflow.js";
import {
  FIX_RESULT_FILE,
  FixCommit,
  copilotArgs,
  fixAttention,
  isActionable,
  nextPatchVersion,
  parseRecommendations,
  renderBacklogSection,
  renderFixBrief,
} from "./recommendations.js";

function git(args: string[]): string {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8" });
}

function commitsSince(base: string): FixCommit[] {
  return git(["log", "--format=%H%x09%s", `${base}..HEAD`])
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const [hash, ...subject] = line.split("\t");
      const files = git(["diff-tree", "--no-commit-id", "--name-only", "-r", hash]).split("\n").filter(Boolean);
      return { hash, subject: subject.join("\t"), files };
    });
}

function readResult(path: string): unknown {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return undefined;
  }
}

function recommendationsPath(run: EvaluationRun, override: string | undefined): string {
  if (override) return resolveInputPath(override);
  for (const folder of [run.archiveDestination, run.reportSource]) {
    if (folder && existsSync(join(folder, VERDICT_REPORT))) return join(folder, VERDICT_REPORT);
  }
  throw new Error(`no archived ${VERDICT_REPORT} found; run evaluation:archive first or pass --report`);
}

function main(): void {
  const args = parseArgs(process.argv.slice(2), new Set(["dry-run", "no-prepare"]));
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
    console.log("Nothing for the fix agent to do. Next: the owner's Publish decision (docs/release-process.md, Step 5).");
    return;
  }

  const nextVersion = nextPatchVersion(version);
  const briefPath = join(inboxRoot, slug, version, "fix-brief.md");
  const resultPath = join(inboxRoot, slug, version, FIX_RESULT_FILE);
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
      resultPath,
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
  rmSync(resultPath, { force: true });
  const base = git(["rev-parse", "HEAD"]).trim();
  const result = spawnSync("copilot", command, { cwd: ROOT, stdio: "inherit" });
  const ok = !result.error && result.status === 0;
  if (!ok) {
    save("agent-failed", { fixBrief: briefPath, fixVersion: nextVersion });
    throw new Error(
      `the fix agent did not finish (${result.error ? result.error.message : `exit code ${result.status}`}); ` +
        `the brief is at ${briefPath}`,
    );
  }

  const submissionDir = relativeToRoot(submission.dir);
  const attention = fixAttention({
    slug,
    nextVersion,
    actionableIds: actionable.map((fix) => fix.id),
    result: readResult(resultPath),
    submissionVersion: findSubmission(slug).version,
    submissionDir,
    commits: commitsSince(base),
    uncommitted: git(["status", "--porcelain", "--", submissionDir]).split("\n").filter(Boolean),
  });
  console.log("");
  if (attention.length > 0) {
    save("needs-attention", { fixBrief: briefPath, fixVersion: nextVersion, fixAttention: attention });
    throw new Error(
      `the fix agent finished, but ${nextVersion} needs the owner's attention before it is prepared:\n  ` +
        `${attention.join("\n  ")}\nReview its work (git --no-pager log -1 --stat), then prepare ${nextVersion} with ` +
        `npm run evaluation:prepare -- --slug ${slug}`,
    );
  }
  save("agent-finished", { fixBrief: briefPath, fixVersion: nextVersion });
  console.log(`Fix agent finished cleanly: every fix applied and committed as ${nextVersion}.`);
  if (args.has("no-prepare")) {
    console.log(`Automatic prepare skipped (--no-prepare). Prepare ${nextVersion} with:`);
    console.log(`  npm run evaluation:prepare -- --slug ${slug}`);
    return;
  }

  // The next version goes the same way as this one: queued if this run was queued, else manual.
  const queueArgs = args.has("queue-root")
    ? ["--queue-root", requiredArg(args, "queue-root")]
    : run.queueSubmission
      ? []
      : ["--no-queue"];
  console.log(`Preparing ${nextVersion}...`);
  runScript("prepare-evaluation.ts", ["--slug", slug, "--inbox-root", inboxRoot, ...queueArgs]);
  save("next-prepared", { fixBrief: briefPath, fixVersion: nextVersion });
  console.log(`Review the fix commit (git --no-pager log -1 --stat); then watch ${nextVersion}:`);
  console.log(`  npm run evaluation:watch -- --slug ${slug}`);
}

try {
  main();
} catch (error) {
  console.error(`Evaluation fix step failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
