import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  REQUIRED_REPORTS,
  ROOT,
  EvaluationRun,
  assertNonEmptyFile,
  confirmsArtifactMatch,
  findSubmission,
  htmlToText,
  parseArgs,
  requiredArg,
  resolveInputPath,
  resolveSharepointRoot,
  sha256,
} from "./evaluation-workflow.js";

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function positiveNumber(raw: string | undefined, fallback: number, label: string): number {
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${label} must be a positive number`);
  }
  return value;
}

function defaultTasksRoot(): string {
  const oneDrive = process.env.OneDriveCommercial || process.env.OneDrive;
  if (!oneDrive) {
    throw new Error(
      "--tasks-root is required because no OneDriveCommercial or OneDrive environment variable is set",
    );
  }
  return join(oneDrive, "Documents", "Cowork", "Tasks");
}

function findMatchingTasks(tasksRoot: string, slug: string, digest: string): string[] {
  if (!existsSync(tasksRoot)) return [];
  const directories = readdirSync(tasksRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => join(tasksRoot, entry.name))
    .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);

  return directories.filter((directory) => {
    const candidate = join(directory, "input", `${slug}.zip`);
    return existsSync(candidate) && sha256(candidate) === digest;
  });
}

function reportsPresentAndNonEmpty(source: string): boolean {
  return REQUIRED_REPORTS.every((report) => {
    const path = join(source, report);
    return existsSync(path) && statSync(path).isFile() && statSync(path).size > 0;
  });
}

function reportSizes(source: string): Map<string, number> {
  return new Map(
    REQUIRED_REPORTS.map((report) => [report, statSync(join(source, report)).size]),
  );
}

function reportsMatchRun(
  source: string,
  slug: string,
  version: string,
  digest: string,
): boolean {
  const fullReport = readFileSync(join(source, "full-report.html"), "utf8");
  const text = htmlToText(fullReport).toLowerCase();
  return (
    text.includes(slug.toLowerCase()) &&
    text.includes(version.toLowerCase()) &&
    confirmsArtifactMatch(fullReport, digest)
  );
}

function archive(
  slug: string,
  version: string,
  source: string,
  inboxRoot: string,
  sharepointRoot: string,
): void {
  const args = [
    "--slug",
    slug,
    "--version",
    version,
    "--source",
    source,
    "--inbox-root",
    inboxRoot,
    "--sharepoint-root",
    sharepointRoot,
  ];

  const tsxCli = join(ROOT, "node_modules", "tsx", "dist", "cli.mjs");
  const archiveScript = join(ROOT, "scripts", "archive-evaluation.ts");
  execFileSync(process.execPath, [tsxCli, archiveScript, ...args], {
    cwd: ROOT,
    stdio: "inherit",
  });
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const slug = requiredArg(args, "slug");
  const submission = findSubmission(slug);
  const version = args.get("version")?.trim() || submission.version;
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const tasksRoot = args.has("tasks-root")
    ? resolveInputPath(requiredArg(args, "tasks-root"))
    : defaultTasksRoot();
  const { root: sharepointRoot, source: sharepointSource } = resolveSharepointRoot({
    flag: args.has("sharepoint-root") ? requiredArg(args, "sharepoint-root") : undefined,
  });
  const timeoutMinutes = positiveNumber(
    args.get("timeout-minutes"),
    180,
    "--timeout-minutes",
  );
  const pollSeconds = positiveNumber(args.get("poll-seconds"), 30, "--poll-seconds");
  const stableSeconds = positiveNumber(
    args.get("stable-seconds"),
    15,
    "--stable-seconds",
  );

  const manifestPath = join(inboxRoot, slug, version, "evaluation-run.json");
  assertNonEmptyFile(manifestPath, "frozen evaluation-run.json");
  const runData = JSON.parse(readFileSync(manifestPath, "utf8")) as EvaluationRun;
  if (
    runData.schemaVersion !== 1 ||
    runData.slug !== slug ||
    runData.artifactVersion !== version ||
    runData.status !== "prepared"
  ) {
    throw new Error("frozen evaluation manifest is not a prepared run for this slug/version");
  }

  const deadline = Date.now() + timeoutMinutes * 60_000;
  console.log(`Watching ${tasksRoot} for ${slug} ${version}.`);
  console.log(`Expected ZIP SHA-256: ${runData.artifactSha256}`);
  if (runData.testDataFile) {
    // Tasks are matched on the plugin ZIP only; the archive step copies and re-verifies the test data.
    console.log(`Test-data ZIP: ${runData.testDataFile} (SHA-256 ${runData.testDataSha256}); archived alongside the reports.`);
  }
  console.log(`Archive root (${sharepointSource}): ${sharepointRoot}`);

  const reportedTasks = new Set<string>();
  const reportedStaleOutput = new Set<string>();
  while (Date.now() < deadline) {
    const tasks = findMatchingTasks(tasksRoot, slug, runData.artifactSha256);
    for (const task of tasks) {
      if (!reportedTasks.has(task)) {
        console.log(`Matched Cowork task: ${task}`);
        reportedTasks.add(task);
      }
    }

    const stableCandidates = tasks
      .map((task) => ({ task, source: join(task, "output") }))
      .filter(({ source }) => reportsPresentAndNonEmpty(source))
      .map(({ task, source }) => ({ task, source, sizes: reportSizes(source) }));

    if (stableCandidates.length > 0) {
      await sleep(stableSeconds * 1000);
      for (const candidate of stableCandidates) {
        if (
          !reportsPresentAndNonEmpty(candidate.source) ||
          !REQUIRED_REPORTS.every(
            (report) =>
              statSync(join(candidate.source, report)).size ===
              candidate.sizes.get(report),
          )
        ) {
          continue;
        }
        if (!reportsMatchRun(candidate.source, slug, version, runData.artifactSha256)) {
          if (!reportedStaleOutput.has(candidate.task)) {
            console.log(
              `Reports in ${candidate.task} do not affirm the matching version/hash; continuing to search.`,
            );
            reportedStaleOutput.add(candidate.task);
          }
          continue;
        }
        console.log("All three reports are present and stable.");
        archive(slug, version, candidate.source, inboxRoot, sharepointRoot);
        return;
      }
    }
    await sleep(pollSeconds * 1000);
  }
  throw new Error(`timed out after ${timeoutMinutes} minutes waiting for Cowork reports`);
}

main().catch((error) => {
  console.error(`Evaluation watcher failed: ${(error as Error).message}`);
  process.exitCode = 1;
});
