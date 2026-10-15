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
  EvaluationRun,
  VERDICT_REPORT,
  assertNonEmptyFile,
  confirmsArtifactMatch,
  extractVerdict,
  findSubmission,
  htmlToText,
  parseArgs,
  requiredArg,
  resolveInputPath,
  resolveSharepointRoot,
  sha256,
  verdictGuidance,
} from "./evaluation-workflow.js";

// OneDrive briefly locks newly created folders while it registers them for sync.
const TRANSIENT_RENAME_CODES = new Set(["EPERM", "EBUSY", "EACCES"]);

function renameWithRetry(from: string, to: string, attempts = 8): void {
  for (let attempt = 1; ; attempt += 1) {
    try {
      renameSync(from, to);
      return;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code ?? "";
      if (!TRANSIENT_RENAME_CODES.has(code) || attempt >= attempts || existsSync(to)) {
        throw error;
      }
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 1000 * attempt);
    }
  }
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const slug = requiredArg(args, "slug");
  const source = resolveInputPath(requiredArg(args, "source"));
  const inboxRoot = args.has("inbox-root")
    ? resolveInputPath(requiredArg(args, "inbox-root"))
    : DEFAULT_INBOX_ROOT;
  const { root: sharepointRoot } = resolveSharepointRoot({
    flag: args.has("sharepoint-root") ? requiredArg(args, "sharepoint-root") : undefined,
  });
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

  // Legacy: runs prepared before 2026-10-15 also froze a test-data ZIP; archive it with the reports.
  let testDataPath: string | undefined;
  if (runData.testDataFile !== undefined) {
    if (runData.testDataFile !== `${slug}-test-data-${version}.zip` || !runData.testDataSha256) {
      throw new Error("frozen evaluation manifest has an unexpected test-data filename or no test-data SHA-256");
    }
    testDataPath = join(runDir, runData.testDataFile);
    assertNonEmptyFile(testDataPath, "frozen test-data ZIP");
    if (sha256(testDataPath) !== runData.testDataSha256) {
      throw new Error("frozen test-data ZIP no longer matches its recorded SHA-256");
    }
  }

  for (const report of REQUIRED_REPORTS) {
    assertNonEmptyFile(join(source, report), report);
  }

  const verdictReport = readFileSync(join(source, VERDICT_REPORT), "utf8");
  const verdictText = htmlToText(verdictReport).toLowerCase();
  if (!verdictText.includes(slug.toLowerCase())) {
    throw new Error(`${VERDICT_REPORT} does not identify plugin slug ${slug}`);
  }
  if (!verdictText.includes(version.toLowerCase())) {
    throw new Error(`${VERDICT_REPORT} does not identify artifact version ${version}`);
  }
  if (!confirmsArtifactMatch(verdictReport, runData.artifactSha256)) {
    throw new Error(
      `${VERDICT_REPORT} does not affirm that the evaluated artifact matches the frozen SHA-256`,
    );
  }
  const automatedVerdict = extractVerdict(verdictReport);

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
    if (testDataPath && runData.testDataFile) {
      const archivedTestData = join(staging, runData.testDataFile);
      copyFileSync(testDataPath, archivedTestData);
      if (sha256(archivedTestData) !== runData.testDataSha256) {
        throw new Error("archived test-data ZIP hash verification failed");
      }
    }
    renameWithRetry(staging, destination);
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
  if (runData.testDataFile) {
    console.log(`  Test-data ZIP: ${runData.testDataFile} (SHA-256 ${runData.testDataSha256})`);
  }
  console.log(`  Reports: ${REQUIRED_REPORTS.map((report) => basename(report)).join(", ")}`);
  console.log("");
  for (const line of verdictGuidance(automatedVerdict)) console.log(line);
}

try {
  main();
} catch (error) {
  console.error(`Evaluation archival failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
