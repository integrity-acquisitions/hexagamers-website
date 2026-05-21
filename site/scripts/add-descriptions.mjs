// Adds a `description:` field to post frontmatter using the first plain-text paragraph from the body.
// Skips posts that already have a description. Truncates to 155 chars at a word boundary.

import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const POSTS_DIR = new URL('../src/content/posts/', import.meta.url).pathname;
const MAX_LEN = 155;

function extractFirstParagraph(body) {
  // Remove HTML tags, markdown headings, divs, shortcodes
  const lines = body.split('\n');
  for (const line of lines) {
    const stripped = line
      .replace(/<[^>]+>/g, '')   // strip HTML tags
      .replace(/^#+\s+/, '')     // strip markdown headings
      .replace(/!\[.*?\]\(.*?\)/g, '') // strip images
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // collapse links
      .trim();

    // Skip empty, short, or line-only content
    if (stripped.length > 40 && !stripped.startsWith('{') && !stripped.startsWith('|')) {
      return stripped;
    }
  }
  return null;
}

function truncate(text, maxLen) {
  if (text.length <= maxLen) return text;
  const cut = text.lastIndexOf(' ', maxLen);
  return text.slice(0, cut > 0 ? cut : maxLen) + '…';
}

const files = (await readdir(POSTS_DIR)).filter(f => f.endsWith('.md'));
let updated = 0;
let skipped = 0;

for (const file of files) {
  const path = join(POSTS_DIR, file);
  const raw = await readFile(path, 'utf8');

  // Check if description already exists in frontmatter
  const fmMatch = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) { skipped++; continue; }

  const fm = fmMatch[1];
  if (/^description:/m.test(fm)) { skipped++; continue; }

  const body = raw.slice(fmMatch[0].length);
  const para = extractFirstParagraph(body);
  if (!para) { console.log(`WARN: no paragraph found in ${file}`); skipped++; continue; }

  const description = truncate(para, MAX_LEN);

  // Insert description after the last frontmatter field (before closing ---)
  const newRaw = raw.replace(
    /^(---\n[\s\S]*?)\n---/,
    `$1\ndescription: "${description.replace(/"/g, '\\"')}"\n---`
  );

  await writeFile(path, newRaw, 'utf8');
  updated++;
  console.log(`✓ ${file}: "${description.slice(0, 60)}…"`);
}

console.log(`\nDone. Updated: ${updated}, Skipped: ${skipped}`);
