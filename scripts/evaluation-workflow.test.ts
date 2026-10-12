import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
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
  findSubmission,
  htmlToText,
  parseArgs,
  resolveSharepointRoot,
  resolveTestTimeoutMinutes,
  sha256,
  verdictGuidance,
  verifyShippedTests,
} from "./evaluation-workflow.js";
import { buildMos3Zip } from "./mos3-package.js";
import { makeMos3Submission } from "./test-fixtures.js";

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

test("parseArgs reads declared boolean flags without a value", () => {
  assert.deepEqual(
    [...parseArgs(["--skip-atk", "--slug", "example-plugin"], new Set(["skip-atk"])).entries()],
    [
      ["skip-atk", "true"],
      ["slug", "example-plugin"],
    ],
  );
  assert.throws(() => parseArgs(["--skip-atk"]), /requires a value/);
});

test("htmlToText removes markup and decodes common entities", () => {
  assert.equal(
    htmlToText("<style>bad</style><h1>Ready &amp; reviewed</h1><p>Version&nbsp;1.2.3</p>"),
    "Ready & reviewed Version 1.2.3",
  );
});

test("extractVerdict normalizes supported Cowork verdicts", () => {
  assert.equal(extractVerdict("<p>Automated verdict: Ready for human review</p>"), "Ready for human review");
  assert.equal(extractVerdict("<p>Automated verdict: Ready</p>"), "Ready for human review");
  assert.equal(extractVerdict("<p>Automated verdict — Blocked</p>"), "Blocked");
  assert.equal(extractVerdict("<p>Automated verdict: NO-SHIP</p>"), "No-ship");
  assert.equal(extractVerdict("<p>Automated verdict: STOP</p>"), "No-ship");
  assert.throws(() => extractVerdict("<p>Looks good</p>"), /must state/);
});

test("extractVerdict reads the new phrase whole and never as a bare Ready", () => {
  assert.equal(
    extractVerdict("<h2>Automated verdict</h2><p><strong>READY FOR HUMAN REVIEW</strong> — not a publish signal</p>"),
    "Ready for human review",
  );
  assert.equal(extractVerdict("<p>Automated verdict: Ready-for-human-review</p>"), "Ready for human review");
  // A different "Ready for ..." phrase is not silently accepted as the legacy bare Ready.
  assert.throws(
    () => extractVerdict("<p>Automated verdict: Ready for publication</p>"),
    /must state an automated verdict of Ready for human review, Blocked, or No-ship/,
  );
  // The first stated verdict wins, and words after the phrase do not change it.
  assert.equal(
    extractVerdict("<p>Automated verdict: Ready for human review. Blocked items: none.</p><p>Automated verdict: No-ship</p>"),
    "Ready for human review",
  );
  assert.equal(extractVerdict("<p>Automated verdict: Blocked</p><p>Automated verdict: Ready</p>"), "Blocked");
});

test("verdictGuidance never treats Ready for human review as a publish signal", () => {
  assert.deepEqual(verdictGuidance("Ready for human review"), [
    "Next: two independent reviewers install this exact ZIP and complete the tracker tab; " +
      "publication still needs the Publish gate and the owner decision.",
  ]);
  assert.match(verdictGuidance("No-ship")[0], /^Do not publish this artifact/);
  const blocked = verdictGuidance("Blocked").join(" ");
  assert.match(blocked, /^Do not publish this artifact/);
  assert.match(blocked, /Missing human-review evidence alone should not produce Blocked under the current prompt/);
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
  // MOS3 reports state a plugin check and a test-data check; a mismatch on either fails closed.
  assert.equal(
    confirmsArtifactMatch(
      "<p>Plugin SHA-256: ABCDEF0123456789</p><p>Plugin SHA-256 check: MISMATCH</p>"
        + "<p>Test-data SHA-256 check: MATCH</p>",
      digest,
    ),
    false,
  );
  assert.equal(
    confirmsArtifactMatch(
      "<p>Plugin SHA-256: ABCDEF0123456789</p><p>Plugin SHA-256 check: MATCH</p>"
        + "<p>Test-data SHA-256 check: MATCH</p>",
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

test("verifyShippedTests runs a MOS3 candidate's regression from the test-data ZIP against the plugin ZIP", () => {
  const dir = mkdtempSync(join(tmpdir(), "verify-mos3-"));
  try {
    const pluginZip = join(dir, "demo-plugin.zip");
    buildMos3Zip(makeMos3Submission(join(dir, "repo")), pluginZip, new Date("2026-01-01T00:00:00Z"));
    const testData = (name: string, files: Record<string, string>) => {
      const zip = new AdmZip();
      for (const [entry, content] of Object.entries(files)) zip.addFile(entry, Buffer.from(content));
      const path = join(dir, name);
      zip.writeZip(path);
      return path;
    };
    // The runner contract: --plugin-root names the extracted plugin, PLUGIN_ROOT matches it,
    // and the working directory is the extracted test-data folder (the data root).
    const runner = [
      "import os, sys",
      "args = sys.argv[1:]",
      "assert args[0] == '--plugin-root', args",
      "root = args[1]",
      "assert os.environ['PLUGIN_ROOT'] == root",
      "assert os.path.basename(root) == 'plugin'",
      "assert os.path.isfile(os.path.join(root, 'manifest.json'))",
      "assert os.path.isfile(os.path.join(root, 'skills', 'alpha-skill', 'SKILL.md'))",
      "assert not os.path.exists(os.path.join(root, 'tests'))",
      "assert os.path.isfile('README.md') and os.path.isdir('demo-data')",
      "assert os.path.basename(os.getcwd()) == 'test-data'",
      "print('1/1 checks passed')",
      "",
    ].join("\n");
    verifyShippedTests(pluginZip, "demo-plugin", {
      testDataZip: testData("good.zip", {
        "README.md": "x",
        "demo-data/input.json": "{}",
        "tests/run_tests.py": runner,
        "tests/check_shared_copies.py": runner,
      }),
    });
    assert.throws(
      () =>
        verifyShippedTests(pluginZip, "demo-plugin", {
          testDataZip: testData("bad.zip", { "tests/test_engines.py": "raise SystemExit(1)\n" }),
        }),
      /shipped tests\/test_engines\.py fails when run from the test-data ZIP against the built plugin ZIP/,
    );
    assert.throws(
      () =>
        verifyShippedTests(pluginZip, "demo-plugin", {
          testDataZip: testData("norunner.zip", { "README.md": "x", "tests/check_shared_copies.py": "pass\n" }),
        }),
      /has no tests\/run_tests\.py or tests\/test_engines\.py/,
    );
    assert.throws(
      () => verifyShippedTests(pluginZip, "demo-plugin", { testDataZip: join(dir, "missing.zip") }),
      /no test data for demo-plugin: .*missing\.zip does not exist/,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("findSubmission reads a MOS3 version from manifest.json and requires it to match metadata", () => {
  const root = mkdtempSync(join(tmpdir(), "find-mos3-"));
  try {
    const dir = makeMos3Submission(root);
    const submission = findSubmission("demo-plugin", root);
    assert.equal(submission.version, "1.2.3");
    assert.equal(submission.packageFormat, "mos3");
    const manifestPath = join(dir, "manifest.json");
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as Record<string, unknown>;
    writeFileSync(manifestPath, JSON.stringify({ ...manifest, version: "1.2.4" }));
    assert.throws(() => findSubmission("demo-plugin", root), /version mismatch: metadata 1\.2\.3, manifest\.json 1\.2\.4/);
    rmSync(manifestPath);
    assert.throws(() => findSubmission("demo-plugin", root), /MOS3 submission but has no manifest\.json/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("both Cowork prompt templates require the three verdicts and the pending human-review section", () => {
  const read = (name: string) => readFileSync(join(import.meta.dirname, "..", "docs", "evaluation", name), "utf8");
  const placeholders = (text: string) => [...new Set(text.match(/\{\{[A-Z0-9_]+\}\}/g))].sort();
  const claude = read("cowork-evaluation-prompt.txt");
  const mos3 = read("cowork-evaluation-prompt-mos3.txt");
  for (const text of [claude, mos3]) {
    assert.match(text, /exactly one of: Ready for human review, Blocked, or No-ship/);
    assert.match(text, /a "Pending human-review evidence" section/);
    assert.match(text, /never a publish signal/);
    assert.match(text, /publication remains pending until two independent human reviewers/);
    assert.match(text, /--list-groups/);
    assert.doesNotMatch(text, /one of: Ready, Blocked/);
  }
  assert.deepEqual(placeholders(claude), ["{{DISPLAY_NAME}}", "{{RUN_LABEL}}", "{{SHA256}}", "{{SLUG}}", "{{VERSION}}"]);
  assert.deepEqual(placeholders(mos3), [
    "{{DISPLAY_NAME}}",
    "{{RUN_LABEL}}",
    "{{SHA256}}",
    "{{SLUG}}",
    "{{TEST_DATA_FILE}}",
    "{{TEST_DATA_SHA256}}",
    "{{VERSION}}",
  ]);
  assert.match(mos3, /MOS3 Microsoft 365 app package \(manifest schema 1\.28\)/);
  assert.match(mos3, /Plugin SHA-256 check: MATCH/);
  assert.match(mos3, /Test-data SHA-256 check: MATCH/);
  assert.match(mos3, /--plugin-root <extracted plugin folder>/);
  assert.match(mos3, /tool description validation: N\/A when the package declares no agentConnectors/);
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
