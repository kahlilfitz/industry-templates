import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import AdmZip from "adm-zip";
import { evaluationArchiveDir, sha256, sharepointPluginDir } from "./evaluation-workflow.js";
import {
  MOS_128_SCHEMA,
  MOS_PACKAGE_FOLDER,
  README_MARKER,
  buildMosPackage,
  deriveMos128Zip,
  toManifest128,
  validateAgainst128Schema,
} from "./mos-package.js";
import { MOS3_SCHEMA, buildMos3Zip } from "./mos3-package.js";
import { FIXED_ZIP_TIMESTAMP } from "./package-files.js";
import { makeMos3Submission, validManifest, write } from "./test-fixtures.js";

const WAVE_SLUG = "deliverable-review-quality-gate";
const VERSION = "1.2.3";

function withTemp(run: (dir: string) => void): void {
  const dir = mkdtempSync(join(tmpdir(), "mos-package-"));
  try {
    run(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** A repo with a MOS3 submission and a SharePoint root holding its archived evaluated ZIP. */
function fixture(dir: string, slug = WAVE_SLUG) {
  const repoRoot = join(dir, "repo");
  const sharepointRoot = join(dir, "sharepoint");
  const submission = makeMos3Submission(repoRoot, slug, VERSION);
  const archived = join(evaluationArchiveDir(sharepointRoot, "Professional Services", slug, VERSION), `${slug}.zip`);
  write(archived, Buffer.alloc(0));
  buildMos3Zip(submission, archived, FIXED_ZIP_TIMESTAMP);
  const pluginDir = sharepointPluginDir(sharepointRoot, "Professional Services", slug);
  return { repoRoot, sharepointRoot, submission, archived, pluginDir, slug };
}

function zipEntries(path: string): Map<string, Buffer> {
  return new Map(new AdmZip(path).getEntries().map((e) => [e.entryName, e.getData()]));
}

test("toManifest128 changes only $schema, manifestVersion and packageName, keeping order and formatting", () => {
  const source = validManifest(VERSION);
  const raw = JSON.stringify(source, null, 4).split("\n").join("\r\n") + "\r\n";
  const text = toManifest128(raw);
  const parsed = JSON.parse(text) as Record<string, unknown>;

  assert.equal(parsed.$schema, MOS_128_SCHEMA);
  assert.equal(parsed.manifestVersion, "1.28");
  assert.equal("packageName" in parsed, false);
  assert.deepEqual(
    Object.keys(parsed),
    Object.keys(source).filter((key) => key !== "packageName"),
  );
  for (const key of Object.keys(parsed)) {
    if (key !== "$schema" && key !== "manifestVersion") assert.deepEqual(parsed[key], source[key], key);
  }
  assert.ok(text.endsWith("}\r\n"));
  assert.ok(!/[^\r]\n/.test(text), "line endings stay CRLF");
  assert.match(text, /\r\n {4}"manifestVersion"/);
});

test("toManifest128 refuses a manifest that is not the evaluated devPreview manifest", () => {
  const already128 = { ...validManifest(VERSION), $schema: MOS_128_SCHEMA, manifestVersion: "1.28" };
  assert.throws(() => toManifest128(JSON.stringify(already128)), /must be the evaluated devPreview manifest/);
  const mixed = { ...validManifest(VERSION), manifestVersion: "1.28" };
  assert.equal(mixed.$schema, MOS3_SCHEMA);
  assert.throws(() => toManifest128(JSON.stringify(mixed)), /must be the evaluated devPreview manifest/);
});

test("the v1.28 schema rejects the devPreview manifest and accepts the derived one", () => {
  const errors = validateAgainst128Schema(validManifest(VERSION));
  assert.ok(errors.some((e) => e.includes("packageName")), errors.join("\n"));
  assert.ok(errors.some((e) => e.includes("/manifestVersion")), errors.join("\n"));
  assert.deepEqual(validateAgainst128Schema(JSON.parse(toManifest128(JSON.stringify(validManifest(VERSION))))), []);
});

test("deriveMos128Zip keeps every entry except manifest.json byte-identical", () =>
  withTemp((dir) => {
    const { archived } = fixture(dir);
    const source = readFileSync(archived);
    const d = deriveMos128Zip(source);

    const before = new AdmZip(source).getEntries().map((e) => e.entryName);
    const after = new AdmZip(d.zip).getEntries().map((e) => e.entryName);
    assert.deepEqual(after, before);
    for (const entry of d.entries) {
      if (entry.name === "manifest.json") assert.notEqual(entry.sha256, entry.sourceSha256);
      else assert.equal(entry.sha256, entry.sourceSha256, entry.name);
    }
    assert.equal(d.identicalEntries, d.entries.length - 1);
    assert.equal(d.manifest.manifestVersion, "1.28");
    assert.equal(d.removedPackageName, "com.microsoft.cowork.demo-plugin");
    assert.deepEqual(d.skillIcons, [
      { folder: "alpha-skill", icon: "DocumentSearch" },
      { folder: "beta-skill", icon: "DocumentSearch" },
    ]);
    assert.equal(deriveMos128Zip(source).sha256, d.sha256, "derivation is reproducible");
  }));

test("deriveMos128Zip refuses a source with entries outside the package layout", () =>
  withTemp((dir) => {
    const { archived } = fixture(dir);
    const zip = new AdmZip(archived);
    zip.addFile("README.md", Buffer.from("not part of a package"));
    assert.throws(() => deriveMos128Zip(zip.toBuffer()), /unexpected entry .*README\.md/);

    const noManifest = new AdmZip(archived);
    noManifest.deleteFile("manifest.json");
    assert.throws(() => deriveMos128Zip(noManifest.toBuffer()), /no manifest\.json/);
  }));

test("buildMosPackage --out-dir writes the package, README and skills copy", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot, archived, pluginDir } = fixture(dir);
    const outDir = join(dir, "out");
    const result = buildMosPackage({ slug: WAVE_SLUG, sharepointRoot, outDir, repoRoot });

    assert.equal(result.status, "written");
    assert.equal(result.packagePath, join(outDir, `${WAVE_SLUG}-mos3-v${VERSION}.zip`));
    assert.equal(sha256(result.packagePath), result.derivation.sha256);
    const entries = zipEntries(result.packagePath);
    const manifest = JSON.parse(entries.get("manifest.json")!.toString("utf8"));
    assert.equal(manifest.$schema, MOS_128_SCHEMA);
    assert.deepEqual(
      readFileSync(join(outDir, "skills", "alpha-skill", "SKILL.md")),
      entries.get("skills/alpha-skill/SKILL.md"),
    );

    const readme = readFileSync(join(outDir, "README.md"), "utf8");
    assert.ok(readme.startsWith(README_MARKER));
    assert.ok(readme.includes(sha256(archived)), "README cites the evaluated ZIP hash");
    assert.ok(readme.includes(result.derivation.sha256), "README cites the package hash");
    assert.match(readme, new RegExp(`${result.derivation.entries.length - 1} of ${result.derivation.entries.length} entries byte-identical`));
    assert.match(readme, /errors: none/);
    assert.equal(existsSync(join(pluginDir, MOS_PACKAGE_FOLDER)), false, "a dry run never touches SharePoint");
  }));

test("buildMosPackage writes into the plugin folder only after the C4 promotion", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot, archived, pluginDir } = fixture(dir);
    const options = { slug: WAVE_SLUG, sharepointRoot, repoRoot };
    const promoted = join(pluginDir, `${WAVE_SLUG}-cowork.zip`);

    assert.throws(() => buildMosPackage(options), /cowork\.zip does not exist.*C4/s);
    write(promoted, Buffer.from("a different build"));
    assert.throws(() => buildMosPackage(options), /not byte-identical to the evaluated ZIP/);
    assert.equal(existsSync(join(pluginDir, MOS_PACKAGE_FOLDER)), false);

    write(promoted, readFileSync(archived));
    const result = buildMosPackage(options);
    assert.equal(result.outDir, join(pluginDir, MOS_PACKAGE_FOLDER));
    assert.match(readFileSync(join(result.outDir, "README.md"), "utf8"), /cowork\.zip` is byte-identical/);
    assert.equal(buildMosPackage(options).status, "unchanged");
  }));

test("buildMosPackage refuses to overwrite or leave stale files instead of deleting", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot } = fixture(dir);
    const options = { slug: WAVE_SLUG, sharepointRoot, repoRoot };

    const zipClash = join(dir, "zip-clash");
    write(join(zipClash, `${WAVE_SLUG}-mos3-v${VERSION}.zip`), Buffer.from("old"));
    assert.throws(() => buildMosPackage({ ...options, outDir: zipClash }), /already exists with different content/);

    const handReadme = join(dir, "hand-readme");
    write(join(handReadme, "README.md"), "# Written by a person\n");
    assert.throws(() => buildMosPackage({ ...options, outDir: handReadme }), /was not generated by mos:build/);
    assert.equal(readFileSync(join(handReadme, "README.md"), "utf8"), "# Written by a person\n");

    const stale = join(dir, "stale");
    write(join(stale, "skills", "retired-skill", "SKILL.md"), "old");
    assert.throws(() => buildMosPackage({ ...options, outDir: stale }), /retired-skill\/SKILL\.md/);
    assert.equal(existsSync(join(stale, `${WAVE_SLUG}-mos3-v${VERSION}.zip`)), false, "nothing written on refusal");
  }));

test("the README flags listing sections taken from a newer source version", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot, submission } = fixture(dir);
    write(
      join(submission, "listing-metadata.md"),
      "# Listing\n\n## Top 3 prompts\n\n1. First prompt\n2. Second prompt\n3. Third prompt\n\n## Icons\n\nnone\n",
    );
    const metadataPath = join(submission, "metadata.json");
    write(metadataPath, readFileSync(metadataPath, "utf8").replace(`"version": "${VERSION}"`, '"version": "1.2.4"'));
    const manifestPath = join(submission, "manifest.json");
    write(manifestPath, readFileSync(manifestPath, "utf8").replace(`"version": "${VERSION}"`, '"version": "1.2.4"'));

    const outDir = join(dir, "out");
    buildMosPackage({ slug: WAVE_SLUG, version: VERSION, sharepointRoot, outDir, repoRoot });
    const readme = readFileSync(join(outDir, "README.md"), "utf8");
    assert.match(readme, /### Top 3 prompts\n\n1\. First prompt\n2\. Second prompt\n3\. Third prompt/);
    assert.match(readme, /listing-metadata\.md` for plugin version 1\.2\.4, not 1\.2\.3/);
  }));

test("buildMosPackage refuses an --out-dir inside the SharePoint library, so the C4 gate cannot be bypassed", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot, pluginDir } = fixture(dir);
    for (const outDir of [join(pluginDir, MOS_PACKAGE_FOLDER), join(sharepointRoot, "elsewhere")]) {
      assert.throws(
        () => buildMosPackage({ slug: WAVE_SLUG, sharepointRoot, outDir, repoRoot }),
        /inside the SharePoint library/,
      );
      assert.equal(existsSync(outDir), false);
    }
  }));

test("buildMosPackage refuses a file/folder clash before writing anything", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot } = fixture(dir);
    const outDir = join(dir, "clash");
    mkdirSync(join(outDir, "skills", "alpha-skill", "SKILL.md"), { recursive: true });
    assert.throws(
      () => buildMosPackage({ slug: WAVE_SLUG, sharepointRoot, outDir, repoRoot }),
      /SKILL\.md is not a regular file/,
    );
    assert.equal(existsSync(join(outDir, `${WAVE_SLUG}-mos3-v${VERSION}.zip`)), false);
    assert.equal(existsSync(join(outDir, "README.md")), false);
    assert.equal(existsSync(join(outDir, "skills", "beta-skill")), false);
  }));

test("buildMosPackage needs --out-dir for plugins outside the Retail layout", () =>
  withTemp((dir) => {
    const { repoRoot, sharepointRoot } = fixture(dir, "demo-plugin");
    assert.throws(
      () => buildMosPackage({ slug: "demo-plugin", sharepointRoot, repoRoot }),
      /not filed in the Retail layout/,
    );
    const outDir = join(dir, "out");
    assert.equal(buildMosPackage({ slug: "demo-plugin", sharepointRoot, outDir, repoRoot }).status, "written");
  }));
