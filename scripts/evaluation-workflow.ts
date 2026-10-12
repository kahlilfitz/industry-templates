import {
  existsSync,
  lstatSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { findTestDataVersionDir, writeTestDataZip } from "./test-data.js";

export {
  FROZEN_MANIFEST,
  checkTestData,
  computeFrozenManifest,
  findTestDataVersionDir,
  verifyFrozenManifest,
  writeFrozenManifest,
} from "./test-data.js";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const DEFAULT_INBOX_ROOT = join(ROOT, "evaluation-inbox");
export const REQUIRED_REPORTS = [
  "plugin-health.html",
  "behavioral-test-report.html",
  "full-report.html",
] as const;

/**
 * "Ready for human review" means every measured bar is met and only the evidence the two-reviewer
 * human review supplies is pending. It is never a publish signal.
 */
export type EvaluationVerdict = "Ready for human review" | "Blocked" | "No-ship";

export type PackageFormat = "claude-plugin" | "mos3";

export type EvaluationRun = {
  schemaVersion: 1;
  status: "prepared" | "archived";
  slug: string;
  displayName: string;
  industry: string;
  artifactVersion: string;
  artifactFile: string;
  artifactSha256: string;
  gitCommit: string;
  gitDirty: boolean;
  preparedAt: string;
  coworkTaskName: string;
  packageFormat?: PackageFormat;
  testDataFile?: string;
  testDataSha256?: string;
  atkValidated?: boolean;
  archivedAt?: string;
  automatedVerdict?: EvaluationVerdict;
  reportSource?: string;
  archiveDestination?: string;
};

export type Submission = {
  slug: string;
  dir: string;
  industryDir: string;
  industry: string;
  displayName: string;
  version: string;
  packageFormat: PackageFormat;
};

export function parseArgs(argv: string[], booleanFlags: ReadonlySet<string> = new Set()): Map<string, string> {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      throw new Error(`unexpected argument: ${token}`);
    }
    const name = token.slice(2);
    if (booleanFlags.has(name)) {
      args.set(name, "true");
      continue;
    }
    const value = argv[i + 1];
    if (!name || value === undefined || value.startsWith("--")) {
      throw new Error(`${token} requires a value`);
    }
    args.set(name, value);
    i++;
  }
  return args;
}

export function requiredArg(args: Map<string, string>, name: string): string {
  const value = args.get(name)?.trim();
  if (!value) throw new Error(`--${name} is required`);
  return value;
}

export function resolveInputPath(value: string): string {
  return isAbsolute(value) ? resolve(value) : resolve(ROOT, value);
}

export const SHAREPOINT_ENV = "INDUSTRY_TEMPLATES_SHAREPOINT_ROOT";
export const SHAREPOINT_LINK = join(ROOT, "sharepoint");

export type SharepointRoot = {
  root: string;
  source: "flag" | "env" | "link";
};

/**
 * Resolves where evaluation evidence is archived: --sharepoint-root, then the
 * environment variable, then the repo's `sharepoint` link to the OneDrive-synced
 * library. A plain `sharepoint` folder is refused because nobody else can see it.
 */
export function resolveSharepointRoot(
  options: { flag?: string; env?: string; linkPath?: string } = {},
): SharepointRoot {
  const flag = options.flag?.trim();
  if (flag) return { root: resolveInputPath(flag), source: "flag" };

  const env = (options.env ?? process.env[SHAREPOINT_ENV])?.trim();
  if (env) {
    const root = resolveInputPath(env);
    if (!existsSync(root) || !statSync(root).isDirectory()) {
      throw new Error(`${SHAREPOINT_ENV} does not point to a folder: ${root}`);
    }
    return { root, source: "env" };
  }

  const linkPath = options.linkPath ?? SHAREPOINT_LINK;
  let link;
  try {
    link = lstatSync(linkPath);
  } catch {
    throw new Error(
      `no SharePoint root configured: ${linkPath} does not exist. Run \`npm run sharepoint:link\` ` +
        `(see docs/sharepoint-sync.md), set ${SHAREPOINT_ENV}, or pass --sharepoint-root.`,
    );
  }
  if (!link.isSymbolicLink()) {
    throw new Error(
      `${linkPath} is a plain local folder, not a link to the synced SharePoint library. ` +
        "Run `npm run sharepoint:link` (see docs/sharepoint-sync.md) or pass --sharepoint-root explicitly.",
    );
  }
  if (!existsSync(linkPath)) {
    throw new Error(
      `${linkPath} is a broken link; its OneDrive target is missing. Run \`npm run sharepoint:doctor\`.`,
    );
  }
  return { root: linkPath, source: "link" };
}

export function sha256(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex").toUpperCase();
}

export function htmlToText(html: string): string {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#39;/gi, "'")
    .replace(/&quot;/gi, '"')
    .replace(/\s+/g, " ")
    .trim();
}

export function containsDigest(html: string, digest: string): boolean {
  const compactText = htmlToText(html).replace(/[^a-f0-9]/gi, "").toLowerCase();
  return compactText.includes(digest.replace(/[^a-f0-9]/gi, "").toLowerCase());
}

export function confirmsArtifactMatch(html: string, digest: string): boolean {
  if (!containsDigest(html, digest)) return false;
  const text = htmlToText(html);
  const negativeEvidence = [
    /\bobserved\b.{0,120}\b(?:sha-?256|hash|artifact|zip)\b.{0,160}\b(?:does not|doesn't|did not|failed to)\s+match\b/i,
    /\b(?:attached|observed)\s+(?:zip|package|artifact)\b.{0,160}\b(?:mismatch|different plugin|isn['’]t the declared release candidate)\b/i,
    // A MOS3 report states two SHA checks (plugin and test data); any mismatch fails closed.
    /\bsha-?256\s+check\s*[:—-]?\s*mismatch\b/i,
  ];
  if (negativeEvidence.some((pattern) => pattern.test(text))) return false;

  const positiveEvidence = [
    /\bsha-?256\s+check\s*[:—-]?\s*match\b/i,
    /\bhash\s+re-verified\s*[:—-]?\s*yes\b/i,
    /\bartifact\s+sha-?256\b.{0,160}\bre-verified\b/i,
    /\brecomputed\s+sha-?256\b.{0,160}\bmatches?\b/i,
    /\bevaluated copy is byte-identical\b/i,
    /\bartifact identity(?:\s*&\s*integrity)?\s*[:—-]?\s*pass\b/i,
  ];
  return positiveEvidence.some((pattern) => pattern.test(text));
}

/**
 * The automated verdict stated in full-report.html. "Ready for human review" is matched first so
 * it is never read as a bare "Ready"; a bare legacy "Ready" maps to it, and "Stop" maps to No-ship.
 */
export function extractVerdict(html: string): EvaluationVerdict {
  const text = htmlToText(html);
  const match = text.match(
    /\bautomated\s+verdict[\s:—-]*(ready[\s-]+for[\s-]+human[\s-]+review|ready(?![\s-]+for\b)|blocked|no[\s-]?ship|stop)\b/i,
  );
  if (!match) {
    throw new Error(
      "full-report.html must state an automated verdict of Ready for human review, Blocked, or No-ship",
    );
  }
  const value = match[1].toLowerCase();
  if (value.startsWith("ready")) return "Ready for human review";
  if (value === "blocked") return "Blocked";
  return "No-ship";
}

/** Guidance printed after a verdict is archived. */
export function verdictGuidance(verdict: EvaluationVerdict): string[] {
  if (verdict === "Ready for human review") {
    return [
      "Next: two independent reviewers install this exact ZIP and complete the tracker tab; " +
        "publication still needs the Publish gate and the owner decision.",
    ];
  }
  const lines = ["Do not publish this artifact. Fix the reported blockers and prepare a new version."];
  if (verdict === "Blocked") {
    lines.push(
      "Blocked means evidence human review cannot supply is missing, or a gate failed closed without " +
        "an observed plugin defect. Missing human-review evidence alone should not produce Blocked under " +
        "the current prompt; if that is the only reason given, check the report's \"Pending human-review " +
        "evidence\" section and raise it with the owner before remediating.",
    );
  }
  return lines;
}

export function findSubmission(slug: string, root: string = ROOT): Submission {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    throw new Error(`invalid plugin slug: ${slug}`);
  }

  const submissionsRoot = join(root, "submissions");
  const matches: Array<{ industryDir: string; dir: string }> = [];
  for (const industryDir of readdirSync(submissionsRoot)) {
    const industryPath = join(submissionsRoot, industryDir);
    if (!statSync(industryPath).isDirectory()) continue;
    const candidate = join(industryPath, slug);
    if (existsSync(candidate) && statSync(candidate).isDirectory()) {
      matches.push({ industryDir, dir: candidate });
    }
  }

  if (matches.length === 0) {
    throw new Error(`submission not found for slug: ${slug}`);
  }
  if (matches.length > 1) {
    throw new Error(`multiple submissions found for slug: ${slug}`);
  }

  const { industryDir, dir } = matches[0];
  const metadataPath = join(dir, "metadata.json");
  if (!existsSync(metadataPath)) {
    throw new Error(`missing metadata.json for ${slug}`);
  }
  const metadata = JSON.parse(readFileSync(metadataPath, "utf8")) as Record<string, unknown>;
  const industry = String(metadata.industry ?? "").trim();
  const displayName = String(metadata.name ?? "").trim();
  const version = String(metadata.version ?? "").trim();
  if (!industry || !displayName || !version) {
    throw new Error(`${slug} metadata must include industry, name, and version`);
  }
  if (!/^[0-9A-Za-z]+(?:[._-][0-9A-Za-z]+)*$/.test(version)) {
    throw new Error(`${slug} metadata version is not a safe path segment: ${version}`);
  }

  const manifestPath = join(dir, ".claude-plugin", "plugin.json");
  const packageFormat: PackageFormat = metadata.packageFormat === "mos3" ? "mos3" : "claude-plugin";
  if (packageFormat === "mos3") {
    const mos3ManifestPath = join(dir, "manifest.json");
    if (!existsSync(mos3ManifestPath)) {
      throw new Error(`${slug} is a MOS3 submission but has no manifest.json at its root`);
    }
    const manifest = JSON.parse(readFileSync(mos3ManifestPath, "utf8").replace(/^\uFEFF/, "")) as Record<
      string,
      unknown
    >;
    const manifestVersion = String(manifest.version ?? "").trim();
    if (manifestVersion !== version) {
      throw new Error(
        `${slug} version mismatch: metadata ${version}, manifest.json ${manifestVersion}`,
      );
    }
  } else if (existsSync(manifestPath)) {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as Record<string, unknown>;
    const manifestName = String(manifest.name ?? "").trim();
    const manifestVersion = String(manifest.version ?? "").trim();
    if (manifestName !== slug) {
      throw new Error(
        `${slug} manifest name is "${manifestName}"; expected "${slug}"`,
      );
    }
    if (manifestVersion !== version) {
      throw new Error(
        `${slug} version mismatch: metadata ${version}, manifest ${manifestVersion}`,
      );
    }
  }

  return { slug, dir, industryDir, industry, displayName, version, packageFormat };
}

export function assertNonEmptyFile(path: string, label = path): void {
  if (!existsSync(path) || !statSync(path).isFile()) {
    throw new Error(`missing ${label}`);
  }
  if (statSync(path).size === 0) {
    throw new Error(`${label} is empty`);
  }
}

export function relativeToRoot(path: string): string {
  return relative(ROOT, path);
}

const SHIPPED_TEST_RUNNERS = ["run_tests.py", "test_engines.py", "check_shared_copies.py"];

export const TEST_TIMEOUT_ENV = "EVALUATION_TEST_TIMEOUT_MINUTES";
export const DEFAULT_TEST_TIMEOUT_MINUTES = 30;

/** Resolves the per-runner shipped-test timeout: --test-timeout-minutes, then the environment variable, then 30. */
export function resolveTestTimeoutMinutes(
  options: { flag?: string; env?: string } = {},
): number {
  const flag = options.flag?.trim();
  const env = (options.env ?? process.env[TEST_TIMEOUT_ENV])?.trim();
  const [raw, label] = flag
    ? [flag, "--test-timeout-minutes"]
    : env
      ? [env, TEST_TIMEOUT_ENV]
      : [undefined, ""];
  if (raw === undefined) return DEFAULT_TEST_TIMEOUT_MINUTES;
  const minutes = Number(raw);
  if (!Number.isFinite(minutes) || minutes <= 0) {
    throw new Error(`${label} must be a positive number of minutes; got "${raw}"`);
  }
  return minutes;
}

/** Extracts a ZIP with Python's zipfile, the same extractor Cowork's sandbox uses. */
function extractZip(zipPath: string, destination: string): void {
  execFileSync(
    "python",
    ["-c", "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])", zipPath, destination],
    { stdio: "inherit" },
  );
}

type RunnerOptions = {
  cwd: string;
  args: string[];
  env: Record<string, string>;
  timeoutMinutes: number;
  source: string;
  failure: string;
};

function runShippedRunner(runner: string, options: RunnerOptions): void {
  const { cwd, args, env, timeoutMinutes, source, failure } = options;
  console.log(
    `Running shipped tests/${runner} from ${source} ` +
      `(timeout ${timeoutMinutes} min; output follows)...`,
  );
  const started = Date.now();
  // Output is inherited so long suites show progress; PYTHONUNBUFFERED stops Python batching it.
  const result = spawnSync("python", [join("tests", runner), ...args], {
    cwd,
    stdio: ["ignore", "inherit", "inherit"],
    timeout: Math.round(timeoutMinutes * 60_000),
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONIOENCODING: "utf-8",
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONUNBUFFERED: "1",
      ...env,
    },
  });
  const elapsed = ((Date.now() - started) / 1000).toFixed(1);
  const errorCode = (result.error as NodeJS.ErrnoException | undefined)?.code;
  if (errorCode === "ETIMEDOUT") {
    console.log(`tests/${runner} timed out after ${elapsed} s and was stopped.`);
    throw new Error(
      `shipped tests/${runner} did not finish within the ${timeoutMinutes}-minute test timeout ` +
        "and was stopped; if the suite is just slow, rerun with a longer timeout, for example " +
        `--test-timeout-minutes 60 (or set ${TEST_TIMEOUT_ENV})`,
    );
  }
  if (result.error) {
    throw new Error(`could not run shipped tests/${runner} with python: ${result.error.message}`);
  }
  console.log(
    `tests/${runner} finished in ${elapsed} s with exit code ` +
      `${result.status ?? `null (signal ${result.signal})`}.`,
  );
  if (result.status !== 0) {
    throw new Error(`shipped tests/${runner} ${failure}`);
  }
}

/**
 * Runs the shipped regression before a candidate is frozen, from extracted ZIPs rather than the
 * source folder, because Cowork only ever sees the ZIPs.
 *
 * Claude-layout bundles carry their own tests/ and run from the extracted bundle. For a MOS3
 * candidate, pass `testDataZip`: the plugin ZIP is extracted to `<tmp>\plugin`, the test-data ZIP
 * to `<tmp>\test-data`, and each runner in `<tmp>\test-data\tests\` runs with the test-data folder
 * as its working directory, `--plugin-root <tmp>\plugin` and PLUGIN_ROOT set to the same path.
 */
export function verifyShippedTests(
  bundlePath: string,
  slug: string,
  options: { timeoutMinutes?: number; testDataZip?: string } = {},
): void {
  const timeoutMinutes = options.timeoutMinutes ?? DEFAULT_TEST_TIMEOUT_MINUTES;
  if (!Number.isFinite(timeoutMinutes) || timeoutMinutes <= 0) {
    throw new Error(`test timeout must be a positive number of minutes; got ${timeoutMinutes}`);
  }
  const workDir = mkdtempSync(join(tmpdir(), `bundle-${slug}-`));
  try {
    if (options.testDataZip !== undefined) {
      verifyFromTestData(bundlePath, options.testDataZip, slug, workDir, timeoutMinutes);
      return;
    }
    // Cowork runs the shipped tests from the ZIP, where source-only files such as metadata.json are absent.
    extractZip(bundlePath, workDir);
    const roots = readdirSync(workDir, { withFileTypes: true }).filter((entry) => entry.isDirectory());
    const pluginRoot = roots.length === 1 ? join(workDir, roots[0].name) : workDir;
    const runners = SHIPPED_TEST_RUNNERS.filter((name) => existsSync(join(pluginRoot, "tests", name)));
    if (runners.length === 0) {
      console.log("No shipped tests in the bundle; skipping the from-ZIP test run.");
      return;
    }
    for (const runner of runners) {
      runShippedRunner(runner, {
        cwd: pluginRoot,
        args: [],
        env: {},
        timeoutMinutes,
        source: "the extracted bundle",
        failure:
          "fails when run from the built ZIP; " +
          "run it from an extracted copy of public\\bundles\\" + `${slug}.zip to see why ` +
          "(often a test reads a source-only file such as metadata.json or README.md)",
      });
    }
  } finally {
    rmSync(workDir, { recursive: true, force: true, maxRetries: 5 });
  }
}

function verifyFromTestData(
  bundlePath: string,
  testDataZip: string,
  slug: string,
  workDir: string,
  timeoutMinutes: number,
): void {
  if (!existsSync(testDataZip)) {
    throw new Error(`no test data for ${slug}: ${testDataZip} does not exist`);
  }
  const pluginRoot = join(workDir, "plugin");
  const dataRoot = join(workDir, "test-data");
  extractZip(bundlePath, pluginRoot);
  extractZip(testDataZip, dataRoot);
  const runners = SHIPPED_TEST_RUNNERS.filter((name) => existsSync(join(dataRoot, "tests", name)));
  if (!runners.some((name) => name !== "check_shared_copies.py")) {
    throw new Error(
      `the test-data ZIP for ${slug} has no tests/run_tests.py or tests/test_engines.py; ` +
        "a MOS3 candidate cannot be frozen without its shipped regression",
    );
  }
  for (const runner of runners) {
    runShippedRunner(runner, {
      cwd: dataRoot,
      args: ["--plugin-root", pluginRoot],
      env: { PLUGIN_ROOT: pluginRoot },
      timeoutMinutes,
      source: "the extracted test-data ZIP against the extracted plugin ZIP",
      failure:
        "fails when run from the test-data ZIP against the built plugin ZIP; extract both ZIPs and run " +
        `\`python tests\\${runner} --plugin-root <extracted plugin>\` from the extracted test data to see why ` +
        "(often a test reads a source-only file such as metadata.json, or a fixture outside the test-data folder)",
    });
  }
}

/**
 * Builds `<slug>-test-data-<version>.zip` from `test-data\<industry>\<slug>\<version>\`: README.md,
 * demo-data/** and tests/** at the ZIP root, without build litter or FROZEN.sha256, with sorted
 * entries and a fixed timestamp. Returns the ZIP path.
 */
export function buildTestDataZip(
  slug: string,
  version: string,
  options: { root?: string; outDir?: string } = {},
): string {
  const root = options.root ?? ROOT;
  const versionDir = findTestDataVersionDir(slug, version, root);
  const outPath = join(options.outDir ?? join(root, "public", "test-data"), `${slug}-test-data-${version}.zip`);
  writeTestDataZip(versionDir, outPath);
  return outPath;
}