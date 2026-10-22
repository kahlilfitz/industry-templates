import {
  constants,
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, isAbsolute, join, relative, sep } from "node:path";
import { ROOT, findSubmission, sha256, sharepointPluginDir } from "./evaluation-workflow.js";

export const MATRIX_BUILT_FOLDER = join("4 - Matrices", "2 - Built");
export const MATRIX_DESTINATION_FOLDER = "Evaluation Matrices";
export const MATRIX_LEDGER_FILE = join("evaluation-inbox", "matrix-collected.json");

export type MatrixLedgerEntry = { source: string; digest: string; destination: string; collectedAt: string };

export function readMatrixLedger(path: string): MatrixLedgerEntry[] {
  if (!existsSync(path)) return [];
  const data = JSON.parse(readFileSync(path, "utf8")) as { collected?: MatrixLedgerEntry[] };
  if (!Array.isArray(data.collected)) throw new Error(`matrix ledger is malformed: ${path}`);
  return data.collected;
}

function writeMatrixLedger(path: string, entries: MatrixLedgerEntry[]): void {
  mkdirSync(dirname(path), { recursive: true });
  const temp = `${path}.${process.pid}.tmp`;
  writeFileSync(temp, `${JSON.stringify({ collected: entries }, null, 2)}\n`);
  renameSync(temp, path);
}

function ledgerKey(source: string, digest: string, destination: string): string {
  return `${source}\0${digest}\0${destination}`;
}

export type MatrixResult = {
  source: string;
  destination?: string;
  status: "waiting" | "copied" | "unchanged" | "dry-run" | "error";
  message?: string;
};

type Observation = { signature: string; since: number };

type MatrixName = { slug: string; version: string; kind: "eval-matrix" | "matrix-notes"; timestamp: string };
type MatrixFile = MatrixName & { source: string; digest?: string; ready: boolean };

export function parseMatrixName(name: string): MatrixName {
  const match = name.match(
    /^([a-z0-9]+(?:-[a-z0-9]+)*)-v([0-9A-Za-z]+(?:[._-][0-9A-Za-z]+)*)-(eval-matrix|matrix-notes)-(\d{4}-\d{2}-\d{2}-\d{4})\.(xlsx|md)$/,
  );
  if (!match || (match[3] === "eval-matrix" ? match[5] !== "xlsx" : match[5] !== "md")) {
    throw new Error(`unrecognized matrix filename: ${name}; expected <slug>-v<version>-eval-matrix-YYYY-MM-DD-HHMM.xlsx or <slug>-v<version>-matrix-notes-YYYY-MM-DD-HHMM.md`);
  }
  return { slug: match[1], version: match[2], kind: match[3] === "eval-matrix" ? "eval-matrix" : "matrix-notes", timestamp: match[4] };
}

function inside(root: string, path: string): boolean {
  const rel = relative(root, path);
  return rel === "" || (!isAbsolute(rel) && rel !== ".." && !rel.startsWith(`..${sep}`));
}

function temporary(name: string): boolean {
  return name.startsWith(".") || name.startsWith("~$") || /\.(?:tmp|part|partial|crdownload|download)$/i.test(name);
}

function builtFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap((entry) => {
    if (temporary(entry.name)) return [];
    const path = join(root, entry.name);
    return entry.isDirectory() ? builtFiles(path) : [path];
  });
}

function existingCopy(destination: string, digest: string): boolean {
  if (!existsSync(destination)) return false;
  const stat = lstatSync(destination);
  if (!stat.isFile() || stat.isSymbolicLink() || sha256(destination) !== digest) {
    throw new Error(`matrix destination already exists with different content or is not a regular file: ${destination}; nothing overwritten`);
  }
  return true;
}

export class MatrixWatcher {
  private observations = new Map<string, Observation>();
  private readonly repoRoot: string;
  private readonly stableMilliseconds: number;

  constructor(private readonly options: {
    builtRoot: string;
    sharepointRoot: string;
    repoRoot?: string;
    stableSeconds?: number;
    dryRun?: boolean;
    // Records collected pairs: SharePoint rewrites Office files after upload, so a
    // collected workbook can no longer be compared byte-for-byte with its source.
    ledgerPath?: string;
  }) {
    this.repoRoot = options.repoRoot ?? ROOT;
    this.stableMilliseconds = (options.stableSeconds ?? 15) * 1000;
    if (!Number.isFinite(this.stableMilliseconds) || this.stableMilliseconds <= 0) {
      throw new Error("stableSeconds must be a positive number");
    }
    for (const root of [options.builtRoot, options.sharepointRoot]) {
      if (!existsSync(root) || !statSync(root).isDirectory()) {
        throw new Error(`folder does not exist: ${root}`);
      }
    }
    const built = realpathSync(options.builtRoot);
    const library = realpathSync(options.sharepointRoot);
    if (inside(built, library) || inside(library, built)) {
      throw new Error("Built and SharePoint folders must not overlap");
    }
  }

  scan(now = Date.now()): MatrixResult[] {
    const files = builtFiles(this.options.builtRoot);
    const results: MatrixResult[] = [];
    const groups = new Map<string, MatrixFile[]>();
    const present = new Set(files);
    for (const source of this.observations.keys()) {
      if (!present.has(source)) this.observations.delete(source);
    }
    for (const source of files) {
      try {
        const stat = lstatSync(source);
        if (!stat.isFile() || stat.isSymbolicLink()) {
          throw new Error(`matrix source is not a regular file: ${source}`);
        }
        const name = parseMatrixName(basename(source));
        let digest: string | undefined;
        let ready = false;
        if (stat.size === 0) {
          this.observations.delete(source);
        } else {
          digest = sha256(source);
          const signature = `${stat.size}:${stat.mtimeMs}:${digest}`;
          const previous = this.observations.get(source);
          if (!previous || previous.signature !== signature) {
            this.observations.set(source, { signature, since: now });
          } else {
            ready = now - previous.since >= this.stableMilliseconds;
          }
        }
        const key = join(dirname(source), `${name.slug}-v${name.version}-${name.timestamp}`);
        const group = groups.get(key) ?? [];
        group.push({ ...name, source, digest, ready });
        groups.set(key, group);
      } catch (error) {
        results.push({ source, status: "error", message: error instanceof Error ? error.message : String(error) });
      }
    }

    for (const group of groups.values()) {
      if (group.length !== 2 || group.some((file) => !file.ready)) {
        const message = group.length !== 2
          ? "waiting for the matching workbook and notes in the same folder"
          : "waiting for both files to be non-empty and stable";
        results.push(...group.map(({ source }): MatrixResult => ({ source, status: "waiting", message })));
        continue;
      }
      try {
        const { slug } = group[0];
        const submission = findSubmission(slug, this.repoRoot);
        const pluginDir = sharepointPluginDir(this.options.sharepointRoot, submission.industry, slug);
        if (!existsSync(pluginDir) || !statSync(pluginDir).isDirectory()) {
          throw new Error(`plugin folder does not exist: ${pluginDir}; check the SharePoint layout and run npm run sharepoint:doctor`);
        }
        if (!inside(realpathSync(this.options.sharepointRoot), realpathSync(pluginDir))) {
          throw new Error(`plugin folder resolves outside the SharePoint library: ${pluginDir}`);
        }
        const directory = join(pluginDir, MATRIX_DESTINATION_FOLDER);
        if (existsSync(directory)) {
          const stat = lstatSync(directory);
          if (!stat.isDirectory() || stat.isSymbolicLink()) {
            throw new Error(`matrix destination is not a regular directory: ${directory}`);
          }
        }
        const ledger = this.options.ledgerPath ? readMatrixLedger(this.options.ledgerPath) : [];
        const collected = new Set(ledger.map((entry) => ledgerKey(entry.source, entry.digest, entry.destination)));
        const targets = group.map((file) => {
          if (!file.digest) throw new Error(`matrix has no content digest: ${file.source}`);
          const destination = join(directory, basename(file.source));
          return { ...file, digest: file.digest, destination, recorded: collected.has(ledgerKey(file.source, file.digest, destination)) && existsSync(destination) };
        });
        if (targets.every((file) => file.recorded)) {
          results.push(...targets.map(({ source, destination }): MatrixResult => ({ source, destination, status: "unchanged", message: "already collected" })));
          continue;
        }
        const planned = targets.map((file) => ({ ...file, exists: file.recorded || existingCopy(file.destination, file.digest) }));
        const copied: MatrixResult[] = [];
        for (const file of planned) {
          const { source, digest, destination } = file;
          if (file.exists || this.options.dryRun) {
            copied.push({ source, destination, status: file.exists ? "unchanged" : "dry-run" });
            continue;
          }
          if (!existsSync(directory)) mkdirSync(directory);
          try {
            copyFileSync(source, destination, constants.COPYFILE_EXCL);
          } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "EEXIST" || !existingCopy(destination, digest)) throw error;
            copied.push({ source, destination, status: "unchanged" });
            continue;
          }
          try {
            if (sha256(source) !== digest || sha256(destination) !== digest) {
              throw new Error(`matrix changed during copying or copy verification failed: ${source}`);
            }
          } catch (error) {
            this.observations.delete(source);
            unlinkSync(destination);
            throw error;
          }
          copied.push({ source, destination, status: "copied" });
        }
        if (this.options.ledgerPath && !this.options.dryRun) {
          const now = new Date().toISOString();
          const additions = planned
            .filter((file) => !collected.has(ledgerKey(file.source, file.digest, file.destination)))
            .map(({ source, digest, destination }) => ({ source, digest, destination, collectedAt: now }));
          writeMatrixLedger(this.options.ledgerPath, [...ledger, ...additions]);
        }
        results.push(...copied);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        results.push(...group.map(({ source }): MatrixResult => ({ source, status: "error", message })));
      }
    }
    return results;
  }
}
