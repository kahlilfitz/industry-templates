/** Throwaway fixtures for the MOS3 and test-data unit tests. Never used by the build. */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { deflateSync } from "node:zlib";
import { MOS3_REQUIRED_LINKS, MOS3_SCHEMA, crc32 } from "./mos3-package.js";

type Pixel = [number, number, number, number];

function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "latin1"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

/**
 * Encode an 8-bit PNG. `filter` picks the row filter (0-4, or "cycle" to rotate through all five)
 * so the decoder's unfiltering is exercised; `colorType` 2 drops alpha, other values only patch
 * the header to produce unsupported files.
 */
export function encodePng(
  width: number,
  height: number,
  pixel: (x: number, y: number) => Pixel,
  options: { filter?: number | "cycle"; colorType?: number; interlace?: number } = {},
): Buffer {
  const colorType = options.colorType ?? 6;
  const channels = colorType === 2 ? 3 : 4;
  const stride = width * channels;
  const raw: number[][] = [];
  for (let y = 0; y < height; y++) {
    const row: number[] = [];
    for (let x = 0; x < width; x++) row.push(...pixel(x, y).slice(0, channels));
    raw.push(row);
  }
  const rows: Buffer[] = [];
  for (let y = 0; y < height; y++) {
    const filter = options.filter === "cycle" ? y % 5 : (options.filter ?? 0);
    const out = Buffer.alloc(stride + 1);
    out[0] = filter;
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? raw[y][x - channels] : 0;
      const b = y > 0 ? raw[y - 1][x] : 0;
      const c = x >= channels && y > 0 ? raw[y - 1][x - channels] : 0;
      const p = a + b - c;
      const paeth =
        Math.abs(p - a) <= Math.abs(p - b) && Math.abs(p - a) <= Math.abs(p - c)
          ? a
          : Math.abs(p - b) <= Math.abs(p - c)
            ? b
            : c;
      const predictor = [0, a, b, (a + b) >> 1, paeth][filter];
      out[x + 1] = (raw[y][x] - predictor) & 0xff;
    }
    rows.push(out);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = colorType;
  ihdr[12] = options.interlace ?? 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

export const colorIcon = () => encodePng(192, 192, (x, y) => [x % 256, y % 256, 128, 255], { filter: "cycle" });
/** A white ring on a transparent background. */
export const outlineIcon = () =>
  encodePng(32, 32, (x, y) => (x < 4 || y < 4 || x > 27 || y > 27 ? [255, 255, 255, 255] : [0, 0, 0, 0]), {
    filter: "cycle",
  });

export function write(path: string, content: string | Buffer): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content);
}

export const FULL_DESCRIPTION =
  "Demo plugin for tests.\n\n" + MOS3_REQUIRED_LINKS.map(([label, url]) => `${label}: ${url}`).join("\n");

export function skillMd(name: string, version = "1.2.3", extra = ""): string {
  return [
    "---",
    `name: ${name}`,
    "description: >-",
    `  Does ${name} things. Use when the user asks "run ${name}", "check ${name}", "list ${name}",`,
    `  "explain ${name}" or "fix ${name}".`,
    "  Do NOT use for anything else (use another skill).",
    "license: Proprietary",
    "metadata:",
    `  version: "${version}"`,
    "  icon: DocumentSearch",
    "  author: Tests",
    ...(extra ? [extra] : []),
    "---",
    `# ${name}`,
    "1. Run `python skills/" + name + "/scripts/engine.py`.",
    "",
  ].join("\n");
}

export function validManifest(version = "1.2.3", skills = ["alpha-skill", "beta-skill"]): Record<string, unknown> {
  return {
    $schema: MOS3_SCHEMA,
    manifestVersion: "1.28",
    version,
    id: "0f8c3a52-6d1e-4b7a-9c2d-3e4f5a6b7c8d",
    developer: {
      name: "Microsoft Corporation",
      websiteUrl: "https://www.microsoft.com/en-us/copilot/features/cowork",
      privacyUrl: "https://privacy.microsoft.com/privacystatement",
      termsOfUseUrl: "https://www.microsoft.com/servicesagreement",
    },
    name: { short: "Demo Plugin", full: "Demo Plugin for Tests" },
    description: { short: "Demo plugin used by the tooling tests.", full: FULL_DESCRIPTION },
    icons: { color: "color.png", outline: "outline.png" },
    accentColor: "#0F6CBD",
    agentSkills: skills.map((name) => ({ folder: `./skills/${name}` })),
  };
}

/**
 * A valid MOS3 submission at `<root>/submissions/professional-services/<slug>/`, with the
 * source-only material a package must leave out (README, demo data, tests, root references…).
 */
export function makeMos3Submission(root: string, slug = "demo-plugin", version = "1.2.3"): string {
  const dir = join(root, "submissions", "professional-services", slug);
  write(
    join(dir, "metadata.json"),
    JSON.stringify(
      {
        name: "Demo Plugin",
        description: "A demo plugin.",
        industry: "Professional Services",
        platforms: ["Cowork"],
        tags: ["demo"],
        author: "Tests",
        version,
        createdAt: "2026-10-01",
        updatedAt: "2026-10-02",
        packageFormat: "mos3",
      },
      null,
      2,
    ),
  );
  write(join(dir, "manifest.json"), JSON.stringify(validManifest(version), null, 2));
  write(join(dir, "color.png"), colorIcon());
  write(join(dir, "outline.png"), outlineIcon());
  for (const name of ["alpha-skill", "beta-skill"]) {
    write(join(dir, "skills", name, "SKILL.md"), skillMd(name, version));
    write(join(dir, "skills", name, "scripts", "engine.py"), "import json\nprint(json.dumps({'ok': True}))\n");
    write(join(dir, "skills", name, "references", "rules.md"), "# Rules\nSee ../references/rules.md\n");
  }
  write(join(dir, "skills", "alpha-skill", "scripts", "__pycache__", "engine.cpython-312.pyc"), "litter");
  write(join(dir, "README.md"), "# Demo\n");
  write(join(dir, "CHANGELOG.md"), "# Changelog\n");
  write(join(dir, "listing-metadata.md"), "listing\n");
  write(join(dir, "demo-data", "scenario.json"), "{}\n");
  write(join(dir, "tests", "run_tests.py"), "print('ok')\n");
  write(join(dir, "references", "shared.md"), "# Shared\n");
  write(join(dir, "contracts", "contract.json"), "{}\n");
  write(join(dir, "config", "settings.json"), "{}\n");
  write(join(dir, "scripts", "tool.py"), "pass\n");
  return dir;
}
