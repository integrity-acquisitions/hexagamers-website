#!/usr/bin/env python3
"""
Generate 16:9 thumbnails for all best-of / favourites-list posts.
Uploads to hexagamers-articles/ on Cloudinary. Runs all jobs in parallel.

Usage:
  python3 batch-bestof-thumbnails.py
"""

import os, sys, re, json, time, hashlib, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, '..')
POSTS_DIR   = os.path.join(PROJECT_DIR, 'site', 'src', 'content', 'posts')
IMAGES_DIR  = os.path.join(PROJECT_DIR, '.tmp', 'images')
ENV_PATH    = os.path.join(PROJECT_DIR, '.env')

print_lock = threading.Lock()

def make_prompt(scene, label):
    return (
        f"16:9 editorial thumbnail. {scene} "
        f"Very dark near-black background (#0d0d0e) with warm amber-gold dramatic side lighting. "
        f"Subtle vignette. Bold text overlay in the lower third: '{label}' set in Playfair Display "
        f"serif font, amber-gold color (#f0a500), with a soft dark gradient behind it for legibility. "
        f"Sharp, high-contrast editorial photography aesthetic."
    )


ARTICLES = [
    (
        'best-board-game-podcasts',
        'Best Board Game Podcasts',
        make_prompt(
            "Flat-lay of a podcast microphone, headphones, and several board game boxes arranged "
            "artfully on a dark wood table.",
            "Best Board Game Podcasts"
        )
    ),
    (
        'best-board-games-2-year-olds-reviews',
        'Best Board Games for 2 Year Olds',
        make_prompt(
            "Flat-lay of bright chunky toddler game components — oversized colourful pieces, "
            "simple illustrated cards, large wooden pawns — scattered playfully on a dark surface.",
            "Best Board Games for 2 Year Olds"
        )
    ),
    (
        'best-board-games-3-year-olds-reviews',
        'Best Board Games for 3 Year Olds',
        make_prompt(
            "Flat-lay of colourful preschool board game components — bright animal tokens, "
            "simple game board, large illustrated cards — arranged invitingly on a dark surface.",
            "Best Board Games for 3 Year Olds"
        )
    ),
    (
        'best-board-games-for-adults',
        'Best Board Games for Adults',
        make_prompt(
            "Overhead flat-lay of sophisticated board game components — strategy cards, "
            "wooden resource tokens, hex tiles, player boards — arranged on a dark slate surface.",
            "Best Board Games for Adults"
        )
    ),
    (
        'best-board-games-for-christmas-gifts',
        'Best Board Games for Christmas Gifts',
        make_prompt(
            "Flat-lay of several board game boxes with ribbon and small gift tags "
            "scattered on a dark wood surface.",
            "Best Board Games for Christmas Gifts"
        )
    ),
    (
        'best-card-drafting-board-games',
        'Best Card Drafting Board Games',
        make_prompt(
            "Overhead flat-lay of illustrated game cards fanned out, additional card decks "
            "face-down in rows on a dark felt surface, tokens nearby.",
            "Best Card Drafting Board Games"
        )
    ),
    (
        'best-cooperative-board-games',
        'Best Cooperative Board Games',
        make_prompt(
            "Flat-lay of cooperative game components — several player pawns gathered together "
            "on a shared game board, event cards, resource tokens — arranged on a dark wood surface.",
            "Best Cooperative Board Games"
        )
    ),
    (
        'best-custom-settlers-of-catan-game-boards',
        'Best Custom Catan Boards',
        make_prompt(
            "Overhead shot of a beautifully crafted custom Catan board — hand-painted wooden "
            "hex tiles in earth tones showing forests, fields, mountains, and pastures.",
            "Best Custom Catan Boards"
        )
    ),
    (
        'best-deck-building-board-games',
        'Best Deck Building Board Games',
        make_prompt(
            "Overhead flat-lay of a growing deck of cards sorted into piles, illustrated card "
            "art visible, a few face-up showing abilities — on a dark wood table.",
            "Best Deck Building Board Games"
        )
    ),
    (
        'best-gateway-board-games-for-beginners-with-reviews',
        'Best Gateway Board Games for Beginners',
        make_prompt(
            "Flat-lay of approachable colourful board game components — a simple game board, "
            "illustrated cards, friendly wooden pieces — arranged on a dark surface.",
            "Best Gateway Board Games for Beginners"
        )
    ),
    (
        'best-murder-mystery-party-companies',
        'Best Murder Mystery Party Companies',
        make_prompt(
            "Moody flat-lay of murder mystery party props — sealed envelope, magnifying glass, "
            "candlestick, name cards, a suspect dossier — on a dark wood table.",
            "Best Murder Mystery Party Companies"
        )
    ),
    (
        'best-one-player-solo-board-games-with-reviews',
        'Best Solo Board Games',
        make_prompt(
            "Intimate flat-lay of a single-player game setup — one player board, hand of cards, "
            "tokens arranged neatly — with a cosy evening atmosphere.",
            "Best Solo Board Games"
        )
    ),
    (
        'best-party-board-games-with-reviews',
        'Best Party Board Games',
        make_prompt(
            "Energetic flat-lay of party game components — bright colourful cards, chunky tokens, "
            "a timer, dice — scattered dynamically on a dark surface.",
            "Best Party Board Games"
        )
    ),
    (
        'best-settlers-of-catan-gifts',
        'Best Catan Gifts',
        make_prompt(
            "Flat-lay of Catan-themed items — resource cards, wooden settlements and cities, "
            "robber piece, number tokens — on a dark wood surface with a small gift ribbon.",
            "Best Catan Gifts"
        )
    ),
    (
        'best-social-deduction-board-games',
        'Best Social Deduction Board Games',
        make_prompt(
            "Moody flat-lay of social deduction game components — role cards face-down, "
            "voting tokens, a hidden traitor card peeking out — on a dark felt surface.",
            "Best Social Deduction Board Games"
        )
    ),
    (
        'best-two-player-board-games',
        'Best Two Player Board Games',
        make_prompt(
            "Intimate flat-lay of a two-player game setup — two hands of cards, two sets of "
            "player tokens facing each other across a game board.",
            "Best Two Player Board Games"
        )
    ),
    (
        'best-worker-placement-board-games-reviews',
        'Best Worker Placement Board Games',
        make_prompt(
            "Overhead flat-lay of wooden worker meeples in multiple colours placed on action "
            "spaces of a game board, resource tokens and cards nearby.",
            "Best Worker Placement Board Games"
        )
    ),
]

NEGATIVE_PROMPT = (
    "blurry, text errors, misspelled text, distorted typography, watermark, logo, "
    "people, hands, faces, cluttered background, neon colors, plastic look, "
    "AI smoothing, stock photo feel, white background, studio seamless paper, "
    "company logos, publisher logos, brand logos, trademark symbols"
)


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


def submit_kie_task(api_key, prompt_text):
    payload = {
        'model': 'nano-banana-2',
        'input': {
            'prompt': prompt_text,
            'negative_prompt': NEGATIVE_PROMPT,
            'aspect_ratio': '16:9',
            'resolution': '2K',
            'output_format': 'jpg',
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    resp = requests.post(
        'https://api.kie.ai/api/v1/jobs/createTask',
        headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()
    task_id = resp.json().get('data', {}).get('taskId')
    if not task_id:
        raise RuntimeError(f"No taskId in response: {resp.text[:200]}")
    return task_id


def poll_kie_task(api_key, task_id, slug, max_attempts=90):
    headers = {'Authorization': f'Bearer {api_key}'}
    for attempt in range(1, max_attempts + 1):
        time.sleep(4)
        try:
            resp = requests.get(
                'https://api.kie.ai/api/v1/jobs/recordInfo',
                headers=headers, params={'taskId': task_id}, timeout=15
            )
            resp.raise_for_status()
            data = resp.json().get('data', {})
        except Exception as e:
            log(slug, f"Poll {attempt} error: {e}")
            continue

        state = data.get('state', '')
        log(slug, f"Poll {attempt}: {state}")

        if state in ('success', 'completed'):
            result_json = json.loads(data.get('resultJson', '{}'))
            urls = result_json.get('resultUrls', [])
            if urls:
                return urls[0]
            raise RuntimeError("No resultUrls in completed task")
        elif state in ('failed', 'error', 'fail'):
            raise RuntimeError(f"Kie task failed: {json.dumps(data)[:200]}")

    raise RuntimeError("Timed out waiting for Kie.ai job")


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
            'public_id': public_id,
            'timestamp': timestamp,
            'api_key': api_key,
            'signature': signature,
        }, files={'file': img}, timeout=60)
    if resp.status_code == 200:
        return resp.json().get('secure_url')
    raise RuntimeError(f"Cloudinary error {resp.status_code}: {resp.text[:200]}")


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


def process_one(slug, title, prompt_text, env, kie_api_key):
    md_path     = os.path.join(POSTS_DIR, f"{slug}.md")
    output_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")

    try:
        log(slug, "Submitting Kie.ai task...")
        task_id = submit_kie_task(kie_api_key, prompt_text)
        log(slug, f"Task ID: {task_id}")

        image_url = poll_kie_task(kie_api_key, task_id, slug)
        log(slug, f"Generated: {image_url}")

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(img_resp.content)

        public_id = f"hexagamers-articles/{slug}"
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
        print("ERROR: KIE_API_KEY not found in .env")
        sys.exit(1)

    total = len(ARTICLES)
    print(f"Submitting {total} best-of thumbnail jobs in parallel...\n")

    results = []
    with ThreadPoolExecutor(max_workers=total) as executor:
        futures = {
            executor.submit(process_one, slug, title, prompt, env, kie_api_key): slug
            for slug, title, prompt in ARTICLES
        }
        for future in as_completed(futures):
            slug, ok, detail = future.result()
            results.append((slug, ok, detail))

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
