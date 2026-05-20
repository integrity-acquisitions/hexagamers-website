import fs from 'fs';
import path from 'path';
import https from 'https';
import http from 'http';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const env = fs.readFileSync(path.join(__dirname, '../.env'), 'utf8');
const getEnv = (key) => env.match(new RegExp(`^${key}=(.+)$`, 'm'))?.[1]?.trim();

const CLOUD_NAME = getEnv('CLOUDINARY_CLOUD_NAME');
const API_KEY = getEnv('CLOUDINARY_API_KEY');
const API_SECRET = getEnv('CLOUDINARY_API_SECRET');
const POSTS_DIR = path.join(__dirname, '../site/src/content/posts');

// Fetch URL as buffer
function fetchBuffer(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    client.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return fetchBuffer(res.headers.location).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    }).on('error', reject);
  });
}

// Upload buffer to Cloudinary via upload API
function uploadToCloudinary(buffer, filename) {
  return new Promise((resolve, reject) => {
    const boundary = '----FormBoundary' + Math.random().toString(36).slice(2);
    const auth = Buffer.from(`${API_KEY}:${API_SECRET}`).toString('base64');

    // Build multipart form
    const disposition = `Content-Disposition: form-data; name="file"; filename="${filename}"`;
    const parts = [
      `--${boundary}\r\n${disposition}\r\nContent-Type: application/octet-stream\r\n\r\n`,
      buffer,
      `\r\n--${boundary}\r\nContent-Disposition: form-data; name="public_id"\r\n\r\n${path.parse(filename).name}`,
      `\r\n--${boundary}--\r\n`,
    ];
    const body = Buffer.concat(parts.map(p => Buffer.isBuffer(p) ? p : Buffer.from(p)));

    const options = {
      hostname: 'api.cloudinary.com',
      path: `/v1_1/${CLOUD_NAME}/image/upload`,
      method: 'POST',
      headers: {
        Authorization: `Basic ${auth}`,
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': body.length,
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.error) reject(new Error(json.error.message));
          else resolve(json);
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function main() {
  const posts = fs.readdirSync(POSTS_DIR).filter(f => f.endsWith('.md'));

  // Collect all unique missing HostGator URLs
  const missingUrls = new Set();
  for (const file of posts) {
    const content = fs.readFileSync(path.join(POSTS_DIR, file), 'utf8');
    const matches = content.match(/\/\/hexagamers\.com\/wp-content\/uploads\/[^\s)"']+/g) ?? [];
    matches.forEach(u => missingUrls.add(u));
  }

  console.log(`Found ${missingUrls.size} missing image URLs to fetch\n`);

  // Map old URL → new Cloudinary URL
  const urlMap = new Map();
  let success = 0;
  let failed = 0;

  for (const oldUrl of missingUrls) {
    const fullUrl = 'https:' + oldUrl;
    const filename = oldUrl.split('/').pop().split('?')[0];

    process.stdout.write(`  Fetching ${filename}... `);
    try {
      const buffer = await fetchBuffer(fullUrl);
      const result = await uploadToCloudinary(buffer, filename);
      const newUrl = result.secure_url;
      urlMap.set(oldUrl, newUrl);
      console.log(`✓`);
      success++;
      // Small delay to avoid rate limiting
      await new Promise(r => setTimeout(r, 300));
    } catch (err) {
      console.log(`✗ ${err.message}`);
      failed++;
    }
  }

  console.log(`\nFetched: ${success}, Failed: ${failed}`);
  console.log('Rewriting post URLs...\n');

  // Rewrite posts
  let totalReplaced = 0;
  for (const file of posts) {
    const filePath = path.join(POSTS_DIR, file);
    let content = fs.readFileSync(filePath, 'utf8');
    let replaced = 0;

    for (const [oldUrl, newUrl] of urlMap) {
      if (content.includes(oldUrl)) {
        content = content.replaceAll(oldUrl, newUrl);
        replaced++;
      }
    }

    if (replaced > 0) {
      fs.writeFileSync(filePath, content, 'utf8');
      console.log(`  ${file}: ${replaced} URLs updated`);
      totalReplaced += replaced;
    }
  }

  console.log(`\nDone — ${totalReplaced} URLs rewritten across posts`);
}

main();
