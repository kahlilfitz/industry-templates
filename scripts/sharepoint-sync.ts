import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { hostname } from "node:os";
import { basename, extname, join } from "node:path";

export const LIBRARY_FOLDER = "Industry Templates";
export const INDUSTRY_FOLDERS = [
  "FSI",
  "HealthCare",
  "Manufacturing",
  "OGE",
  "Professional Services",
  "Retail",
];

export type SyncMount = { mountPoint: string; urlNamespace: string };

/** Parses `reg query HKCU\Software\SyncEngines\Providers\OneDrive /s` output. */
export function parseOneDriveMounts(regOutput: string): SyncMount[] {
  const mounts: SyncMount[] = [];
  let current: Partial<SyncMount> = {};
  const flush = () => {
    if (current.mountPoint) {
      mounts.push({ mountPoint: current.mountPoint, urlNamespace: current.urlNamespace ?? "" });
    }
    current = {};
  };
  for (const line of regOutput.split(/\r?\n/)) {
    if (/^HKEY_/i.test(line.trim())) {
      flush();
      continue;
    }
    const value = line.match(/^\s*(MountPoint|UrlNamespace)\s+REG_\w+\s+(.*)$/i);
    if (!value) continue;
    if (value[1].toLowerCase() === "mountpoint") current.mountPoint = value[2].trim();
    else current.urlNamespace = value[2].trim();
  }
  flush();
  return mounts;
}

export function readOneDriveMounts(): SyncMount[] {
  if (process.platform !== "win32") return [];
  try {
    const output = execFileSync(
      "reg",
      ["query", "HKCU\\Software\\SyncEngines\\Providers\\OneDrive", "/s"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    );
    return parseOneDriveMounts(output);
  } catch {
    return [];
  }
}

/** A library root holds at least three of the known industry folders. */
export function looksLikeLibraryRoot(path: string): boolean {
  if (!existsSync(path) || !statSync(path).isDirectory()) return false;
  const present = INDUSTRY_FOLDERS.filter((name) => {
    const child = join(path, name);
    return existsSync(child) && statSync(child).isDirectory();
  });
  return present.length >= 3 && present.includes("Professional Services");
}

/**
 * Candidate folders for the synced library, de-duplicated. Each base (an organisation library
 * folder, a OneDrive root or a registered sync mount) is tried as the library itself, with an
 * `Industry Templates` child, and one level deeper: any child named `... Industry Templates` (an
 * Add-shortcut folder) or holding an `Industry Templates` folder. `looksLikeLibraryRoot` decides.
 */
export function candidateRoots(
  mounts: SyncMount[],
  oneDriveRoots: string[],
  orgFolders: string[],
  listDir: (path: string) => string[] = safeReaddir,
): string[] {
  const out: string[] = [];
  const add = (path: string) => {
    if (!out.some((existing) => existing.toLowerCase() === path.toLowerCase())) out.push(path);
  };
  const bases = [...mounts.map((m) => m.mountPoint), ...orgFolders, ...oneDriveRoots];
  for (const base of bases) {
    add(base);
    add(join(base, LIBRARY_FOLDER));
  }
  for (const base of bases) {
    for (const child of listDir(base)) {
      if (child.startsWith(".")) continue;
      if (child.toLowerCase().endsWith(LIBRARY_FOLDER.toLowerCase())) add(join(base, child));
      add(join(base, child, LIBRARY_FOLDER));
    }
  }
  return out;
}

/** Library folders the OneDrive client creates under %USERPROFILE%\<Org>\ ("<Site> - <Library>"). */
export function orgLibraryFolders(userProfile: string): string[] {
  const out: string[] = [];
  for (const entry of safeReaddir(userProfile)) {
    if (entry.startsWith(".") || entry.toLowerCase().startsWith("onedrive")) continue;
    const orgPath = join(userProfile, entry);
    for (const library of safeReaddir(orgPath)) {
      if (/\s-\s/.test(library)) out.push(join(orgPath, library));
    }
  }
  return out;
}

function safeReaddir(path: string): string[] {
  try {
    return statSync(path).isDirectory() ? readdirSync(path) : [];
  } catch {
    return [];
  }
}

export function detectLibraryRoot(): string | undefined {
  const userProfile = process.env.USERPROFILE ?? "";
  const oneDriveRoots = [process.env.OneDriveCommercial, process.env.OneDrive].filter(
    (value): value is string => Boolean(value),
  );
  return candidateRoots(readOneDriveMounts(), oneDriveRoots, orgLibraryFolders(userProfile)).find(
    looksLikeLibraryRoot,
  );
}

/** OneDrive names conflicting edits `<name>-<COMPUTERNAME>[-n].<ext>`. */
export function isConflictCopy(fileName: string, computerName = hostname()): boolean {
  const stem = basename(fileName, extname(fileName));
  const escaped = computerName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`-${escaped}(?:-\\d+)?$`, "i").test(stem);
}

export function walkFiles(root: string, limit = 50_000): string[] {
  const files: string[] = [];
  const stack = [root];
  while (stack.length && files.length < limit) {
    const dir = stack.pop() as string;
    for (const entry of safeReaddir(dir)) {
      const path = join(dir, entry);
      try {
        if (statSync(path).isDirectory()) stack.push(path);
        else files.push(path);
      } catch {
        // Unreadable entries are reported by OneDrive itself.
      }
    }
  }
  return files;
}
