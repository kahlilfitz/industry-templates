/**
 * `npm run evaluation:prepare -- --slug <slug>`: package one plugin for a Cowork evaluation.
 *
 * Validates submissions, builds the bundles, copies the plugin ZIP into `evaluation-inbox\<slug>\<version>\`, records its SHA-256 in
 * evaluation-run.json and renders the Cowork prompt. If the Cowork evaluation queue folder exists
 * (`<OneDrive>\Cowork Plugin Evals\1 - To evaluate`, or --queue-root), it also drops the
 * `<slug>-v<version>.zip` and `-prompt.md` pair there for Cowork to pick up; --no-queue skips that.
 * It runs no plugin tests and freezes nothing.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  EVAL_QUEUE_STAGES,
  ROOT,
  EvaluationRun,
  assertNonEmptyFile,
  defaultQueueRoot,
  findSubmission,
  parseArgs,
  queuePairNames,
  queuePrompt,
  requiredArg,
  resolveInputPath,
  sha256,
} from "./evaluation-workflow.js";

/** Same-volume rename so Cowork never sees a half-written file; copy only across volumes. */
function moveInto(source: string, target: string): void {
  try {
    renameSync(source, target);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EXDEV") throw error;
    copyFileSync(source, target);
    rmSync(source);
  }
}

function run(command: string, args: string[]): void {
  if (process.platform === "win32") {
    const commandLine = [command, ...args].join(" ");
    execFileSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", commandLine], {
      cwd: ROOT,
      stdio: "inherit",
    });
    return;
  }
  execFileSync(command, args, { cwd: ROOT, stdio: "inherit" });
}

function git(args: string[]): string {
  return execFileSync("git", args, {
    cwd: ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  }).trim();
}

function renderPrompt(template: string, values: Record<string, string>): string {
  const output = Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{{${name}}}`, value),
    template,
  );
  const leftover = output.match(/\{\{[A-Z0-9_]+\}\}/);
  if (leftover) throw new Error(`prompt template placeholder ${leftover[0]} was not filled`);
  return output;
}

function main(): void {
  const args = parseArgs(process.argv.slice(2), new Set(["no-queue"]));
  const slug = requiredArg(args, "slug");
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const submission = findSubmission(slug);
  const mos3 = submission.packageFormat === "mos3";

  const runDir = join(inboxRoot, slug, submission.version);
  if (existsSync(runDir)) {
    throw new Error(`an evaluation candidate already exists for ${slug} ${submission.version}: ${runDir}`);
  }

  const queueRoot = args.has("no-queue")
    ? undefined
    : args.has("queue-root")
      ? resolveInputPath(requiredArg(args, "queue-root"))
      : defaultQueueRoot();
  const queueInbox = queueRoot && join(queueRoot, EVAL_QUEUE_STAGES.toEvaluate);
  const useQueue = Boolean(queueInbox && existsSync(queueInbox));
  if (args.has("queue-root") && !useQueue) {
    throw new Error(`Cowork evaluation queue folder not found: ${queueInbox}`);
  }
  const pair = queuePairNames(slug, submission.version);
  if (useQueue && queueRoot) {
    for (const stage of [EVAL_QUEUE_STAGES.toEvaluate, EVAL_QUEUE_STAGES.inProgress]) {
      for (const name of [pair.zip, pair.prompt]) {
        const existing = join(queueRoot, stage, name);
        if (existsSync(existing)) throw new Error(`${name} is already queued for Cowork: ${existing}`);
      }
    }
  }

  console.log(`Validating submissions before packaging ${slug} ${submission.version}...`);
  run("npm", ["run", "check:submissions"]);
  console.log("Building reproducible bundles...");
  run("npm", ["run", "build"]);

  const bundlePath = join(ROOT, "public", "bundles", `${slug}.zip`);
  assertNonEmptyFile(bundlePath, `generated bundle public\\bundles\\${slug}.zip`);

  const artifactPath = join(runDir, `${slug}.zip`);
  const manifestPath = join(runDir, "evaluation-run.json");
  const promptPath = join(runDir, "cowork-prompt.txt");
  let created = false;
  const dropped: string[] = [];

  try {
    mkdirSync(dirname(runDir), { recursive: true });
    mkdirSync(runDir);
    created = true;
    copyFileSync(bundlePath, artifactPath);
    const artifactSha256 = sha256(artifactPath);
    if (artifactSha256 !== sha256(bundlePath)) {
      throw new Error("copied plugin ZIP hash does not match the generated bundle");
    }

    const preparedAt = new Date().toISOString();
    const coworkTaskName = `evaluate-${slug}-v${submission.version}-${preparedAt.slice(0, 10)}`;
    const gitDirty = git(["status", "--porcelain"]).length > 0;

    const templateName = mos3 ? "cowork-evaluation-prompt-mos3.txt" : "cowork-evaluation-prompt.txt";
    const template = readFileSync(join(ROOT, "docs", "evaluation", templateName), "utf8");
    const prompt = renderPrompt(template, {
      SLUG: slug,
      DISPLAY_NAME: submission.displayName,
      VERSION: submission.version,
      RUN_LABEL: coworkTaskName,
      SHA256: artifactSha256,
    });
    writeFileSync(promptPath, prompt, "utf8");

    let queueSubmission: EvaluationRun["queueSubmission"];
    if (useQueue && queueInbox) {
      const zipTarget = join(queueInbox, pair.zip);
      const promptTarget = join(queueInbox, pair.prompt);
      const stagedZip = join(runDir, `.queue-${pair.zip}`);
      const stagedPrompt = join(runDir, `.queue-${pair.prompt}`);
      copyFileSync(artifactPath, stagedZip);
      writeFileSync(stagedPrompt, queuePrompt(prompt, slug, submission.version), "utf8");
      moveInto(stagedZip, zipTarget);
      dropped.push(zipTarget);
      if (sha256(zipTarget) !== artifactSha256) {
        throw new Error("queued plugin ZIP hash does not match the prepared ZIP");
      }
      moveInto(stagedPrompt, promptTarget);
      dropped.push(promptTarget);
      queueSubmission = { zip: zipTarget, prompt: promptTarget, submittedAt: new Date().toISOString() };
    }

    const runData: EvaluationRun = {
      schemaVersion: 1,
      status: "prepared",
      slug,
      displayName: submission.displayName,
      industry: submission.industry,
      artifactVersion: submission.version,
      artifactFile: `${slug}.zip`,
      artifactSha256,
      gitCommit: git(["rev-parse", "HEAD"]),
      gitDirty,
      preparedAt,
      coworkTaskName,
      ...(mos3 ? { packageFormat: "mos3" as const } : {}),
      ...(queueSubmission ? { queueSubmission } : {}),
    };
    writeFileSync(manifestPath, `${JSON.stringify(runData, null, 2)}\n`, "utf8");

    console.log("");
    console.log("Evaluation candidate prepared.");
    console.log(`  Task name: ${coworkTaskName}`);
    console.log(`  Plugin ZIP: ${artifactPath}`);
    console.log(`  SHA-256: ${artifactSha256}`);
    console.log(`  Cowork prompt: ${promptPath}`);
    if (gitDirty) console.log("  Note: prepared from a dirty worktree; the commit is recorded.");
    console.log("");
    if (queueSubmission) {
      console.log(`Queued for Cowork in ${queueInbox}:`);
      console.log(`  ${pair.zip}`);
      console.log(`  ${pair.prompt}`);
      console.log("Cowork picks the pair up from the queue; keep OneDrive running.");
    } else {
      console.log("No Cowork queue folder found (or --no-queue): create the named Cowork task, attach the plugin ZIP, and paste the prompt.");
    }
    console.log(`Then run: npm run evaluation:watch -- --slug ${slug}`);
  } catch (error) {
    for (const path of dropped) rmSync(path, { force: true });
    if (created) rmSync(runDir, { recursive: true, force: true });
    throw error;
  }
}

try {
  main();
} catch (error) {
  console.error(`Evaluation preparation failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
