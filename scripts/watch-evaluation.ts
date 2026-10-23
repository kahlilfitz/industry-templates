import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  EVAL_QUEUE_STAGES,
  REQUIRED_REPORTS,
  EvaluationRun,
  VERDICT_REPORT,
  assertNonEmptyFile,
  confirmsArtifactMatch,
  defaultQueueRoot,
  findEvaluatedQueueRuns,
  findQueueAttention,
  findReports,
  findSubmission,
  htmlToText,
  parseArgs,
  queuePairNames,
  requiredArg,
  resolveInputPath,
  resolveSharepointRoot,
  runScript,
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

function reportSizes(reports: Map<string, string>): Map<string, number> {
  return new Map([...reports].map(([report, path]) => [report, statSync(path).size]));
}

function sameReports(left: Map<string, string>, right: Map<string, string> | undefined): boolean {
  return (
    right !== undefined &&
    REQUIRED_REPORTS.every((report) => left.get(report) === right.get(report))
  );
}

function reportsMatchRun(
  verdictPath: string,
  slug: string,
  version: string,
  digest: string,
): boolean {
  const verdictReport = readFileSync(verdictPath, "utf8");
  const text = htmlToText(verdictReport).toLowerCase();
  return (
    text.includes(slug.toLowerCase()) &&
    text.includes(version.toLowerCase()) &&
    confirmsArtifactMatch(verdictReport, digest)
  );
}

function archive(
  slug: string,
  version: string,
  source: string,
  inboxRoot: string,
  sharepointRoot: string,
  extra: string[],
): void {
  runScript("archive-evaluation.ts", [
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
    ...extra,
  ]);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2), new Set(["no-fix", "no-prepare", "no-matrix"]));
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
  const fix = !args.has("no-fix");
  const stableSeconds = positiveNumber(
    args.get("stable-seconds"),
    15,
    "--stable-seconds",
  );

  const manifestPath = join(inboxRoot, slug, version, "evaluation-run.json");
  assertNonEmptyFile(manifestPath, "evaluation-run.json");
  const runData = JSON.parse(readFileSync(manifestPath, "utf8")) as EvaluationRun;
  if (
    runData.schemaVersion !== 1 ||
    runData.slug !== slug ||
    runData.artifactVersion !== version ||
    runData.status !== "prepared"
  ) {
    throw new Error("evaluation-run.json is not a prepared run for this slug/version");
  }

  const deadline = Date.now() + timeoutMinutes * 60_000;
  const queueRoot = args.has("queue-root")
    ? resolveInputPath(requiredArg(args, "queue-root"))
    : defaultQueueRoot();
  const useQueue = Boolean(queueRoot && existsSync(queueRoot));
  const pair = queuePairNames(slug, version);
  console.log(`Watching ${tasksRoot} for ${slug} ${version}.`);
  if (useQueue) console.log(`Watching the Cowork queue ${queueRoot} for ${pair.zip}.`);
  console.log(`Expected ZIP SHA-256: ${runData.artifactSha256}`);
  console.log(`Archive root (${sharepointSource}): ${sharepointRoot}`);
  console.log(fix ? "After archiving, the fix step starts a Copilot CLI agent (--no-fix to skip)." : "Fix step disabled (--no-fix).");
  console.log(
    args.has("no-matrix")
      ? "Matrix request disabled (--no-matrix)."
      : "A Ready verdict also sends the ZIP to Cowork's matrix queue (--no-matrix to skip).",
  );

  const reported = new Set<string>();
  const once = (key: string, message: string) => {
    if (!reported.has(key)) {
      console.log(message);
      reported.add(key);
    }
  };
  while (Date.now() < deadline) {
    const sources: string[] = [];
    for (const task of findMatchingTasks(tasksRoot, slug, runData.artifactSha256)) {
      once(`task:${task}`, `Matched Cowork task: ${task}`);
      sources.push(join(task, "output"));
    }
    if (useQueue && queueRoot) {
      const attention = findQueueAttention(queueRoot, slug, version, runData.artifactSha256);
      if (attention.length > 0) {
        throw new Error(
          `Cowork moved ${pair.zip} to "${EVAL_QUEUE_STAGES.needsAttention}" (missing pair, SHA-256 mismatch or a ` +
            `failed run); read its note and eval-ledger.md. If the plugin is unchanged, re-send it with ` +
            `npm run evaluation:prepare -- --slug ${slug} --requeue:\n  ${attention.join("\n  ")}`,
        );
      }
      if (existsSync(join(queueRoot, EVAL_QUEUE_STAGES.inProgress, pair.zip))) {
        once("queue:in-progress", `Cowork started the queued run (${EVAL_QUEUE_STAGES.inProgress}).`);
      }
      for (const dir of findEvaluatedQueueRuns(queueRoot, slug, version, runData.artifactSha256)) {
        once(`queue:${dir}`, `Matched Cowork queue run: ${dir}`);
        sources.push(dir);
      }
    }

    const candidates = sources.flatMap((dir) => {
      const reports = findReports(dir);
      return reports ? [{ dir, reports, sizes: reportSizes(reports) }] : [];
    });

    if (candidates.length > 0) {
      await sleep(stableSeconds * 1000);
      for (const candidate of candidates) {
        const now = findReports(candidate.dir);
        if (
          !now ||
          !sameReports(candidate.reports, now) ||
          !REQUIRED_REPORTS.every(
            (report) => statSync(now.get(report) as string).size === candidate.sizes.get(report),
          )
        ) {
          continue;
        }
        if (!reportsMatchRun(now.get(VERDICT_REPORT) as string, slug, version, runData.artifactSha256)) {
          once(
            `stale:${candidate.dir}`,
            `Reports in ${candidate.dir} do not affirm the matching version/hash; continuing to search.`,
          );
          continue;
        }
        console.log(`All three reports are present and stable: ${candidate.dir}`);
        archive(slug, version, candidate.dir, inboxRoot, sharepointRoot, [
          ...(args.has("no-matrix") ? ["--no-matrix"] : []),
          ...(args.has("queue-root") ? ["--queue-root", requiredArg(args, "queue-root")] : []),
        ]);
        if (fix) {
          runScript("fix-evaluation.ts", [
            "--slug",
            slug,
            "--version",
            version,
            "--inbox-root",
            inboxRoot,
            ...(args.has("model") ? ["--model", requiredArg(args, "model")] : []),
            ...(args.has("no-prepare") ? ["--no-prepare"] : []),
            ...(args.has("queue-root") ? ["--queue-root", requiredArg(args, "queue-root")] : []),
          ]);
        }
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
