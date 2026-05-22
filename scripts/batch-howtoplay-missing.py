#!/usr/bin/env python3
"""
Generate 16:9 thumbnails for How To Play Simplified posts missing hexagamers-guides thumbnails.
Uses existing Cloudinary images as box art reference. Runs all jobs in parallel.
Label always includes "Simplified" per site convention.

Usage:
  python3 batch-howtoplay-missing.py
"""

import os, sys, re, json, time, hashlib, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, '..')
POSTS_DIR   = os.path.join(PROJECT_DIR, 'site', 'src', 'content', 'posts')
IMAGES_DIR  = os.path.join(PROJECT_DIR, '.tmp', 'images')
ENV_PATH    = os.path.join(PROJECT_DIR, '.env')

print_lock = threading.Lock()

GUIDES = [
    ('agricola-how-to-play-simplified', 'Agricola',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Agricola-Wooden-Pieces-2_xjls89.jpg'),
    ('betrayal-at-house-on-the-hill-how-to-play-simplified', 'Betrayal at House on the Hill',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Betrayal-at-House-on-the-Hill-Character-Cards_koahdn.jpg'),
    ('ghost-blitz-how-to-play-simplified', 'Ghost Blitz',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Ghost-Blitz-2-Items_ivdigo.jpg'),
    ('lords-of-waterdeep-how-to-play-simplified', 'Lords of Waterdeep',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Lords-of-Waterdeep-Player-Cards_mxxbzs.jpg'),
    ('mammut-how-to-play-simplified', 'Mammut',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Mammut-How-To-Play-Simplified-1_gauxdc.png'),
    ('ticket-to-ride-europe-how-to-play-simplified', 'Ticket to Ride Europe',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Ticket-to-Ride-Europe-Game-Board_cnyswt.jpg'),
    ('gallerist-play-simplified', 'The Gallerist',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Gallerist-Overview-2-1_jk1vdj.jpg'),
]

NEGATIVE_PROMPT = (
    "blurry, text errors, misspelled text, distorted typography, watermark, logo, "
    "people, hands, faces, cluttered background, neon colors, plastic look, "
    "AI smoothing, stock photo feel, white background, studio seamless paper, "
    "company logos, publisher logos, brand logos, trademark symbols, copyright symbols"
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


def submit_kie_task(api_key, box_url_remote, game_title, slug):
    label = f"How To Play {game_title} — Simplified"
    prompt = (
        f"Flat-lay instructional photography of the board game '{game_title}' — rulebook open beside "
        f"neatly arranged game components: cards fanned out, tokens stacked, dice placed on a dark "
        f"wood table. Warm overhead lighting with soft shadows. Bold typographic overlay centered at "
        f"the bottom: '{label}' in clean serif font, white text on a dark gradient band. "
        f"35mm lens, f/5.6, ISO 320. Sharp component detail, educational and inviting aesthetic. "
        f"Board game tutorial thumbnail style. The entire box art must be fully visible with no cropping."
    )
    payload = {
        'model': 'nano-banana-2',
        'input': {
            'prompt': prompt,
            'negative_prompt': NEGATIVE_PROMPT,
            'aspect_ratio': '16:9',
            'resolution': '2K',
            'output_format': 'jpg',
            'image_input': [box_url_remote],
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


def process_one(slug, title, box_cloudinary_url, env, kie_api_key):
    md_path     = os.path.join(POSTS_DIR, f"{slug}.md")
    box_local   = os.path.join(IMAGES_DIR, f"{slug}-box.jpg")
    output_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")

    try:
        log(slug, "Downloading box art...")
        r = requests.get(box_cloudinary_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        r.raise_for_status()
        with open(box_local, 'wb') as f:
            f.write(r.content)

        log(slug, "Uploading to litterbox...")
        box_remote_url = upload_to_litterbox(box_local)
        log(slug, f"Litterbox: {box_remote_url}")

        log(slug, "Submitting Kie.ai task...")
        task_id = submit_kie_task(kie_api_key, box_remote_url, title, slug)
        log(slug, f"Task ID: {task_id}")

        image_url = poll_kie_task(kie_api_key, task_id, slug)
        log(slug, f"Generated: {image_url}")

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(img_resp.content)

        public_id = f"hexagamers-guides/{slug}"
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

    total = len(GUIDES)
    print(f"Submitting {total} how-to-play thumbnail jobs in parallel...\n")

    results = []
    with ThreadPoolExecutor(max_workers=total) as executor:
        futures = {
            executor.submit(process_one, slug, title, box_url, env, kie_api_key): slug
            for slug, title, box_url in GUIDES
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
