import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";
import { templateSchema } from "./lib/template-schema";

const templates = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/templates" }),
  schema: templateSchema,
});

// Optional human-facing "overview" for an entry, generated from a submission's
// README.md. Keyed by the same slug as its template so the detail page can look
// it up. Plain markdown — any frontmatter is ignored.
const guides = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/guides" }),
  schema: z.object({}).passthrough(),
});

export const collections = { templates, guides };
