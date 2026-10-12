/**
 * `npm run check:test-data`: every MOS3 submission has a complete
 * `test-data\<industry>\<slug>\<version>\` for its current version, every frozen version folder
 * matches its FROZEN.sha256, and no test data is left without a submission. Writes nothing.
 */
import { checkTestData } from "./test-data.js";

const report = checkTestData();
if (report.checked.length) {
  console.log(`Checked test data for ${report.checked.length} MOS3 submission(s):`);
  console.log(report.checked.join("\n"));
} else {
  console.log("No MOS3 submissions; nothing requires test data.");
}
if (report.warnings.length) {
  console.warn(`\n${report.warnings.length} warning(s):`);
  console.warn(report.warnings.join("\n"));
}
if (report.errors.length) {
  console.error(`\n${report.errors.length} problem(s) found:`);
  console.error(report.errors.join("\n"));
  process.exit(1);
}
console.log("\nTest data valid.");
