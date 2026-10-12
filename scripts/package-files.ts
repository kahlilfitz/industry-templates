/**
 * File-walking and reproducible ZIP helpers shared by the bundle builder, the MOS3 packager and
 * the test-data packager.
 */
import { readFileSync, readdirSync, lstatSync } from "node:fs";
import { join, posix, relative, sep } from "node:path";
import AdmZip from "adm-zip";

/**
 * Build litter that can turn up at any depth, not just the top level. Several
 * submissions ship Python that the agent is told to run from the plugin folder,
 * which leaves `__pycache__` next to the script; the compiled files embed the
 * author's absolute paths, so they must never reach a downloader.
 */
export const LITTER_DIRS = new Set(["__pycache__", ".pytest_cache", ".ruff_cache", ".DS_Store"]);

export function isBuildLitter(rel: string): boolean {
  return rel
    .split(posix.sep)
    .some((segment) => LITTER_DIRS.has(segment) || segment.endsWith(".pyc"));
}

/** Pinned entry time for packages that have no submission date of their own. */
export const FIXED_ZIP_TIMESTAMP = new Date("2026-01-01T00:00:00Z");

export type WalkResult = { files: string[]; symlinks: string[] };

/**
 * Every file under `dir`, as sorted slash-separated paths relative to `dir`. Symbolic links and
 * junctions are reported separately and never followed.
 */
export function walkNoFollow(dir: string, base = dir): WalkResult {
  const files: string[] = [];
  const symlinks: string[] = [];
  for (const entry of readdirSync(dir).sort()) {
    const abs = join(dir, entry);
    const rel = relative(base, abs).split(sep).join(posix.sep);
    const stat = lstatSync(abs);
    if (stat.isSymbolicLink()) symlinks.push(rel);
    else if (stat.isDirectory()) {
      const nested = walkNoFollow(abs, base);
      files.push(...nested.files);
      symlinks.push(...nested.symlinks);
    } else files.push(rel);
  }
  return { files: files.sort(), symlinks: symlinks.sort() };
}

/** A DOS date/time computed from UTC fields, so the ZIP is identical in every time zone. */
function dosTimeUtc(date: Date): number {
  const time =
    (date.getUTCHours() << 11) | (date.getUTCMinutes() << 5) | Math.floor(date.getUTCSeconds() / 2);
  const day =
    ((date.getUTCFullYear() - 1980) << 9) | ((date.getUTCMonth() + 1) << 5) | date.getUTCDate();
  return ((day << 16) | time) >>> 0;
}

/**
 * Write a ZIP whose bytes depend only on the input: entries at the given names, sorted, one
 * fixed timestamp, Deflate or Store compression, no directory entries.
 */
export function writeReproducibleZip(
  entries: Array<{ name: string; path: string }>,
  outPath: string,
  stamp: Date = FIXED_ZIP_TIMESTAMP,
): void {
  const zip = new AdmZip();
  const timeval = dosTimeUtc(stamp);
  const sorted = [...entries].sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  for (const { name, path } of sorted) {
    const segments = name.split("/");
    if (!name || name.startsWith("/") || segments.some((s) => !s || s === "." || s === "..")) {
      throw new Error(`refusing to write unsafe ZIP entry name: ${name}`);
    }
    zip.addFile(name, readFileSync(path));
  }
  // adm-zip's `time` setter converts through local time; the raw DOS value keeps every time zone identical.
  for (const entry of zip.getEntries()) (entry.header as unknown as { timeval: number }).timeval = timeval;
  zip.writeZip(outPath);
}
