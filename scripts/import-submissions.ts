/**
 * Validate `submissions/` and build downloadable packages.
 *
 * Contributors only touch `submissions/<industry>/<slug>/`. This script validates each
 * submission and writes one generated artifact:
 *
 *   - `public/bundles/<slug>.zip`
 *
 * Run `npm run check:submissions` to validate without writing anything, or `npm run build`
 * to recreate every bundle. CI runs both.
 *
 * With `--catalog-output <dir>`, each plugin's inner skills are additionally
 * exported unpacked to that directory, flattened one per folder. CI publishes
 * the result on the orphan `catalog` branch, which is the URL people paste
 * into Copilot Studio's "Add skill › From GitHub".
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, rmSync, existsSync } from "node:fs";
import { dirname, isAbsolute, join, posix, relative, resolve, sep } from "node:path";
import AdmZip from "adm-zip";

const ROOT = process.cwd();
const SUBMISSIONS = join(ROOT, "submissions");
const OUT_BUNDLES = join(ROOT, "public", "bundles");

const CHECK_ONLY = process.argv.includes("--check");
const INDUSTRIES = new Set([
  "Manufacturing",
  "Retail & CPG",
  "Financial Services",
  "Healthcare",
  "Energy",
  "Public Sector",
  "Professional Services",
  "Cross-industry",
]);
const PLATFORMS = new Set(["Cowork", "Copilot Studio", "Scout"]);

/** Files and folders excluded by default. A submission may opt tests in via metadata.bundleTests. */
const NEVER_BUNDLE = new Set([
  "metadata.json",
  "metadata.yaml",
  "README.md",
  "PACKAGE-NOTES.md",
  "tests",
]);

/**
 * Build litter that can turn up at any depth, not just the top level. Several
 * submissions ship Python that the agent is told to run from the plugin folder,
 * which leaves `__pycache__` next to the script; the compiled files embed the
 * author's absolute paths, so they must never reach a downloader.
 */
const LITTER_DIRS = new Set(["__pycache__", ".pytest_cache", ".ruff_cache", ".DS_Store"]);

function isBuildLitter(rel: string): boolean {
  return rel
    .split(posix.sep)
    .some((segment) => LITTER_DIRS.has(segment) || segment.endsWith(".pyc"));
}

const errors: string[] = [];
const notes: string[] = [];

function fail(slug: string, message: string) {
  errors.push(`  ${slug}: ${message}`);
}

type SubmissionData = {
  industry: string;
  createdAt?: Date;
  updatedAt?: Date;
  bundleTests: boolean;
};

function optionalDate(slug: string, field: string, value: unknown): Date | undefined {
  if (value === undefined) return undefined;
  const date = new Date(String(value));
  if (Number.isNaN(date.valueOf())) {
    fail(slug, `${field} must be a valid date`);
    return undefined;
  }
  return date;
}

function validateMetadata(
  slug: string,
  meta: Record<string, unknown>,
  authorGithub: string | undefined,
): SubmissionData | undefined {
  const before = errors.length;
  for (const field of ["name", "description", "author"] as const) {
    if (typeof meta[field] !== "string" || !meta[field].trim()) {
      fail(slug, `${field} is required and must be a non-empty string`);
    }
  }
  if (typeof meta.industry !== "string" || !INDUSTRIES.has(meta.industry)) {
    fail(slug, `industry must be one of: ${[...INDUSTRIES].join(", ")}`);
  }
  if (
    !Array.isArray(meta.platforms) ||
    meta.platforms.length === 0 ||
    meta.platforms.some((platform) => typeof platform !== "string" || !PLATFORMS.has(platform))
  ) {
    fail(slug, `platforms must contain one or more of: ${[...PLATFORMS].join(", ")}`);
  }
  if (
    !Array.isArray(meta.tags) ||
    meta.tags.length === 0 ||
    meta.tags.some((tag) => typeof tag !== "string" || !tag.trim())
  ) {
    fail(slug, "tags must contain one or more non-empty strings");
  }
  if (meta.authorUrl !== undefined) {
    try {
      new URL(String(meta.authorUrl));
    } catch {
      fail(slug, "authorUrl must be a valid URL");
    }
  }
  if (
    authorGithub !== undefined &&
    !/^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i.test(authorGithub)
  ) {
    fail(slug, "authorGithub must be a bare GitHub username (no leading @)");
  }
  if (meta.version !== undefined && typeof meta.version !== "string") {
    fail(slug, "version must be a string");
  }
  if (meta.bundleTests !== undefined && typeof meta.bundleTests !== "boolean") {
    fail(slug, "bundleTests must be a boolean");
  }

  const createdAt = optionalDate(slug, "createdAt", meta.createdAt);
  const updatedAt = optionalDate(slug, "updatedAt", meta.updatedAt);
  if (errors.length !== before || typeof meta.industry !== "string") return undefined;
  return {
    industry: meta.industry,
    createdAt,
    updatedAt,
    bundleTests: meta.bundleTests === true,
  };
}

/** Every file under `dir`, as slash-separated paths relative to `dir`, sorted. */
function walk(dir: string, base = dir): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const abs = join(dir, entry);
    if (statSync(abs).isDirectory()) out.push(...walk(abs, base));
    else out.push(relative(base, abs).split(sep).join(posix.sep));
  }
  return out.sort();
}

/** A GitHub login from an explicit field, else from a github.com profile URL. */
function resolveGithub(
  explicit: unknown,
  authorUrl: unknown,
): string | undefined {
  if (typeof explicit === "string" && explicit.trim()) {
    return explicit.trim().replace(/^@/, "");
  }
  if (typeof authorUrl === "string") {
    const m = authorUrl.match(/^https?:\/\/(?:www\.)?github\.com\/([^/?#]+)\/?$/i);
    if (m) return m[1];
  }
  return undefined;
}

/** The folder an industry's submissions live in: "Retail & CPG" -> "retail-and-cpg". */
function industryFolder(industry: string): string {
  return industry.toLowerCase().replace(/ & /g, "-and-").replace(/\s+/g, "-");
}

type SkillEntry = { name: string; description?: string };

/** Read the skills a plugin package bundles, from `skills/<name>/SKILL.md`. */
function readPluginSkills(dir: string): SkillEntry[] {
  const skillsDir = join(dir, "skills");
  if (!existsSync(skillsDir)) return [];
  const out: SkillEntry[] = [];
  for (const entry of readdirSync(skillsDir).sort()) {
    const skillFile = join(skillsDir, entry, "SKILL.md");
    if (!existsSync(skillFile)) continue;
    const raw = readFileSync(skillFile, "utf8");
    // Pull `description` out of the SKILL.md frontmatter. It may be a plain
    // scalar or a folded block (`description: >-`), so take the first line and,
    // for a block, the indented lines that follow.
    let description: string | undefined;
    const fm = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (fm) {
      const lines = fm[1].split(/\r?\n/);
      const i = lines.findIndex((l) => /^description\s*:/.test(l));
      if (i >= 0) {
        const head = lines[i].replace(/^description\s*:\s*/, "").trim();
        if (head && !/^[>|][-+]?$/.test(head)) {
          description = head.replace(/^["']|["']$/g, "");
        } else {
          const block: string[] = [];
          for (let j = i + 1; j < lines.length; j++) {
            if (!/^\s+\S/.test(lines[j])) break;
            block.push(lines[j].trim());
          }
          description = block.join(" ");
        }
      }
    }
    out.push({ name: entry, description });
  }
  return out;
}

/**
 * Export a plugin's skills as standalone canonical Agent Skills.
 *
 * A template ships as a Cowork plugin package, but each `skills/<name>/` inside
 * it is already a canonical skill — a root `SKILL.md` plus its own `scripts/`,
 * `references/`, `contracts/` and `templates/`. Copying those out one level up
 * gives the flat `<skill>/SKILL.md` layout that Copilot Studio's "Add skill ›
 * From GitHub" importer reads, so one catalog URL installs the whole library.
 *
 * The result is written to a directory outside the repo and published by CI on
 * the orphan `catalog` branch, rather than duplicated on `main`.
 *
 * Every folder is named `<template-slug>-<skill-name>`. The importer's format
 * wants one flat level, so bare skill names would share a single namespace
 * across the whole library — and they collide in practice: `policy-retrieve`
 * belongs to two Retail templates, and `knowledge-retrieve` to one Retail and
 * one Manufacturing template. The prefix makes every folder unique by
 * construction and says which template a skill came from, which matters once
 * the list runs to a hundred folders.
 */
function exportCatalogSkills(dir: string, slug: string, outputDir: string): string[] {
  const skillsDir = join(dir, "skills");
  if (!existsSync(skillsDir)) return [];

  const exported: string[] = [];
  for (const name of readdirSync(skillsDir).sort()) {
    const from = join(skillsDir, name);
    if (!statSync(from).isDirectory()) continue;
    if (!existsSync(join(from, "SKILL.md"))) continue;

    const folder = `${slug}-${name}`;
    const to = join(outputDir, folder);
    for (const rel of walk(from)) {
      if (isBuildLitter(rel)) continue;
      // Reject anything that could escape the output directory before writing.
      const segments = rel.split(posix.sep);
      if (segments.some((s) => !s || s === "." || s === "..")) {
        throw new Error(`Refusing to export unsafe skill path: ${name}/${rel}`);
      }
      const target = join(to, ...segments);
      mkdirSync(dirname(target), { recursive: true });
      writeFileSync(target, readFileSync(join(from, segments.join(sep))));
    }
    exported.push(folder);
  }
  return exported;
}

/** Resolve `--catalog-output <dir>`, refusing a path inside the repo. */
function catalogOutputDir(): string | undefined {
  const i = process.argv.indexOf("--catalog-output");
  if (i < 0) return undefined;
  const value = process.argv[i + 1];
  if (!value || value.startsWith("--")) {
    throw new Error("`--catalog-output` requires a directory path");
  }
  const outputDir = resolve(value);
  const fromRoot = relative(ROOT, outputDir);
  if (fromRoot && !fromRoot.startsWith("..") && !isAbsolute(fromRoot)) {
    throw new Error(
      `--catalog-output must point outside the repository (got ${outputDir}); ` +
        "the catalog is published on its own branch, never committed to main",
    );
  }
  return outputDir;
}

function main() {
  if (!existsSync(SUBMISSIONS)) {
    console.error("No submissions/ directory found.");
    process.exit(1);
  }

  // Submissions are filed as `submissions/<industry>/<slug>/`. The industry
  // folder is for humans reading the repo — the published industry still comes
  // from metadata.json — so discovery walks two levels and everything
  // downstream keys on the leaf slug exactly as before.
  const isEntry = (name: string) => !name.startsWith("_") && !name.startsWith(".");
  const entries = readdirSync(SUBMISSIONS)
    .filter(isEntry)
    .filter((name) => statSync(join(SUBMISSIONS, name)).isDirectory())
    .sort()
    .flatMap((industryDir) =>
      readdirSync(join(SUBMISSIONS, industryDir))
        .filter(isEntry)
        .filter((slug) => statSync(join(SUBMISSIONS, industryDir, slug)).isDirectory())
        .sort()
        .map((slug) => ({ industryDir, slug })),
    );

  const catalogDir = CHECK_ONLY ? undefined : catalogOutputDir();

  if (!CHECK_ONLY) {
    // Regenerate from scratch so a removed submission does not leave a stale bundle behind.
    rmSync(OUT_BUNDLES, { recursive: true, force: true });
    mkdirSync(OUT_BUNDLES, { recursive: true });
    if (catalogDir) {
      rmSync(catalogDir, { recursive: true, force: true });
      mkdirSync(catalogDir, { recursive: true });
    }
  }

  const catalogSkills: string[] = [];

  for (const { industryDir, slug } of entries) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
      fail(slug, "folder name must be lowercase and hyphenated (e.g. quality-inspection)");
      continue;
    }

    const dir = join(SUBMISSIONS, industryDir, slug);
    const metaPath = join(dir, "metadata.json");
    if (!existsSync(metaPath)) {
      fail(slug, "missing metadata.json");
      continue;
    }

    let meta: Record<string, unknown>;
    try {
      meta = JSON.parse(readFileSync(metaPath, "utf8"));
    } catch (e) {
      fail(slug, `metadata.json is not valid JSON — ${(e as Error).message}`);
      continue;
    }

    const manifestPath = join(dir, ".claude-plugin", "plugin.json");
    const hasManifest = existsSync(manifestPath);
    const hasSkillMd = existsSync(join(dir, "SKILL.md"));
    if (!hasManifest && !hasSkillMd) {
      fail(
        slug,
        "no payload found — a plugin needs .claude-plugin/plugin.json, a single skill needs SKILL.md",
      );
      continue;
    }

    if (hasManifest) {
      try {
        JSON.parse(readFileSync(manifestPath, "utf8"));
      } catch (e) {
        fail(slug, `.claude-plugin/plugin.json is not valid JSON — ${(e as Error).message}`);
        continue;
      }
    }

    const skills = hasManifest ? readPluginSkills(dir) : [];
    if (hasManifest && skills.length === 0) {
      fail(slug, "plugin has no skills/<name>/SKILL.md — a package must bundle at least one skill");
      continue;
    }

    const type = hasManifest ? "plugin" : "skill";
    const authorGithub = resolveGithub(meta.authorGithub, meta.authorUrl);

    const d = validateMetadata(slug, meta, authorGithub);
    if (!d) continue;

    // The industry now appears twice: as the folder a submission sits in, and as
    // `metadata.json`'s `industry`. Metadata is authoritative, so keep the folder
    // from drifting away from it and quietly filing a template under the wrong heading.
    if (industryFolder(d.industry) !== industryDir) {
      fail(
        slug,
        `filed under submissions/${industryDir}/ but metadata.json says "${d.industry}" ` +
          `— move it to submissions/${industryFolder(d.industry)}/ or fix the metadata`,
      );
      continue;
    }

    notes.push(
      `  ${slug} — ${d.industry} · ${type} · ${skills.length} ${skills.length === 1 ? "skill" : "skills"}`,
    );

    if (CHECK_ONLY) continue;

    // --- bundle -----------------------------------------------------------
    // The package keeps a single root folder named after the slug, so unzipping
    // never scatters files into the current directory.
    //
    // Entry timestamps are pinned to the submission's own updatedAt rather than
    // "now", so re-running the importer on unchanged input produces a
    // byte-identical zip. Without that, every run would show up as a diff and
    // CI's "generated content is out of date" check could never pass.
    const stamp = d.updatedAt ?? d.createdAt ?? new Date("2026-01-01T00:00:00Z");
    const zip = new AdmZip();
    for (const rel of walk(dir)) {
      const top = rel.split(posix.sep)[0];
      if ((NEVER_BUNDLE.has(top) && !(top === "tests" && d.bundleTests)) || isBuildLitter(rel)) {
        continue;
      }
      zip.addFile(`${slug}/${rel}`, readFileSync(join(dir, rel.split(posix.sep).join(sep))));
    }
    for (const entry of zip.getEntries()) entry.header.time = stamp;
    zip.writeZip(join(OUT_BUNDLES, `${slug}.zip`));

    // --- catalog branch (this plugin's skills, flattened) -----------------
    if (catalogDir) catalogSkills.push(...exportCatalogSkills(dir, slug, catalogDir));
  }

  if (catalogSkills.length) {
    // The `<template-slug>-<skill-name>` folder name should make a clash
    // impossible, but two templates whose slugs and skill names happen to
    // concatenate the same way would still overwrite each other. Cheap to check.
    const dupes = [
      ...new Set(catalogSkills.filter((n, i) => catalogSkills.indexOf(n) !== i)),
    ];
    if (dupes.length) {
      errors.push(
        `  catalog: folder name(s) produced by more than one template: ${dupes.join(", ")}`,
      );
    } else {
      console.log(`\nCatalog: exported ${catalogSkills.length} skill(s).`);
    }
  }

  if (notes.length) {
    console.log(`${CHECK_ONLY ? "Checked" : "Imported"} ${notes.length} submission(s):`);
    console.log(notes.join("\n"));
  }

  if (errors.length) {
    console.error(`\n${errors.length} problem(s) found:`);
    console.error(errors.join("\n"));
    process.exit(1);
  }

  console.log(CHECK_ONLY ? "\nAll submissions valid." : "\nImport complete.");
}

main();
