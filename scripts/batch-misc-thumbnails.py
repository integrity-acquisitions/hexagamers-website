#!/usr/bin/env python3
"""
Generate 16:9 thumbnails for 9 misc posts.
Some use box art image reference (pandemic logs, agricola vs caverna, carcassonne).
Others use text-only prompts.
All use #f0a500 amber-gold / Playfair Display color scheme.
Runs all jobs in parallel.

Usage:
  python3 batch-misc-thumbnails.py
"""

import os, sys, re, json, time, hashlib, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, '..')
POSTS_DIR   = os.path.join(PROJECT_DIR, 'site', 'src', 'content', 'posts')
IMAGES_DIR  = os.path.join(PROJECT_DIR, '.tmp', 'images')
ENV_PATH    = os.path.join(PROJECT_DIR, '.env')

print_lock = threading.Lock()

NEGATIVE_PROMPT = (
    "blurry, text errors, misspelled text, distorted typography, watermark, "
    "people, hands, faces, cluttered background, neon colors, plastic look, "
    "AI smoothing, stock photo feel, white background, "
    "company logos, publisher logos, brand logos, trademark symbols, copyright symbols"
)

def editorial(scene, label):
    return (
        f"16:9 editorial thumbnail. {scene} "
        f"Very dark near-black background (#0d0d0e) with warm amber-gold dramatic side lighting. "
        f"Subtle vignette. Bold text overlay in the lower third: '{label}' set in Playfair Display "
        f"serif font, amber-gold color (#f0a500), with a soft dark gradient behind it for legibility. "
        f"Sharp, high-contrast editorial photography aesthetic."
    )

# (slug, cloudinary_folder, label, prompt_text, box_art_url_or_None)
ARTICLES = [
    (
        'cultural-themed-board-games-asia',
        'hexagamers-articles',
        editorial(
            "Flat-lay of Asian-themed board game components — illustrated tiles with East Asian "
            "artistic motifs, bamboo-themed cards, ornate wooden pieces — on a dark surface.",
            "Cultural Board Games: Asia"
        ),
        None
    ),
    (
        '25-games-under-25',
        'hexagamers-articles',
        editorial(
            "Flat-lay of a varied collection of small compact board game boxes and card game "
            "boxes arranged on a dark wood surface, suggesting great value.",
            "25 Games Under $25"
        ),
        None
    ),
    (
        'board-game-related-gifts-arent-board-games-2017',
        'hexagamers-articles',
        editorial(
            "Flat-lay of board game accessories and gifts — dice bag, custom meeples, game mat, "
            "card sleeves, small trinkets — arranged on a dark surface with a ribbon accent.",
            "Board Game Gifts (That Aren't Board Games)"
        ),
        None
    ),
    (
        'edmonton-board-game-cafes',
        'hexagamers-articles',
        editorial(
            "Atmospheric interior shot suggestion: shelves of board games, small café tables with "
            "games set up, warm lamp lighting — cosy board game café aesthetic on a dark background.",
            "Edmonton Board Game Cafes"
        ),
        None
    ),
    (
        'top-rated-board-games-that-teach-math-skills',
        'hexagamers-articles',
        editorial(
            "Flat-lay of math-themed board game components — numbered tiles, counting tokens, "
            "arithmetic cards, dice — arranged neatly on a dark surface.",
            "Board Games That Teach Math Skills"
        ),
        None
    ),
    (
        'pandemic-legacy-s1-logs-february',
        'hexagamers-articles',
        editorial(
            "Close-up of a Pandemic Legacy game board mid-campaign — stickered city names, "
            "outbreak markers, funded event cards, player cards showing February month progression.",
            "Pandemic Legacy S1: February Log"
        ),
        'https://res.cloudinary.com/dt4ujaczs/image/upload/Pandemic-Legacy-February-Setting-Up_qvwyzu.jpg'
    ),
    (
        'pandemic-legacy-s1-logs-january',
        'hexagamers-articles',
        editorial(
            "Pandemic Legacy game board freshly set up for campaign play — clean city connections, "
            "infection cards face-up, player pawns at starting positions, January campaign envelope.",
            "Pandemic Legacy S1: January Log"
        ),
        'https://res.cloudinary.com/dt4ujaczs/image/upload/Pandemic-Legacy-Blank_mzynoj.jpg'
    ),
    (
        'carcassonne-versions-expansions',
        'hexagamers-articles',
        editorial(
            "Flat-lay of Carcassonne tiles and meeples from multiple expansions — abbey tiles, "
            "mayor meeples, barn tokens, river tiles — spread across a dark surface.",
            "Carcassonne: Versions & Expansions"
        ),
        'https://res.cloudinary.com/dt4ujaczs/image/upload/Carcassonne-Abbey-Mayor-2007_xllgpa.jpg'
    ),
    (
        'agricola-vs-caverna-which-game-should-you-buy',
        'hexagamers-articles',
        editorial(
            "Split flat-lay comparison — left side Agricola wooden farm pieces and occupation cards, "
            "right side Caverna cave tiles and dwarf figures — divided by a subtle amber line.",
            "Agricola vs Caverna: Which Should You Buy?"
        ),
        'https://res.cloudinary.com/dt4ujaczs/image/upload/Agricola-Wooden-Pieces-2_xjls89.jpg'
    ),
]


def log(slug, msg):
    with print_lock:
        print(f"[{slug}] {msg}", flush=True)


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


def upload_to_litterbox(file_path):
    with open(file_path, 'rb') as f:
        resp = requests.post(
            'https://litterbox.catbox.moe/resources/internals/api.php',
            data={'reqtype': 'fileupload', 'time': '1h'},
            files={'fileToUpload': f},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.text.strip()


def submit_kie_task(api_key, prompt_text, box_url=None):
    input_payload = {
        'prompt': prompt_text,
        'negative_prompt': NEGATIVE_PROMPT,
        'aspect_ratio': '16:9',
        'resolution': '2K',
        'output_format': 'jpg',
    }
    if box_url:
        input_payload['image_input'] = [box_url]

    payload = {'model': 'nano-banana-2', 'input': input_payload}
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    resp = requests.post('https://api.kie.ai/api/v1/jobs/createTask',
                         headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    task_id = resp.json().get('data', {}).get('taskId')
    if not task_id:
        raise RuntimeError(f"No taskId: {resp.text[:200]}")
    return task_id


def poll_kie_task(api_key, task_id, slug, max_attempts=90):
    headers = {'Authorization': f'Bearer {api_key}'}
    for attempt in range(1, max_attempts + 1):
        time.sleep(4)
        try:
            resp = requests.get('https://api.kie.ai/api/v1/jobs/recordInfo',
                                headers=headers, params={'taskId': task_id}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get('data', {})
        except Exception as e:
            log(slug, f"Poll {attempt} error: {e}")
            continue

        state = data.get('state', '')
        log(slug, f"Poll {attempt}: {state}")

        if state in ('success', 'completed'):
            urls = json.loads(data.get('resultJson', '{}')).get('resultUrls', [])
            if urls:
                return urls[0]
            raise RuntimeError("No resultUrls")
        elif state in ('failed', 'error', 'fail'):
            raise RuntimeError(f"Kie failed: {json.dumps(data)[:200]}")

    raise RuntimeError("Timed out")


def upload_to_cloudinary(image_path, public_id, env):
    cloud_name = env.get('CLOUDINARY_CLOUD_NAME')
    api_key    = env.get('CLOUDINARY_API_KEY')
    api_secret = env.get('CLOUDINARY_API_SECRET')
    if not all([cloud_name, api_key, api_secret]):
        return None
    timestamp = str(int(time.time()))
    sig_str   = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(sig_str.encode()).hexdigest()
    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    with open(image_path, 'rb') as img:
        resp = requests.post(url, data={
            'public_id': public_id, 'timestamp': timestamp,
            'api_key': api_key, 'signature': signature,
        }, files={'file': img}, timeout=60)
    if resp.status_code == 200:
        return resp.json().get('secure_url')
    raise RuntimeError(f"Cloudinary {resp.status_code}: {resp.text[:200]}")


def patch_frontmatter(md_path, image_url):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'coverImage:' in content:
        content = re.sub(r'^coverImage:.*$', f'coverImage: "{image_url}"', content, flags=re.MULTILINE)
    else:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == '---':
                lines.insert(i, f'coverImage: "{image_url}"')
                break
        content = '\n'.join(lines)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)


def process_one(slug, folder, prompt_text, box_cloudinary_url, env, kie_api_key):
    md_path     = os.path.join(POSTS_DIR, f"{slug}.md")
    output_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")

    try:
        box_remote_url = None
        if box_cloudinary_url:
            box_local = os.path.join(IMAGES_DIR, f"{slug}-box.jpg")
            log(slug, "Downloading box art...")
            r = requests.get(box_cloudinary_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            with open(box_local, 'wb') as f:
                f.write(r.content)
            log(slug, "Uploading to litterbox...")
            box_remote_url = upload_to_litterbox(box_local)
            log(slug, f"Litterbox: {box_remote_url}")

        log(slug, "Submitting Kie.ai task...")
        task_id = submit_kie_task(kie_api_key, prompt_text, box_remote_url)
        log(slug, f"Task ID: {task_id}")

        image_url = poll_kie_task(kie_api_key, task_id, slug)
        log(slug, f"Generated: {image_url}")

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(img_resp.content)

        public_id = f"{folder}/{slug}"
        cover_url = upload_to_cloudinary(output_path, public_id, env)
        log(slug, f"Cloudinary: {cover_url}")

        patch_frontmatter(md_path, cover_url)
        log(slug, "Frontmatter patched. DONE.")
        return (slug, True, cover_url)

    except Exception as e:
        log(slug, f"FAILED: {e}")
        return (slug, False, str(e))


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    env = read_env()
    kie_api_key = env.get('KIE_API_KEY') or env.get('KIE_AI_API_KEY')
    if not kie_api_key:
        root_env_path = '/workspaces/.env'
        if os.path.exists(root_env_path):
            with open(root_env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('KIE_AI_API_KEY=') or line.startswith('KIE_API_KEY='):
                        kie_api_key = line.split('=', 1)[1].strip('"\'')
                        break

    if not kie_api_key:
        print("ERROR: KIE_API_KEY not found")
        sys.exit(1)

    total = len(ARTICLES)
    print(f"Submitting {total} jobs in parallel...\n")

    results = []
    with ThreadPoolExecutor(max_workers=total) as executor:
        futures = {
            executor.submit(process_one, slug, folder, prompt, box_url, env, kie_api_key): slug
            for slug, folder, prompt, box_url in ARTICLES
        }
        for future in as_completed(futures):
            results.append(future.result())

    print(f"\n{'='*60}")
    success = [r for r in results if r[1]]
    failed  = [r for r in results if not r[1]]
    print(f"Done. {len(success)}/{total} succeeded.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for slug, _, err in failed:
            print(f"  - {slug}: {err}")
    print("\nRun 'astro build' and push to deploy.")


if __name__ == '__main__':
    main()
