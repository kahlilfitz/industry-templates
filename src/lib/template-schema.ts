/**
 * Single source of truth for a template's frontmatter schema.
 *
 * Imported by both the Astro content collection (`src/content.config.ts`) and
 * the submission importer (`scripts/import-submissions.ts`) so the rules
 * enforced at build time and at submission time can never drift apart.
 */
import { z } from "astro/zod";
import { INDUSTRIES, PLATFORMS } from "./templates";

/** Zod schema for a template's frontmatter metadata. */
export const templateSchema = z.object({
  name: z.string(),
  // Catalog/gallery summary shown to humans on the card, in search, and at the
  // top of the detail page. Comes from metadata.json.
  description: z.string(),
  // The agent-facing description the model reads to decide when to invoke the
  // work. For a plugin this is the package manifest's own description.
  agentDescription: z.string().optional(),
  // The industry this template is built for — the gallery's primary facet.
  industry: z.enum(INDUSTRIES),
  // Agent platform(s) the template targets.
  platforms: z.array(z.enum(PLATFORMS)).nonempty(),
  // Distinguishes a plugin (a package bundling one or more skills + optional
  // connectors) from a single cross-platform Agent Skill or a scheduled
  // automation. Derived by the importer, not authored.
  type: z.enum(["plugin", "skill", "automation"]).default("plugin"),
  tags: z.array(z.string()).nonempty(),
  // Human-readable author (person or team) shown on the gallery card and the
  // detail page. Required: every submission must declare who authored it.
  author: z
    .string({
      error: (issue) =>
        issue.input === undefined
          ? "author is required — add it to the submission's metadata.json"
          : "author must be a string",
    })
    .trim()
    .min(1, "author must not be empty"),
  // Optional URL to the author's website / profile, shown as a link on the
  // template page when an `author` is also present.
  authorUrl: z.string().url().optional(),
  // The author's GitHub login, stored WITHOUT a leading `@`. Resolved by the
  // importer from an explicit `authorGithub`, else derived from a
  // `github.com/<login>` `authorUrl`, else unset. A bare GitHub username:
  // 1-39 chars, alphanumerics or single hyphens, no leading/trailing hyphen.
  authorGithub: z
    .string()
    .regex(
      /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i,
      "must be a bare GitHub username (no leading @)",
    )
    .optional(),
  version: z.string().optional(),
  createdAt: z.coerce.date().optional(),
  updatedAt: z.coerce.date().optional(),
  // Path (relative to /public) of the packaged download for this template.
  bundle: z.string().optional(),
  // Named skills inside a plugin package, listed on the detail page.
  skills: z
    .array(z.object({ name: z.string(), description: z.string().optional() }))
    .optional(),
  // Optional override for the auto-generated cover color (any CSS color).
  coverColor: z.string().optional(),
  featured: z.boolean().default(false),
});

export type TemplateFrontmatter = z.infer<typeof templateSchema>;
