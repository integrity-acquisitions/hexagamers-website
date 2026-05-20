import fs from 'fs';
import path from 'path';
import https from 'https';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Load .env
const env = fs.readFileSync(path.join(__dirname, '../.env'), 'utf8');
const getEnv = (key) => env.match(new RegExp(`^${key}=(.+)$`, 'm'))?.[1]?.trim();

const CLOUD_NAME = getEnv('CLOUDINARY_CLOUD_NAME');
const API_KEY = getEnv('CLOUDINARY_API_KEY');
const API_SECRET = getEnv('CLOUDINARY_API_SECRET');
const POSTS_DIR = path.join(__dirname, '../site/src/content/posts');

// Fetch all resources from Cloudinary with pagination
async function fetchAllResources() {
  const resources = [];
  let nextCursor = null;

  do {
    const url = `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/resources/image?max_results=500${nextCursor ? `&next_cursor=${nextCursor}` : ''}`;
    const auth = Buffer.from(`${API_KEY}:${API_SECRET}`).toString('base64');

    const data = await new Promise((resolve, reject) => {
      https.get(url, { headers: { Authorization: `Basic ${auth}` } }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body)));
        res.on('error', reject);
      });
    });

    if (data.error) {
      console.error('Cloudinary API error:', data.error.message);
      process.exit(1);
    }

    resources.push(...data.resources);
    nextCursor = data.next_cursor;
    console.log(`Fetched ${resources.length} images so far...`);
  } while (nextCursor);

  return resources;
}

// Build a map of base filename (no extension) → full Cloudinary URL
function buildFilenameMap(resources) {
  const map = new Map();
  for (const r of resources) {
    // public_id may include folder prefix or Cloudinary suffix like "filename_abc123"
    // Strip folder path, keep just the last segment
    const publicId = r.public_id.split('/').pop();
    const format = r.format;
    const url = `https://res.cloudinary.com/${CLOUD_NAME}/image/upload/${r.public_id}.${format}`;

    // Map by full public_id filename (with suffix)
    map.set(publicId.toLowerCase(), url);

    // Also map by stripping the Cloudinary random suffix (_xxxxxx at end)
    const withoutSuffix = publicId.replace(/_[a-z0-9]{6}$/, '').toLowerCase();
    if (!map.has(withoutSuffix)) {
      map.set(withoutSuffix, url);
    }
  }
  return map;
}

// Extract base filename from a HostGator URL
function extractBasename(url) {
  const filename = url.split('/').pop().split('?')[0];
  // Remove extension
  return filename.replace(/\.[^.]+$/, '').toLowerCase();
}

async function main() {
  console.log('Fetching images from Cloudinary...');
  const resources = await fetchAllResources();
  console.log(`Total images in Cloudinary: ${resources.length}`);

  const filenameMap = buildFilenameMap(resources);
  console.log(`Built filename map with ${filenameMap.size} entries`);

  const posts = fs.readdirSync(POSTS_DIR).filter(f => f.endsWith('.md'));
  let totalReplaced = 0;
  let totalMissed = 0;
  const missed = [];

  for (const postFile of posts) {
    const filePath = path.join(POSTS_DIR, postFile);
    let content = fs.readFileSync(filePath, 'utf8');

    // Match all HostGator image URLs
    const regex = /\/\/hexagamers\.com\/wp-content\/uploads\/[^\s)"']+/g;
    const matches = [...new Set(content.match(regex) ?? [])];

    if (matches.length === 0) continue;

    let replaced = 0;
    let notFound = 0;

    for (const match of matches) {
      const basename = extractBasename(match);
      const cloudinaryUrl = filenameMap.get(basename);

      if (cloudinaryUrl) {
        content = content.replaceAll(match, cloudinaryUrl);
        replaced++;
      } else {
        notFound++;
        missed.push({ post: postFile, url: match, basename });
      }
    }

    if (replaced > 0) {
      fs.writeFileSync(filePath, content, 'utf8');
    }

    totalReplaced += replaced;
    totalMissed += notFound;

    if (replaced > 0 || notFound > 0) {
      console.log(`  ${postFile}: ${replaced} replaced, ${notFound} not found`);
    }
  }

  console.log('\n=== Summary ===');
  console.log(`URLs replaced: ${totalReplaced}`);
  console.log(`URLs not matched: ${totalMissed}`);

  if (missed.length > 0) {
    console.log('\nUnmatched URLs (may need manual review):');
    for (const { post, basename } of missed) {
      console.log(`  [${post}] ${basename}`);
    }
  }
}

main();
