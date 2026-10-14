import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  assertShippedRegression,
  containsDigest,
  confirmsArtifactMatch,
  extractVerdict,
  findSubmission,
  htmlToText,
  parseArgs,
  REQUIRED_REPORTS,
  resolveSharepointRoot,
  sha256,
  verdictGuidance,
} from "./evaluation-workflow.js";
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

test("assertShippedRegression refuses a MOS3 version with no regression runner, without running it", () => {
  const dir = mkdtempSync(join(tmpdir(), "shipped-regression-"));
  try {
    mkdirSync(join(dir, "tests"));
    writeFileSync(join(dir, "tests", "check_shared_copies.py"), "raise SystemExit(1)\n");
    assert.throws(() => assertShippedRegression(dir, "demo-plugin"), /has no tests\/run_tests\.py or tests\/test_engines\.py/);
    // A failing runner is not executed: preparation only checks it ships.
    writeFileSync(join(dir, "tests", "test_engines.py"), "raise SystemExit(1)\n");
    assertShippedRegression(dir, "demo-plugin");
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

test("both Cowork prompt templates request the two Cowork reports plus recommendations.html, verdict there", () => {
  const read = (name: string) => readFileSync(join(import.meta.dirname, "..", "docs", "evaluation", name), "utf8");
  const placeholders = (text: string) => [...new Set(text.match(/\{\{[A-Z0-9_]+\}\}/g))].sort();
  const claude = read("cowork-evaluation-prompt.txt");
  const mos3 = read("cowork-evaluation-prompt-mos3.txt");
  assert.deepEqual(REQUIRED_REPORTS, ["plugin-health.html", "behavioral-test-report.html", "recommendations.html"]);
  for (const text of [claude, mos3]) {
    for (const report of REQUIRED_REPORTS) assert.match(text, new RegExp(report.replace(".", "\\.")));
    assert.doesNotMatch(text, /full-report\.html/);
    assert.match(text, /recommendations\.html must visibly state/);
    assert.match(text, /suggested fixes/);
    assert.match(text, /decided only from\s+plugin-health\.html and behavioral-test-report\.html/);
    assert.match(text, /exactly one of: Ready for human review, Blocked, or No-ship/);
    assert.match(text, /a "Pending human-review evidence" section/);
    assert.match(text, /never a\s+publish signal/);
    assert.match(text, /publication remains pending until two independent human reviewers/);
    // The verdict relies only on Cowork's own evaluation: no shipped regression, no test-data ZIP.
    assert.doesNotMatch(text, /run_tests|test_engines|--plugin-root|shipped regression|test-data ZIP/i);
    assert.doesNotMatch(text, /one of: Ready, Blocked/);
  }
  const expected = ["{{DISPLAY_NAME}}", "{{RUN_LABEL}}", "{{SHA256}}", "{{SLUG}}", "{{VERSION}}"];
  assert.deepEqual(placeholders(claude), expected);
  assert.deepEqual(placeholders(mos3), expected);
  assert.match(claude, /SHA-256 check: MATCH/);
  assert.match(mos3, /MOS3 Microsoft 365 app package \(manifest schema 1\.28\)/);
  assert.match(mos3, /Plugin SHA-256 check: MATCH/);
});
