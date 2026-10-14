import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { basename, dirname, join, relative } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  ROOT,
  EvaluationRun,
  assertNonEmptyFile,
  assertShippedRegression,
  buildTestDataZip,
  findSubmission,
  findTestDataVersionDir,
  parseArgs,
  requiredArg,
  resolveInputPath,
  sha256,
  writeFrozenManifest,
} from "./evaluation-workflow.js";

const ATK_PACKAGE = "@microsoft/m365agentstoolkit-cli";

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

/**
 * `npx --yes @microsoft/m365agentstoolkit-cli validate --package-file <zip> --interactive false`
 * (the toolkit's `atk validate`). Package validation needs no Microsoft 365 sign-in, and
 * `--interactive false` stops the toolkit opening a sign-in window. A non-zero exit fails preparation.
 */
const ATK_TIMEOUT_MINUTES = 15;

function atkValidate(packagePath: string): void {
  const args = ["--yes", ATK_PACKAGE, "validate", "--package-file", packagePath, "--interactive", "false"];
  console.log(`Validating the app package with the Microsoft 365 Agents Toolkit: npx ${args.join(" ")}`);
  console.log(`It runs without a sign-in prompt and is stopped after ${ATK_TIMEOUT_MINUTES} minutes.`);
  const quoted = ["npx", ...args.map((arg) => (/\s/.test(arg) ? `"${arg}"` : arg))].join(" ");
  const options = { cwd: ROOT, stdio: "inherit" as const, timeout: ATK_TIMEOUT_MINUTES * 60_000 };
  const result =
    process.platform === "win32"
      ? spawnSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", `"${quoted}"`], {
          ...options,
          windowsVerbatimArguments: true,
        })
      : spawnSync("npx", args, options);
  const timedOut = (result.error as NodeJS.ErrnoException | undefined)?.code === "ETIMEDOUT";
  if (result.error || result.status !== 0) {
    throw new Error(
      `Microsoft 365 Agents Toolkit validation failed for ${basename(packagePath)} ` +
        (timedOut
          ? `(no result within ${ATK_TIMEOUT_MINUTES} minutes; check network access to the toolkit's acceptance-test service); `
          : `(${result.error ? result.error.message : `exit code ${result.status ?? `null, signal ${result.signal}`}`}); `) +
        "fix the package, or pass --skip-atk for a local-only check that is not a deployable acceptance result",
    );
  }
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
  const args = parseArgs(process.argv.slice(2), new Set(["skip-atk"]));
  const slug = requiredArg(args, "slug");
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const skipAtk = args.has("skip-atk");
  const submission = findSubmission(slug);
  const mos3 = submission.packageFormat === "mos3";
  if (skipAtk && !mos3) {
    console.log("Note: --skip-atk is ignored; Agents Toolkit validation applies only to MOS3 submissions.");
  }

  console.log(`Validating submissions before freezing ${slug} ${submission.version}...`);
  run("npm", ["run", "check:submissions"]);
  run("npm", ["run", "check:shared"]);
  console.log("Building reproducible bundles...");
  run("npm", ["run", "build"]);
  if (mos3) {
    console.log("Checking per-version test data...");
    run("npm", ["run", "check:test-data"]);
  }

  const bundlePath = join(ROOT, "public", "bundles", `${slug}.zip`);
  assertNonEmptyFile(bundlePath, `generated bundle public\\bundles\\${slug}.zip`);

  let testDataZip: string | undefined;
  let testDataDir: string | undefined;
  if (mos3) {
    testDataDir = findTestDataVersionDir(slug, submission.version);
    assertShippedRegression(testDataDir, slug);
    testDataZip = buildTestDataZip(slug, submission.version);
    assertNonEmptyFile(testDataZip, `test-data ZIP ${basename(testDataZip)}`);
  }

  let atkValidated: boolean | undefined;
  if (mos3) {
    if (skipAtk) {
      console.log("Skipping Microsoft 365 Agents Toolkit validation (--skip-atk).");
      console.log("LocalChecksOnly: not a deployable acceptance result");
      atkValidated = false;
    } else {
      atkValidate(bundlePath);
      atkValidated = true;
    }
  }

  const runDir = join(inboxRoot, slug, submission.version);
  const artifactPath = join(runDir, `${slug}.zip`);
  const manifestPath = join(runDir, "evaluation-run.json");
  const promptPath = join(runDir, "cowork-prompt.txt");
  const testDataFile = testDataZip ? basename(testDataZip) : undefined;
  const frozenTestDataZip = testDataFile ? join(runDir, testDataFile) : undefined;
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
    let testDataSha256: string | undefined;
    if (testDataZip && frozenTestDataZip) {
      copyFileSync(testDataZip, frozenTestDataZip);
      testDataSha256 = sha256(frozenTestDataZip);
      if (testDataSha256 !== sha256(testDataZip)) {
        throw new Error("frozen test-data ZIP hash does not match the generated test-data ZIP");
      }
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
      ...(mos3 ? { packageFormat: "mos3" as const, testDataFile, testDataSha256, atkValidated } : {}),
    };
    writeFileSync(manifestPath, `${JSON.stringify(runData, null, 2)}\n`, "utf8");

    const templateName = mos3 ? "cowork-evaluation-prompt-mos3.txt" : "cowork-evaluation-prompt.txt";
    const templatePath = join(ROOT, "docs", "evaluation", templateName);
    const template = readFileSync(templatePath, "utf8");
    const prompt = renderPrompt(template, {
      SLUG: slug,
      DISPLAY_NAME: submission.displayName,
      VERSION: submission.version,
      RUN_LABEL: coworkTaskName,
      SHA256: artifactSha256,
    });
    writeFileSync(promptPath, prompt, "utf8");

    // Freeze the test data this candidate was verified against; check:test-data then refuses any edit.
    let frozenManifest: string | undefined;
    if (testDataDir) frozenManifest = writeFrozenManifest(testDataDir);

    console.log("");
    console.log("Evaluation candidate prepared.");
    console.log(`  Task name: ${coworkTaskName}`);
    console.log(`  Frozen ZIP: ${artifactPath}`);
    console.log(`  SHA-256: ${artifactSha256}`);
    if (frozenTestDataZip) {
      console.log(`  Test-data ZIP: ${frozenTestDataZip}`);
      console.log(`  Test-data SHA-256: ${testDataSha256}`);
      console.log(`  ATK validated: ${atkValidated ? "yes" : "no (LocalChecksOnly: not a deployable acceptance result)"}`);
    }
    console.log(`  Cowork prompt: ${promptPath}`);
    if (gitDirty) {
      console.log("  Note: the candidate was prepared from a dirty worktree; the commit is recorded.");
    }
    console.log("");
    if (frozenManifest) {
      console.log(
        `Wrote ${relative(ROOT, frozenManifest)}; commit it now (git add -- "${relative(ROOT, frozenManifest)}") ` +
          `so this version's test data stays frozen.`,
      );
    }
    console.log("Next: create the named Cowork task, attach the frozen plugin ZIP, and paste the prompt.");
    if (frozenTestDataZip) {
      console.log("The test-data ZIP is not sent to Cowork; it is archived with the reports as the test record.");
    }
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
