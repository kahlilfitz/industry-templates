import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
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
  return Object.entries(values).reduce(
    (output, [name, value]) => output.replaceAll(`{{${name}}}`, value),
    template,
  );
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const slug = requiredArg(args, "slug");
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const submission = findSubmission(slug);

  console.log(`Validating submissions before freezing ${slug} ${submission.version}...`);
  run("npm", ["run", "check:submissions"]);
  run("npm", ["run", "check:shared"]);
  console.log("Building reproducible bundles...");
  run("npm", ["run", "build"]);

  const bundlePath = join(ROOT, "public", "bundles", `${slug}.zip`);
  assertNonEmptyFile(bundlePath, `generated bundle public\\bundles\\${slug}.zip`);
  verifyShippedTests(bundlePath, slug);

  const runDir = join(inboxRoot, slug, submission.version);
  const artifactPath = join(runDir, `${slug}.zip`);
  const manifestPath = join(runDir, "evaluation-run.json");
  const promptPath = join(runDir, "cowork-prompt.txt");
  let created = false;

  try {
    if (existsSync(runDir)) {
      throw new Error(`frozen evaluation candidate already exists: ${runDir}`);
    }
    mkdirSync(dirname(runDir), { recursive: true });
    mkdirSync(runDir);
    created = true;
    copyFileSync(bundlePath, artifactPath);
    const artifactSha256 = sha256(artifactPath);
    if (artifactSha256 !== sha256(bundlePath)) {
      throw new Error("frozen artifact hash does not match the generated bundle");
    }

    const preparedAt = new Date().toISOString();
    const date = preparedAt.slice(0, 10);
    const gitCommit = git(["rev-parse", "HEAD"]);
    const gitDirty = git(["status", "--porcelain"]).length > 0;
    const coworkTaskName = `evaluate-${slug}-v${submission.version}-${date}`;
    const runData: EvaluationRun = {
      schemaVersion: 1,
      status: "prepared",
      slug,
      displayName: submission.displayName,
      industry: submission.industry,
      artifactVersion: submission.version,
      artifactFile: `${slug}.zip`,
      artifactSha256,
      gitCommit,
      gitDirty,
      preparedAt,
      coworkTaskName,
    };
    writeFileSync(manifestPath, `${JSON.stringify(runData, null, 2)}\n`, "utf8");

    const templatePath = join(ROOT, "docs", "evaluation", "cowork-evaluation-prompt.txt");
    const template = readFileSync(templatePath, "utf8");
    const prompt = renderPrompt(template, {
      SLUG: slug,
      DISPLAY_NAME: submission.displayName,
      VERSION: submission.version,
      RUN_LABEL: coworkTaskName,
      SHA256: artifactSha256,
    });
    writeFileSync(promptPath, prompt, "utf8");

    console.log("");
    console.log("Evaluation candidate prepared.");
    console.log(`  Task name: ${coworkTaskName}`);
    console.log(`  Frozen ZIP: ${artifactPath}`);
    console.log(`  SHA-256: ${artifactSha256}`);
    console.log(`  Cowork prompt: ${promptPath}`);
    if (gitDirty) {
      console.log("  Note: the candidate was prepared from a dirty worktree; the commit is recorded.");
    }
    console.log("");
    console.log("Next: create the named Cowork task, attach the frozen ZIP, and paste the prompt.");
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
