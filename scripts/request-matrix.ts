/**
 * `npm run evaluation:request-matrix -- --slug <slug>`: request a Cowork evaluation matrix for an
 * archived Ready run by hand. `evaluation:archive` (and so `evaluation:watch`) does this
 * automatically after a Ready verdict; use this when that was skipped or failed.
 *
 * Copies the run's frozen, hash-verified ZIP from `evaluation-inbox\<slug>\<version>\` to
 * `<OneDrive>\Cowork Plugin Evals\4 - Matrices\1 - Queue\<slug>-v<version>.zip` and records the
 * request in evaluation-run.json. A version already queued, processed or built is skipped; nothing
 * is overwritten. `--dry-run` reports the destination without writing.
 */
import {
  DEFAULT_INBOX_ROOT,
  defaultQueueRoot,
  findSubmission,
  parseArgs,
  readRun,
  requiredArg,
  resolveInputPath,
} from "./evaluation-workflow.js";
import { describeMatrixRequest, requestRunMatrix } from "./evaluation-matrices.js";

function main(): void {
  const args = parseArgs(process.argv.slice(2), new Set(["dry-run"]));
  const slug = requiredArg(args, "slug");
  const version = args.get("version")?.trim() || findSubmission(slug).version;
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const queueRoot = args.has("queue-root")
    ? resolveInputPath(requiredArg(args, "queue-root"))
    : defaultQueueRoot();
  const { path } = readRun(inboxRoot, slug, version);
  console.log(describeMatrixRequest(requestRunMatrix(path, queueRoot, args.has("dry-run"))));
}

try {
  main();
} catch (error) {
  console.error(`Matrix request failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
