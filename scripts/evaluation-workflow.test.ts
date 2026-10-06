import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import AdmZip from "adm-zip";
import {
  DEFAULT_TEST_TIMEOUT_MINUTES,
  TEST_TIMEOUT_ENV,
  containsDigest,
  confirmsArtifactMatch,
  extractVerdict,
  htmlToText,
  parseArgs,
  resolveSharepointRoot,
  resolveTestTimeoutMinutes,
  sha256,
  verifyShippedTests,
} from "./evaluation-workflow.js";

test("parseArgs reads named values", () => {
  assert.deepEqual(
    [...parseArgs(["--slug", "example-plugin", "--source", "output"]).entries()],
    [
      ["slug", "example-plugin"],
      ["source", "output"],
    ],
  );
  assert.throws(() => parseArgs(["--slug"]), /requires a value/);
  assert.throws(() => parseArgs(["example-plugin"]), /unexpected argument/);
});

test("htmlToText removes markup and decodes common entities", () => {
  assert.equal(
    htmlToText("<style>bad</style><h1>Ready &amp; reviewed</h1><p>Version&nbsp;1.2.3</p>"),
    "Ready & reviewed Version 1.2.3",
  );
});

test("extractVerdict normalizes supported Cowork verdicts", () => {
  assert.equal(extractVerdict("<p>Automated verdict: Ready</p>"), "Ready");
  assert.equal(extractVerdict("<p>Automated verdict — Blocked</p>"), "Blocked");
  assert.equal(extractVerdict("<p>Automated verdict: NO-SHIP</p>"), "No-ship");
  assert.equal(extractVerdict("<p>Automated verdict: STOP</p>"), "No-ship");
  assert.throws(() => extractVerdict("<p>Looks good</p>"), /must state/);
});

test("containsDigest tolerates formatting in rendered HTML text", () => {
  const digest = "ABCDEF0123456789";
  assert.equal(
    containsDigest("<p>SHA-256: ABCD EF01 2345 6789</p>", digest),
    true,
  );
});

test("confirmsArtifactMatch requires affirmative identity evidence", () => {
  const digest = "ABCDEF0123456789";
  assert.equal(
    confirmsArtifactMatch(
      "<p>SHA-256: ABCD EF01 2345 6789</p><p>SHA-256 check: MATCH</p>",
      digest,
    ),
    true,
  );
  assert.equal(
    confirmsArtifactMatch(
      "<p>Declared SHA-256: ABCDEF0123456789</p><p>Observed artifact does not match.</p>",
      digest,
    ),
    false,
  );
  assert.equal(
    confirmsArtifactMatch(
      "<p>SHA-256 check: MATCH</p><p>Policy: a future hash mismatch is a stop.</p>"
        + "<p>Artifact: ABCDEF0123456789</p>",
      digest,
    ),
    true,
  );
  assert.equal(
    confirmsArtifactMatch(
      "<p>Artifact SHA-256: ABCDEF0123456789 (re-verified 2026-10-01; 223,349 bytes)</p>",
      digest,
    ),
    true,
  );
});

test("sha256 hashes file bytes", () => {
  const dir = mkdtempSync(join(tmpdir(), "evaluation-workflow-"));
  try {
    const path = join(dir, "artifact.zip");
    writeFileSync(path, "artifact");
    assert.equal(
      sha256(path),
      "C7C5C1D70C5DEC4416AB6158AFD0B223EF40C29B1DC1F97ED9428B94D4CADB1C",
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("resolveSharepointRoot prefers flag, then env, then a link; refuses plain folders", () => {
  const dir = mkdtempSync(join(tmpdir(), "sharepoint-root-"));
  try {
    const library = join(dir, "library");
    mkdirSync(library);
    const linkPath = join(dir, "sharepoint");

    assert.deepEqual(resolveSharepointRoot({ flag: library, env: "ignored", linkPath }), {
      root: library,
      source: "flag",
    });
    assert.deepEqual(resolveSharepointRoot({ env: library, linkPath }), { root: library, source: "env" });
    assert.throws(() => resolveSharepointRoot({ env: join(dir, "nope"), linkPath }), /does not point to a folder/);

    assert.throws(() => resolveSharepointRoot({ env: "", linkPath }), /no SharePoint root configured/);

    mkdirSync(linkPath);
    assert.throws(() => resolveSharepointRoot({ env: "", linkPath }), /plain local folder/);
    rmSync(linkPath, { recursive: true });

    symlinkSync(library, linkPath, "junction");
    assert.deepEqual(resolveSharepointRoot({ env: "", linkPath }), { root: linkPath, source: "link" });

    rmSync(linkPath);
    rmSync(library, { recursive: true });
    symlinkSync(join(dir, "gone"), linkPath, "junction");
    assert.throws(() => resolveSharepointRoot({ env: "", linkPath }), /broken link/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("verifyShippedTests runs bundled tests from the extracted ZIP", () => {
  const dir = mkdtempSync(join(tmpdir(), "verify-shipped-"));
  try {
    const bundle = (name: string, runner: string) => {
      const zip = new AdmZip();
      zip.addFile("demo-plugin/tests/run_tests.py", Buffer.from(runner));
      const path = join(dir, name);
      zip.writeZip(path);
      return path;
    };
    verifyShippedTests(
      bundle("ok.zip", "print('1/1 checks passed')\n"),
      "demo-plugin",
    );
    assert.throws(
      () => verifyShippedTests(bundle("bad.zip", "open('metadata.json').read()\n"), "demo-plugin"),
      /fails when run from the built ZIP.*metadata\.json/,
    );
    assert.throws(
      () =>
        verifyShippedTests(
          bundle("slow.zip", "import time\nprint('starting', flush=True)\ntime.sleep(60)\n"),
          "demo-plugin",
          { timeoutMinutes: 0.05 },
        ),
      (error: Error) =>
        /tests\/run_tests\.py did not finish within the 0\.05-minute test timeout/.test(error.message) &&
        /--test-timeout-minutes/.test(error.message),
    );
    assert.throws(
      () => verifyShippedTests(bundle("ok2.zip", "pass\n"), "demo-plugin", { timeoutMinutes: 0 }),
      /positive number/,
    );
    const empty = new AdmZip();
    empty.addFile("demo-plugin/README.md", Buffer.from("x"));
    empty.writeZip(join(dir, "none.zip"));
    verifyShippedTests(join(dir, "none.zip"), "demo-plugin");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("resolveTestTimeoutMinutes prefers the flag, then the env var, then 30; rejects non-positive", () => {
  assert.equal(resolveTestTimeoutMinutes({ env: "" }), DEFAULT_TEST_TIMEOUT_MINUTES);
  assert.equal(DEFAULT_TEST_TIMEOUT_MINUTES, 30);
  assert.equal(resolveTestTimeoutMinutes({ env: "45" }), 45);
  assert.equal(resolveTestTimeoutMinutes({ flag: "12.5", env: "45" }), 12.5);
  assert.throws(() => resolveTestTimeoutMinutes({ flag: "0" }), /--test-timeout-minutes must be a positive/);
  assert.throws(() => resolveTestTimeoutMinutes({ flag: "-5" }), /positive/);
  assert.throws(() => resolveTestTimeoutMinutes({ flag: "abc" }), /positive/);
  assert.throws(
    () => resolveTestTimeoutMinutes({ env: "Infinity" }),
    new RegExp(`${TEST_TIMEOUT_ENV} must be a positive`),
  );
});
