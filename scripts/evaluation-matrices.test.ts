import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test, { type TestContext } from "node:test";
import {
  MATRIX_BUILT_FOLDER,
  MATRIX_DESTINATION_FOLDER,
  MATRIX_PROCESSED_FOLDER,
  MATRIX_QUEUE_FOLDER,
  MatrixWatcher,
  describeMatrixRequest,
  parseMatrixName,
  readMatrixLedger,
  requestMatrix,
  requestRunMatrix,
} from "./evaluation-matrices.js";
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

test("matrix ledger skips collected pairs after SharePoint rewrites the workbook, and still guards new pairs", (t) => {
  const f = fixture(t);
  const ledgerPath = join(f.root, "state", "matrix-collected.json");
  const sources = pair(f.builtRoot);
  const watcher = new MatrixWatcher({ ...f.options, ledgerPath });
  watcher.scan(0);
  assert.ok(watcher.scan(1000).every((result) => result.status === "copied"));
  const ledger = readMatrixLedger(ledgerPath);
  assert.deepEqual(ledger.map((entry) => entry.source), sources);
  assert.deepEqual(ledger.map((entry) => entry.digest), sources.map((source) => sha256(source)));
  // SharePoint adds metadata to Office files after upload.
  const workbook = join(f.outDir, names()[0]);
  write(workbook, Buffer.from([0x50, 0x4b, 0x03, 0x04, 1, 2, 3, 4, 5]));
  const restarted = new MatrixWatcher({ ...f.options, ledgerPath });
  restarted.scan(2000);
  const results = restarted.scan(3000);
  assert.ok(results.every((result) => result.status === "unchanged" && result.message === "already collected"), JSON.stringify(results));
  assert.notEqual(sha256(workbook), sha256(sources[0]), "the SharePoint copy is left alone");
  const unrecorded = new MatrixWatcher(f.options);
  unrecorded.scan(4000);
  assert.ok(unrecorded.scan(5000).every((result) => result.status === "error"), "without a ledger record the difference is still a conflict");
  rmSync(workbook);
  const recopy = new MatrixWatcher({ ...f.options, ledgerPath });
  recopy.scan(6000);
  assert.deepEqual(recopy.scan(7000).map((result) => result.status).sort(), ["copied", "unchanged"]);
  assert.equal(sha256(workbook), sha256(sources[0]));
  write(sources[1], "# Rebuilt notes\n");
  const changed = new MatrixWatcher({ ...f.options, ledgerPath });
  changed.scan(8000);
  assert.ok(changed.scan(9000).every((result) => result.status === "error" && /nothing overwritten/.test(result.message ?? "")));
  assert.equal(readMatrixLedger(ledgerPath).length, 2);
});

test("matrix watcher dry runs do not write the ledger", (t) => {
  const f = fixture(t);
  const ledgerPath = join(f.root, "matrix-collected.json");
  pair(f.builtRoot);
  const watcher = new MatrixWatcher({ ...f.options, ledgerPath, dryRun: true });
  watcher.scan(0);
  assert.ok(watcher.scan(1000).every((result) => result.status === "dry-run"));
  assert.equal(existsSync(ledgerPath), false);
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
    "--sharepoint-root", f.sharepointRoot, "--stable-seconds", "0.01", "--ledger", join(f.root, "ledger.json")];
  // The CLI uses the real repository's submission metadata, but all writes stay in the fixture.
  const dryRun = execFileSync(process.execPath, [...args, "--dry-run"], { cwd: ROOT, encoding: "utf8" });
  assert.match(dryRun, /dry-run:/);
  assert.equal(existsSync(f.outDir), false);
  const copied = execFileSync(process.execPath, args, { cwd: ROOT, encoding: "utf8" });
  assert.match(copied, /copied:/);
  assert.ok(existsSync(join(f.outDir, names()[0])));
  write(join(f.outDir, names()[1]), "conflict");
  // A fresh ledger has no record of the pair, so the changed destination is a real conflict.
  const failed = spawnSync(process.execPath, [...args.slice(0, -1), join(f.root, "fresh-ledger.json")], { cwd: ROOT, encoding: "utf8" });
  assert.equal(failed.status, 1);
  assert.match(failed.stderr, /nothing overwritten/);
  const invalid = spawnSync(process.execPath, [...args, "--poll-seconds", "0"], { cwd: ROOT, encoding: "utf8" });
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /positive number/);
});

function matrixQueue(t: TestContext, verdict = "Ready") {
  const root = mkdtempSync(join(tmpdir(), "evaluation-matrix-request-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const queueRoot = join(root, "queue");
  for (const folder of [MATRIX_QUEUE_FOLDER, MATRIX_BUILT_FOLDER, MATRIX_PROCESSED_FOLDER]) {
    mkdirSync(join(queueRoot, folder), { recursive: true });
  }
  const runDir = join(root, "inbox", SLUG, VERSION);
  const artifactPath = join(runDir, `${SLUG}.zip`);
  write(artifactPath, Buffer.from([0x50, 0x4b, 0x05, 0x06, 1, 2, 3]));
  const digest = sha256(artifactPath);
  const runPath = join(runDir, "evaluation-run.json");
  const run = {
    schemaVersion: 1, status: "archived", slug: SLUG, displayName: "T&E", industry: "Professional Services",
    artifactVersion: VERSION, artifactFile: `${SLUG}.zip`, artifactSha256: digest, gitCommit: "abc", gitDirty: false,
    preparedAt: "2026-10-23T00:00:00Z", coworkTaskName: "evaluate", automatedVerdict: verdict,
  };
  writeFileSync(runPath, `${JSON.stringify(run, null, 2)}\n`);
  const target = join(queueRoot, MATRIX_QUEUE_FOLDER, `${SLUG}-v${VERSION}.zip`);
  const options = { queueRoot, slug: SLUG, version: VERSION, artifactPath, digest };
  return { root, queueRoot, runDir, runPath, artifactPath, digest, target, options };
}

test("a Ready run's matrix request copies the exact ZIP into the matrix queue once, with no staging left", (t) => {
  const q = matrixQueue(t);
  const dry = requestRunMatrix(q.runPath, q.queueRoot, true);
  assert.equal(dry.status, "dry-run");
  assert.equal(existsSync(q.target), false);
  assert.equal(JSON.parse(readFileSync(q.runPath, "utf8")).matrixRequest, undefined);

  const request = requestRunMatrix(q.runPath, q.queueRoot);
  assert.equal(request.status, "queued");
  assert.equal(request.zip, q.target);
  assert.equal(sha256(q.target), q.digest);
  assert.deepEqual(readdirSync(join(q.queueRoot, "4 - Matrices")).filter((name) => name.startsWith(".")), []);
  assert.deepEqual(readdirSync(join(q.queueRoot, MATRIX_QUEUE_FOLDER)), [`${SLUG}-v${VERSION}.zip`]);
  const recorded = JSON.parse(readFileSync(q.runPath, "utf8"));
  assert.equal(recorded.matrixRequest.status, "queued");
  assert.equal(recorded.matrixRequest.zip, q.target);
  assert.match(describeMatrixRequest(request), /Matrix requested/);

  assert.equal(requestRunMatrix(q.runPath, q.queueRoot).status, "already-queued");
});

test("a matrix request skips a version already processed or built and never overwrites a different ZIP", (t) => {
  const q = matrixQueue(t);
  const processed = join(q.queueRoot, MATRIX_PROCESSED_FOLDER, `${SLUG}-v${VERSION}.zip`);
  write(processed, readFileSync(q.artifactPath));
  assert.equal(requestMatrix(q.options).status, "already-processed");
  write(processed, "different bytes");
  assert.throws(() => requestMatrix(q.options), /different .*nothing overwritten/);
  rmSync(processed);

  mkdirSync(join(q.queueRoot, MATRIX_BUILT_FOLDER, SLUG, `v${VERSION} - 2026-10-23-1540`), { recursive: true });
  assert.equal(requestMatrix(q.options).status, "already-built");
  rmSync(join(q.queueRoot, MATRIX_BUILT_FOLDER, SLUG), { recursive: true });

  write(q.target, "someone else's ZIP");
  assert.throws(() => requestRunMatrix(q.runPath, q.queueRoot), /nothing overwritten/);
  assert.equal(readFileSync(q.target, "utf8"), "someone else's ZIP");
  assert.match(JSON.parse(readFileSync(q.runPath, "utf8")).matrixRequestError, /nothing overwritten/);
  rmSync(q.target);
  assert.equal(requestRunMatrix(q.runPath, q.queueRoot).status, "queued");
  assert.equal(JSON.parse(readFileSync(q.runPath, "utf8")).matrixRequestError, undefined);
});

test("a matrix request refuses a changed ZIP, a missing queue folder and runs that are not archived Ready", (t) => {
  const q = matrixQueue(t);
  assert.throws(() => requestMatrix({ ...q.options, digest: "0".repeat(64) }), /no longer matches/);
  assert.throws(() => requestMatrix({ ...q.options, queueRoot: join(q.root, "missing") }), /matrix queue folder does not exist/);
  for (const queueRoot of [undefined, join(q.root, "missing")]) {
    assert.throws(() => requestRunMatrix(q.runPath, queueRoot), /queue folder is not available/);
    assert.match(JSON.parse(readFileSync(q.runPath, "utf8")).matrixRequestError, /queue folder is not available/);
  }
  for (const verdict of ["No-ship", "Blocked"]) {
    const other = matrixQueue(t, verdict);
    assert.throws(() => requestRunMatrix(other.runPath, other.queueRoot), new RegExp(`only an archived Ready run.*${verdict}`));
    assert.equal(existsSync(other.target), false);
  }
  assert.equal(existsSync(q.target), false);
});

function archiveFixture(t: TestContext, verdict: string) {
  const q = matrixQueue(t, verdict);
  const run = JSON.parse(readFileSync(q.runPath, "utf8"));
  writeFileSync(q.runPath, `${JSON.stringify({ ...run, status: "prepared", automatedVerdict: undefined }, null, 2)}\n`);
  const source = join(q.root, "reports");
  const body = `<p>${SLUG} ${VERSION}</p><p>Expected and observed SHA-256 ${q.digest}. SHA-256 check: MATCH</p><p>Automated verdict: ${verdict}</p>`;
  for (const report of ["plugin-health.html", "behavioral-test-report.html", "recommendations.html"]) write(join(source, report), body);
  const sharepointRoot = join(q.root, "library");
  mkdirSync(sharepointRoot);
  const args = ["--import", "tsx", join(ROOT, "scripts", "archive-evaluation.ts"), "--slug", SLUG, "--version", VERSION,
    "--source", source, "--inbox-root", join(q.root, "inbox"), "--sharepoint-root", sharepointRoot, "--queue-root", q.queueRoot];
  return { ...q, args };
}

test("archiving a Ready verdict requests the matrix; --no-matrix and other verdicts do not", (t) => {
  const ready = archiveFixture(t, "Ready");
  const output = execFileSync(process.execPath, ready.args, { cwd: ROOT, encoding: "utf8" });
  assert.match(output, /Automated verdict: Ready/);
  assert.match(output, /Matrix requested/);
  assert.equal(sha256(ready.target), ready.digest);
  assert.equal(JSON.parse(readFileSync(ready.runPath, "utf8")).matrixRequest.status, "queued");

  const skipped = archiveFixture(t, "Ready");
  assert.match(execFileSync(process.execPath, [...skipped.args, "--no-matrix"], { cwd: ROOT, encoding: "utf8" }), /Matrix request skipped/);
  assert.equal(existsSync(skipped.target), false);

  const noShip = archiveFixture(t, "No-ship");
  const noShipOutput = execFileSync(process.execPath, noShip.args, { cwd: ROOT, encoding: "utf8" });
  assert.doesNotMatch(noShipOutput, /Matrix/);
  assert.equal(existsSync(noShip.target), false);

  const conflict = archiveFixture(t, "Ready");
  write(conflict.target, "someone else's ZIP");
  const failed = spawnSync(process.execPath, conflict.args, { cwd: ROOT, encoding: "utf8" });
  assert.equal(failed.status, 0, "a failed matrix request does not undo or fail the archive");
  assert.match(failed.stderr, /Matrix request failed \(the evaluation is still archived\)/);
  assert.equal(JSON.parse(readFileSync(conflict.runPath, "utf8")).status, "archived");
  assert.equal(readFileSync(conflict.target, "utf8"), "someone else's ZIP");

  const unavailable = archiveFixture(t, "Ready");
  const missingQueue = [...unavailable.args.slice(0, -1), join(unavailable.root, "missing")];
  const unavailableRun = spawnSync(process.execPath, missingQueue, { cwd: ROOT, encoding: "utf8" });
  assert.equal(unavailableRun.status, 0);
  assert.match(unavailableRun.stderr, /queue folder is not available[\s\S]*evaluation:request-matrix/);
  assert.match(JSON.parse(readFileSync(unavailable.runPath, "utf8")).matrixRequestError, /queue folder is not available/);

  const request = ["--import", "tsx", join(ROOT, "scripts", "request-matrix.ts"), "--slug", SLUG, "--version", VERSION,
    "--inbox-root", join(skipped.root, "inbox"), "--queue-root", skipped.queueRoot];
  assert.match(execFileSync(process.execPath, request, { cwd: ROOT, encoding: "utf8" }), /Matrix requested/);
  assert.equal(sha256(skipped.target), skipped.digest);
  const again = execFileSync(process.execPath, request, { cwd: ROOT, encoding: "utf8" });
  assert.match(again, /already requested/);
});