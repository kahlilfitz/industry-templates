/**
 * Optional Microsoft Clarity analytics.
 *
 * Clarity gives session replay, heatmaps, and custom event tracking. Two events
 * matter here:
 *
 *   - `template_download` — a visitor downloads a template package.
 *   - `template_view`     — a visitor lands on a template detail page.
 *
 * A Clarity project id is NOT a secret — Clarity emits it into the public client
 * bundle — so it is safe to commit. This gallery ships with analytics OFF: set
 * `PUBLIC_CLARITY_PROJECT_ID` at build time to switch it on for a deployment.
 */

/** Clarity project id (public client id, safe to commit). Empty = disabled. */
export const CLARITY_PROJECT_ID = import.meta.env.PUBLIC_CLARITY_PROJECT_ID ?? "";

/**
 * Clarity only loads when a project id is configured, so builds without an id
 * never inject a broken loader.
 */
export const ANALYTICS_ENABLED = Boolean(CLARITY_PROJECT_ID);
