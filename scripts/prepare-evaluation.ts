/**
 * `npm run evaluation:prepare -- --slug <slug>`: package one plugin for a Cowork evaluation.
 *
 * Validates submissions, builds the bundles, copies the plugin ZIP into `evaluation-inbox\<slug>\<version>\`, records its SHA-256 in
 * evaluation-run.json and renders the Cowork prompt. It runs no plugin tests and freezes nothing.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  ROOT,
  EvaluationRun,
  assertNonEmptyFile,
  findSubmission,
  parseArgs,
  requiredArg,
  resolveInputPath,
  sha256,
} from "./evaluation-workflow.js";

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
  const args = parseArgs(process.argv.slice(2));
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
    };
    writeFileSync(manifestPath, `${JSON.stringify(runData, null, 2)}\n`, "utf8");

    const templateName = mos3 ? "cowork-evaluation-prompt-mos3.txt" : "cowork-evaluation-prompt.txt";
    const template = readFileSync(join(ROOT, "docs", "evaluation", templateName), "utf8");
    writeFileSync(
      promptPath,
      renderPrompt(template, {
        SLUG: slug,
        DISPLAY_NAME: submission.displayName,
        VERSION: submission.version,
        RUN_LABEL: coworkTaskName,
        SHA256: artifactSha256,
      }),
      "utf8",
    );

    console.log("");
    console.log("Evaluation candidate prepared.");
    console.log(`  Task name: ${coworkTaskName}`);
    console.log(`  Plugin ZIP: ${artifactPath}`);
    console.log(`  SHA-256: ${artifactSha256}`);
    console.log(`  Cowork prompt: ${promptPath}`);
    if (gitDirty) console.log("  Note: prepared from a dirty worktree; the commit is recorded.");
    console.log("");
    console.log("Next: create the named Cowork task, attach the plugin ZIP, and paste the prompt.");
    console.log(`Then run: npm run evaluation:watch -- --slug ${slug}`);
  } catch (error) {
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
