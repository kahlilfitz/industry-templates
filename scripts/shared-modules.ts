import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, relative } from "node:path";
import { ROOT, sha256 } from "./evaluation-workflow.js";

// shared/<module>/vendor.json maps a canonical file to the name each plugin vendors it under,
// e.g. { "files": { "steering_guard.py": "steering_guard.py", "corpus.json": "steering-corpus.json" } }.
export interface VendorManifest {
  files: Record<string, string>;
}

export interface SharedFileReport {
  module: string;
  source: string;
  vendoredName: string;
  copies: string[];
  mismatched: string[];
}

function walk(dir: string, found: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__pycache__" || entry.startsWith(".")) continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path, found);
    else found.push(path);
  }
  return found;
}

export function checkSharedModules(root: string = ROOT): SharedFileReport[] {
  const sharedRoot = join(root, "shared");
  const submissionsRoot = join(root, "submissions");
  if (!existsSync(sharedRoot)) return [];
  const submissionFiles = existsSync(submissionsRoot) ? walk(submissionsRoot) : [];
  const reports: SharedFileReport[] = [];
  for (const module of readdirSync(sharedRoot).sort()) {
    const manifestPath = join(sharedRoot, module, "vendor.json");
    if (!existsSync(manifestPath)) continue;
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as VendorManifest;
    for (const [sourceName, vendoredName] of Object.entries(manifest.files ?? {})) {
      const source = join(sharedRoot, module, sourceName);
      if (!existsSync(source)) {
        throw new Error(`shared/${module}/vendor.json lists ${sourceName}, which does not exist`);
      }
      const expected = sha256(source);
      const copies = submissionFiles.filter((path) => basename(path) === vendoredName);
      reports.push({
        module,
        source: relative(root, source),
        vendoredName,
        copies: copies.map((path) => relative(root, path)),
        mismatched: copies.filter((path) => sha256(path) !== expected).map((path) => relative(root, path)),
      });
    }
  }
  return reports;
}
