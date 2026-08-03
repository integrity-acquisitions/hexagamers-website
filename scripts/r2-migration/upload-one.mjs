#!/usr/bin/env node
/**
 * Upload a single local image to R2 as an optimized WebP, print the public URL.
 *
 * Reusable helper for the content pipeline (e.g. generate-thumbnail-from-box.py)
 * so new post images go straight to R2 instead of Cloudinary. Mirrors the bulk
 * migration's conventions: long edge <=1600px, WebP q80. Cache-Control depends on
 * the key: post covers get a short revalidating cache (they're overwritten in place
 * when a thumbnail is regenerated), everything else keeps the 1-year immutable cache.
 *
 * Usage:
 *   node upload-one.mjs <local-image-path> <r2-key-without-ext>
 *
 *   <r2-key-without-ext>  e.g. "hexagamers-reviews/wingspan-review"
 *                         -> object key "hexagamers-reviews/wingspan-review.webp"
 *
 * On success prints exactly one line to stdout: the public URL.
 * Reads R2 creds from scripts/r2-migration/.env (same as the other scripts).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// load .env
const env = {};
const ENV_FILE = path.join(__dirname, ".env");
if (fs.existsSync(ENV_FILE)) {
  for (const line of fs.readFileSync(ENV_FILE, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const [, , srcPath, keyNoExt] = process.argv;
if (!srcPath || !keyNoExt) {
  console.error("usage: node upload-one.mjs <local-image> <r2-key-without-ext>");
  process.exit(2);
}
for (const k of ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE"]) {
  if (!env[k]) {
    console.error(`✗ missing ${k} in scripts/r2-migration/.env`);
    process.exit(2);
  }
}
if (!fs.existsSync(srcPath)) {
  console.error(`✗ source not found: ${srcPath}`);
  process.exit(2);
}

const sharp = (await import("sharp")).default;
const MAX_EDGE = 1600;

const input = fs.readFileSync(srcPath);
let img = sharp(input, { failOn: "none" }).rotate();
const meta = await img.metadata();
if (Math.max(meta.width || 0, meta.height || 0) > MAX_EDGE) {
  img = img.resize({
    width: meta.width >= meta.height ? MAX_EDGE : undefined,
    height: meta.height > meta.width ? MAX_EDGE : undefined,
    withoutEnlargement: true,
  });
}
const body = await img.webp({ quality: 80 }).toBuffer();

const key = `${keyNoExt.replace(/\.[^/.]+$/, "")}.webp`;

// Cache policy depends on whether the key gets overwritten in place.
//
// Post covers (hexagamers-reviews/, hexagamers-guides/, hexagamers-articles/) are
// regenerated onto the SAME key whenever a thumbnail is redone, so `immutable` is
// wrong for them: Cloudflare pins the old bytes at the edge for a year and the new
// image never appears on the site, even though R2 has it. (Hit 2026-08-03 on
// ticket-to-ride-versions-ranked — R2 was correct, the edge served a 53-hour-old
// copy with cf-cache-status: HIT.) One hour is long enough to be cheap and short
// enough that a regenerated cover self-heals without a dashboard purge.
//
// Box art and migrated assets are write-once, so they keep the 1-year immutable cache.
const COVER_FOLDERS = ["hexagamers-reviews/", "hexagamers-guides/", "hexagamers-articles/"];
const isCover = COVER_FOLDERS.some((f) => key.startsWith(f));
const cacheControl = isCover
  ? "public, max-age=3600, must-revalidate"
  : "public, max-age=31536000, immutable";
const s3 = new S3Client({
  region: "auto",
  endpoint: `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: { accessKeyId: env.R2_ACCESS_KEY_ID, secretAccessKey: env.R2_SECRET_ACCESS_KEY },
});
await s3.send(
  new PutObjectCommand({
    Bucket: env.R2_BUCKET,
    Key: key,
    Body: body,
    ContentType: "image/webp",
    CacheControl: cacheControl,
  })
);

// the only stdout line: the public URL (Python captures this)
console.log(`${env.R2_PUBLIC_BASE.replace(/\/$/, "")}/${key}`);
