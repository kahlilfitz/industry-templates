/**
 * MOS3 Microsoft 365 app package support: validation and packaging for submissions that set
 * `"packageFormat": "mos3"` in metadata.json.
 *
 * The rules follow the "Building a Cowork Plugin — Partner Team Guide", with the manifest format
 * Cowork's package validation requires (devPreview schema with a `packageName`): `manifest.json` at the ZIP root, the two icons next to it, and one canonical Agent Skill per
 * `skills/<name>/` folder. Nothing else ships: README, demo data and tests stay in the submission
 * folder (`demo-data\`, `tests\`) outside the package.
 */
import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, posix } from "node:path";
import { inflateSync } from "node:zlib";
import { isBuildLitter, walkNoFollow, writeReproducibleZip } from "./package-files.js";

export const MOS3_SCHEMA =
  "https://developer.microsoft.com/json-schemas/teams/vDevPreview/MicrosoftTeams.schema.json";
export const MOS3_MANIFEST_VERSION = "devPreview";
/** devPreview schema: reverse-domain notation, at most 64 characters. */
export const MOS3_PACKAGE_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$/;
export const MOS3_PACKAGE_NAME_MAX = 64;
export const MOS3_DEVELOPER_NAME = "Microsoft Corporation";

/** The four links the Partner Team Guide requires at the end of `description.full`, in order. */
export const MOS3_REQUIRED_LINKS: ReadonlyArray<readonly [string, string]> = [
  ["Sign up", "https://www.microsoft.com/en-us/copilot/pricing/enterprise"],
  ["Get started", "https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-cowork"],
  ["Help", "https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/use-cowork"],
  ["Contact us", "https://support.microsoft.com/home/contact"],
];

export const MOS3_ALLOWED_MANIFEST_KEYS = new Set([
  "$schema",
  "manifestVersion",
  "packageName",
  "version",
  "id",
  "developer",
  "name",
  "description",
  "icons",
  "accentColor",
  "agentSkills",
  "localizationInfo",
  "agentConnectors",
]);

export const SKILL_FRONTMATTER_KEYS = new Set([
  "name",
  "description",
  "license",
  "compatibility",
  "metadata",
  "allowed-tools",
]);

export const MAX_AGENT_SKILLS = 20;
export const MAX_SKILL_NAME = 64;
export const MAX_DESCRIPTION = 1024;
export const WARN_DESCRIPTION = 800;
export const MAX_COMPATIBILITY = 500;
export const WARN_BODY_WORDS = 2000;
export const MAX_COMPANION_FILES = 20;
export const MAX_COMPANION_FILE_BYTES = 5 * 1024 * 1024;
export const MAX_COMPANION_TOTAL_BYTES = 10 * 1024 * 1024;

const PACKAGE_ROOT_FILES = ["manifest.json", "color.png", "outline.png"] as const;
const KEBAB = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MANIFEST_SEMVER = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;

export type Mos3Result = { errors: string[]; warnings: string[] };

// --- PNG ---------------------------------------------------------------------------------------

export type DecodedPng = { width: number; height: number; rgba: Uint8Array };

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

/**
 * Decode a non-interlaced 8-bit RGB or RGBA PNG into RGBA pixels. Anything else (palette,
 * greyscale, 16-bit, interlaced) is rejected with a message saying how to re-export it.
 */
export function decodePng(data: Buffer): DecodedPng {
  if (data.length < 8 || !data.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Error("is not a PNG file (bad signature)");
  }
  let offset = 8;
  let header: { width: number; height: number; bitDepth: number; colorType: number; interlace: number } | undefined;
  let transparentKey: [number, number, number] | undefined;
  const idat: Buffer[] = [];
  let ended = false;
  while (offset < data.length) {
    if (offset + 12 > data.length) throw new Error("is truncated (incomplete chunk)");
    const length = data.readUInt32BE(offset);
    const type = data.toString("latin1", offset + 4, offset + 8);
    const end = offset + 12 + length;
    if (end > data.length) throw new Error(`is truncated (chunk ${type} runs past the end)`);
    const body = data.subarray(offset + 8, offset + 8 + length);
    if (crc32(data.subarray(offset + 4, offset + 8 + length)) !== data.readUInt32BE(offset + 8 + length)) {
      throw new Error(`is corrupt (CRC mismatch in chunk ${type})`);
    }
    if (!header && type !== "IHDR") throw new Error("is malformed (first chunk is not IHDR)");
    if (type === "IHDR") {
      if (length !== 13) throw new Error("is malformed (IHDR length)");
      header = {
        width: body.readUInt32BE(0),
        height: body.readUInt32BE(4),
        bitDepth: body[8],
        colorType: body[9],
        interlace: body[12],
      };
      if (body[10] !== 0 || body[11] !== 0) throw new Error("uses an unknown compression or filter method");
    } else if (type === "tRNS" && header?.colorType === 2 && length === 6) {
      transparentKey = [body.readUInt16BE(0), body.readUInt16BE(2), body.readUInt16BE(4)];
    } else if (type === "IDAT") {
      idat.push(body);
    } else if (type === "IEND") {
      ended = true;
      break;
    }
    offset = end;
  }
  if (!header) throw new Error("is malformed (no IHDR chunk)");
  if (!ended) throw new Error("is truncated (no IEND chunk)");
  const { width, height, bitDepth, colorType, interlace } = header;
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(
      `uses bit depth ${bitDepth} and color type ${colorType}; only 8-bit RGB (type 2) or RGBA ` +
        "(type 6) PNGs are supported — re-export it as 8-bit RGBA",
    );
  }
  if (interlace !== 0) throw new Error("is interlaced; re-export it as a non-interlaced PNG");
  if (width === 0 || height === 0) throw new Error("has a zero width or height");

  const channels = colorType === 6 ? 4 : 3;
  const stride = width * channels;
  let raw: Buffer;
  try {
    raw = inflateSync(Buffer.concat(idat));
  } catch (error) {
    throw new Error(`has corrupt image data (${(error as Error).message})`);
  }
  if (raw.length !== height * (stride + 1)) {
    throw new Error(`has ${raw.length} bytes of image data; expected ${height * (stride + 1)}`);
  }

  const pixels = new Uint8Array(height * stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const out = y * stride;
    const prev = y * stride - stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? pixels[out + x - channels] : 0;
      const b = y > 0 ? pixels[prev + x] : 0;
      const c = x >= channels && y > 0 ? pixels[prev + x - channels] : 0;
      let predictor: number;
      switch (filter) {
        case 0:
          predictor = 0;
          break;
        case 1:
          predictor = a;
          break;
        case 2:
          predictor = b;
          break;
        case 3:
          predictor = (a + b) >> 1;
          break;
        case 4: {
          const p = a + b - c;
          const pa = Math.abs(p - a);
          const pb = Math.abs(p - b);
          const pc = Math.abs(p - c);
          predictor = pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
          break;
        }
        default:
          throw new Error(`has an unknown row filter type ${filter} on row ${y}`);
      }
      pixels[out + x] = (line[x] + predictor) & 0xff;
    }
  }

  if (channels === 4) return { width, height, rgba: pixels };
  const rgba = new Uint8Array(width * height * 4);
  for (let i = 0, j = 0; i < pixels.length; i += 3, j += 4) {
    rgba[j] = pixels[i];
    rgba[j + 1] = pixels[i + 1];
    rgba[j + 2] = pixels[i + 2];
    const keyed =
      transparentKey !== undefined &&
      pixels[i] === transparentKey[0] &&
      pixels[i + 1] === transparentKey[1] &&
      pixels[i + 2] === transparentKey[2];
    rgba[j + 3] = keyed ? 0 : 255;
  }
  return { width, height, rgba };
}

/** Problems with the two package icons, as messages naming the file. */
export function checkIcons(dir: string): string[] {
  const problems: string[] = [];
  const load = (file: string): DecodedPng | undefined => {
    const path = join(dir, file);
    if (!existsSync(path)) {
      problems.push(`${file} is missing at the submission root`);
      return undefined;
    }
    try {
      return decodePng(readFileSync(path));
    } catch (error) {
      problems.push(`${file} ${(error as Error).message}`);
      return undefined;
    }
  };

  const color = load("color.png");
  if (color && (color.width !== 192 || color.height !== 192)) {
    problems.push(`color.png must be 192x192 pixels; it is ${color.width}x${color.height}`);
  }

  const outline = load("outline.png");
  if (outline) {
    if (outline.width !== 32 || outline.height !== 32) {
      problems.push(`outline.png must be 32x32 pixels; it is ${outline.width}x${outline.height}`);
    } else {
      let transparent = 0;
      let visible = 0;
      let notWhite = 0;
      let firstNotWhite = "";
      for (let i = 0; i < outline.rgba.length; i += 4) {
        if (outline.rgba[i + 3] === 0) {
          transparent++;
          continue;
        }
        visible++;
        if (outline.rgba[i] !== 255 || outline.rgba[i + 1] !== 255 || outline.rgba[i + 2] !== 255) {
          if (!notWhite) {
            const pixel = i / 4;
            firstNotWhite = ` (first at x=${pixel % 32}, y=${Math.floor(pixel / 32)})`;
          }
          notWhite++;
        }
      }
      if (!transparent) problems.push("outline.png must have a transparent background; no pixel is transparent");
      if (!visible) problems.push("outline.png is fully transparent; it needs a white outline");
      if (notWhite) {
        problems.push(
          `outline.png must be white on transparent; ${notWhite} visible pixel(s) are not white${firstNotWhite}`,
        );
      }
    }
  }
  return problems;
}

// --- SKILL.md frontmatter -----------------------------------------------------------------------

export type Frontmatter = { data: Record<string, unknown>; body: string; bodyStartLine: number };

function unquote(value: string, where: string): string {
  if (value.startsWith('"')) {
    if (!value.endsWith('"') || value.length < 2) throw new Error(`${where}: unterminated double-quoted string`);
    try {
      return JSON.parse(value) as string;
    } catch {
      return value
        .slice(1, -1)
        .replace(/\\(["\\/])/g, "$1")
        .replace(/\\n/g, "\n")
        .replace(/\\t/g, "\t");
    }
  }
  if (value.startsWith("'")) {
    if (!value.endsWith("'") || value.length < 2) throw new Error(`${where}: unterminated single-quoted string`);
    return value.slice(1, -1).replace(/''/g, "'");
  }
  return value.replace(/\s+#.*$/, "").trim();
}

function parseScalarOrFlow(value: string, where: string): unknown {
  const trimmed = value.trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    const inner = trimmed.slice(1, -1).trim();
    return inner ? inner.split(",").map((item) => unquote(item.trim(), where)) : [];
  }
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    const out: Record<string, unknown> = {};
    const inner = trimmed.slice(1, -1).trim();
    if (!inner) return out;
    for (const pair of inner.split(",")) {
      const m = pair.match(/^\s*([^:]+?)\s*:\s*(.*?)\s*$/);
      if (!m) throw new Error(`${where}: malformed flow mapping`);
      out[unquote(m[1], where)] = unquote(m[2], where);
    }
    return out;
  }
  return plainScalar(trimmed, where);
}

/** YAML 1.2 core-schema typing for an unquoted scalar, so `false` or `1.0` are not read as text. */
function plainScalar(value: string, where: string): unknown {
  if (value.startsWith('"') || value.startsWith("'")) return unquote(value, where);
  const text = unquote(value, where);
  if (/^(?:~|null|Null|NULL)$/.test(text)) return null;
  if (/^(?:true|True|TRUE)$/.test(text)) return true;
  if (/^(?:false|False|FALSE)$/.test(text)) return false;
  if (/^[-+]?(?:\d+|\d*\.\d+|\d+\.\d*)(?:[eE][-+]?\d+)?$|^0x[0-9a-fA-F]+$|^0o[0-7]+$/.test(text)) return Number(text);
  return text;
}

function blockScalar(indicator: string, lines: string[]): string {
  const nonBlank = lines.filter((l) => l.trim());
  const indent = Math.min(...nonBlank.map((l) => l.match(/^ */)![0].length));
  const stripped = lines.map((l) => (l.trim() ? l.slice(indent) : ""));
  let text: string;
  if (indicator.startsWith("|")) text = stripped.join("\n");
  else {
    text = "";
    for (const line of stripped) {
      if (!line) text += "\n";
      else text += text && !text.endsWith("\n") ? ` ${line}` : line;
    }
  }
  return indicator.includes("-") ? text.replace(/\n+$/, "") : `${text.replace(/\n+$/, "")}\n`;
}

/**
 * Parse SKILL.md frontmatter. Supports the YAML subset skills use: top-level `key: value`, quoted
 * and plain scalars (including multi-line ones), `>`/`|` block scalars, flow `[a, b]` lists,
 * `- item` lists and one level of nested mapping (for `metadata`). Throws on anything malformed.
 */
export function parseFrontmatter(raw: string): Frontmatter {
  const text = raw.replace(/^\uFEFF/, "");
  const lines = text.split(/\r?\n/);
  if (lines[0] !== "---") throw new Error("does not start with a `---` frontmatter block");
  const close = lines.indexOf("---", 1);
  if (close < 0) throw new Error("has no closing `---` for its frontmatter");

  const data: Record<string, unknown> = {};
  const groups: Array<{ key: string; head: string; line: number; rest: string[] }> = [];
  for (let i = 1; i < close; i++) {
    const line = lines[i];
    if (!line.trim() || /^#/.test(line)) {
      if (groups.length) groups[groups.length - 1].rest.push(line);
      continue;
    }
    if (/^\s/.test(line)) {
      if (!groups.length) throw new Error(`frontmatter line ${i + 1} is indented before any key`);
      groups[groups.length - 1].rest.push(line);
      continue;
    }
    const m = line.match(/^([^\s:#][^:]*?)\s*:(?:\s+(.*)|\s*)$/);
    if (!m) throw new Error(`frontmatter line ${i + 1} is not valid YAML: ${line.trim()}`);
    groups.push({ key: m[1], head: (m[2] ?? "").trim(), line: i + 1, rest: [] });
  }

  for (const { key, head, line, rest } of groups) {
    const where = `frontmatter key "${key}" (line ${line})`;
    if (Object.prototype.hasOwnProperty.call(data, key)) throw new Error(`${where} is duplicated`);
    while (rest.length && !rest[rest.length - 1].trim()) rest.pop();
    const content = rest.filter((l) => l.trim() && !/^\s*#/.test(l));
    if (/^[>|][-+]?\d?$/.test(head)) {
      data[key] = blockScalar(head, rest);
    } else if (head) {
      const joined = [head, ...rest.map((l) => l.trim())].filter(Boolean).join(" ");
      data[key] = parseScalarOrFlow(joined, where);
    } else if (!content.length) {
      data[key] = null;
    } else if (content.every((l) => /^\s*-(\s|$)/.test(l))) {
      data[key] = content.map((l) => unquote(l.replace(/^\s*-\s*/, ""), where));
    } else {
      const indent = content[0].match(/^ */)![0].length;
      const nested: Record<string, unknown> = {};
      let last: string | undefined;
      for (const l of content) {
        const own = l.match(/^ */)![0].length;
        if (own > indent && last) {
          const previous = nested[last];
          nested[last] = typeof previous === "string" && previous ? `${previous} ${l.trim()}` : l.trim();
          continue;
        }
        if (own !== indent) throw new Error(`${where}: inconsistent indentation`);
        const nm = l.trim().match(/^([^\s:#][^:]*?)\s*:(?:\s+(.*)|\s*)$/);
        if (!nm) throw new Error(`${where}: nested line is not valid YAML: ${l.trim()}`);
        if (Object.prototype.hasOwnProperty.call(nested, nm[1])) {
          throw new Error(`${where}: nested key "${nm[1]}" is duplicated`);
        }
        nested[nm[1]] = nm[2] ? parseScalarOrFlow(nm[2], where) : "";
        last = nm[1];
      }
      data[key] = nested;
    }
  }
  return { data, body: lines.slice(close + 1).join("\n"), bodyStartLine: close + 2 };
}

// --- skills -------------------------------------------------------------------------------------

/** Text files only: a NUL byte in the first 8 KB marks a binary. */
function readText(path: string): string | undefined {
  const buffer = readFileSync(path);
  if (buffer.subarray(0, 8192).includes(0)) return undefined;
  return buffer.toString("utf8");
}

/**
 * `../` references in a skill file that resolve outside the skill folder. Paths are resolved
 * from the referencing file's own folder, so `scripts/x.py` may reach `../references/` but not
 * `../../references/`.
 */
export function findEscapingReferences(skillRel: string, text: string): Array<{ line: number; ref: string }> {
  const hits: Array<{ line: number; ref: string }> = [];
  const fileDir = posix.dirname(skillRel);
  text.split(/\r?\n/).forEach((content, index) => {
    for (const match of content.matchAll(/(?:\.\.[\\/])+[^\s'"`)\]>,;]*/g)) {
      // `../` inside an absolute URL (https://host/a/../b) is not a local path.
      const token = content.slice(0, match.index).match(/[^\s'"`(\[<,;]*$/)![0];
      if (/^[a-z][a-z0-9+.-]*:\/\//i.test(token)) continue;
      const ref = match[0];
      const resolved = posix.normalize(posix.join(fileDir, ref.replace(/\\/g, "/")));
      if (resolved === ".." || resolved.startsWith("../")) hits.push({ line: index + 1, ref });
    }
  });
  return hits;
}

function validateSkill(dir: string, name: string, version: string, out: Mos3Result): void {
  const skillDir = join(dir, "skills", name);
  const label = `skills/${name}`;
  const err = (message: string) => out.errors.push(`${label}: ${message}`);
  const warn = (message: string) => out.warnings.push(`${label}: ${message}`);

  const { files, symlinks } = walkNoFollow(skillDir);
  for (const link of symlinks) err(`${link} is a symbolic link; MOS3 packages cannot contain links`);
  const shipped = files.filter((rel) => !isBuildLitter(rel));

  const rootSkill = shipped.filter((rel) => rel === "SKILL.md");
  const nested = shipped.filter((rel) => rel !== "SKILL.md" && posix.basename(rel).toLowerCase() === "skill.md");
  if (rootSkill.length !== 1) err("must contain exactly one root SKILL.md (case-sensitive)");
  for (const rel of nested) err(`${rel} is a nested SKILL.md; each skill folder has exactly one, at its root`);

  if (!KEBAB.test(name)) {
    err("folder name must be kebab-case: lowercase a-z, 0-9 and single hyphens, no leading or trailing hyphen");
  }
  if (name.length > MAX_SKILL_NAME) err(`folder name is ${name.length} characters; the limit is ${MAX_SKILL_NAME}`);

  if (rootSkill.length === 1) {
    const raw = readFileSync(join(skillDir, "SKILL.md"), "utf8");
    let fm: Frontmatter | undefined;
    try {
      fm = parseFrontmatter(raw);
    } catch (error) {
      err(`SKILL.md ${(error as Error).message}`);
    }
    if (fm) {
      const { data, body } = fm;
      for (const key of Object.keys(data)) {
        if (!SKILL_FRONTMATTER_KEYS.has(key)) {
          err(
            `SKILL.md frontmatter key "${key}" is not allowed; use only ${[...SKILL_FRONTMATTER_KEYS].join(", ")} ` +
              "(put anything else under metadata)",
          );
        }
      }
      const skillName = data.name;
      if (skillName !== undefined && skillName !== null && typeof skillName !== "string") {
        err("SKILL.md name must be a string");
      } else if (typeof skillName !== "string" || !skillName) err("SKILL.md frontmatter needs a name");
      else if (skillName !== name) {
        err(`SKILL.md name "${skillName}" must equal its folder name "${name}" exactly (MOS3 rule ASKILL-P006)`);
      }
      const description = data.description;
      if (description !== undefined && description !== null && typeof description !== "string") {
        err("SKILL.md description must be a string (quote it if it reads as a YAML boolean or number)");
      } else if (typeof description !== "string" || !description.trim()) err("SKILL.md frontmatter needs a description");
      else if (description.length > MAX_DESCRIPTION) {
        err(`SKILL.md description is ${description.length} characters; the limit is ${MAX_DESCRIPTION}`);
      } else if (description.length > WARN_DESCRIPTION) {
        warn(`SKILL.md description is ${description.length} characters; the guide targets ${WARN_DESCRIPTION} or fewer`);
      }
      if (typeof description === "string" && description.trim()) {
        const exclusions = description.match(/Do NOT use for/g)?.length ?? 0;
        if (exclusions !== 1) {
          err(`SKILL.md description needs exactly one "Do NOT use for … (use <skill>)" line; found ${exclusions}`);
        }
        const triggers = description.match(/"[^"]+"/g)?.length ?? 0;
        if (triggers < 5) warn(`SKILL.md description quotes ${triggers} trigger phrase(s); the guide asks for 5 or more`);
      }
      if (data.compatibility !== undefined) {
        if (typeof data.compatibility !== "string") err("SKILL.md compatibility must be a string");
        else if (data.compatibility.length > MAX_COMPATIBILITY) {
          err(`SKILL.md compatibility is ${data.compatibility.length} characters; the limit is ${MAX_COMPATIBILITY}`);
        }
      }
      const metadata = data.metadata;
      if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
        err("SKILL.md frontmatter needs a metadata mapping with icon and version");
      } else {
        const m = metadata as Record<string, unknown>;
        if (typeof m.icon !== "string" || !m.icon.trim()) {
          err("SKILL.md metadata.icon is required (a Fluent icon ID); the manifest has no per-skill icons");
        }
        if (typeof m.version !== "string" || m.version !== version) {
          err(
            `SKILL.md metadata.version is ${typeof m.version === "string" ? `"${m.version}"` : `${String(m.version ?? "missing")} (not a string)`}; ` +
              `it must be the string "${version}", the plugin version`,
          );
        }
      }
      const words = body.split(/\s+/).filter(Boolean).length;
      if (words > WARN_BODY_WORDS) {
        warn(`SKILL.md body is ${words} words; the guide targets ${WARN_BODY_WORDS} or fewer (move detail to references/)`);
      }
    }
  }

  const companions = shipped.filter((rel) => rel !== "SKILL.md");
  if (companions.length > MAX_COMPANION_FILES) {
    err(`has ${companions.length} companion files besides SKILL.md; the limit is ${MAX_COMPANION_FILES}`);
  }
  let total = 0;
  for (const rel of companions) {
    const size = statSync(join(skillDir, ...rel.split("/"))).size;
    total += size;
    if (size > MAX_COMPANION_FILE_BYTES) err(`${rel} is ${size} bytes; each companion file is limited to 5 MB`);
  }
  if (total > MAX_COMPANION_TOTAL_BYTES) {
    err(`companion files total ${total} bytes; the combined limit is 10 MB`);
  }

  for (const rel of shipped.filter((r) => r === "SKILL.md" || r.startsWith("scripts/"))) {
    const text = readText(join(skillDir, ...rel.split("/")));
    if (text === undefined) continue;
    for (const { line, ref } of findEscapingReferences(rel, text)) {
      err(
        `${rel}:${line} references "${ref}", which points outside the skill folder; ` +
          "keep the files a skill needs inside skills/<name>/",
      );
    }
  }
}

// --- manifest -----------------------------------------------------------------------------------

function isHttpsUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

/** True when `text` ends with the four required "Label: URL" links, in order. */
export function endsWithRequiredLinks(text: string): boolean {
  const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
  const pattern = MOS3_REQUIRED_LINKS.map(([label, url]) => `${escape(label)}:[ \\t]*${escape(url)}`).join("\\s+");
  return new RegExp(`(?:^|\\s)${pattern}\\s*$`).test(text);
}

function validateManifest(manifest: Record<string, unknown>, version: string, skillFolders: string[], out: Mos3Result) {
  const err = (message: string) => out.errors.push(`manifest.json: ${message}`);

  for (const key of Object.keys(manifest)) {
    if (MOS3_ALLOWED_MANIFEST_KEYS.has(key)) continue;
    if (/starter/i.test(key)) {
      err(`"${key}" is not allowed; the manifest has no conversation starters (keep them in the metadata template)`);
    } else {
      err(`unknown top-level key "${key}"; allowed keys are ${[...MOS3_ALLOWED_MANIFEST_KEYS].join(", ")}`);
    }
  }
  if (manifest.$schema !== MOS3_SCHEMA) err(`$schema must be exactly ${MOS3_SCHEMA} (Cowork's package validation requires devPreview)`);
  if (manifest.manifestVersion !== MOS3_MANIFEST_VERSION) err(`manifestVersion must be "${MOS3_MANIFEST_VERSION}"`);
  if (typeof manifest.packageName !== "string" || !manifest.packageName.trim()) {
    err("packageName is required (reverse-domain notation, for example com.microsoft.cowork.<slug>)");
  } else if (manifest.packageName.length > MOS3_PACKAGE_NAME_MAX) {
    err(`packageName is ${manifest.packageName.length} characters; it must be ${MOS3_PACKAGE_NAME_MAX} or fewer`);
  } else if (!MOS3_PACKAGE_NAME.test(manifest.packageName)) {
    err("packageName must be lowercase reverse-domain notation, for example com.microsoft.cowork.<slug>");
  }
  if (typeof manifest.id !== "string" || !GUID.test(manifest.id)) err("id must be a GUID, not a text slug");
  if (typeof manifest.version !== "string" || !MANIFEST_SEMVER.test(manifest.version)) {
    err("version must be a MAJOR.MINOR.PATCH string");
  } else if (manifest.version !== version) {
    err(`version ${manifest.version} must equal metadata.json version ${version}`);
  }

  const developer = manifest.developer as Record<string, unknown> | undefined;
  if (!developer || typeof developer !== "object") err("developer is required");
  else {
    if (developer.name !== MOS3_DEVELOPER_NAME) {
      err(`developer.name must be exactly "${MOS3_DEVELOPER_NAME}"; got ${JSON.stringify(developer.name)}`);
    }
    for (const field of ["websiteUrl", "privacyUrl", "termsOfUseUrl"]) {
      if (!isHttpsUrl(developer[field])) err(`developer.${field} must be an https:// URL`);
    }
  }

  const name = manifest.name as Record<string, unknown> | undefined;
  const description = manifest.description as Record<string, unknown> | undefined;
  const limited = (
    parent: Record<string, unknown> | undefined,
    path: string,
    field: string,
    max: number,
    inclusive: boolean,
  ) => {
    const value = parent?.[field];
    if (typeof value !== "string" || !value.trim()) {
      err(`${path}.${field} is required`);
      return undefined;
    }
    if (inclusive ? value.length > max : value.length >= max) {
      err(`${path}.${field} is ${value.length} characters; it must be ${inclusive ? `${max} or fewer` : `under ${max}`}`);
    }
    return value;
  };
  limited(name, "name", "short", 30, true);
  limited(name, "name", "full", 100, true);
  limited(description, "description", "short", 80, true);
  const full = limited(description, "description", "full", 4000, false);
  if (full !== undefined && !endsWithRequiredLinks(full)) {
    err(
      "description.full must end with the four links, in order: " +
        MOS3_REQUIRED_LINKS.map(([label, url]) => `${label}: ${url}`).join(" | "),
    );
  }

  const icons = manifest.icons as Record<string, unknown> | undefined;
  if (icons?.color !== "color.png") err('icons.color must be "color.png"');
  if (icons?.outline !== "outline.png") err('icons.outline must be "outline.png"');
  if (typeof manifest.accentColor !== "string" || !/^#[0-9A-Fa-f]{6}$/.test(manifest.accentColor)) {
    err("accentColor is required and must be #RRGGBB");
  }

  const agentSkills = manifest.agentSkills;
  if (!Array.isArray(agentSkills) || agentSkills.length === 0) {
    err("agentSkills must be a non-empty array of { \"folder\": \"skills/<name>\" }");
    return;
  }
  if (agentSkills.length > MAX_AGENT_SKILLS) {
    err(`agentSkills lists ${agentSkills.length} skills; the limit is ${MAX_AGENT_SKILLS}`);
  }
  const listed: string[] = [];
  agentSkills.forEach((entry, index) => {
    const keys = entry && typeof entry === "object" && !Array.isArray(entry) ? Object.keys(entry) : [];
    if (keys.length !== 1 || keys[0] !== "folder") {
      err(`agentSkills[${index}] must be an object with only "folder" (descriptions and icons come from SKILL.md)`);
      return;
    }
    const folder = (entry as { folder: unknown }).folder;
    const m = typeof folder === "string" ? folder.match(/^(?:\.\/)?skills\/([^/]+)$/) : null;
    if (!m) {
      err(`agentSkills[${index}].folder must be "./skills/<name>" or "skills/<name>"; got ${JSON.stringify(folder)}`);
      return;
    }
    if (listed.includes(m[1])) err(`agentSkills lists skills/${m[1]} more than once`);
    else listed.push(m[1]);
  });
  for (const folder of skillFolders) {
    if (!listed.includes(folder)) err(`skills/${folder}/ exists but is not listed in agentSkills`);
  }
  for (const folder of listed) {
    if (!skillFolders.includes(folder)) err(`agentSkills lists skills/${folder}, which is not a folder under skills/`);
  }
}

// --- submission ---------------------------------------------------------------------------------

/** The skill folders of a MOS3 submission, sorted. */
function skillFolderNames(dir: string): string[] {
  const skillsDir = join(dir, "skills");
  if (!existsSync(skillsDir)) return [];
  return readdirSync(skillsDir)
    .filter((entry) => lstatSync(join(skillsDir, entry)).isDirectory())
    .sort();
}

/** Every check a MOS3 submission must pass before it can be packaged. */
export function validateMos3Submission(dir: string, meta: Record<string, unknown>): Mos3Result {
  const out: Mos3Result = { errors: [], warnings: [] };
  const err = (message: string) => out.errors.push(message);

  const version = typeof meta.version === "string" ? meta.version.trim() : "";
  if (!version) err("metadata.json version is required for a MOS3 package (it must equal manifest.json version)");
  if (meta.bundleTests !== undefined) {
    err("bundleTests is not allowed with packageFormat mos3; tests and demo data stay in the submission folder, outside the package");
  }
  if (existsSync(join(dir, ".claude-plugin"))) {
    err(".claude-plugin/ must be removed; a MOS3 package is described by manifest.json at the submission root");
  }

  for (const file of PACKAGE_ROOT_FILES) {
    const path = join(dir, file);
    if (existsSync(path) && lstatSync(path).isSymbolicLink()) err(`${file} is a symbolic link; MOS3 packages cannot contain links`);
  }

  const skillsDir = join(dir, "skills");
  if (!existsSync(skillsDir)) {
    err("skills/ is missing; a MOS3 package needs at least one skills/<name>/SKILL.md");
  } else if (lstatSync(skillsDir).isSymbolicLink()) {
    err("skills/ is a symbolic link; MOS3 packages cannot contain links");
  } else {
    for (const entry of readdirSync(skillsDir).sort()) {
      const stat = lstatSync(join(skillsDir, entry));
      if (stat.isSymbolicLink()) err(`skills/${entry} is a symbolic link; MOS3 packages cannot contain links`);
      else if (!stat.isDirectory() && !isBuildLitter(entry)) err(`skills/${entry} is a file; skills/ may contain only skill folders`);
    }
  }
  const folders = skillFolderNames(dir);
  if (existsSync(skillsDir) && folders.length === 0) err("skills/ has no skill folders");

  const manifestPath = join(dir, "manifest.json");
  if (!existsSync(manifestPath)) {
    err("manifest.json is missing at the submission root");
  } else {
    let manifest: unknown;
    try {
      manifest = JSON.parse(readFileSync(manifestPath, "utf8").replace(/^\uFEFF/, ""));
    } catch (error) {
      err(`manifest.json is not valid JSON — ${(error as Error).message}`);
    }
    if (manifest !== undefined) {
      if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) err("manifest.json must be a JSON object");
      else validateManifest(manifest as Record<string, unknown>, version, folders, out);
    }
  }

  for (const problem of checkIcons(dir)) err(problem);
  for (const folder of folders) validateSkill(dir, folder, version, out);
  return out;
}

/** The files a MOS3 package ships, as ZIP-root entry names: the manifest, both icons and skills/**. */
export function mos3PackageEntries(dir: string): string[] {
  const skills = walkNoFollow(join(dir, "skills"))
    .files.filter((rel) => !isBuildLitter(rel))
    .map((rel) => `skills/${rel}`);
  return [...PACKAGE_ROOT_FILES, ...skills].sort();
}

/** Write the MOS3 package for a validated submission. Entries sit at the ZIP root. */
export function buildMos3Zip(dir: string, outPath: string, stamp: Date): void {
  writeReproducibleZip(
    mos3PackageEntries(dir).map((name) => ({ name, path: join(dir, ...name.split("/")) })),
    outPath,
    stamp,
  );
}
