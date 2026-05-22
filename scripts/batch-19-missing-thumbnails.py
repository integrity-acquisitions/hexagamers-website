#!/usr/bin/env python3
"""
Generate 16:9 thumbnails for the 19 review posts missing hexagamers-reviews style thumbnails.
Runs all jobs in parallel via ThreadPoolExecutor.

Usage:
  python3 batch-19-missing-thumbnails.py
"""

import os, sys, re, json, time, hashlib, threading, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, '..')
POSTS_DIR   = os.path.join(PROJECT_DIR, 'site', 'src', 'content', 'posts')
IMAGES_DIR  = os.path.join(PROJECT_DIR, '.tmp', 'images')
PROMPTS_DIR = os.path.join(PROJECT_DIR, '.tmp', 'prompts')
ENV_PATH    = os.path.join(PROJECT_DIR, '.env')

print_lock = threading.Lock()

REVIEWS = [
    # betrayal, coloretto, count-your-chickens, dragons-hoard already done in prior run
    ('dimension-review', 'Dimension',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Dimension-Review_qrbkgy.jpg'),
    ('dreamescape-review', 'DreamEscape',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/20180702_170638_ycjl29.jpg'),
    ('forbidden-desert-review', 'Forbidden Desert',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Forbidden-Desert_bfbd8t.jpg'),
    ('forbidden-island-review', 'Forbidden Island',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Forbidden-Island-Box_iokoh1.jpg'),
    ('gloom-review', 'Gloom',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Gloom-Review_hr7vbt.jpg'),
    ('hive-review', 'Hive',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/v1779305645/IMG_1436-2-300x295.jpg'),
    ('lords-of-waterdeep-review', 'Lords of Waterdeep',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Lords-of-Waterdeep-Player-Card-Full_abbcgh.jpg'),
    ('mammut-review', 'Mammut',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Mammut_kp7njm.jpg'),
    ('raptor-review', 'Raptor',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/20180421_135028_o55u3k.jpg'),
    ('sheriff-of-nottingham-review', 'Sheriff of Nottingham',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/sheriff_bhi6ht.jpg'),
    ('splendor-review', 'Splendor',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/P1020785_qwkwu9.jpg'),
    ('squirmish-review', 'Squirmish',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Squirmish-Review-Cover_m00ohd.png'),
    ('takenoko-review', 'Takenoko',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/Takenoko_psyu9h.jpg'),
    ('the-gallerist-review', 'The Gallerist',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/20170829_214229_pe9d3x.jpg'),
    ('zombie-fluxx-review', 'Zombie Fluxx',
     'https://res.cloudinary.com/dt4ujaczs/image/upload/ZF.box__mdxagi.jpg'),
]

NEGATIVE_PROMPT = (
    "cropped box, partial box, cut-off box, missing text, blurry, distorted typography, "
    "watermark, people, hands, faces, cluttered background, neon colors, "
    "AI smoothing, stock photo feel, white background, stretched image, sans-serif font, "
    "company logos, publisher logos, brand logos, trademark symbols, copyright symbols, "
    "Hasbro, Stonemaier, Rio Grande, Z-Man, Fantasy Flight, Days of Wonder, CMON, "
    "Repos Production, Mayfair, Asmodee, publisher branding, studio logos"
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
    label = f"{game_title} Review"
    prompt = (
        f"16:9 editorial thumbnail for a board game review. "
        f"The board game box for '{game_title}' is shown prominently — full box visible, "
        f"slightly angled, centered in frame. Very dark near-black background (#0d0d0e) "
        f"with warm amber-gold dramatic side lighting. Subtle vignette. "
        f"Bold text overlay in the lower third: '{label}' set in Playfair Display serif font, "
        f"amber-gold color (#f0a500), with a soft dark gradient behind it for legibility. "
        f"Sharp, high-contrast product photography aesthetic. "
        f"The entire box art must be fully visible with no cropping."
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
        # 1. Download box art locally
        log(slug, f"Downloading box art...")
        r = requests.get(box_cloudinary_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        r.raise_for_status()
        with open(box_local, 'wb') as f:
            f.write(r.content)

        # 2. Upload box art to litterbox for Kie reference
        log(slug, "Uploading box art to litterbox...")
        box_remote_url = upload_to_litterbox(box_local)
        log(slug, f"Litterbox URL: {box_remote_url}")

        # 3. Submit Kie task
        log(slug, "Submitting Kie.ai task...")
        task_id = submit_kie_task(kie_api_key, box_remote_url, title, slug)
        log(slug, f"Task ID: {task_id}")

        # 4. Poll until done
        image_url = poll_kie_task(kie_api_key, task_id, slug)
        log(slug, f"Generated: {image_url}")

        # 5. Download result
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(img_resp.content)

        # 6. Upload to Cloudinary
        public_id = f"hexagamers-reviews/{slug}"
        cover_url = upload_to_cloudinary(output_path, public_id, env)
        log(slug, f"Cloudinary: {cover_url}")

        # 7. Patch frontmatter
        patch_frontmatter(md_path, cover_url)
        log(slug, "Frontmatter patched. DONE.")
        return (slug, True, cover_url)

    except Exception as e:
        log(slug, f"FAILED: {e}")
        return (slug, False, str(e))


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    env = read_env()
    kie_api_key = env.get('KIE_API_KEY') or env.get('KIE_AI_API_KEY')
    if not kie_api_key:
        # fall back to root .env
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

    total = len(REVIEWS)
    print(f"Submitting {total} thumbnail jobs in parallel...\n")

    results = []
    with ThreadPoolExecutor(max_workers=total) as executor:
        futures = {
            executor.submit(process_one, slug, title, box_url, env, kie_api_key): slug
            for slug, title, box_url in REVIEWS
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
