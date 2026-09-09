/**
 * Import `submissions/` into the published gallery.
 *
 * Contributors only ever touch `submissions/<industry>/<slug>/`. This script is the single
 * place that turns a submission into the two generated artifacts the site is
 * built from:
 *
 *   - `src/content/templates/<slug>.md`  — catalog frontmatter + overview body
 *   - `public/bundles/<slug>.zip`        — the downloadable package
 *
 * plus, when the submission ships a human-facing `README.md`:
 *
 *   - `src/content/guides/<slug>.md`     — becomes the detail page's main content
 *
 * Run `npm run check:submissions` to validate without writing anything, or
 * `npm run import:submissions` to regenerate. CI runs both.
 *
 * With `--catalog-output <dir>`, each plugin's inner skills are additionally
 * exported unpacked to that directory, flattened one per folder. CI publishes
 * the result on the orphan `catalog` branch, which is the URL people paste
 * into Copilot Studio's "Add skill › From GitHub".
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, rmSync, existsSync } from "node:fs";
import { dirname, isAbsolute, join, posix, relative, resolve, sep } from "node:path";
import AdmZip from "adm-zip";
import { templateSchema } from "../src/lib/template-schema";

const ROOT = process.cwd();
const SUBMISSIONS = join(ROOT, "submissions");
const OUT_TEMPLATES = join(ROOT, "src", "content", "templates");
const OUT_GUIDES = join(ROOT, "src", "content", "guides");
const OUT_BUNDLES = join(ROOT, "public", "bundles");

const CHECK_ONLY = process.argv.includes("--check");

/** Files and folders that are for humans or CI, never shipped in the bundle. */
const NEVER_BUNDLE = new Set([
  "metadata.json",
  "metadata.yaml",
  "README.md",
  "PACKAGE-NOTES.md",
  "tests",
]);

const errors: string[] = [];
const notes: string[] = [];

function fail(slug: string, message: string) {
  errors.push(`  ${slug}: ${message}`);
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

function yamlScalar(value: string): string {
  return /^[\w][\w .\-/()&,']*$/.test(value) ? value : JSON.stringify(value);
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
 * The boilerplate every template page carries: what the package contains and
 * how to install it. Generated from the payload itself so it can never drift
 * from the files that actually ship. Appended after a submission's `README.md`
 * when it has one, and used on its own when it doesn't.
 */
function standardSections(
  repoPath: string,
  skills: SkillEntry[],
  hasDemoData: boolean,
  hasTests: boolean,
): string {
  const lines: string[] = [];

  if (skills.length > 0) {
    lines.push("## Skills in this package", "");
    for (const s of skills) {
      lines.push(`- **${s.name}**${s.description ? ` — ${s.description}` : ""}`);
    }
    lines.push("");
  }

  if (hasDemoData) {
    lines.push(
      "## Demo data",
      "",
      "The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.",
      "",
    );
  }

  lines.push(
    "## Install",
    "",
    "1. Download the plugin package (the `.zip` on this page).",
    "2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).",
    "3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.",
    "",
    "See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.",
    "",
  );

  if (hasTests) {
    lines.push(
      "## Test evidence",
      "",
      `A test report and sample prompt set are kept with the source, in [\`submissions/${repoPath}/tests/\`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/${repoPath}/tests).`,
      "",
    );
  }

  lines.push(
    "## Before you use it on real work",
    "",
    "This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.",
    "",
  );

  return lines.join("\n");
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
 * across the whole gallery — and they collide in practice: `policy-retrieve`
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

/** The generated page body: catalog summary, package callout, then boilerplate. */
function buildBody(
  repoPath: string,
  meta: Record<string, unknown>,
  skills: SkillEntry[],
  hasDemoData: boolean,
  hasTests: boolean,
): string {
  return [
    String(meta.description ?? "").trim(),
    "",
    `> **${meta.industry} template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a \`.zip\` bundling the skills, rules, and contracts below.`,
    "",
    standardSections(repoPath, skills, hasDemoData, hasTests),
  ].join("\n");
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
    // Regenerate from scratch so a removed submission does not leave a stale
    // page or bundle behind.
    for (const dir of [OUT_TEMPLATES, OUT_GUIDES, OUT_BUNDLES]) {
      rmSync(dir, { recursive: true, force: true });
      mkdirSync(dir, { recursive: true });
    }
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

    let manifest: Record<string, unknown> = {};
    if (hasManifest) {
      try {
        manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
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

    const frontmatterData = {
      name: meta.name,
      description: meta.description,
      agentDescription: meta.agentDescription ?? manifest.description ?? undefined,
      industry: meta.industry,
      platforms: meta.platforms,
      type,
      tags: meta.tags,
      author: meta.author,
      authorUrl: meta.authorUrl,
      authorGithub,
      version: meta.version ?? manifest.version ?? undefined,
      createdAt: meta.createdAt,
      updatedAt: meta.updatedAt,
      bundle: `bundles/${slug}.zip`,
      skills: skills.length ? skills.map((s) => ({ name: s.name })) : undefined,
      coverColor: meta.coverColor,
      featured: meta.featured ?? false,
    };

    const parsed = templateSchema.safeParse(frontmatterData);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        fail(slug, `${issue.path.join(".") || "(root)"} — ${issue.message}`);
      }
      continue;
    }
    const d = parsed.data;

    // The industry now appears twice: as the folder a submission sits in, and as
    // `metadata.json`'s `industry`, which is what the site actually publishes.
    // Only the metadata is authoritative — this keeps the folder from drifting
    // away from it and quietly filing a template under the wrong heading.
    if (industryFolder(d.industry) !== industryDir) {
      fail(
        slug,
        `filed under submissions/${industryDir}/ but metadata.json says "${d.industry}" ` +
          `— move it to submissions/${industryFolder(d.industry)}/ or fix the metadata`,
      );
      continue;
    }

    const hasDemoData = existsSync(join(dir, "demo-data"));
    const hasTests = existsSync(join(dir, "tests"));

    notes.push(
      `  ${slug} — ${d.industry} · ${d.type} · ${skills.length} ${skills.length === 1 ? "skill" : "skills"}`,
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
      if (NEVER_BUNDLE.has(top)) continue;
      zip.addFile(`${slug}/${rel}`, readFileSync(join(dir, rel.split(posix.sep).join(sep))));
    }
    for (const entry of zip.getEntries()) entry.header.time = stamp;
    zip.writeZip(join(OUT_BUNDLES, `${slug}.zip`));

    // --- page -------------------------------------------------------------
    const fm: string[] = ["---"];
    fm.push(`name: ${yamlScalar(d.name)}`);
    fm.push(`description: ${JSON.stringify(d.description)}`);
    if (d.agentDescription) fm.push(`agentDescription: ${JSON.stringify(d.agentDescription)}`);
    fm.push(`industry: ${yamlScalar(d.industry)}`);
    fm.push(`platforms: [${d.platforms.join(", ")}]`);
    fm.push(`type: ${d.type}`);
    fm.push(`tags: [${d.tags.join(", ")}]`);
    fm.push(`author: ${yamlScalar(d.author)}`);
    if (d.authorUrl) fm.push(`authorUrl: ${JSON.stringify(d.authorUrl)}`);
    if (d.authorGithub) fm.push(`authorGithub: ${d.authorGithub}`);
    if (d.version) fm.push(`version: ${yamlScalar(d.version)}`);
    if (d.createdAt) fm.push(`createdAt: ${d.createdAt.toISOString().slice(0, 10)}`);
    if (d.updatedAt) fm.push(`updatedAt: ${d.updatedAt.toISOString().slice(0, 10)}`);
    fm.push(`bundle: ${d.bundle}`);
    if (d.skills?.length) {
      fm.push("skills:");
      for (const s of d.skills) fm.push(`  - name: ${yamlScalar(s.name)}`);
    }
    if (d.coverColor) fm.push(`coverColor: ${JSON.stringify(d.coverColor)}`);
    if (d.featured) fm.push("featured: true");
    fm.push("---", "");

    const repoPath = `${industryDir}/${slug}`;
    const body = buildBody(repoPath, meta, skills, hasDemoData, hasTests);
    writeFileSync(join(OUT_TEMPLATES, `${slug}.md`), fm.join("\n") + body, "utf8");

    // --- guide (human-facing README becomes the page's main content) ------
    // The README leads, in the author's own voice; the "what's in the package"
    // and install boilerplate is appended so it always matches the real payload.
    const readmePath = join(dir, "README.md");
    if (existsSync(readmePath)) {
      const readme = readFileSync(readmePath, "utf8")
        .replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")
        .trimEnd();
      const guide = `${readme}\n\n${standardSections(slug, skills, hasDemoData, hasTests)}`;
      writeFileSync(join(OUT_GUIDES, `${slug}.md`), guide, "utf8");
    }

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
