import { setTimeout as sleep } from "node:timers/promises";
import { join } from "node:path";
import {
  defaultQueueRoot,
  parseArgs,
  requiredArg,
  resolveInputPath,
  resolveSharepointRoot,
} from "./evaluation-workflow.js";
import { MATRIX_BUILT_FOLDER, MatrixWatcher, type MatrixResult } from "./evaluation-matrices.js";

function positiveNumber(value: string | undefined, fallback: number, flag: string): number {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${flag} must be a positive number`);
  return number;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2), new Set(["once", "dry-run"]));
  const allowed = new Set(["once", "dry-run", "built-root", "queue-root", "sharepoint-root", "poll-seconds", "stable-seconds"]);
  for (const name of args.keys()) {
    if (!allowed.has(name)) throw new Error(`unknown option --${name}`);
  }
  if (args.has("built-root") && args.has("queue-root")) {
    throw new Error("use --built-root or --queue-root, not both");
  }
  const queueRoot = args.has("queue-root")
    ? resolveInputPath(requiredArg(args, "queue-root"))
    : defaultQueueRoot();
  if (!args.has("built-root") && !queueRoot) {
    throw new Error("--built-root or --queue-root is required when OneDrive is not configured");
  }
  const builtRoot = args.has("built-root")
    ? resolveInputPath(requiredArg(args, "built-root"))
    : join(queueRoot ?? "", MATRIX_BUILT_FOLDER);
  const { root: sharepointRoot } = resolveSharepointRoot({
    flag: args.has("sharepoint-root") ? requiredArg(args, "sharepoint-root") : undefined,
  });
  const pollSeconds = positiveNumber(args.get("poll-seconds"), 30, "--poll-seconds");
  const stableSeconds = positiveNumber(args.get("stable-seconds"), 15, "--stable-seconds");
  const watcher = new MatrixWatcher({ builtRoot, sharepointRoot, stableSeconds, dryRun: args.has("dry-run") });
  const reported = new Map<string, string>();
  const report = (results: MatrixResult[]) => {
    const present = new Set(results.map((result) => result.source));
    for (const source of reported.keys()) {
      if (!present.has(source)) reported.delete(source);
    }
    for (const result of results) {
      const message = `${result.status}: ${result.source}${result.destination ? ` -> ${result.destination}` : ""}${result.message ? ` (${result.message})` : ""}`;
      if (reported.get(result.source) !== message) {
        if (result.status === "error") console.error(message);
        else console.log(message);
        reported.set(result.source, message);
      }
    }
  };
  console.log(`Watching completed evaluation matrices: ${builtRoot}`);
  console.log(`SharePoint library: ${sharepointRoot}`);
  console.log(`Poll: ${pollSeconds}s; stable content: ${stableSeconds}s. Originals stay in Built; existing files are never overwritten.`);
  if (args.has("dry-run")) console.log("Dry run: no files or folders will be written.");
  let results = watcher.scan();
  report(results);
  console.log("Matrix watcher ready.");
  if (args.has("once")) {
    if (results.some((result) => result.status === "waiting")) {
      await sleep(stableSeconds * 1000);
      results = watcher.scan();
      report(results);
    }
    console.log(`Scan complete: ${results.length} file(s); ${results.filter((result) => result.status === "waiting").length} still waiting.`);
    if (results.some((result) => result.status === "error" || result.status === "waiting")) {
      process.exitCode = 1;
    }
    return;
  }
  while (true) {
    await sleep(pollSeconds * 1000);
    results = watcher.scan();
    report(results);
  }
}

main().catch((error) => {
  console.error(`Matrix watcher failed: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
