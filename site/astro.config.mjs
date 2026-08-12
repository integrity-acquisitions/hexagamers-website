// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Legacy-URL redirect map: old /blog/<slug>, WordPress slug variants, and
// migration artifacts → their current root /<slug>/ home. Generated from the
// URLs actually hitting the 404 page in GA4 (property 366576353). In static
// output each entry emits a <meta http-equiv="refresh"> + canonical stub page,
// which is how a GitHub Pages site (no server redirects) preserves link equity.
// To refresh: re-run the GA4 404 query and update src/redirects.json.
import redirects from './src/redirects.json' with { type: 'json' };

// Markdown image links (`[![](box-art)](amazon-url)`) can't carry target/rel,
// so outbound links used to open in the same tab while the HTML buy buttons
// opened in a new one. This normalises both at build time.
import { rehypeExternalLinks } from './src/plugins/rehype-external-links.mjs';

export default defineConfig({
  site: 'https://hexagamers.com',
  output: 'static',
  trailingSlash: 'always',
  redirects,
  integrations: [sitemap()],
  markdown: {
    rehypePlugins: [rehypeExternalLinks],
  },
});
