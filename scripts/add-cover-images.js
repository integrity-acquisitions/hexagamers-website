import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const POSTS_DIR = path.join(__dirname, '../site/src/content/posts');

const posts = fs.readdirSync(POSTS_DIR).filter(f => f.endsWith('.md'));
let updated = 0;

for (const file of posts) {
  const filePath = path.join(POSTS_DIR, file);
  const content = fs.readFileSync(filePath, 'utf8');

  // Skip if already has coverImage
  if (/^coverImage:/m.test(content)) continue;

  // Find first Cloudinary image URL in the body
  const match = content.match(/https:\/\/res\.cloudinary\.com\/[^\s)"']+\.(?:jpg|jpeg|png|gif|webp)/i);
  if (!match) continue;

  const imageUrl = match[0];

  // Insert coverImage into frontmatter (after the closing ---)
  const updated_content = content.replace(
    /^(---\n[\s\S]*?\n)---/m,
    `$1coverImage: "${imageUrl}"\n---`
  );

  fs.writeFileSync(filePath, updated_content, 'utf8');
  updated++;
  console.log(`  ${file} → ${imageUrl.split('/').pop()}`);
}

console.log(`\nDone — added coverImage to ${updated} posts`);
