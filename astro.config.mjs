// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// GitHub Pages deployment: served from /industry-templates
export default defineConfig({
  site: "https://sravaniseethi.github.io",
  base: "/industry-templates",
  trailingSlash: "ignore",
  vite: {
    plugins: [tailwindcss()],
  },
});
