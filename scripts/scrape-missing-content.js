import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const POSTS_DIR = path.join(__dirname, '../site/src/content/posts');

function fetchHtml(url) {
  try {
    return execSync(
      `curl -s -L --max-time 15 \
        -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        -H "Accept-Language: en-US,en;q=0.5" \
        "${url}"`,
      { maxBuffer: 10 * 1024 * 1024 }
    ).toString();
  } catch (e) {
    throw new Error(e.message);
  }
}

function stripTags(html) {
  return html
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#8211;/g, '–')
    .replace(/&#8212;/g, '—')
    .replace(/&#8216;/g, "'")
    .replace(/&#8217;/g, "'")
    .replace(/&#8220;/g, '"')
    .replace(/&#8221;/g, '"')
    .replace(/&#\d+;/g, '')
    .trim();
}

function htmlToMarkdown(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_, t) => `\n# ${stripTags(t)}\n`)
    .replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_, t) => `\n## ${stripTags(t)}\n`)
    .replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_, t) => `\n### ${stripTags(t)}\n`)
    .replace(/<h4[^>]*>([\s\S]*?)<\/h4>/gi, (_, t) => `\n#### ${stripTags(t)}\n`)
    .replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, (_, t) => `**${stripTags(t)}**`)
    .replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, (_, t) => `**${stripTags(t)}**`)
    .replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, (_, t) => `*${stripTags(t)}*`)
    .replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, (_, t) => `*${stripTags(t)}*`)
    .replace(/<img[^>]*src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*\/?>/gi, (_, src, alt) => `\n![${alt}](${src})\n`)
    .replace(/<img[^>]*alt=["']([^"']*)["'][^>]*src=["']([^"']+)["'][^>]*\/?>/gi, (_, alt, src) => `\n![${alt}](${src})\n`)
    .replace(/<img[^>]*src=["']([^"']+)["'][^>]*\/?>/gi, (_, src) => `\n![](${src})\n`)
    .replace(/<a[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, (_, href, text) => {
      const t = stripTags(text).trim();
      if (!t) return '';
      return `[${t}](${href})`;
    })
    .replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_, item) => `- ${stripTags(item).trim()}\n`)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, (_, t) => `\n${stripTags(t).trim()}\n`)
    .replace(/<hr\s*\/?>/gi, '\n---\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#8211;/g, '–')
    .replace(/&#8212;/g, '—')
    .replace(/&#8216;/g, "'")
    .replace(/&#8217;/g, "'")
    .replace(/&#8220;/g, '"')
    .replace(/&#8221;/g, '"')
    .replace(/&#\d+;/g, '')
    .replace(/\n{4,}/g, '\n\n')
    .trim();
}

function extractContent(html) {
  // Try Thrive Architect wrapper first, then standard WordPress containers
  const patterns = [
    /<div[^>]*class="[^"]*thrv_wrapper[^"]*"[^>]*>([\s\S]+)/i,
    /<div[^>]*class="[^"]*tve_editor[^"]*"[^>]*>([\s\S]+)/i,
    /<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>([\s\S]+)/i,
    /<div[^>]*class="[^"]*post-content[^"]*"[^>]*>([\s\S]+)/i,
    /<article[^>]*>([\s\S]+?)<\/article>/i,
    /<main[^>]*>([\s\S]+?)<\/main>/i,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match?.[1]?.length > 300) return match[1];
  }
  return null;
}

async function main() {
  const posts = fs.readdirSync(POSTS_DIR).filter(f => f.endsWith('.md'));
  const emptyPosts = [];

  for (const file of posts) {
    const filePath = path.join(POSTS_DIR, file);
    const content = fs.readFileSync(filePath, 'utf8');
    const body = content.replace(/^---[\s\S]*?---\n/, '').trim();
    if (body.length === 0) {
      emptyPosts.push({ file, filePath, slug: file.replace('.md', '') });
    }
  }

  console.log(`Found ${emptyPosts.length} empty posts\n`);

  let success = 0, failed = 0, empty = 0;

  for (const { file, filePath, slug } of emptyPosts) {
    const url = `https://hexagamers.com/${slug}/`;
    process.stdout.write(`  ${slug}... `);

    try {
      const html = fetchHtml(url);
      const contentHtml = extractContent(html);

      if (!contentHtml || contentHtml.trim().length < 100) {
        console.log(`⚠ no content found`);
        empty++;
        continue;
      }

      const markdown = htmlToMarkdown(contentHtml);

      if (markdown.length < 50) {
        console.log(`⚠ too short`);
        empty++;
        continue;
      }

      const existing = fs.readFileSync(filePath, 'utf8');
      const frontmatter = existing.match(/^---[\s\S]*?---\n/)?.[0] ?? '';
      fs.writeFileSync(filePath, frontmatter + '\n' + markdown + '\n', 'utf8');

      console.log(`✓ (${markdown.length} chars)`);
      success++;

      await new Promise(r => setTimeout(r, 600));
    } catch (err) {
      console.log(`✗ ${err.message}`);
      failed++;
    }
  }

  console.log(`\n=== Done ===`);
  console.log(`Scraped: ${success}, No content: ${empty}, Failed: ${failed}`);
}

main();
