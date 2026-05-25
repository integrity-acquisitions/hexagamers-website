#!/usr/bin/env python3
"""
Generate a 16:9 review thumbnail from a box art image.

Usage:
  python generate-thumbnail-from-box.py <slug> <box-art-url-or-path> [game-title] [components]

Arguments:
  slug           Post filename without .md (e.g. wingspan-review)
  box-art-url    URL or local path to the box art image
  game-title     Human-readable game name (default: derived from slug)
  components     Description of game-specific components to scatter in the scene
                 (e.g. "bird cards, egg tokens, food tokens, a nesting mat, and wooden eggs")
                 If omitted, falls back to a generic flat-lay description.

Examples:
  python generate-thumbnail-from-box.py wingspan-review "https://res.cloudinary.com/..." "Wingspan" "bird cards, egg tokens, food tokens, and a nesting mat"
  python generate-thumbnail-from-box.py catan-review "https://m.media-amazon.com/images/..." "Catan" "hexagonal resource tiles, wooden settlements and cities, and number tokens"
  python generate-thumbnail-from-box.py wingspan-review "/path/to/wingspan-box.jpg" "Wingspan"

The script will:
  1. Download the box art (if a URL) to .tmp/images/
  2. Generate a 16:9 thumbnail via Kie.ai using the box art as image reference
  3. Upload the result to Cloudinary under hexagamers-reviews/<slug>.jpg
  4. Patch the post's frontmatter with the new coverImage URL
"""

import os, sys, re, json, time, hashlib, requests, subprocess, urllib.parse

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR      = os.path.join(SCRIPT_DIR, '..')
POSTS_DIR        = os.path.join(PROJECT_DIR, 'site', 'src', 'content', 'posts')
IMAGES_DIR       = os.path.join(PROJECT_DIR, '.tmp', 'images')
PROMPTS_DIR      = os.path.join(PROJECT_DIR, '.tmp', 'prompts')
KIE_SCRIPT       = '/workspaces/scripts/generate_kie.py'
ENV_PATH         = os.path.join(PROJECT_DIR, '.env')
COMPONENTS_FILE  = os.path.join(PROJECT_DIR, 'assets', 'content', 'game-components.json')


def load_components(slug):
    """Return (title, components, label) from game-components.json for this slug, or (None, None, None)."""
    if not os.path.exists(COMPONENTS_FILE):
        return None, None, None
    with open(COMPONENTS_FILE) as f:
        data = json.load(f)
    entry = data.get(slug)
    if not entry:
        return None, None, None
    return entry.get('title'), entry.get('components'), entry.get('label')


def read_env():
    env = {}
    if not os.path.exists(ENV_PATH):
        return env
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"\'')
    return env


def download_image(url, dest_path):
    """Download an image from a URL to dest_path."""
    print(f"  Downloading box art from: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    with open(dest_path, 'wb') as f:
        f.write(resp.content)
    print(f"  Saved to: {dest_path}")


def build_prompt(game_title, box_art_path, components=None, label=None):
    label = label or f"{game_title} Review"
    if components:
        scene = (
            f"Flat-lay scene of the board game '{game_title}' — the game box centered and fully visible, "
            f"surrounded by {components} arranged naturally around it on a dark wood table. "
            f"Components are scattered organically, not stacked, creating a lived-in tabletop scene. "
            f"Dramatic warm amber-gold side lighting, soft shadows, rich tones. Subtle vignette."
        )
    else:
        scene = (
            f"Flat-lay product photography of the board game '{game_title}' — the game box centered "
            f"and fully visible, surrounded by its cards and components arranged naturally on a dark wood table. "
            f"Dramatic warm amber-gold side lighting, soft shadows, rich tones. Subtle vignette."
        )
    return {
        "prompt": (
            f"16:9 editorial thumbnail for a board game review. "
            f"{scene} "
            f"Bold typographic overlay in the lower third: '{label}' set in Playfair Display serif font, "
            f"amber-gold color (#f0a500), with a soft dark gradient behind it for legibility. "
            f"Sharp, high-contrast editorial board game review thumbnail aesthetic. "
            f"The entire game box must be fully visible with no cropping."
        ),
        "negative_prompt": (
            "cropped box, partial box, cut-off box, missing text, blurry, distorted typography, "
            "generic components, unrecognizable pieces, watermark, people, hands, faces, "
            "neon colors, AI smoothing, stock photo feel, white background, stretched image, "
            "sans-serif font, company logos, publisher logos, brand logos, trademark symbols, "
            "copyright symbols, Hasbro, Stonemaier, Rio Grande, Z-Man, Fantasy Flight, "
            "Days of Wonder, CMON, Repos Production, Mayfair, Asmodee, publisher branding, studio logos"
        ),
        "image_input": [box_art_path],
        "api_parameters": {
            "aspect_ratio": "16:9",
            "resolution": "2K",
            "output_format": "jpg"
        }
    }


def upload_to_cloudinary(image_path, public_id, env):
    cloud_name = env.get('CLOUDINARY_CLOUD_NAME')
    api_key    = env.get('CLOUDINARY_API_KEY')
    api_secret = env.get('CLOUDINARY_API_SECRET')

    if not all([cloud_name, api_key, api_secret]):
        print("  WARNING: Cloudinary credentials missing — skipping upload")
        return None

    timestamp = str(int(time.time()))
    sig_str = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(sig_str.encode()).hexdigest()

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    with open(image_path, 'rb') as img:
        resp = requests.post(upload_url, data={
            'public_id': public_id,
            'timestamp': timestamp,
            'api_key': api_key,
            'signature': signature,
        }, files={'file': img}, timeout=60)

    if resp.status_code == 200:
        url = resp.json().get('secure_url')
        print(f"  Uploaded to Cloudinary: {url}")
        return url

    print(f"  Cloudinary error {resp.status_code}: {resp.text[:300]}")
    return None


def patch_frontmatter(md_path, image_url):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace existing coverImage
    if 'coverImage:' in content:
        content = re.sub(
            r'^coverImage:.*$',
            f'coverImage: "{image_url}"',
            content,
            flags=re.MULTILINE
        )
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Updated existing coverImage in frontmatter")
        return

    # Insert before closing ---
    lines = content.split('\n')
    fm_close = -1
    for i, line in enumerate(lines):
        if i > 0 and line.strip() == '---':
            fm_close = i
            break
    if fm_close == -1:
        print(f"  WARNING: Could not find frontmatter end in {md_path}")
        return
    lines.insert(fm_close, f'coverImage: "{image_url}"')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  Inserted coverImage into frontmatter")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    slug        = sys.argv[1].replace('.md', '')
    box_source  = sys.argv[2]

    # Look up title, components, and optional label override from game-components.json
    stored_title, stored_components, stored_label = load_components(slug)

    game_title  = sys.argv[3] if len(sys.argv) > 3 else (stored_title or slug.replace('-review', '').replace('-', ' ').title())
    components  = sys.argv[4] if len(sys.argv) > 4 else stored_components
    label       = sys.argv[5] if len(sys.argv) > 5 else stored_label  # None falls back to "<title> Review"

    if components:
        print(f"  Using components from game-components.json: {components[:60]}...")
    else:
        print(f"  No components found for '{slug}' in game-components.json — using generic flat-lay")

    md_path = os.path.join(POSTS_DIR, f"{slug}.md")
    if not os.path.exists(md_path):
        print(f"ERROR: Post not found: {md_path}")
        sys.exit(1)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    env = read_env()

    # Step 1: Get the box art locally
    box_art_local = os.path.join(IMAGES_DIR, f"{slug}-box.jpg")
    if box_source.startswith('http://') or box_source.startswith('https://'):
        download_image(box_source, box_art_local)
    else:
        # Local path provided
        if not os.path.exists(box_source):
            print(f"ERROR: Local file not found: {box_source}")
            sys.exit(1)
        box_art_local = box_source

    # Step 2: Build and save the Kie prompt
    prompt_path  = os.path.join(PROMPTS_DIR, f"{slug}-thumbnail.json")
    output_path  = os.path.join(IMAGES_DIR, f"{slug}.jpg")

    prompt = build_prompt(game_title, box_art_local, components, label)
    with open(prompt_path, 'w') as f:
        json.dump(prompt, f, indent=2)

    print(f"\nGenerating 16:9 thumbnail for: {game_title}")

    # Step 3: Run Kie.ai generation
    result = subprocess.run(
        [sys.executable, KIE_SCRIPT, prompt_path, output_path, '16:9'],
        capture_output=False, text=True
    )
    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"ERROR: Kie.ai generation failed")
        sys.exit(1)

    print(f"  Thumbnail saved: {output_path}")

    # Step 4: Upload to Cloudinary
    public_id = f"hexagamers-reviews/{slug}"
    cover_url = upload_to_cloudinary(output_path, public_id, env)

    if not cover_url:
        print(f"  Falling back to local path — upload manually to Cloudinary as: {public_id}")
        cover_url = f"/images/reviews/{slug}.jpg"

    # Step 5: Patch the post frontmatter
    patch_frontmatter(md_path, cover_url)
    print(f"\nDone. coverImage = {cover_url}")
    print(f"Run 'astro build' and push to deploy.")


if __name__ == '__main__':
    main()
