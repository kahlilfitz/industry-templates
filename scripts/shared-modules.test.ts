import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { checkSharedModules } from "./shared-modules.js";

test("checkSharedModules finds vendored copies by manifest name and flags drift", () => {
  const root = mkdtempSync(join(tmpdir(), "shared-modules-"));
  try {
    mkdirSync(join(root, "shared", "guard"), { recursive: true });
    writeFileSync(join(root, "shared", "guard", "guard.py"), "VERSION = 2\n");
    writeFileSync(join(root, "shared", "guard", "corpus.json"), "{}\n");
    writeFileSync(
      join(root, "shared", "guard", "vendor.json"),
      JSON.stringify({ files: { "guard.py": "guard.py", "corpus.json": "guard-corpus.json" } }),
    );
    const good = join(root, "submissions", "ind", "a", "skills", "x", "scripts");
    const stale = join(root, "submissions", "ind", "b", "scripts");
    const tests = join(root, "submissions", "ind", "a", "tests");
    for (const dir of [good, stale, tests]) mkdirSync(dir, { recursive: true });
    writeFileSync(join(good, "guard.py"), "VERSION = 2\n");
    writeFileSync(join(stale, "guard.py"), "VERSION = 1\n");
    writeFileSync(join(tests, "guard-corpus.json"), "{}\n");

    const reports = checkSharedModules(root);
    const module = reports.find((r) => r.vendoredName === "guard.py")!;
    const corpus = reports.find((r) => r.vendoredName === "guard-corpus.json")!;
    assert.equal(module.copies.length, 2);
    assert.deepEqual(module.mismatched, [join("submissions", "ind", "b", "scripts", "guard.py")]);
    assert.equal(corpus.copies.length, 1);
    assert.deepEqual(corpus.mismatched, []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("checkSharedModules is a no-op without shared/ and rejects a manifest naming a missing file", () => {
  const root = mkdtempSync(join(tmpdir(), "shared-modules-"));
  try {
    assert.deepEqual(checkSharedModules(root), []);
    mkdirSync(join(root, "shared", "guard"), { recursive: true });
    writeFileSync(join(root, "shared", "guard", "vendor.json"), JSON.stringify({ files: { "gone.py": "gone.py" } }));
    assert.throws(() => checkSharedModules(root), /does not exist/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
