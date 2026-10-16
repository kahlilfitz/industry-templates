import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const DEFAULT_INBOX_ROOT = join(ROOT, "evaluation-inbox");
export const VERDICT_REPORT = "recommendations.html";
export const REQUIRED_REPORTS = [
  "plugin-health.html",
  "behavioral-test-report.html",
  VERDICT_REPORT,
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
  /** Legacy: runs prepared before 2026-10-15 also froze a test-data ZIP, which archive still copies. */
  testDataFile?: string;
  testDataSha256?: string;
  archivedAt?: string;
  automatedVerdict?: EvaluationVerdict;
  reportSource?: string;
  archiveDestination?: string;
  fixStatus?: FixStatus;
  fixBrief?: string;
  fixVersion?: string;
  fixUpdatedAt?: string;
  /** Set when prepare dropped the pair into the Cowork evaluation queue folder. */
  queueSubmission?: QueueSubmission;
  /** Earlier queue submissions of this same ZIP, replaced by `prepare --requeue`. */
  queueHistory?: QueueSubmission[];
};

export type QueueSubmission = {
  zip: string;
  prompt: string;
  submittedAt: string;
  resubmission?: boolean;
  /** Where `--requeue` moved this submission's `4 - Needs attention` entries (Cowork's note included). */
  needsAttentionMovedTo?: string;
};

export type FixStatus = "nothing-to-fix" | "brief-written" | "agent-finished" | "agent-failed";

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

/**
 * Plugins filed in the Retail library layout, `<Industry>\Wave <n>\<Title Case Slug>\`, with
 * evaluations under `Evaluation\v<version>\`. Every other plugin keeps `<Industry>\<slug>\`.
 */
export const SHAREPOINT_WAVES: Readonly<Record<string, Readonly<Record<string, number>>>> = {
  "Professional Services": {
    "engagement-closeout-knowledge-harvest": 1,
    "engagement-staffing-bench-match": 1,
    "engagement-mobilization-onboarding-pack": 1,
    "time-expense-narrative-compliance": 1,
    "deliverable-review-quality-gate": 1,
    "client-status-qbr": 2,
    "sow-drafting-scoping-notes": 2,
    "credential-case-study-assembly": 2,
    "engagement-financial-health-brief": 2,
    "conflicts-independence-precheck": 2,
  },
};

// Slug words written in capitals in folder names, as Retail does ("Order Intake O2C Exception").
const FOLDER_NAME_ACRONYMS = new Set(["qbr", "sow"]);

export function pluginFolderName(slug: string): string {
  return slug
    .split("-")
    .map((word) =>
      FOLDER_NAME_ACRONYMS.has(word) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function sharepointWave(industry: string, slug: string): number | undefined {
  return SHAREPOINT_WAVES[industry]?.[slug];
}

export function usesRetailLayout(industry: string, slug: string): boolean {
  return sharepointWave(industry, slug) !== undefined;
}

export function sharepointPluginDir(sharepointRoot: string, industry: string, slug: string): string {
  const wave = sharepointWave(industry, slug);
  return wave === undefined
    ? join(sharepointRoot, industry, slug)
    : join(sharepointRoot, industry, `Wave ${wave}`, pluginFolderName(slug));
}

export function evaluationArchiveDir(
  sharepointRoot: string,
  industry: string,
  slug: string,
  version: string,
): string {
  const folder = sharepointWave(industry, slug) === undefined ? version : `v${version}`;
  return join(sharepointPluginDir(sharepointRoot, industry, slug), "Evaluation", folder);
}

/**
 * The OneDrive folder Cowork watches (eval-ledger.md in it describes the contract): a
 * `<slug>-v<version>.zip` and `<slug>-v<version>-prompt.md` pair dropped in `1 - To evaluate` is
 * evaluated, and the pair plus reports land in `3 - Evaluated\<slug>\v<version> - <timestamp>\`.
 */
export const EVAL_QUEUE_DIR = "Cowork Plugin Evals";
export const EVAL_QUEUE_STAGES = {
  toEvaluate: "1 - To evaluate",
  inProgress: "2 - In progress",
  evaluated: "3 - Evaluated",
  needsAttention: "4 - Needs attention",
} as const;

export function defaultQueueRoot(env: NodeJS.ProcessEnv = process.env): string | undefined {
  const oneDrive = env.OneDriveCommercial || env.OneDrive;
  return oneDrive ? join(oneDrive, EVAL_QUEUE_DIR) : undefined;
}

export function queuePairNames(slug: string, version: string): { zip: string; prompt: string } {
  const base = `${slug}-v${version}`;
  return { zip: `${base}.zip`, prompt: `${base}-prompt.md` };
}

/** The rendered Cowork prompt with a header naming the queued ZIP, which the template calls `<slug>.zip`. */
export function queuePrompt(prompt: string, slug: string, version: string): string {
  const { zip } = queuePairNames(slug, version);
  return [
    "Queue submission (Cowork Plugin Evals).",
    "",
    `The plugin ZIP for this prompt is \`${zip}\`, the other file of this pair.`,
    `Wherever the prompt below says \`${slug}.zip\` or "the attached plugin", it means \`${zip}\`.`,
    "Its SHA-256 must be the one stated below. Keep the three report filenames exactly as named below.",
    "",
    "---",
    "",
    prompt,
  ].join("\n");
}

function entries(dir: string): string[] {
  return existsSync(dir) && statSync(dir).isDirectory() ? readdirSync(dir) : [];
}

/**
 * Each required report in a folder: the exact name, else the one newest `.html` file whose name
 * contains the report's stem (Cowork may timestamp report names). Undefined if any is missing or empty.
 */
export function findReports(dir: string): Map<string, string> | undefined {
  const files = entries(dir)
    .map((name) => join(dir, name))
    .filter((path) => statSync(path).isFile() && statSync(path).size > 0);
  const found = new Map<string, string>();
  for (const report of REQUIRED_REPORTS) {
    const exact = files.find((path) => basename(path).toLowerCase() === report);
    const stem = report.replace(/\.html$/, "");
    const named = files
      .filter((path) => {
        const name = basename(path).toLowerCase();
        return name.endsWith(".html") && name.includes(stem);
      })
      .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);
    const path = exact ?? named[0];
    if (!path) return undefined;
    found.set(report, path);
  }
  return found;
}

/** `3 - Evaluated\<slug>\v<version> - *` folders whose queued ZIP has the digest, newest first. */
export function findEvaluatedQueueRuns(queueRoot: string, slug: string, version: string, digest: string): string[] {
  const pluginDir = join(queueRoot, EVAL_QUEUE_STAGES.evaluated, slug);
  const { zip } = queuePairNames(slug, version);
  return entries(pluginDir)
    .filter((name) => name === `v${version}` || name.startsWith(`v${version} `))
    .map((name) => join(pluginDir, name))
    .filter((dir) => statSync(dir).isDirectory())
    .filter((dir) => {
      const candidate = join(dir, zip);
      return existsSync(candidate) && sha256(candidate) === digest;
    })
    .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);
}

/**
 * Entries in `4 - Needs attention` for this slug and version (the pair, a note or a folder). An entry
 * holding a ZIP with a different digest belongs to another candidate and is ignored.
 */
export function findQueueAttention(queueRoot: string, slug: string, version: string, digest: string): string[] {
  const dir = join(queueRoot, EVAL_QUEUE_STAGES.needsAttention);
  const { zip } = queuePairNames(slug, version);
  const base = `${slug}-v${version}`.toLowerCase();
  return entries(dir)
    .filter((name) => {
      const lower = name.toLowerCase();
      // `-v1.0.1` must not match `-v1.0.13…`.
      return lower.startsWith(base) && !/^(\d|\.\d)/.test(lower.slice(base.length));
    })
    .map((name) => join(dir, name))
    .filter((path) => {
      const candidate = statSync(path).isDirectory() ? join(path, zip) : path;
      if (!candidate.toLowerCase().endsWith(".zip") || !existsSync(candidate)) return true;
      return sha256(candidate) === digest;
    });
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
 * The automated verdict stated in recommendations.html. "Ready for human review" is matched first so
 * it is never read as a bare "Ready"; a bare legacy "Ready" maps to it, and "Stop" maps to No-ship.
 */
export function extractVerdict(html: string): EvaluationVerdict {
  const text = htmlToText(html);
  const match = text.match(
    /\bautomated\s+verdict[\s:—-]*(ready[\s-]+for[\s-]+human[\s-]+review|ready(?![\s-]+for\b)|blocked|no[\s-]?ship|stop)\b/i,
  );
  if (!match) {
    throw new Error(
      `${VERDICT_REPORT} must state an automated verdict of Ready for human review, Blocked, or No-ship`,
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

/** Reads `<inbox>\<slug>\<version>\evaluation-run.json`. */
export function readRun(inboxRoot: string, slug: string, version: string): { path: string; run: EvaluationRun } {
  const path = join(inboxRoot, slug, version, "evaluation-run.json");
  assertNonEmptyFile(path, "evaluation-run.json");
  const run = JSON.parse(readFileSync(path, "utf8")) as EvaluationRun;
  if (run.schemaVersion !== 1 || run.slug !== slug || run.artifactVersion !== version) {
    throw new Error("evaluation-run.json does not match the requested plugin and version");
  }
  return { path, run };
}