/**
 * Shared helpers for the industry-templates gallery: the two facets every entry
 * is filed under (industry + platform), deterministic cover styling, and small
 * utilities reused across pages, endpoints, and the client island.
 */

/** The industries a template can belong to. Manufacturing shipped first. */
export const INDUSTRIES = [
  "Manufacturing",
  // Retail and CPG ship as one portfolio rather than two: the retailer-side and
  // brand-side scenarios share systems, artifacts and buyers, so they are filed
  // under one industry and split by a `retailer` / `cpg` tag.
  "Retail & CPG",
  "Financial Services",
  "Healthcare",
  "Energy",
  "Public Sector",
  // Professional Services covers the engagement lifecycle shared by consulting,
  // legal, accounting, audit and engineering firms: pursuit, mobilisation,
  // delivery, commercial control and closeout. The portfolio is filed under one
  // industry and split by lifecycle stage in the tags.
  "Professional Services",
  "Cross-industry",
] as const;
export type Industry = (typeof INDUSTRIES)[number];

/** The agent platforms a template can target. */
export const PLATFORMS = ["Cowork", "Copilot Studio", "Scout"] as const;
export type Platform = (typeof PLATFORMS)[number];

/**
 * A submission is a plugin (a package bundling one or more skills + optional
 * connectors), a single cross-platform Agent Skill, or an automation (a
 * scheduled `.json` of ordered prompt steps).
 */
export type TemplateType = "plugin" | "skill" | "automation";

/** Accent color used for each industry's badge. */
export const INDUSTRY_COLORS: Record<Industry, string> = {
  Manufacturing: "#0078d4",
  "Retail & CPG": "#e06c00",
  "Financial Services": "#0d9488",
  Healthcare: "#d83b73",
  Energy: "#7f39fb",
  "Public Sector": "#5b8def",
  "Professional Services": "#2e7d32",
  "Cross-industry": "#9aa0a6",
};

/** Accent color used for each platform's badge. */
export const PLATFORM_COLORS: Record<Platform, string> = {
  Cowork: "#7f39fb",
  "Copilot Studio": "#0078d4",
  Scout: "#0d9488",
};

/**
 * Cover gradient pairs drawn from the brand spectrum
 * (blue -> purple -> pink -> orange). Calm enough to read well against both
 * light and dark backgrounds.
 */
const COVER_PALETTE: Array<[string, string]> = [
  ["#0078d4", "#5b8def"],
  ["#5b8def", "#7f39fb"],
  ["#7f39fb", "#c26cf3"],
  ["#c26cf3", "#d83b73"],
  ["#d83b73", "#ff8c00"],
  ["#0078d4", "#7f39fb"],
  ["#3aa0ff", "#5b8def"],
  ["#7f39fb", "#d83b73"],
  ["#0d9488", "#5b8def"],
  ["#c26cf3", "#5b8def"],
  ["#d83b73", "#c26cf3"],
  ["#0078d4", "#0d9488"],
];

/** Stable hash for a string (FNV-1a style, good enough for theming). */
function hash(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Deterministic gradient for a template, derived from its slug. */
export function coverGradient(slug: string, override?: string): string {
  if (override) {
    return `linear-gradient(135deg, ${override} 0%, ${override} 100%)`;
  }
  const [from, to] = COVER_PALETTE[hash(slug) % COVER_PALETTE.length];
  const angle = 110 + (hash(slug + "angle") % 60);
  return `linear-gradient(${angle}deg, ${from} 0%, ${to} 100%)`;
}

/** Up to two-letter initials used as a watermark on covers. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "IT";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function formatDate(date?: Date): string | undefined {
  if (!date) return undefined;
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
