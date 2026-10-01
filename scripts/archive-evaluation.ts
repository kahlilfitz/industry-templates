import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { basename, join } from "node:path";
import {
  DEFAULT_INBOX_ROOT,
  REQUIRED_REPORTS,
  ROOT,
  EvaluationRun,
  assertNonEmptyFile,
  confirmsArtifactMatch,
  extractVerdict,
  findSubmission,
  htmlToText,
  parseArgs,
  requiredArg,
  resolveInputPath,
  sha256,
} from "./evaluation-workflow.js";

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const slug = requiredArg(args, "slug");
  const source = resolveInputPath(requiredArg(args, "source"));
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const sharepointRoot = args.has("sharepoint-root")
    ? resolveInputPath(requiredArg(args, "sharepoint-root"))
    : process.env.INDUSTRY_TEMPLATES_SHAREPOINT_ROOT
      ? resolveInputPath(process.env.INDUSTRY_TEMPLATES_SHAREPOINT_ROOT)
      : join(ROOT, "sharepoint");
  const submission = findSubmission(slug);
  const version = args.get("version")?.trim() || submission.version;

  if (!existsSync(source)) {
    throw new Error(`Cowork output folder does not exist: ${source}`);
  }

  const runDir = join(inboxRoot, slug, version);
  const manifestPath = join(runDir, "evaluation-run.json");
  assertNonEmptyFile(manifestPath, "frozen evaluation-run.json");
  const runData = JSON.parse(readFileSync(manifestPath, "utf8")) as EvaluationRun;
  if (
    runData.schemaVersion !== 1 ||
    runData.slug !== slug ||
    runData.artifactVersion !== version
  ) {
    throw new Error("frozen evaluation manifest does not match the requested plugin and version");
  }
  if (runData.artifactFile !== `${slug}.zip`) {
    throw new Error(`frozen evaluation manifest has an unexpected artifact filename`);
  }
  if (runData.status !== "prepared") {
    throw new Error(`evaluation run is already ${runData.status}`);
  }

  const artifactPath = join(runDir, runData.artifactFile);
  assertNonEmptyFile(artifactPath, "frozen evaluated ZIP");
  const actualDigest = sha256(artifactPath);
  if (actualDigest !== runData.artifactSha256) {
    throw new Error("frozen evaluated ZIP no longer matches its recorded SHA-256");
  }

  for (const report of REQUIRED_REPORTS) {
    assertNonEmptyFile(join(source, report), report);
  }

  const fullReportPath = join(source, "full-report.html");
  const fullReport = readFileSync(fullReportPath, "utf8");
  const fullReportText = htmlToText(fullReport).toLowerCase();
  if (!fullReportText.includes(slug.toLowerCase())) {
    throw new Error(`full-report.html does not identify plugin slug ${slug}`);
  }
  if (!fullReportText.includes(version.toLowerCase())) {
    throw new Error(
      `full-report.html does not identify artifact version ${version}`,
    );
  }
  if (!confirmsArtifactMatch(fullReport, runData.artifactSha256)) {
    throw new Error(
      "full-report.html does not affirm that the evaluated artifact matches the frozen SHA-256",
    );
  }
  const automatedVerdict = extractVerdict(fullReport);

  const destination = join(
    sharepointRoot,
    runData.industry,
    slug,
    "Evaluation",
    version,
  );
  if (existsSync(destination)) {
    throw new Error(`evaluation archive already exists: ${destination}`);
  }

  const parent = join(sharepointRoot, runData.industry, slug, "Evaluation");
  mkdirSync(parent, { recursive: true });
  const staging = join(parent, `.${version}-${process.pid}.tmp`);
  mkdirSync(staging);

  try {
    const archivedArtifact = join(staging, `${slug}.zip`);
    copyFileSync(artifactPath, archivedArtifact);
    for (const report of REQUIRED_REPORTS) {
      copyFileSync(join(source, report), join(staging, report));
    }
    if (sha256(archivedArtifact) !== runData.artifactSha256) {
      throw new Error("archived ZIP hash verification failed");
    }
    renameSync(staging, destination);
  } catch (error) {
    rmSync(staging, { recursive: true, force: true });
    throw error;
  }

  const updatedRun: EvaluationRun = {
    ...runData,
    status: "archived",
    archivedAt: new Date().toISOString(),
    automatedVerdict,
    reportSource: source,
    archiveDestination: destination,
  };
  writeFileSync(manifestPath, `${JSON.stringify(updatedRun, null, 2)}\n`, "utf8");

  console.log("Evaluation evidence archived.");
  console.log(`  Plugin: ${slug} ${version}`);
  console.log(`  Automated verdict: ${automatedVerdict}`);
  console.log(`  Source: ${source}`);
  console.log(`  Destination: ${destination}`);
  console.log(`  ZIP SHA-256: ${runData.artifactSha256}`);
  console.log(`  Reports: ${REQUIRED_REPORTS.map((report) => basename(report)).join(", ")}`);
  console.log("");
  if (automatedVerdict === "Ready") {
    console.log("Next gate: two independent human reviewers must complete the critical-path checks.");
  } else {
    console.log("Do not publish this artifact. Fix the reported blockers and prepare a new version.");
  }
}

try {
  main();
} catch (error) {
  console.error(`Evaluation archival failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
