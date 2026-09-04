import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

/**
 * Machine-readable index of the whole gallery. Handy for scripting installs,
 * building a dashboard, or letting an agent discover what's available.
 */
export const GET: APIRoute = async ({ site }) => {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  const origin = site ? site.origin : "";

  const templates = (await getCollection("templates"))
    .sort((a, b) => a.data.name.localeCompare(b.data.name))
    .map((t) => ({
      slug: t.id,
      name: t.data.name,
      description: t.data.description,
      industry: t.data.industry,
      platforms: t.data.platforms,
      type: t.data.type,
      tags: t.data.tags,
      author: t.data.author,
      authorGithub: t.data.authorGithub ?? null,
      version: t.data.version ?? null,
      createdAt: t.data.createdAt?.toISOString() ?? null,
      updatedAt: t.data.updatedAt?.toISOString() ?? null,
      featured: t.data.featured,
      skills: t.data.skills?.map((s) => s.name) ?? [],
      url: `${origin}${base}/templates/${t.id}`,
      download: t.data.bundle ? `${origin}${base}/${t.data.bundle}` : null,
    }));

  return new Response(JSON.stringify({ count: templates.length, templates }, null, 2), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
};
