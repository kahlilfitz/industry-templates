import assert from "node:assert/strict";
import test from "node:test";
import {
  copilotArgs,
  isActionable,
  nextPatchVersion,
  normalizeSeverity,
  parseRecommendations,
  renderBacklogSection,
  renderFixBrief,
} from "./recommendations.js";

const REPORT = `
<h1>Recommendations: demo-plugin 1.0.6</h1>
<p>SHA-256 check: MATCH</p><p>Automated verdict: No-ship</p>
<table><tr><th>Bar</th><th>Result</th></tr><tr><td>Health</td><td>Pass</td></tr></table>
<table>
  <thead><tr><th>ID</th><th>Severity</th><th>Skill or file</th><th>Evidence</th><th>Suggested change</th></tr></thead>
  <tbody>
    <tr><td>R1</td><td><b>Blocker</b></td><td>skills/draft/SKILL.md</td><td>Behavioral GR-3: leaked a name</td><td>Redact names &amp; IDs</td></tr>
    <tr><td>R2</td><td>required</td><td>skills/route</td><td>Health: trigger 2/3</td><td>Add 3 quoted triggers</td></tr>
    <tr><td>R3</td><td>Advisory</td><td>README</td><td>Output 3.6/5</td><td>Tighten tone</td></tr>
  </tbody>
</table>`;

test("parseRecommendations reads the suggested-fixes table and skips other tables", () => {
  const fixes = parseRecommendations(REPORT);
  assert.deepEqual(
    fixes.map((fix) => [fix.id, fix.severity, fix.target]),
    [
      ["R1", "blocker", "skills/draft/SKILL.md"],
      ["R2", "required", "skills/route"],
      ["R3", "advisory", "README"],
    ],
  );
  assert.equal(fixes[0].change, "Redact names & IDs");
  assert.equal(fixes[0].evidence, "Behavioral GR-3: leaked a name");
  assert.deepEqual(fixes.filter(isActionable).map((fix) => fix.id), ["R1", "R2"]);
});

test("parseRecommendations accepts a nothing-to-fix row and refuses a report with no fixes table", () => {
  const empty =
    "<table><tr><th>ID</th><th>Severity</th><th>Skill or file</th><th>Evidence</th><th>Suggested change</th></tr>" +
    "<tr><td colspan=5>Nothing to fix</td></tr></table>";
  assert.deepEqual(parseRecommendations(empty), []);
  assert.throws(() => parseRecommendations("<p>No table</p>"), /no suggested-fixes table/);
});

test("normalizeSeverity maps the strategy's wording", () => {
  assert.equal(normalizeSeverity("Hard stop"), "blocker");
  assert.equal(normalizeSeverity("REQUIRED"), "required");
  assert.equal(normalizeSeverity("advisory (nice to have)"), "advisory");
  assert.equal(normalizeSeverity("n/a"), undefined);
});

test("nextPatchVersion bumps the last number", () => {
  assert.equal(nextPatchVersion("1.0.6"), "1.0.7");
  assert.equal(nextPatchVersion("1.1.9"), "1.1.10");
  assert.throws(() => nextPatchVersion("1.0-beta"), /does not end in a number/);
});

test("renderFixBrief lists only blocker and required fixes with the guardrails", () => {
  const fixes = parseRecommendations(REPORT);
  const brief = renderFixBrief({
    slug: "demo-plugin",
    displayName: "Demo",
    version: "1.0.6",
    nextVersion: "1.0.7",
    submissionDir: "submissions\\demo\\demo-plugin",
    verdict: "No-ship",
    reportPath: "C:\\reports\\recommendations.html",
    fixes,
    backlogPath: "submissions\\demo\\demo-plugin\\BACKLOG.md",
    advisoryCount: 1,
  });
  assert.match(brief, /### R1 \(blocker\): skills\/draft\/SKILL\.md/);
  assert.match(brief, /### R2 \(required\)/);
  assert.doesNotMatch(brief, /### R3/);
  assert.match(brief, /Set the version to 1\.0\.7/);
  assert.match(brief, /Do not invoke skills/);
  assert.match(brief, /Do not push/);
  assert.match(brief, /listing-metadata\.md/);
  assert.doesNotMatch(brief, /Do not run the plugin's own test suites/);
  assert.match(brief, /Run the plugin's regression suite before applying any fix and again after/);
  assert.match(brief, /tests\\README\.md/);
  assert.match(brief, /Every check that passed before must still pass afterwards/);
  assert.match(brief, /Never relax, delete or change the expected result of an existing check/);
  assert.match(brief, /Do not edit the plugin's tests\\ or demo-data\\ folders unless a fix cannot be applied without it/);
  assert.match(brief, /npm run test:evaluation/);
  assert.match(brief, /git commit -m "demo-plugin 1\.0\.7: apply Cowork recommendations" -- <paths>/);
});

test("renderBacklogSection records only advisory items under the run label", () => {
  const section = renderBacklogSection("evaluate-demo-plugin-v1.0.6-2026-10-15", "1.0.6", parseRecommendations(REPORT));
  assert.match(section, /^## 1\.0\.6 evaluation \(evaluate-demo-plugin-v1\.0\.6-2026-10-15\)/);
  assert.match(section, /- \[ \] \*\*R3\*\* \(README\): Tighten tone/);
  assert.doesNotMatch(section, /R1|R2/);
});

test("copilotArgs runs non-interactively and denies git push", () => {
  const args = copilotArgs("C:\\inbox\\fix-brief.md", "claude-opus-5.5");
  assert.equal(args[0], "-p");
  assert.match(args[1], /C:\\inbox\\fix-brief\.md/);
  assert.ok(args.includes("--no-ask-user"));
  assert.ok(args.includes("--deny-tool=shell(git push)"));
  assert.deepEqual(args.slice(-2), ["--model", "claude-opus-5.5"]);
  assert.ok(!copilotArgs("x").includes("--model"));
});
