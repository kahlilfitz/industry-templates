import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  candidateRoots,
  isConflictCopy,
  looksLikeLibraryRoot,
  parseOneDriveMounts,
} from "./sharepoint-sync.js";

const REG_OUTPUT = `
HKEY_CURRENT_USER\\Software\\SyncEngines\\Providers\\OneDrive
HKEY_CURRENT_USER\\Software\\SyncEngines\\Providers\\OneDrive\\Business1
    MountPoint    REG_SZ    C:\\Users\\me\\OneDrive - Contoso
    UrlNamespace    REG_SZ    https://contoso-my.sharepoint.com/personal/me/Documents/
HKEY_CURRENT_USER\\Software\\SyncEngines\\Providers\\OneDrive\\abc123
    UrlNamespace    REG_SZ    https://contoso.sharepoint.com/teams/TeamSite/Projects/
    MountPoint    REG_SZ    C:\\Users\\me\\Contoso\\TeamSite - Projects
`;

test("parseOneDriveMounts reads each provider key regardless of value order", () => {
  assert.deepEqual(parseOneDriveMounts(REG_OUTPUT), [
    {
      mountPoint: "C:\\Users\\me\\OneDrive - Contoso",
      urlNamespace: "https://contoso-my.sharepoint.com/personal/me/Documents/",
    },
    {
      mountPoint: "C:\\Users\\me\\Contoso\\TeamSite - Projects",
      urlNamespace: "https://contoso.sharepoint.com/teams/TeamSite/Projects/",
    },
  ]);
});

test("candidateRoots covers mounts, nested library folders and shortcut folders", () => {
  const listing: Record<string, string[]> = {
    "C:\\Users\\me\\Contoso\\TeamSite - Projects": ["Area", ".hidden"],
    "C:\\Users\\me\\OneDrive - Contoso": ["TeamSite - Industry Templates", "Documents"],
  };
  const roots = candidateRoots(
    parseOneDriveMounts(REG_OUTPUT),
    ["C:\\Users\\me\\OneDrive - Contoso"],
    [],
    (path) => listing[path] ?? [],
  );
  assert.equal(roots[0], "C:\\Users\\me\\OneDrive - Contoso");
  assert.ok(roots.includes(join("C:\\Users\\me\\Contoso\\TeamSite - Projects", "Area", "Industry Templates")));
  assert.ok(roots.includes(join("C:\\Users\\me\\OneDrive - Contoso", "TeamSite - Industry Templates")));
  assert.ok(!roots.some((r) => r.includes(".hidden")));
  assert.equal(new Set(roots.map((r) => r.toLowerCase())).size, roots.length);
});

test("looksLikeLibraryRoot requires Professional Services plus two other industries", () => {
  const dir = mkdtempSync(join(tmpdir(), "library-root-"));
  try {
    mkdirSync(join(dir, "Professional Services"));
    mkdirSync(join(dir, "Retail"));
    assert.equal(looksLikeLibraryRoot(dir), false);
    mkdirSync(join(dir, "FSI"));
    assert.equal(looksLikeLibraryRoot(dir), true);
    assert.equal(looksLikeLibraryRoot(join(dir, "missing")), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("isConflictCopy matches OneDrive conflict names for this computer only", () => {
  assert.equal(isConflictCopy("tracker-LAPTOP7.xlsx", "LAPTOP7"), true);
  assert.equal(isConflictCopy("tracker-laptop7-2.xlsx", "LAPTOP7"), true);
  assert.equal(isConflictCopy("tracker.xlsx", "LAPTOP7"), false);
  assert.equal(isConflictCopy("engagement-staffing-bench-match.zip", "LAPTOP7"), false);
});
