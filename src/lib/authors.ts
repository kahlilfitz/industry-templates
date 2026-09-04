/**
 * Author identity helpers.
 *
 * A contributor is keyed by their GitHub login when we know it, and otherwise by
 * a slug of their display name — so the `?author=` filter, the detail-page
 * byline, and the contributors directory all agree on who is who.
 */

/** A GitHub login without its leading `@`, lowercased. Empty when unknown. */
export function normalizeLogin(login: string | null | undefined): string {
  return (login ?? "").trim().replace(/^@/, "").toLowerCase();
}

/** Slugify a display name into a stable, URL-safe key. */
function slugifyName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Stable key for a contributor: GitHub login first, display-name slug second. */
export function authorKey(
  login: string | null | undefined,
  name: string | null | undefined,
): string {
  return normalizeLogin(login) || slugifyName(name ?? "");
}
