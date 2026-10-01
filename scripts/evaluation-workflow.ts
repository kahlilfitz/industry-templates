import {
  existsSync,
  lstatSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const DEFAULT_INBOX_ROOT = join(ROOT, "evaluation-inbox");
export const REQUIRED_REPORTS = [
  "plugin-health.html",
  "behavioral-test-report.html",
  "full-report.html",
] as const;

export type EvaluationVerdict = "Ready" | "Blocked" | "No-ship";

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
};

export function parseArgs(argv: string[]): Map<string, string> {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      throw new Error(`unexpected argument: ${token}`);
    }
    const name = token.slice(2);
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

export function extractVerdict(html: string): EvaluationVerdict {
  const text = htmlToText(html);
  const match = text.match(
    /\bautomated\s+verdict[\s:—-]*(ready|blocked|no[\s-]?ship|stop)\b/i,
  );
  if (!match) {
    throw new Error(
      "full-report.html must state an automated verdict of Ready, Blocked, or No-ship",
    );
  }
  const value = match[1].toLowerCase();
  if (value === "ready") return "Ready";
  if (value === "blocked") return "Blocked";
  return "No-ship";
}

export function findSubmission(slug: string): Submission {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    throw new Error(`invalid plugin slug: ${slug}`);
  }

  const submissionsRoot = join(ROOT, "submissions");
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
  if (existsSync(manifestPath)) {
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

  return { slug, dir, industryDir, industry, displayName, version };
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

// Cowork runs the shipped tests from the ZIP, where source-only files such as metadata.json are absent.
export function verifyShippedTests(bundlePath: string, slug: string): void {
  const workDir = mkdtempSync(join(tmpdir(), `bundle-${slug}-`));
  try {
    execFileSync(
      "python",
      ["-c", "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])", bundlePath, workDir],
      { stdio: "inherit" },
    );
    const roots = readdirSync(workDir, { withFileTypes: true }).filter((entry) => entry.isDirectory());
    const pluginRoot = roots.length === 1 ? join(workDir, roots[0].name) : workDir;
    const runners = SHIPPED_TEST_RUNNERS.filter((name) => existsSync(join(pluginRoot, "tests", name)));
    if (runners.length === 0) {
      console.log("No shipped tests in the bundle; skipping the from-ZIP test run.");
      return;
    }
    for (const runner of runners) {
      console.log(`Running shipped tests/${runner} from the extracted bundle...`);
      try {
        execFileSync("python", [join("tests", runner)], {
          cwd: pluginRoot,
          stdio: ["ignore", "ignore", "inherit"],
          env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONDONTWRITEBYTECODE: "1" },
        });
      } catch {
        throw new Error(
          `shipped tests/${runner} fails when run from the built ZIP; ` +
            "run it from an extracted copy of public\\bundles\\" + `${slug}.zip to see why ` +
            "(often a test reads a source-only file such as metadata.json or README.md)",
        );
      }
    }
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }
}
