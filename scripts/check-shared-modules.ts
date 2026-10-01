import { checkSharedModules } from "./shared-modules.js";

try {
  const reports = checkSharedModules();
  let failed = false;
  for (const report of reports) {
    const status = report.mismatched.length === 0 ? "ok" : "MISMATCH";
    console.log(`${status}  ${report.source} -> ${report.copies.length} vendored ${report.vendoredName}`);
    for (const path of report.mismatched) {
      console.log(`  differs from source: ${path}`);
      failed = true;
    }
  }
  if (failed) {
    console.error(
      "Vendored shared modules differ from shared/. Edit the source in shared/, bump its version, then copy it byte-for-byte into every plugin.",
    );
    process.exitCode = 1;
  } else {
    console.log("All vendored shared modules match their source.");
  }
} catch (error) {
  console.error(`Shared module check failed: ${(error as Error).message}`);
  process.exitCode = 1;
}
