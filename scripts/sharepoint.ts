import { execFileSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  readdirSync,
  realpathSync,
  rmdirSync,
  symlinkSync,
  unlinkSync,
} from "node:fs";
import { relative } from "node:path";
import {
  ROOT,
  SHAREPOINT_ENV,
  SHAREPOINT_LINK,
  parseArgs,
  resolveInputPath,
} from "./evaluation-workflow.js";
import {
  INDUSTRY_FOLDERS,
  detectLibraryRoot,
  isConflictCopy,
  looksLikeLibraryRoot,
  readOneDriveMounts,
  walkFiles,
} from "./sharepoint-sync.js";

const RUNBOOK = "docs/sharepoint-sync.md";

function linkState(): "missing" | "link" | "empty-folder" | "folder" {
  let stats;
  try {
    stats = lstatSync(SHAREPOINT_LINK);
  } catch {
    return "missing";
  }
  if (stats.isSymbolicLink()) return "link";
  return readdirSync(SHAREPOINT_LINK).length === 0 ? "empty-folder" : "folder";
}

function samePath(a: string, b: string): boolean {
  return a.toLowerCase().replace(/[\\/]+$/, "") === b.toLowerCase().replace(/[\\/]+$/, "");
}

function link(args: Map<string, string>): void {
  const target = args.has("target")
    ? resolveInputPath(args.get("target") as string)
    : process.env[SHAREPOINT_ENV]
      ? resolveInputPath(process.env[SHAREPOINT_ENV] as string)
      : detectLibraryRoot();
  if (!target) {
    throw new Error(
      "could not find the synced Industry Templates library. Sync it with OneDrive " +
        `(see ${RUNBOOK}) or pass --target "<path to Industry Templates>".`,
    );
  }
  if (!looksLikeLibraryRoot(target)) {
    throw new Error(
      `${target} does not look like the Industry Templates library ` +
        `(expected industry folders such as ${INDUSTRY_FOLDERS.join(", ")}).`,
    );
  }

  const state = linkState();
  if (state === "link") {
    const current = realpathSync.native(SHAREPOINT_LINK);
    if (samePath(current, realpathSync.native(target))) {
      console.log(`Already linked: sharepoint -> ${target}`);
      return;
    }
    if (args.get("force") !== "true") {
      throw new Error(
        `sharepoint already links to ${current}. Pass --force true to replace the link (the target is not touched).`,
      );
    }
    unlinkSync(SHAREPOINT_LINK);
  } else if (state === "folder") {
    throw new Error(
      "sharepoint is a plain folder with content. Reconcile it into the synced library and move it out " +
        `of the repository first (see ${RUNBOOK}, "Migrating an existing local mirror"). Nothing was changed.`,
    );
  } else if (state === "empty-folder") {
    rmdirSync(SHAREPOINT_LINK);
  }

  symlinkSync(target, SHAREPOINT_LINK, "junction");
  console.log(`Linked: sharepoint -> ${target}`);
  console.log("Run `npm run sharepoint:doctor` to check sync health.");
}

function unlink(): void {
  const state = linkState();
  if (state !== "link") {
    throw new Error(`sharepoint is not a link (${state}); nothing was removed.`);
  }
  unlinkSync(SHAREPOINT_LINK);
  console.log("Removed the sharepoint link. The synced library was not touched.");
}

function placeholderCount(path: string): number | undefined {
  try {
    const output = execFileSync(
      "powershell",
      [
        "-NoProfile",
        "-Command",
        "(Get-ChildItem -LiteralPath $env:SP_SCAN -Recurse -File -Force -ErrorAction SilentlyContinue | " +
          "Where-Object { ([int64]$_.Attributes -band 0x401000) -ne 0 } | Measure-Object).Count",
      ],
      { encoding: "utf8", env: { ...process.env, SP_SCAN: path }, stdio: ["ignore", "pipe", "ignore"] },
    );
    return Number.parseInt(output.trim(), 10);
  } catch {
    return undefined;
  }
}

function doctor(): void {
  const errors: string[] = [];
  const warnings: string[] = [];
  const ok = (message: string) => console.log(`  ok    ${message}`);

  const state = linkState();
  let target: string | undefined;
  if (state === "link") {
    if (existsSync(SHAREPOINT_LINK)) {
      target = realpathSync.native(SHAREPOINT_LINK);
      ok(`sharepoint -> ${target}`);
    } else {
      errors.push("sharepoint is a broken link; the OneDrive folder is missing or no longer synced.");
    }
  } else if (state === "folder") {
    errors.push("sharepoint is a plain local folder; nothing syncs it. Migrate it and run `npm run sharepoint:link`.");
  } else {
    errors.push("sharepoint link is missing. Run `npm run sharepoint:link`.");
  }

  const env = process.env[SHAREPOINT_ENV];
  if (env) {
    const envPath = resolveInputPath(env);
    if (!existsSync(envPath)) errors.push(`${SHAREPOINT_ENV} points to a missing folder: ${envPath}`);
    else if (target && !samePath(realpathSync.native(envPath), target)) {
      warnings.push(`${SHAREPOINT_ENV} (${envPath}) overrides the link target; archives go there.`);
    }
    target ??= existsSync(envPath) ? realpathSync.native(envPath) : undefined;
  }

  if (target) {
    if (looksLikeLibraryRoot(target)) ok("library markers found");
    else errors.push(`${target} is missing the expected industry folders (${INDUSTRY_FOLDERS.join(", ")}).`);

    for (const industry of INDUSTRY_FOLDERS) {
      if (!existsSync(`${target}\\${industry}`)) warnings.push(`industry folder not present: ${industry}`);
    }

    const mounts = readOneDriveMounts();
    const synced = mounts.some((m) => target!.toLowerCase().startsWith(m.mountPoint.toLowerCase()));
    if (synced) ok("target is inside a OneDrive-synced folder");
    else errors.push("target is not under any OneDrive sync root; changes will not reach SharePoint. Sync the library first.");

    const files = walkFiles(target);
    const conflicts = files.filter((file) => isConflictCopy(file));
    if (conflicts.length) {
      warnings.push(
        `${conflicts.length} OneDrive conflict cop${conflicts.length === 1 ? "y" : "ies"}; resolve and delete:\n` +
          conflicts.slice(0, 20).map((file) => `          ${relative(target!, file)}`).join("\n"),
      );
    } else ok(`no conflict copies across ${files.length} files`);

    const online = placeholderCount(target);
    if (online === undefined) warnings.push("could not read Files On-Demand state.");
    else if (online > 0) {
      warnings.push(
        `${online} file(s) are online-only. Right-click the library folder > "Always keep on this device" ` +
          "so agents and searches can read them offline.",
      );
    } else ok("all files are available locally");
  }

  try {
    execFileSync("git", ["check-ignore", "-q", "sharepoint"], { cwd: ROOT, stdio: "ignore" });
    ok("sharepoint is gitignored");
  } catch {
    errors.push("sharepoint is NOT gitignored; add `/sharepoint` to .gitignore before committing.");
  }

  for (const warning of warnings) console.log(`  warn  ${warning}`);
  for (const error of errors) console.log(`  FAIL  ${error}`);
  console.log(errors.length ? `\nSharePoint sync: not ready (see ${RUNBOOK}).` : "\nSharePoint sync: ready.");
  if (errors.length) process.exitCode = 1;
}

function main(): void {
  const [command, ...rest] = process.argv.slice(2);
  const args = parseArgs(rest);
  if (command === "link") link(args);
  else if (command === "unlink") unlink();
  else if (command === "doctor") doctor();
  else throw new Error("usage: sharepoint.ts <link|doctor|unlink> [--target <path>] [--force true]");
}

try {
  main();
} catch (error) {
  console.error(`SharePoint sync: ${(error as Error).message}`);
  process.exitCode = 1;
}
