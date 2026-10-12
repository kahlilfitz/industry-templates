import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import test from "node:test";
import AdmZip from "adm-zip";
import { buildTestDataZip, sha256 } from "./evaluation-workflow.js";
import {
  FROZEN_MANIFEST,
  checkTestData,
  computeFrozenManifest,
  verifyFrozenManifest,
  writeFrozenManifest,
} from "./test-data.js";
import { makeMos3Submission, write } from "./test-fixtures.js";

/** A repo-shaped root with one MOS3 submission at 1.2.3 and a complete test-data folder for it. */
function withRepo(fn: (root: string, versionDir: string) => void): void {
  const root = mkdtempSync(join(tmpdir(), "test-data-"));
  try {
    makeMos3Submission(root);
    const versionDir = join(root, "test-data", "professional-services", "demo-plugin", "1.2.3");
    write(join(versionDir, "README.md"), "# Demo plugin test data\n");
    write(join(versionDir, "demo-data", "scenario-a", "input.json"), "{}\n");
    write(join(versionDir, "tests", "run_tests.py"), "print('1/1 checks passed')\n");
    write(join(versionDir, "tests", "sample-test-prompts.csv"), "prompt\n");
    fn(root, versionDir);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("checkTestData accepts a complete current-version folder", () => {
  withRepo((root) => {
    const report = checkTestData(root);
    assert.deepEqual(report.errors, []);
    assert.deepEqual(report.warnings, []);
    assert.deepEqual(report.checked, ["  demo-plugin 1.2.3"]);
  });
});

test("checkTestData requires the current version folder, its runner, demo data and README", () => {
  withRepo((root, versionDir) => {
    rmSync(join(versionDir, "tests", "run_tests.py"));
    rmSync(join(versionDir, "README.md"));
    rmSync(join(versionDir, "demo-data"), { recursive: true });
    write(join(versionDir, "notes.txt"), "x");
    const errors = checkTestData(root).errors.join("\n");
    assert.match(errors, /tests\\ has no runner \(run_tests\.py or test_engines\.py\)/);
    assert.match(errors, /1\.2\.3\\README\.md is missing/);
    assert.match(errors, /demo-data\\ is missing/);
    assert.match(errors, /notes\.txt is not expected/);

    rmSync(versionDir, { recursive: true });
    assert.match(
      checkTestData(root).errors.join("\n"),
      /test-data\\professional-services\\demo-plugin\\1\.2\.3\\ is missing; a MOS3 submission keeps/,
    );
  });
});

test("test_engines.py is an accepted runner", () => {
  withRepo((root, versionDir) => {
    rmSync(join(versionDir, "tests", "run_tests.py"));
    write(join(versionDir, "tests", "test_engines.py"), "pass\n");
    assert.deepEqual(checkTestData(root).errors, []);
  });
});

test("frozen folders must match FROZEN.sha256 exactly: changed, extra and missing files fail", () => {
  withRepo((root, versionDir) => {
    const frozen = writeFrozenManifest(versionDir);
    assert.equal(basename(frozen), FROZEN_MANIFEST);
    const lines = readFileSync(frozen, "utf8").trimEnd().split("\n");
    assert.deepEqual(
      lines.map((line) => line.slice(66)),
      ["README.md", "demo-data/scenario-a/input.json", "tests/run_tests.py", "tests/sample-test-prompts.csv"],
    );
    assert.ok(lines.every((line) => /^[0-9a-f]{64} {2}\S/.test(line)));
    assert.deepEqual(checkTestData(root).errors, []);

    // Build litter is not content: running a suite in place must not break the freeze.
    write(join(versionDir, "tests", "__pycache__", "x.cpython-312.pyc"), "litter");
    assert.deepEqual(verifyFrozenManifest(versionDir), []);

    writeFileSync(join(versionDir, "demo-data", "scenario-a", "input.json"), '{"changed": true}\n');
    write(join(versionDir, "tests", "helper.py"), "pass\n");
    rmSync(join(versionDir, "tests", "sample-test-prompts.csv"));
    const errors = checkTestData(root).errors.join("\n");
    assert.match(errors, /is frozen but demo-data\/scenario-a\/input\.json has changed since it was frozen/);
    assert.match(errors, /is frozen but tests\/helper\.py was added after the folder was frozen/);
    assert.match(errors, /is frozen but tests\/sample-test-prompts\.csv is listed but missing/);
  });
});

test("a reordered FROZEN.sha256 is rejected as non-canonical", () => {
  withRepo((_root, versionDir) => {
    const expected = computeFrozenManifest(versionDir);
    writeFileSync(join(versionDir, FROZEN_MANIFEST), expected.split("\n").filter(Boolean).reverse().join("\n") + "\n");
    assert.deepEqual(verifyFrozenManifest(versionDir), [`${FROZEN_MANIFEST} is not in canonical sorted form; regenerate it`]);
  });
});

test("older unfrozen versions warn; orphaned test data fails", () => {
  withRepo((root) => {
    const older = join(root, "test-data", "professional-services", "demo-plugin", "1.2.2");
    write(join(older, "README.md"), "old\n");
    const report = checkTestData(root);
    assert.deepEqual(report.errors, []);
    assert.match(report.warnings.join("\n"), /demo-plugin\\1\.2\.2\\ is not the current version and has no FROZEN\.sha256/);

    write(join(root, "test-data", "professional-services", "gone-plugin", "1.0.0", "README.md"), "x");
    write(join(root, "test-data", "manufacturing", "demo-plugin", "1.2.3", "README.md"), "x");
    const errors = checkTestData(root).errors.join("\n");
    assert.match(errors, /gone-plugin: test-data\\professional-services\\gone-plugin\\ has no submission/);
    assert.match(errors, /demo-plugin: test-data\\manufacturing\\demo-plugin\\ has no submission; the plugin is filed under submissions\\professional-services\\/);
  });
});

test("buildTestDataZip writes a root-level, reproducible ZIP without litter or FROZEN.sha256", () => {
  withRepo((root, versionDir) => {
    write(join(versionDir, "tests", "__pycache__", "x.cpython-312.pyc"), "litter");
    writeFrozenManifest(versionDir);
    const outDir = join(root, "out");
    const zipPath = buildTestDataZip("demo-plugin", "1.2.3", { root, outDir });
    assert.equal(zipPath, join(outDir, "demo-plugin-test-data-1.2.3.zip"));
    const entries = new AdmZip(zipPath).getEntries();
    assert.deepEqual(
      entries.map((e) => e.entryName).sort(),
      ["README.md", "demo-data/scenario-a/input.json", "tests/run_tests.py", "tests/sample-test-prompts.csv"],
    );
    assert.equal(new Set(entries.map((e) => e.header.time.getTime())).size, 1);
    assert.ok(entries.every((e) => [0, 8].includes(e.header.method)));
    const digest = sha256(zipPath);
    rmSync(zipPath);
    assert.equal(sha256(buildTestDataZip("demo-plugin", "1.2.3", { root, outDir })), digest);

    assert.throws(() => buildTestDataZip("demo-plugin", "9.9.9", { root, outDir }), /no test data for demo-plugin 9\.9\.9/);
    rmSync(join(versionDir, "tests", "run_tests.py"));
    assert.throws(() => buildTestDataZip("demo-plugin", "1.2.3", { root, outDir }), /is incomplete: tests\\ has no runner/);
    assert.equal(existsSync(join(root, "public")), false, "explicit outDir is honoured");
  });
});
