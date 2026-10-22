import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, symlinkSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test, { type TestContext } from "node:test";
import { MATRIX_BUILT_FOLDER, MATRIX_DESTINATION_FOLDER, MatrixWatcher, parseMatrixName } from "./evaluation-matrices.js";
import { ROOT, sha256, sharepointPluginDir } from "./evaluation-workflow.js";
import { makeMos3Submission, write } from "./test-fixtures.js";

const SLUG = "time-expense-narrative-compliance";
const VERSION = "1.0.13";
const STAMP = "2026-10-22-1015";

function names(slug = SLUG, version = VERSION, stamp = STAMP) {
  return [
    `${slug}-v${version}-eval-matrix-${stamp}.xlsx`,
    `${slug}-v${version}-matrix-notes-${stamp}.md`,
  ];
}

function fixture(t: TestContext, slug = SLUG) {
  const root = mkdtempSync(join(tmpdir(), "evaluation-matrices-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const repoRoot = join(root, "repo");
  const queueRoot = join(root, "queue");
  const builtRoot = join(queueRoot, MATRIX_BUILT_FOLDER);
  const sharepointRoot = join(root, "library");
  const submission = makeMos3Submission(repoRoot, slug, VERSION);
  const pluginDir = sharepointPluginDir(sharepointRoot, "Professional Services", slug);
  mkdirSync(builtRoot, { recursive: true });
  mkdirSync(pluginDir, { recursive: true });
  const options = { builtRoot, sharepointRoot, repoRoot, stableSeconds: 1 };
  const outDir = join(pluginDir, MATRIX_DESTINATION_FOLDER);
  return { root, submission, repoRoot, queueRoot, builtRoot, sharepointRoot, pluginDir, options, outDir };
}

function pair(directory: string, slug = SLUG, version = VERSION, stamp = STAMP): string[] {
  return names(slug, version, stamp).map((name, index) => {
    const path = join(directory, name);
    write(path, index === 0 ? Buffer.from([0x50, 0x4b, 0x03, 0x04, 0, 255, 42]) : "# Matrix build notes\n");
    return path;
  });
}

test("matrix filenames parse the owner's workbook/notes convention exactly", () => {
  assert.deepEqual(parseMatrixName(names()[0]), { slug: SLUG, version: VERSION, kind: "eval-matrix", timestamp: STAMP });
  assert.deepEqual(parseMatrixName(names()[1]), { slug: SLUG, version: VERSION, kind: "matrix-notes", timestamp: STAMP });
  for (const name of [
    `${SLUG}-v${VERSION}-eval-matrix-${STAMP}.md`,
    `${SLUG}-v${VERSION}-matrix-notes-${STAMP}.xlsx`,
    `${SLUG}-eval-matrix-${STAMP}.xlsx`,
    `${SLUG}-v${VERSION}-eval-matrix-2026-10-22.xlsx`,
    "unidentified-matrix.xlsx",
  ]) assert.throws(() => parseMatrixName(name), /unrecognized matrix filename/);
});

test("matrix watcher copies stable pairs byte-for-byte to the Wave 1 plugin; restarts are idempotent", (t) => {
  const f = fixture(t);
  const sources = pair(f.builtRoot);
  const watcher = new MatrixWatcher(f.options);
  assert.ok(watcher.scan(0).every((result) => result.status === "waiting"));
  assert.equal(existsSync(f.outDir), false);
  assert.ok(watcher.scan(999).every((result) => result.status === "waiting"));
  const copied = watcher.scan(1000);
  assert.equal(copied.length, 2);
  assert.ok(copied.every((result) => result.status === "copied"));
  for (const [index, source] of sources.entries()) {
    const destination = join(f.outDir, names()[index]);
    assert.equal(sha256(destination), sha256(source));
    assert.equal(existsSync(source), true, "the Cowork original is never moved or removed");
  }
  assert.match(f.outDir, /Wave 1/);
  const restarted = new MatrixWatcher(f.options);
  restarted.scan(2000);
  assert.ok(restarted.scan(3000).every((result) => result.status === "unchanged"));
});

test("matrix watcher preserves each timestamp and routes Wave 2 and legacy layouts", (t) => {
  const f = fixture(t, "client-status-qbr");
  pair(f.builtRoot, "client-status-qbr");
  pair(join(f.builtRoot, "completed"), "client-status-qbr", VERSION, "2026-10-22-1115");
  const legacy = "change-order-scope-control";
  makeMos3Submission(f.repoRoot, legacy, VERSION);
  const legacyDir = sharepointPluginDir(f.sharepointRoot, "Professional Services", legacy);
  mkdirSync(legacyDir, { recursive: true });
  pair(f.builtRoot, legacy);
  const watcher = new MatrixWatcher(f.options);
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.equal(results.length, 6);
  assert.ok(results.every((result) => result.status === "copied"));
  assert.match(f.outDir, /Wave 2/);
  assert.ok(existsSync(join(f.outDir, names("client-status-qbr")[0])));
  assert.ok(existsSync(join(f.outDir, names("client-status-qbr", VERSION, "2026-10-22-1115")[0])));
  assert.ok(existsSync(join(legacyDir, MATRIX_DESTINATION_FOLDER, names(legacy)[1])));
});

test("matrix watcher waits for the same plugin, version, timestamp and folder; both files must be non-empty", (t) => {
  const f = fixture(t);
  write(join(f.builtRoot, names()[0]), "workbook");
  write(join(f.builtRoot, names(SLUG, "1.0.14")[1]), "different version");
  write(join(f.builtRoot, names(SLUG, VERSION, "2026-10-22-1115")[1]), "different timestamp");
  write(join(f.builtRoot, "other", names()[1]), "different folder");
  const watcher = new MatrixWatcher(f.options);
  watcher.scan(0);
  assert.ok(watcher.scan(1000).every((result) => result.status === "waiting"));
  assert.equal(existsSync(f.outDir), false);
  write(join(f.builtRoot, names()[1]), "");
  watcher.scan(2000);
  assert.ok(watcher.scan(3000).every((result) => result.status === "waiting"));
  write(join(f.builtRoot, names()[1]), "complete notes");
  watcher.scan(4000);
  assert.equal(watcher.scan(5000).filter((result) => result.status === "copied").length, 2);
});

test("matrix watcher resets stability on content changes even when size and mtime match", (t) => {
  const f = fixture(t);
  const [source] = pair(f.builtRoot);
  const watcher = new MatrixWatcher(f.options);
  const original = statSync(source);
  watcher.scan(0);
  writeFileSync(source, Buffer.alloc(original.size, 65));
  utimesSync(source, original.atime, original.mtime);
  assert.ok(watcher.scan(1000).every((result) => result.status === "waiting"));
  assert.equal(existsSync(f.outDir), false);
  assert.ok(watcher.scan(2000).every((result) => result.status === "copied"));
});

test("matrix watcher preflights both destinations and never overwrites a different existing file", (t) => {
  const f = fixture(t);
  pair(f.builtRoot);
  const conflict = join(f.outDir, names()[1]);
  write(conflict, "human notes that must remain");
  const watcher = new MatrixWatcher(f.options);
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.ok(results.every((result) => result.status === "error" && result.message?.includes("nothing overwritten")));
  assert.equal(readFileSync(conflict, "utf8"), "human notes that must remain");
  assert.equal(existsSync(join(f.outDir, names()[0])), false, "conflict prevents copying the other half");
});

test("matrix watcher dry runs report destinations without creating files or folders", (t) => {
  const f = fixture(t);
  pair(f.builtRoot);
  const watcher = new MatrixWatcher({ ...f.options, dryRun: true });
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.ok(results.every((result) => result.status === "dry-run" && dirname(result.destination ?? "") === f.outDir));
  assert.equal(existsSync(f.outDir), false);
});

test("matrix watcher reports unknown plugins and missing SharePoint folders while copying valid pairs", (t) => {
  const f = fixture(t);
  pair(f.builtRoot);
  pair(f.builtRoot, "unknown-plugin");
  makeMos3Submission(f.repoRoot, "client-status-qbr", VERSION);
  pair(f.builtRoot, "client-status-qbr");
  const watcher = new MatrixWatcher(f.options);
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.equal(results.filter((result) => result.status === "copied").length, 2);
  assert.equal(results.filter((result) => result.message?.includes("submission not found")).length, 2);
  assert.equal(results.filter((result) => result.message?.includes("plugin folder does not exist")).length, 2);
  assert.equal(existsSync(sharepointPluginDir(f.sharepointRoot, "Professional Services", "client-status-qbr")), false);
});

test("matrix watcher ignores temporary/Office lock files but reports unexpected completed files", (t) => {
  const f = fixture(t);
  pair(f.builtRoot);
  for (const name of ["~$matrix.xlsx", ".upload.xlsx", "matrix.xlsx.partial", "matrix.xlsx.tmp"]) {
    write(join(f.builtRoot, name), "uploading");
  }
  write(join(f.builtRoot, "readme.md"), "unexpected");
  const watcher = new MatrixWatcher(f.options);
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.equal(results.length, 3);
  assert.equal(results.filter((result) => result.status === "copied").length, 2);
  assert.match(results.find((result) => result.status === "error")?.message ?? "", /unrecognized matrix filename/);
});

test("matrix watcher refuses linked source directories and destination folders", (t) => {
  const f = fixture(t);
  const external = join(f.root, "external");
  mkdirSync(external);
  pair(external);
  symlinkSync(external, join(f.builtRoot, "linked"), "junction");
  const watcher = new MatrixWatcher(f.options);
  assert.match(watcher.scan(0)[0].message ?? "", /not a regular file/);
  pair(f.builtRoot);
  symlinkSync(external, f.outDir, "junction");
  watcher.scan(0);
  const results = watcher.scan(1000);
  assert.equal(results.filter((result) => result.message?.includes("not a regular directory")).length, 2);
});

test("matrix watcher validates roots and stability settings, including overlapping folders", (t) => {
  const f = fixture(t);
  assert.throws(() => new MatrixWatcher({ ...f.options, builtRoot: join(f.root, "missing") }), /folder does not exist/);
  assert.throws(() => new MatrixWatcher({ ...f.options, sharepointRoot: f.builtRoot }), /must not overlap/);
  assert.throws(() => new MatrixWatcher({ ...f.options, builtRoot: f.pluginDir }), /must not overlap/);
  assert.throws(() => new MatrixWatcher({ ...f.options, stableSeconds: 0 }), /positive number/);
});

test("matrix CLI supports one-shot copying, dry runs and a nonzero exit for a failed scan", (t) => {
  const f = fixture(t);
  pair(f.builtRoot);
  const script = join(ROOT, "scripts", "watch-evaluation-matrices.ts");
  const args = ["--import", "tsx", script, "--once", "--queue-root", f.queueRoot,
    "--sharepoint-root", f.sharepointRoot, "--stable-seconds", "0.01"];
  // The CLI uses the real repository's submission metadata, but all writes stay in the fixture.
  const dryRun = execFileSync(process.execPath, [...args, "--dry-run"], { cwd: ROOT, encoding: "utf8" });
  assert.match(dryRun, /dry-run:/);
  assert.equal(existsSync(f.outDir), false);
  const copied = execFileSync(process.execPath, args, { cwd: ROOT, encoding: "utf8" });
  assert.match(copied, /copied:/);
  assert.ok(existsSync(join(f.outDir, names()[0])));
  write(join(f.outDir, names()[1]), "conflict");
  const failed = spawnSync(process.execPath, args, { cwd: ROOT, encoding: "utf8" });
  assert.equal(failed.status, 1);
  assert.match(failed.stderr, /nothing overwritten/);
  const invalid = spawnSync(process.execPath, [...args, "--poll-seconds", "0"], { cwd: ROOT, encoding: "utf8" });
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /positive number/);
});
