import { visit } from 'unist-util-visit';

/**
 * Open external links in a new tab.
 *
 * Post bodies link out two ways: hand-written HTML buy buttons, which already
 * carry target/rel, and markdown image links (`[![](box-art)](amazon-url)`),
 * which have no syntax for attributes and so used to open in the same tab.
 * That inconsistency sent readers away from the article mid-list.
 *
 * This normalises every outbound link at build time, so new posts get the
 * behaviour without anyone remembering to hand-write it.
 *
 * Internal links (/slug/, #anchor, mailto:) are deliberately left alone.
 * Existing target/rel values are preserved rather than overwritten.
 */
export function rehypeExternalLinks() {
  return (tree) => {
    visit(tree, 'element', (node) => {
      if (node.tagName !== 'a') return;

      const href = node.properties?.href;
      if (typeof href !== 'string') return;
      if (!/^https?:\/\//i.test(href)) return;

      // Same-site absolute URLs are internal navigation, not outbound.
      if (/^https?:\/\/(www\.)?hexagamers\.com(\/|$)/i.test(href)) return;

      node.properties.target ??= '_blank';

      // Preserve an author-specified rel; otherwise pick a sensible default.
      // noopener/noreferrer close the window.opener hole that target=_blank
      // opens; affiliate and other monetised links also need nofollow.
      if (node.properties.rel == null) {
        const isAffiliate = /[?&]tag=hexagamers/i.test(href);
        node.properties.rel = isAffiliate
          ? ['nofollow', 'noopener', 'noreferrer']
          : ['noopener', 'noreferrer'];
      }
    });
  };
}

export default rehypeExternalLinks;
