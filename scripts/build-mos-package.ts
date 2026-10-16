/**
 * npm run mos:build -- --slug <slug> [--version <x.y.z>] [--out-dir <folder>] [--sharepoint-root <folder>]
 *
 * Derives the manifest-1.28 MOS package from the archived Cowork-evaluated ZIP. Without --out-dir it
 * writes `<plugin folder>\MOS Package\` and requires the C4 promotion (`<slug>-cowork.zip`).
 */
import { parseArgs, requiredArg, resolveInputPath, resolveSharepointRoot } from "./evaluation-workflow.js";
import { buildMosPackage } from "./mos-package.js";

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const outDir = args.get("out-dir");
  const { root } = resolveSharepointRoot({ flag: args.get("sharepoint-root") });
  const result = buildMosPackage({
    slug: requiredArg(args, "slug"),
    version: args.get("version"),
    sharepointRoot: root,
    outDir: outDir ? resolveInputPath(outDir) : undefined,
  });
  const d = result.derivation;
  console.log(`MOS package ${result.status}.`);
  console.log(`  Package: ${result.packagePath}`);
  console.log(`  SHA-256: ${d.sha256} (${d.zip.length} bytes)`);
  console.log(`  Source (evaluated) SHA-256: ${d.sourceSha256}`);
  console.log(`  ${d.identicalEntries} of ${d.entries.length} entries byte-identical; manifest.json is the 1.28 manifest`);
  console.log(`  README and skills\\ written to ${result.outDir}`);
}

try {
  main();
} catch (error) {
  console.error(`MOS package build failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
