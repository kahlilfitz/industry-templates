import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import AdmZip from "adm-zip";
import { sha256 } from "./evaluation-workflow.js";
import {
  MOS3_REQUIRED_LINKS,
  decodePng,
  endsWithRequiredLinks,
  findEscapingReferences,
  mos3PackageEntries,
  parseFrontmatter,
  validateMos3Submission,
} from "./mos3-package.js";
import { encodePng, makeMos3Submission, skillMd, validManifest, write } from "./test-fixtures.js";

const REPO = join(import.meta.dirname, "..");
const TSX = join(REPO, "node_modules", "tsx", "dist", "cli.mjs");
const IMPORTER = join(REPO, "scripts", "import-submissions.ts");

const EXPECTED_ENTRIES = [
  "color.png",
  "manifest.json",
  "outline.png",
  "skills/alpha-skill/SKILL.md",
  "skills/alpha-skill/references/rules.md",
  "skills/alpha-skill/scripts/engine.py",
  "skills/beta-skill/SKILL.md",
  "skills/beta-skill/references/rules.md",
  "skills/beta-skill/scripts/engine.py",
];

function withRoot(fn: (root: string, dir: string) => void): void {
  const root = mkdtempSync(join(tmpdir(), "mos3-"));
  try {
    fn(root, makeMos3Submission(root));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

function validate(dir: string) {
  return validateMos3Submission(dir, JSON.parse(readFileSync(join(dir, "metadata.json"), "utf8")));
}

function editJson(path: string, edit: (value: Record<string, any>) => void): void {
  const value = JSON.parse(readFileSync(path, "utf8"));
  edit(value);
  writeFileSync(path, JSON.stringify(value, null, 2));
}

function importer(cwd: string, ...args: string[]) {
  return spawnSync(process.execPath, [TSX, IMPORTER, ...args], { cwd, encoding: "utf8" });
}

function expectError(mutate: (dir: string) => void, pattern: RegExp): void {
  withRoot((_root, dir) => {
    mutate(dir);
    const { errors } = validate(dir);
    assert.ok(
      errors.some((e) => pattern.test(e)),
      `expected an error matching ${pattern}; got:\n${errors.join("\n") || "(no errors)"}`,
    );
  });
}

test("a valid MOS3 submission passes and packages only manifest, icons and skills", () => {
  withRoot((_root, dir) => {
    assert.deepEqual(validate(dir), { errors: [], warnings: [] });
    assert.deepEqual(mos3PackageEntries(dir), EXPECTED_ENTRIES);
  });
});

test("the importer builds a root-level, reproducible MOS3 ZIP and leaves source-only files out", () => {
  withRoot((root) => {
    const check = importer(root, "--check");
    assert.equal(check.status, 0, check.stderr + check.stdout);
    assert.match(check.stdout, /demo-plugin — Professional Services · mos3 plugin · 2 skills/);
    assert.equal(existsSync(join(root, "public")), false, "--check must not write");

    const first = importer(root);
    assert.equal(first.status, 0, first.stderr + first.stdout);
    const zipPath = join(root, "public", "bundles", "demo-plugin.zip");
    const digest = sha256(zipPath);
    const zip = new AdmZip(zipPath);
    const entries = zip.getEntries();
    assert.deepEqual(entries.map((e) => e.entryName).sort(), EXPECTED_ENTRIES);
    assert.ok(entries.every((e) => !e.entryName.startsWith("demo-plugin/")), "no wrapper folder");
    assert.ok(entries.every((e) => [0, 8].includes(e.header.method)), "only Store or Deflate");
    assert.equal(new Set(entries.map((e) => e.header.time.getTime())).size, 1, "one fixed timestamp");
    assert.equal(
      zip.readAsText("manifest.json"),
      readFileSync(join(root, "submissions", "professional-services", "demo-plugin", "manifest.json"), "utf8"),
    );

    const second = importer(root);
    assert.equal(second.status, 0, second.stderr);
    assert.equal(sha256(zipPath), digest, "rebuilding unchanged input is byte-identical");
  });
});

test("the catalog export keeps working for MOS3 submissions", () => {
  withRoot((root) => {
    const catalog = mkdtempSync(join(tmpdir(), "mos3-catalog-"));
    try {
      const result = importer(root, "--catalog-output", catalog);
      assert.equal(result.status, 0, result.stderr);
      assert.ok(existsSync(join(catalog, "demo-plugin-alpha-skill", "SKILL.md")));
      assert.ok(existsSync(join(catalog, "demo-plugin-beta-skill", "scripts", "engine.py")));
      assert.equal(existsSync(join(catalog, "demo-plugin-alpha-skill", "scripts", "__pycache__")), false);
    } finally {
      rmSync(catalog, { recursive: true, force: true });
    }
  });
});

test("the importer fails a bad MOS3 submission and an unknown packageFormat with clear messages", () => {
  withRoot((root, dir) => {
    mkdirSync(join(dir, ".claude-plugin"));
    writeFileSync(join(dir, ".claude-plugin", "plugin.json"), "{}");
    const result = importer(root, "--check");
    assert.equal(result.status, 1);
    assert.match(result.stderr, /demo-plugin: \.claude-plugin\/ must be removed/);

    rmSync(join(dir, ".claude-plugin"), { recursive: true });
    editJson(join(dir, "metadata.json"), (m) => (m.packageFormat = "teams"));
    const unknown = importer(root, "--check");
    assert.equal(unknown.status, 1);
    assert.match(unknown.stderr, /packageFormat must be "mos3" or omitted/);
  });
});

test("manifest rules: schema, developer, links, identity, keys and agentSkills", () => {
  const manifest = (edit: (m: Record<string, any>) => void) => (dir: string) => editJson(join(dir, "manifest.json"), edit);
  expectError(manifest((m) => (m.$schema = m.$schema.replace("vDevPreview", "v1.28"))), /\$schema must be exactly/);
  expectError(manifest((m) => (m.manifestVersion = "1.28")), /manifestVersion must be "devPreview"/);
  expectError(manifest((m) => delete m.packageName), /packageName is required/);
  expectError(manifest((m) => (m.packageName = `com.microsoft.${"x".repeat(51)}`)), /packageName is 65 characters/);
  expectError(manifest((m) => (m.packageName = "DemoPlugin")), /packageName must be lowercase reverse-domain/);
  expectError(manifest((m) => (m.developer.name = "Microsoft")), /developer\.name must be exactly "Microsoft Corporation"/);
  expectError(manifest((m) => (m.developer.privacyUrl = "http://example.com")), /developer\.privacyUrl must be an https/);
  expectError(manifest((m) => (m.id = "demo-plugin")), /id must be a GUID/);
  expectError(manifest((m) => (m.version = "1.2.4")), /version 1\.2\.4 must equal metadata\.json version 1\.2\.3/);
  expectError(manifest((m) => (m.name.short = "x".repeat(31))), /name\.short is 31 characters/);
  expectError(manifest((m) => (m.description.short = "x".repeat(81))), /description\.short is 81 characters/);
  expectError(
    manifest((m) => (m.description.full = m.description.full.replace(/\nContact us: \S+$/, ""))),
    /description\.full must end with the four links/,
  );
  expectError(manifest((m) => (m.icons.outline = "icon-outline.png")), /icons\.outline must be "outline\.png"/);
  expectError(manifest((m) => (m.accentColor = "blue")), /accentColor is required and must be #RRGGBB/);
  expectError(manifest((m) => (m.conversationStarters = [{ text: "hi" }])), /no conversation starters/);
  expectError(manifest((m) => (m.bots = [])), /unknown top-level key "bots"/);
  expectError(manifest((m) => m.agentSkills.pop()), /skills\/beta-skill\/ exists but is not listed/);
  expectError(manifest((m) => m.agentSkills.push({ folder: "skills/alpha-skill" })), /lists skills\/alpha-skill more than once/);
  expectError(manifest((m) => (m.agentSkills[0].icon = "x")), /must be an object with only "folder"/);
  expectError(manifest((m) => (m.agentSkills[0].folder = "alpha-skill")), /must be "\.\/skills\/<name>" or "skills\/<name>"/);
  expectError(manifest((m) => (m.agentSkills = [])), /agentSkills must be a non-empty array/);
});

test("the four required links may be separated by newlines or spaces, in order only", () => {
  const lines = MOS3_REQUIRED_LINKS.map(([label, url]) => `${label}: ${url}`);
  assert.equal(endsWithRequiredLinks(`About.\n${lines.join("\n")}`), true);
  assert.equal(endsWithRequiredLinks(`About. ${lines.join(" ")}\n`), true);
  assert.equal(endsWithRequiredLinks(`About. ${[lines[1], lines[0], lines[2], lines[3]].join(" ")}`), false);
  assert.equal(endsWithRequiredLinks(`About. ${lines.join(" ")} Thanks.`), false);
});

test("metadata rules: bundleTests, leftover .claude-plugin and a missing version", () => {
  expectError((dir) => editJson(join(dir, "metadata.json"), (m) => (m.bundleTests = true)), /bundleTests is not allowed/);
  expectError((dir) => write(join(dir, ".claude-plugin", "plugin.json"), "{}"), /\.claude-plugin\/ must be removed/);
  expectError((dir) => editJson(join(dir, "metadata.json"), (m) => delete m.version), /metadata\.json version is required/);
});

test("icon rules: sizes, white-on-transparent outline and unsupported encodings", () => {
  const icon = (file: string, png: Buffer) => (dir: string) => writeFileSync(join(dir, file), png);
  expectError(icon("color.png", encodePng(96, 96, () => [1, 2, 3, 255])), /color\.png must be 192x192 pixels; it is 96x96/);
  expectError(
    icon("outline.png", encodePng(32, 32, (x) => (x < 16 ? [255, 0, 0, 255] : [0, 0, 0, 0]))),
    /outline\.png must be white on transparent; 512 visible pixel\(s\) are not white \(first at x=0, y=0\)/,
  );
  expectError(icon("outline.png", encodePng(32, 32, () => [255, 255, 255, 255])), /no pixel is transparent/);
  expectError(icon("outline.png", encodePng(32, 32, () => [0, 0, 0, 0])), /fully transparent/);
  expectError(
    icon("color.png", encodePng(192, 192, () => [1, 2, 3, 255], { colorType: 3 })),
    /color\.png uses bit depth 8 and color type 3; only 8-bit RGB/,
  );
  expectError(icon("color.png", encodePng(192, 192, () => [1, 2, 3, 255], { interlace: 1 })), /color\.png is interlaced/);
  expectError(icon("outline.png", Buffer.from("not a png")), /outline\.png is not a PNG file/);
  expectError((dir) => rmSync(join(dir, "color.png")), /color\.png is missing/);
});

test("decodePng unfilters every row filter and reads RGB as opaque", () => {
  const pixel = (x: number, y: number): [number, number, number, number] => [(x * 37) & 255, (y * 59) & 255, (x * y) & 255, (x + y) & 255];
  for (const filter of [0, 1, 2, 3, 4] as const) {
    const decoded = decodePng(encodePng(7, 5, pixel, { filter }));
    for (let y = 0; y < 5; y++) {
      for (let x = 0; x < 7; x++) {
        assert.deepEqual([...decoded.rgba.subarray((y * 7 + x) * 4, (y * 7 + x) * 4 + 4)], pixel(x, y), `filter ${filter}`);
      }
    }
  }
  const rgb = decodePng(encodePng(2, 2, () => [9, 8, 7, 0], { colorType: 2, filter: "cycle" }));
  assert.deepEqual([...rgb.rgba.subarray(0, 4)], [9, 8, 7, 255]);
});

test("skill rules: name/folder, frontmatter keys, icon, version, sizes and nesting", () => {
  const skill = (content: string) => (dir: string) => writeFileSync(join(dir, "skills", "alpha-skill", "SKILL.md"), content);
  expectError(skill(skillMd("alpha-skills")), /name "alpha-skills" must equal its folder name "alpha-skill"/);
  expectError(skill(skillMd("alpha-skill").replace("  icon: DocumentSearch\n", "")), /metadata\.icon is required/);
  expectError(skill(skillMd("alpha-skill", "1.2.2")), /metadata\.version is "1\.2\.2"; it must be the string "1\.2\.3", the plugin version/);
  expectError(skill(skillMd("alpha-skill").replace("license:", "version: 1\nlicense:")), /frontmatter key "version" is not allowed/);
  expectError(skill(skillMd("alpha-skill").replace("license: Proprietary", "compatibility: " + "x".repeat(501))), /compatibility is 501 characters/);
  expectError(skill(skillMd("alpha-skill").replace("description: >-", `description: "${"x".repeat(1025)}"\nx-ignored: >-`)), /description is 1025 characters/);
  expectError(skill("# no frontmatter\n"), /SKILL\.md does not start with a `---` frontmatter block/);
  expectError((dir) => write(join(dir, "skills", "alpha-skill", "nested", "SKILL.md"), skillMd("nested")), /nested\/SKILL\.md is a nested SKILL\.md/);
  expectError((dir) => rmSync(join(dir, "skills", "beta-skill", "SKILL.md")), /skills\/beta-skill: must contain exactly one root SKILL\.md/);
  expectError((dir) => write(join(dir, "skills", "Bad_Skill", "SKILL.md"), skillMd("Bad_Skill")), /skills\/Bad_Skill: folder name must be kebab-case/);
  expectError((dir) => write(join(dir, "skills", "notes.md"), "x"), /skills\/notes\.md is a file/);
  expectError(
    (dir) => {
      for (let i = 0; i < 19; i++) write(join(dir, "skills", "alpha-skill", "references", `r${i}.md`), "x");
    },
    /has 21 companion files besides SKILL\.md; the limit is 20/,
  );
  expectError(
    (dir) => write(join(dir, "skills", "alpha-skill", "references", "big.bin"), Buffer.alloc(5 * 1024 * 1024 + 1)),
    /references\/big\.bin is 5242881 bytes; each companion file is limited to 5 MB/,
  );
});

test("skill warnings: a description over 800 characters and a long body", () => {
  withRoot((_root, dir) => {
    const path = join(dir, "skills", "alpha-skill", "SKILL.md");
    const routing = `Use when asked "a1", "b2", "c3", "d4" or "e5". Do NOT use for other work (use beta-skill). `;
    writeFileSync(
      path,
      skillMd("alpha-skill").replace(/description: >-\n.*\n.*\n.*\n/, `description: '${routing}${"word ".repeat(150)}'\n`) +
        "word ".repeat(2001),
    );
    const { errors, warnings } = validate(dir);
    assert.deepEqual(errors, []);
    assert.equal(warnings.length, 2, warnings.join("\n"));
    assert.match(warnings[0], /description is \d+ characters; the guide targets 800 or fewer/);
    assert.match(warnings[1], /body is \d+ words; the guide targets 2000 or fewer/);
  });
});

test("skill routing: exactly one Do NOT use for line, and a warning under five quoted triggers", () => {
  const withDescription = (text: string) => (dir: string) =>
    writeFileSync(
      join(dir, "skills", "alpha-skill", "SKILL.md"),
      skillMd("alpha-skill").replace(/description: >-\n.*\n.*\n.*\n/, `description: '${text}'\n`),
    );
  expectError(
    withDescription(`Use when asked "a", "b", "c", "d" or "e". Do NOT use to draft (use beta-skill).`),
    /needs exactly one "Do NOT use for/,
  );
  expectError(
    withDescription(`Use when asked "a", "b", "c", "d" or "e". Do NOT use for x (use beta-skill). Do NOT use for y.`),
    /needs exactly one "Do NOT use for[^;]*; found 2/,
  );
  withRoot((_root, dir) => {
    withDescription(`Use when asked "a" or "b". Do NOT use for x (use beta-skill).`)(dir);
    const { errors, warnings } = validate(dir);
    assert.deepEqual(errors, []);
    assert.ok(warnings.some((w) => /quotes 2 trigger phrase\(s\); the guide asks for 5 or more/.test(w)), warnings.join("\n"));
  });
});

test("../ references that leave the skill folder are errors with file and line", () => {
  expectError(
    (dir) =>
      writeFileSync(
        join(dir, "skills", "alpha-skill", "scripts", "engine.py"),
        "import json\nRULES = open('../../references/shared.md').read()\n",
      ),
    /skills\/alpha-skill: scripts\/engine\.py:2 references "\.\.\/\.\.\/references\/shared\.md", which points outside the skill folder/,
  );
  expectError(
    (dir) =>
      writeFileSync(
        join(dir, "skills", "alpha-skill", "SKILL.md"),
        skillMd("alpha-skill") + "See [config](../../config/settings.json).\n",
      ),
    /SKILL\.md:\d+ references "\.\.\/\.\.\/config\/settings\.json"/,
  );
  assert.deepEqual(findEscapingReferences("scripts/engine.py", "open('../references/rules.md')"), []);
  assert.deepEqual(findEscapingReferences("scripts/engine.py", "x = r'..\\..\\config\\a.json'"), [
    { line: 1, ref: "..\\..\\config\\a.json" },
  ]);
  // `../` inside an absolute URL is a remote link, not a path out of the skill folder.
  assert.deepEqual(findEscapingReferences("SKILL.md", "See https://example.com/a/../../b and (http://x.test/../c)."), []);
  assert.deepEqual(findEscapingReferences("SKILL.md", "See https://example.com/a and ../../d.md"), [
    { line: 1, ref: "../../d.md" },
  ]);
});

test("unquoted YAML booleans and numbers are typed, so they fail string-only skill fields", () => {
  assert.deepEqual(
    parseFrontmatter("---\nname: demo\ndescription: false\nmetadata:\n  version: 1.0\n  icon: ~\n  tag: yes\n---\n").data,
    { name: "demo", description: false, metadata: { version: 1, icon: null, tag: "yes" } },
  );
  const expectSkillError = (replace: [string, string], pattern: RegExp) =>
    withRoot((_root, dir) => {
      const path = join(dir, "skills", "alpha-skill", "SKILL.md");
      writeFileSync(path, readFileSync(path, "utf8").replace(replace[0], replace[1]));
      assert.match(validate(dir).errors.join("\n"), pattern);
    });
  expectSkillError(["  icon: DocumentSearch", "  icon: false"], /alpha-skill: SKILL\.md metadata\.icon is required/);
  expectSkillError(['  version: "1.2.3"', "  version: 1.2"], /metadata\.version is 1\.2 \(not a string\); it must be the string "1\.2\.3"/);
  expectSkillError(["name: alpha-skill", "name: 123"], /alpha-skill: SKILL\.md name must be a string/);
});

test("parseFrontmatter reads quoted, folded and nested values and rejects malformed YAML", () => {
  const { data, body } = parseFrontmatter(
    [
      "---",
      'name: "demo"',
      "description: 'It''s a demo:",
      "  continued'",
      "allowed-tools: [Read, \"Bash\"]",
      "metadata:",
      "  version: \"1.0.0\"",
      "  icon: Star # comment",
      "---",
      "Body text",
    ].join("\n"),
  );
  assert.deepEqual(data, {
    name: "demo",
    description: "It's a demo: continued",
    "allowed-tools": ["Read", "Bash"],
    metadata: { version: "1.0.0", icon: "Star" },
  });
  assert.equal(body, "Body text");
  assert.throws(() => parseFrontmatter("---\nname: a\nname: b\n---\n"), /is duplicated/);
  assert.throws(() => parseFrontmatter("---\nname a\n---\n"), /is not valid YAML/);
  assert.throws(() => parseFrontmatter("---\nname: a\n"), /no closing/);
});

test("validManifest fixture matches the skills it lists", () => {
  assert.deepEqual(
    (validManifest().agentSkills as Array<{ folder: string }>).map((s) => s.folder),
    ["./skills/alpha-skill", "./skills/beta-skill"],
  );
});
