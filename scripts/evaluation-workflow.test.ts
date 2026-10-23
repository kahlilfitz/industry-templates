import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  containsDigest,
  confirmsArtifactMatch,
  defaultQueueRoot,
  EVAL_QUEUE_STAGES,
  evaluationArchiveDir,
  extractVerdict,
  findEvaluatedQueueRuns,
  findQueueAttention,
  findReports,
  findSubmission,
  htmlToText,
  parseArgs,
  pluginFolderName,
  queuePairNames,
  queuePrompt,
  REQUIRED_REPORTS,
  resolveSharepointRoot,
  sha256,
  sharepointPluginDir,
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
  assert.equal(extractVerdict("<p>Automated verdict: Ready for human review</p>"), "Ready");
  assert.equal(extractVerdict("<p>Automated verdict: Ready</p>"), "Ready");
  assert.equal(extractVerdict("<p>Automated verdict — Blocked</p>"), "Blocked");
  assert.equal(extractVerdict("<p>Automated verdict: NO-SHIP</p>"), "No-ship");
  assert.equal(extractVerdict("<p>Automated verdict: STOP</p>"), "No-ship");
  assert.throws(() => extractVerdict("<p>Looks good</p>"), /must state/);
});

test("extractVerdict reads the new phrase whole and never as a bare Ready", () => {
  assert.equal(
    extractVerdict("<h2>Automated verdict</h2><p><strong>READY FOR HUMAN REVIEW</strong> — not a publish signal</p>"),
    "Ready",
  );
  assert.equal(extractVerdict("<p>Automated verdict: Ready-for-human-review</p>"), "Ready");
  // A different "Ready for ..." phrase is not silently accepted as the legacy bare Ready.
  assert.throws(
    () => extractVerdict("<p>Automated verdict: Ready for publication</p>"),
    /must state an automated verdict of Ready, Blocked, or No-ship/,
  );
  // The first stated verdict wins, and words after the phrase do not change it.
  assert.equal(
    extractVerdict("<p>Automated verdict: Ready for human review. Blocked items: none.</p><p>Automated verdict: No-ship</p>"),
    "Ready",
  );
  assert.equal(extractVerdict("<p>Automated verdict: Blocked</p><p>Automated verdict: Ready</p>"), "Blocked");
});

test("verdictGuidance never treats Ready as a publish signal", () => {
  assert.deepEqual(verdictGuidance("Ready"), [
    "Next: the owner records a Publish decision in the deployment doc; only then promote this exact ZIP. " +
      "Ready is not a publish signal.",
  ]);
  assert.match(verdictGuidance("No-ship")[0], /^Do not publish this artifact/);
  const blocked = verdictGuidance("Blocked").join(" ");
  assert.match(blocked, /^Do not publish this artifact/);
  assert.match(blocked, /raise it with the owner before remediating/);
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
  // A report that states two SHA checks fails closed on a mismatch in either.
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

test("Professional Services Wave 1 archives use the Retail library layout; other plugins keep theirs", () => {
  const root = join("C:", "library");
  assert.equal(pluginFolderName("time-expense-narrative-compliance"), "Time Expense Narrative Compliance");
  assert.equal(
    sharepointPluginDir(root, "Professional Services", "time-expense-narrative-compliance"),
    join(root, "Professional Services", "Wave 1", "Time Expense Narrative Compliance"),
  );
  assert.equal(
    evaluationArchiveDir(root, "Professional Services", "deliverable-review-quality-gate", "1.0.8"),
    join(root, "Professional Services", "Wave 1", "Deliverable Review Quality Gate", "Evaluation", "v1.0.8"),
  );
  assert.equal(
    evaluationArchiveDir(root, "Professional Services", "client-status-qbr", "1.0.0"),
    join(root, "Professional Services", "Wave 2", "Client Status QBR", "Evaluation", "v1.0.0"),
  );
  assert.equal(
    evaluationArchiveDir(root, "Healthcare", "time-expense-narrative-compliance", "1.0.0"),
    join(root, "Healthcare", "time-expense-narrative-compliance", "Evaluation", "1.0.0"),
  );
});

test("Professional Services Wave 2 plugins use the Retail layout under Wave 2; the unranked substitute does not", () => {
  const root = join("C:", "library");
  assert.equal(pluginFolderName("sow-drafting-scoping-notes"), "SOW Drafting Scoping Notes");
  assert.equal(pluginFolderName("client-status-qbr"), "Client Status QBR");
  for (const [slug, folder] of [
    ["client-status-qbr", "Client Status QBR"],
    ["sow-drafting-scoping-notes", "SOW Drafting Scoping Notes"],
    ["credential-case-study-assembly", "Credential Case Study Assembly"],
    ["engagement-financial-health-brief", "Engagement Financial Health Brief"],
    ["conflicts-independence-precheck", "Conflicts Independence Precheck"],
  ]) {
    assert.equal(
      sharepointPluginDir(root, "Professional Services", slug),
      join(root, "Professional Services", "Wave 2", folder),
    );
  }
  assert.equal(
    evaluationArchiveDir(root, "Professional Services", "change-order-scope-control", "1.0.0"),
    join(root, "Professional Services", "change-order-scope-control", "Evaluation", "1.0.0"),
  );
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
    assert.match(text, /Cowork's built-in plugin evaluation/);
    assert.match(text, /SHA-256 check: MATCH/);
    assert.match(text, /Automated verdict:/);
    assert.match(text, /exactly one of: Ready, Blocked, or No-ship/);
    // The fix step parses this table (scripts/recommendations.ts).
    assert.match(text, /ID \| Severity \| Skill or file \| Evidence \| Suggested change/);
    assert.match(text, /blocker, required, advisory/);
    assert.match(text, /only from plugin-health\.html and behavioral-test-report\.html/);
    assert.match(text, /not a publish signal/);
    // The verdict relies only on Cowork's own evaluation.
    assert.doesNotMatch(text, /run_tests|test_engines|--plugin-root|test-data/i);
  }
  const expected = ["{{DISPLAY_NAME}}", "{{RUN_LABEL}}", "{{SHA256}}", "{{SLUG}}", "{{VERSION}}"];
  assert.deepEqual(placeholders(claude), expected);
  assert.deepEqual(placeholders(mos3), expected);
  assert.match(mos3, /MOS3 Microsoft 365 app package \(manifest schema\s+devPreview, with packageName\)/);
  assert.match(claude, /\.claude-plugin\/plugin\.json/);
});

test("the Cowork queue uses the ledger's pair names under the OneDrive queue folder", () => {
  assert.deepEqual(queuePairNames("demo-plugin", "1.2.3"), {
    zip: "demo-plugin-v1.2.3.zip",
    prompt: "demo-plugin-v1.2.3-prompt.md",
  });
  assert.equal(defaultQueueRoot({ OneDriveCommercial: join("C:", "od") }), join("C:", "od", "Cowork Plugin Evals"));
  assert.equal(defaultQueueRoot({ OneDrive: join("C:", "personal") }), join("C:", "personal", "Cowork Plugin Evals"));
  assert.equal(defaultQueueRoot({}), undefined);
  assert.deepEqual(Object.values(EVAL_QUEUE_STAGES), [
    "1 - To evaluate",
    "2 - In progress",
    "3 - Evaluated",
    "4 - Needs attention",
  ]);
});

test("queuePrompt names the queued ZIP and keeps the rendered prompt unchanged below it", () => {
  const prompt = "Evaluate the attached plugin.\n1. Compute the SHA-256 of demo-plugin.zip.\n";
  const queued = queuePrompt(prompt, "demo-plugin", "1.2.3");
  assert.ok(queued.endsWith(prompt));
  assert.match(queued, /`demo-plugin-v1\.2\.3\.zip`/);
  assert.match(queued, /says `demo-plugin\.zip` or "the attached plugin", it means `demo-plugin-v1\.2\.3\.zip`/);
  assert.match(queued, /Keep the three report filenames exactly as named below/);
});

test("findReports prefers exact names, accepts timestamped names and needs all three non-empty", () => {
  const dir = mkdtempSync(join(tmpdir(), "queue-reports-"));
  try {
    assert.equal(findReports(join(dir, "missing")), undefined);
    writeFileSync(join(dir, "plugin-health.html"), "a");
    writeFileSync(join(dir, "behavioral-test-report-2026-10-16-1230.html"), "b");
    assert.equal(findReports(dir), undefined);
    writeFileSync(join(dir, "recommendations-2026-10-16-1230.html"), "");
    assert.equal(findReports(dir), undefined, "an empty report does not count");
    writeFileSync(join(dir, "recommendations-2026-10-16-1230.html"), "c");
    writeFileSync(join(dir, "recommendations-2026-10-16-1100.html"), "old");
    utimesSync(join(dir, "recommendations-2026-10-16-1100.html"), new Date(2026, 0, 1), new Date(2026, 0, 1));
    const found = findReports(dir);
    assert.deepEqual([...(found?.keys() ?? [])], [...REQUIRED_REPORTS]);
    assert.equal(found?.get("plugin-health.html"), join(dir, "plugin-health.html"));
    assert.equal(found?.get("behavioral-test-report.html"), join(dir, "behavioral-test-report-2026-10-16-1230.html"));
    assert.equal(found?.get("recommendations.html"), join(dir, "recommendations-2026-10-16-1230.html"));
    writeFileSync(join(dir, "recommendations.html"), "exact");
    utimesSync(join(dir, "recommendations.html"), new Date(2026, 0, 1), new Date(2026, 0, 1));
    assert.equal(findReports(dir)?.get("recommendations.html"), join(dir, "recommendations.html"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("queue runs and needs-attention entries match by version and the prepared ZIP's digest", () => {
  const root = mkdtempSync(join(tmpdir(), "queue-root-"));
  try {
    const { zip, prompt } = queuePairNames("demo-plugin", "1.2.3");
    const evaluated = join(root, EVAL_QUEUE_STAGES.evaluated, "demo-plugin");
    const match = join(evaluated, "v1.2.3 - 2026-10-16-1230");
    const otherZip = join(evaluated, "v1.2.3 - 2026-10-16-0900");
    const otherVersion = join(evaluated, "v1.2.30 - 2026-10-16-1230");
    for (const dir of [match, otherZip, otherVersion]) mkdirSync(dir, { recursive: true });
    writeFileSync(join(match, zip), "candidate");
    writeFileSync(join(otherZip, zip), "earlier candidate");
    writeFileSync(join(otherVersion, "demo-plugin-v1.2.30.zip"), "candidate");
    const digest = sha256(join(match, zip));

    assert.deepEqual(findEvaluatedQueueRuns(root, "demo-plugin", "1.2.3", digest), [match]);
    assert.deepEqual(findEvaluatedQueueRuns(join(root, "nope"), "demo-plugin", "1.2.3", digest), []);

    const attention = join(root, EVAL_QUEUE_STAGES.needsAttention);
    mkdirSync(attention);
    assert.deepEqual(findQueueAttention(root, "demo-plugin", "1.2.3", digest), []);
    writeFileSync(join(attention, zip), "earlier candidate");
    assert.deepEqual(findQueueAttention(root, "demo-plugin", "1.2.3", digest), [], "another candidate's ZIP is ignored");
    writeFileSync(join(attention, zip), "candidate");
    writeFileSync(join(attention, prompt), "prompt");
    writeFileSync(join(attention, "demo-plugin-v1.2.3-note.md"), "SHA-256 mismatch");
    writeFileSync(join(attention, "other-plugin-v1.2.3.zip"), "candidate");
    assert.deepEqual(findQueueAttention(root, "demo-plugin", "1.2.3", digest).sort(), [
      join(attention, "demo-plugin-v1.2.3-note.md"),
      join(attention, prompt),
      join(attention, zip),
    ].sort());
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("needs-attention entries for a longer version are not matched", () => {
  const root = mkdtempSync(join(tmpdir(), "queue-attention-"));
  try {
    const attention = join(root, EVAL_QUEUE_STAGES.needsAttention);
    mkdirSync(attention, { recursive: true });
    writeFileSync(join(attention, "demo-plugin-v1.0.13-note.md"), "note");
    writeFileSync(join(attention, "demo-plugin-v1.0.1.2-note.md"), "note");
    assert.deepEqual(findQueueAttention(root, "demo-plugin", "1.0.1", "ANY"), []);
    writeFileSync(join(attention, "demo-plugin-v1.0.1-note.md"), "note");
    writeFileSync(join(attention, "demo-plugin-v1.0.1 - 2026-10-16-1230"), "note");
    assert.deepEqual(findQueueAttention(root, "demo-plugin", "1.0.1", "ANY").sort(), [
      join(attention, "demo-plugin-v1.0.1 - 2026-10-16-1230"),
      join(attention, "demo-plugin-v1.0.1-note.md"),
    ].sort());
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
