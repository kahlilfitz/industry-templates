import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

export async function getStaticPaths() {
  const templates = await getCollection("templates");
  return templates.map((template) => ({
    params: { slug: template.id },
    props: { template },
  }));
}

function quote(value: string): string {
  return /[:#\[\]{},'"]/.test(value) ? JSON.stringify(value) : value;
}

/**
 * The plain-markdown view of a template: its catalog frontmatter plus the
 * generated overview body. Useful for reading the template outside the gallery
 * and for feeding it to an agent as context.
 */
export const GET: APIRoute = ({ props }) => {
  const { template } = props as {
    template: Awaited<ReturnType<typeof getCollection>>[number];
  };
  const d = template.data as Record<string, unknown>;

  const lines: string[] = ["---"];
  lines.push(`name: ${quote(template.id)}`);
  lines.push(`title: ${quote(String(d.name))}`);
  lines.push(`industry: ${quote(String(d.industry))}`);
  lines.push(`platforms: [${(d.platforms as string[]).join(", ")}]`);
  lines.push(`type: ${quote(String(d.type))}`);
  lines.push(`description: ${quote(String(d.agentDescription ?? d.description))}`);
  if (d.version) lines.push(`version: ${quote(String(d.version))}`);
  lines.push("---", "");

  const frontmatter = lines.join("\n");
  const body = template.body ?? "";

  return new Response(frontmatter + body, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="${template.id}.md"`,
    },
  });
};
