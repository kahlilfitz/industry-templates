/**
 * Per-version test data for MOS3 submissions.
 *
 * A MOS3 package ships only its manifest, icons and skills, so the README, demo data and shipped
 * regression live outside it, one folder per plugin version:
 *
 *   test-data/<industry-folder>/<slug>/<version>/
 *   ├── README.md
 *   ├── demo-data/
 *   └── tests/        run_tests.py or test_engines.py (+ optional check_shared_copies.py, helpers)
 *
 * Runner contract: `python tests/<runner> --plugin-root <dir>` (or the PLUGIN_ROOT environment
 * variable), run with the version folder as the current directory. The plugin root is an
 * extracted MOS3 ZIP or the submission folder; the data root is the runner's parent version
 * folder; with neither the flag nor the variable, a runner defaults to
 * `<repo>/submissions/<industry-folder>/<slug>`.
 *
 * A version folder holding `FROZEN.sha256` is immutable: the file lists `sha256  relative/path`
 * for every other file in the folder (build litter excepted), sorted by path.
 */
import { createHash } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isBuildLitter, walkNoFollow, writeReproducibleZip, FIXED_ZIP_TIMESTAMP } from "./package-files.js";

export const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const TEST_DATA_DIR = "test-data";
export const FROZEN_MANIFEST = "FROZEN.sha256";
/** A version folder needs at least one of these in tests/. */
export const TEST_DATA_RUNNERS = ["run_tests.py", "test_engines.py"] as const;
/** The only entries a version folder may hold, besides FROZEN.sha256. */
export const TEST_DATA_ENTRIES = ["README.md", "demo-data", "tests"] as const;

const SAFE_SEGMENT = /^[0-9A-Za-z]+(?:[._-][0-9A-Za-z]+)*$/;

export type TestDataReport = { errors: string[]; warnings: string[]; checked: string[] };

export function testDataVersionDir(root: string, industryDir: string, slug: string, version: string): string {
  return join(root, TEST_DATA_DIR, industryDir, slug, version);
}

/** Files that belong to a version folder's content: everything but FROZEN.sha256 and build litter. */
export function listTestDataFiles(versionDir: string): string[] {
  const { files, symlinks } = walkNoFollow(versionDir);
  if (symlinks.length) {
    throw new Error(`${versionDir} contains symbolic links (${symlinks.join(", ")}); test data must be plain files`);
  }
  return files.filter((rel) => rel !== FROZEN_MANIFEST && !isBuildLitter(rel));
}

function fileSha256(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

/** The canonical FROZEN.sha256 text for a version folder: sorted `sha256  path` lines, LF endings. */
export function computeFrozenManifest(versionDir: string): string {
  return listTestDataFiles(versionDir)
    .map((rel) => `${fileSha256(join(versionDir, ...rel.split("/")))}  ${rel}\n`)
    .join("");
}

/** Write FROZEN.sha256 for a version folder and return its path. */
export function writeFrozenManifest(versionDir: string): string {
  const path = join(versionDir, FROZEN_MANIFEST);
  writeFileSync(path, computeFrozenManifest(versionDir), "utf8");
  return path;
}

/** Differences between a version folder and its FROZEN.sha256; empty when they match exactly. */
export function verifyFrozenManifest(versionDir: string): string[] {
  const recorded = readFileSync(join(versionDir, FROZEN_MANIFEST), "utf8");
  const expected = computeFrozenManifest(versionDir);
  if (recorded === expected) return [];

  const problems: string[] = [];
  const listed = new Map<string, string>();
  recorded.split("\n").forEach((line, index) => {
    if (!line) return;
    const m = line.match(/^([0-9a-f]{64}) {2}(.+)$/);
    if (!m) problems.push(`${FROZEN_MANIFEST} line ${index + 1} is not "<sha256>  <path>"`);
    else listed.set(m[2], m[1]);
  });
  const actual = new Map(
    expected
      .split("\n")
      .filter(Boolean)
      .map((line) => [line.slice(66), line.slice(0, 64)] as [string, string]),
  );
  for (const [rel, digest] of listed) {
    if (!actual.has(rel)) problems.push(`${rel} is listed but missing`);
    else if (actual.get(rel) !== digest) problems.push(`${rel} has changed since it was frozen`);
  }
  for (const rel of actual.keys()) {
    if (!listed.has(rel)) problems.push(`${rel} was added after the folder was frozen`);
  }
  if (!problems.length) problems.push(`${FROZEN_MANIFEST} is not in canonical sorted form; regenerate it`);
  return problems;
}

function isDir(path: string): boolean {
  return existsSync(path) && lstatSync(path).isDirectory();
}

const visible = (name: string) => !name.startsWith(".") && !name.startsWith("_");

/** Problems with the layout of the version folder a candidate is built from. */
export function checkVersionFolderLayout(versionDir: string): string[] {
  const problems: string[] = [];
  if (!existsSync(join(versionDir, "README.md")) || !statSync(join(versionDir, "README.md")).isFile()) {
    problems.push("README.md is missing");
  }
  if (!isDir(join(versionDir, "demo-data"))) problems.push("demo-data\\ is missing");
  if (!isDir(join(versionDir, "tests"))) problems.push("tests\\ is missing");
  else if (!TEST_DATA_RUNNERS.some((runner) => existsSync(join(versionDir, "tests", runner)))) {
    problems.push(`tests\\ has no runner (${TEST_DATA_RUNNERS.join(" or ")})`);
  }
  for (const entry of readdirSync(versionDir).sort()) {
    if (entry === FROZEN_MANIFEST || isBuildLitter(entry)) continue;
    if (!(TEST_DATA_ENTRIES as readonly string[]).includes(entry)) {
      problems.push(`${entry} is not expected; a version folder holds only README.md, demo-data\\ and tests\\`);
    }
  }
  return problems;
}

type SubmissionInfo = { industryDir: string; slug: string; version?: string; mos3: boolean };

function readSubmissions(root: string): SubmissionInfo[] {
  const submissionsRoot = join(root, "submissions");
  if (!existsSync(submissionsRoot)) return [];
  const out: SubmissionInfo[] = [];
  for (const industryDir of readdirSync(submissionsRoot).filter(visible).sort()) {
    if (!isDir(join(submissionsRoot, industryDir))) continue;
    for (const slug of readdirSync(join(submissionsRoot, industryDir)).filter(visible).sort()) {
      const dir = join(submissionsRoot, industryDir, slug);
      if (!isDir(dir)) continue;
      let meta: Record<string, unknown> = {};
      try {
        meta = JSON.parse(readFileSync(join(dir, "metadata.json"), "utf8")) as Record<string, unknown>;
      } catch {
        // check:submissions reports a missing or invalid metadata.json.
      }
      out.push({
        industryDir,
        slug,
        version: typeof meta.version === "string" ? meta.version.trim() : undefined,
        mos3: meta.packageFormat === "mos3",
      });
    }
  }
  return out;
}

/**
 * Check test-data/ against submissions/: every MOS3 submission has a complete folder for its
 * current version, every frozen folder matches its FROZEN.sha256, and no test data is orphaned.
 */
export function checkTestData(root: string = REPO_ROOT): TestDataReport {
  const report: TestDataReport = { errors: [], warnings: [], checked: [] };
  const submissions = readSubmissions(root);
  const bySlug = new Map(submissions.map((s) => [`${s.industryDir}/${s.slug}`, s]));

  for (const s of submissions.filter((x) => x.mos3)) {
    const label = `${s.slug}`;
    if (!s.version || !SAFE_SEGMENT.test(s.version)) {
      report.errors.push(`  ${label}: metadata.json needs a version to locate its test data`);
      continue;
    }
    const versionDir = testDataVersionDir(root, s.industryDir, s.slug, s.version);
    const rel = `test-data\\${s.industryDir}\\${s.slug}\\${s.version}\\`;
    if (!isDir(versionDir)) {
      report.errors.push(
        `  ${label}: ${rel} is missing; a MOS3 submission keeps its README.md, demo-data\\ and tests\\ there`,
      );
      continue;
    }
    for (const problem of checkVersionFolderLayout(versionDir)) report.errors.push(`  ${label}: ${rel}${problem}`);
    report.checked.push(`  ${s.slug} ${s.version}`);
  }

  const testDataRoot = join(root, TEST_DATA_DIR);
  if (!existsSync(testDataRoot)) return report;
  for (const industryDir of readdirSync(testDataRoot).filter(visible).sort()) {
    const industryPath = join(testDataRoot, industryDir);
    if (!isDir(industryPath)) continue;
    for (const slug of readdirSync(industryPath).filter(visible).sort()) {
      const slugPath = join(industryPath, slug);
      const rel = `test-data\\${industryDir}\\${slug}\\`;
      if (!isDir(slugPath)) {
        report.errors.push(`  ${rel.slice(0, -1)}: expected a folder per plugin slug, found a file`);
        continue;
      }
      const submission = bySlug.get(`${industryDir}/${slug}`);
      if (!submission) {
        const elsewhere = submissions.find((s) => s.slug === slug);
        report.errors.push(
          elsewhere
            ? `  ${slug}: ${rel} has no submission; the plugin is filed under submissions\\${elsewhere.industryDir}\\`
            : `  ${slug}: ${rel} has no submission at submissions\\${industryDir}\\${slug}\\`,
        );
        continue;
      }
      for (const version of readdirSync(slugPath).sort()) {
        const versionDir = join(slugPath, version);
        if (!isDir(versionDir)) {
          if (visible(version)) report.errors.push(`  ${slug}: ${rel}${version} is a file; expected version folders only`);
          continue;
        }
        if (!SAFE_SEGMENT.test(version)) {
          report.errors.push(`  ${slug}: ${rel}${version}\\ is not a valid version folder name`);
          continue;
        }
        const current = submission.mos3 && version === submission.version;
        if (existsSync(join(versionDir, FROZEN_MANIFEST))) {
          let problems: string[];
          try {
            problems = verifyFrozenManifest(versionDir);
          } catch (error) {
            problems = [(error as Error).message];
          }
          for (const problem of problems) {
            report.errors.push(`  ${slug}: ${rel}${version}\\ is frozen but ${problem}`);
          }
        } else if (!current) {
          report.warnings.push(
            `  ${slug}: ${rel}${version}\\ is not the current version and has no ${FROZEN_MANIFEST}; ` +
              "freeze it or remove it",
          );
        }
      }
    }
  }
  return report;
}

/** The test-data version folder for a slug, found under any industry folder. */
export function findTestDataVersionDir(slug: string, version: string, root: string = REPO_ROOT): string {
  const testDataRoot = join(root, TEST_DATA_DIR);
  const matches = existsSync(testDataRoot)
    ? readdirSync(testDataRoot)
        .filter(visible)
        .map((industryDir) => join(testDataRoot, industryDir, slug, version))
        .filter(isDir)
    : [];
  if (matches.length === 0) {
    throw new Error(
      `no test data for ${slug} ${version}: expected test-data\\<industry>\\${slug}\\${version}\\ ` +
        "with README.md, demo-data\\ and tests\\",
    );
  }
  if (matches.length > 1) throw new Error(`test data for ${slug} ${version} exists under more than one industry folder`);
  return matches[0];
}

/** Write the test-data ZIP for a version folder: README.md, demo-data/** and tests/** at the root. */
export function writeTestDataZip(versionDir: string, outPath: string): void {
  const problems = checkVersionFolderLayout(versionDir);
  if (problems.length) throw new Error(`test data in ${versionDir} is incomplete: ${problems.join("; ")}`);
  mkdirSync(dirname(outPath), { recursive: true });
  writeReproducibleZip(
    listTestDataFiles(versionDir).map((name) => ({ name, path: join(versionDir, ...name.split("/")) })),
    outPath,
    FIXED_ZIP_TIMESTAMP,
  );
}
