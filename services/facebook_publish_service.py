"""
Facebook Page Video Publishing Service
Handles video and Reel uploads to Facebook Pages via the Graph API.

SETUP INSTRUCTIONS:
1. Go to https://developers.facebook.com/ and create an App (type: Business)
2. Add the "Pages" product to your app
3. Under Settings > Basic, find your App ID and App Secret
4. Generate a Page Access Token with these permissions:
   - pages_manage_posts
   - pages_read_engagement
   - pages_show_list
   - publish_video  (for Reels)
5. Use the Graph API Explorer to generate a long-lived Page Access Token:
   a. Get a short-lived User Token from the Explorer
   b. Exchange for long-lived User Token:
      GET /oauth/access_token?grant_type=fb_exchange_token
        &client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_TOKEN}
   c. Get Page Token from long-lived User Token:
      GET /{PAGE_ID}?fields=access_token&access_token={LONG_LIVED_USER_TOKEN}
   The resulting Page Token never expires.
6. Paste FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN into your .env file.
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Facebook Page Credentials
# Fill these in your .env file (see SETUP INSTRUCTIONS above)
# =============================================================================
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
MAX_POLL_ATTEMPTS = 120  # 10 minutes at 5-second intervals


def publish_to_facebook(
    video_path: str,
    caption: str = "",
    is_reel: bool = False,
    progress_callback=None,
):
    """
    Upload a video to a Facebook Page as a regular video post or as a Reel.

    Args:
        video_path: Path to the video file (mp4)
        caption: Post text / description
        is_reel: If True, upload as a Facebook Reel; otherwise as a regular video post
        progress_callback: Optional callback(percent, message) for progress updates

    Returns:
        dict with result: {"status": "success", "post_id": "...", "url": "..."}
    """
    if not FB_PAGE_ID or not FB_PAGE_ACCESS_TOKEN:
        raise ValueError(
            "Facebook credentials not configured. "
            "Please set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN in your .env file. "
            "See services/facebook_publish_service.py for setup instructions."
        )

    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    file_size = Path(video_path).stat().st_size
    print(f"[FACEBOOK] Starting upload: {'Reel' if is_reel else 'Video'}")
    print(f"[FACEBOOK] File: {video_path} ({file_size / 1024 / 1024:.1f} MB)")
    print(f"[FACEBOOK] Caption: {caption[:80]}...")

    if progress_callback:
        progress_callback(5, "מתחבר ל-Facebook...")

    if is_reel:
        return _upload_reel(video_path, caption, progress_callback)
    else:
        return _upload_video(video_path, caption, progress_callback)


def _upload_video(video_path: str, caption: str, progress_callback=None):
    """
    Upload a regular video post to a Facebook Page using resumable upload.
    Graph API docs: https://developers.facebook.com/docs/video-api/guides/publishing
    """
    file_size = Path(video_path).stat().st_size

    # --- Step 1: Initialize upload session ---
    if progress_callback:
        progress_callback(10, "מאתחל העלאה ל-Facebook...")

    init_url = f"{GRAPH_API_BASE}/{FB_PAGE_ID}/videos"
    init_resp = requests.post(init_url, data={
        "access_token": FB_PAGE_ACCESS_TOKEN,
        "upload_phase": "start",
        "file_size": file_size,
    })

    if init_resp.status_code != 200:
        raise Exception(f"Facebook init failed: {init_resp.text}")

    init_data = init_resp.json()
    upload_session_id = init_data["upload_session_id"]
    video_id = init_data.get("video_id", "")

    print(f"[FACEBOOK] Upload session: {upload_session_id}, video_id: {video_id}")

    # --- Step 2: Upload the file in chunks ---
    if progress_callback:
        progress_callback(15, "מעלה סרטון ל-Facebook...")

    chunk_size = 4 * 1024 * 1024  # 4MB chunks
    offset = 0

    with open(video_path, "rb") as f:
        while offset < file_size:
            chunk = f.read(chunk_size)
            transfer_resp = requests.post(init_url, data={
                "access_token": FB_PAGE_ACCESS_TOKEN,
                "upload_phase": "transfer",
                "upload_session_id": upload_session_id,
                "start_offset": offset,
            }, files={
                "video_file_chunk": ("chunk", chunk, "application/octet-stream"),
            })

            if transfer_resp.status_code != 200:
                raise Exception(f"Facebook chunk upload failed: {transfer_resp.text}")

            transfer_data = transfer_resp.json()
            offset = int(transfer_data.get("start_offset", file_size))

            percent = int((offset / file_size) * 65) + 15  # Map to 15-80%
            if progress_callback:
                progress_callback(percent, f"מעלה... {int(offset / file_size * 100)}%")
            print(f"[FACEBOOK] Upload progress: {int(offset / file_size * 100)}%")

    # --- Step 3: Finish upload ---
    if progress_callback:
        progress_callback(85, "מסיים העלאה...")

    finish_resp = requests.post(init_url, data={
        "access_token": FB_PAGE_ACCESS_TOKEN,
        "upload_phase": "finish",
        "upload_session_id": upload_session_id,
        "title": caption[:100] if caption else "",
        "description": caption,
    })

    if finish_resp.status_code != 200:
        raise Exception(f"Facebook finish failed: {finish_resp.text}")

    result = finish_resp.json()
    post_id = result.get("id", video_id)
    post_url = f"https://www.facebook.com/{FB_PAGE_ID}/videos/{post_id}"

    if progress_callback:
        progress_callback(100, "הסרטון פורסם בהצלחה!")

    print(f"[SUCCESS] Facebook video published: {post_url}")
    return {
        "status": "success",
        "post_id": post_id,
        "url": post_url,
    }


def _upload_reel(video_path: str, caption: str, progress_callback=None):
    """
    Upload a Reel to a Facebook Page.
    Uses the 3-step Reels API:
      1. Initialize  (POST /{page-id}/video_reels  upload_phase=start)
      2. Upload binary (POST https://rupload.facebook.com/video-upload/v19.0/{video-id})
      3. Publish      (POST /{page-id}/video_reels  upload_phase=finish)

    Docs: https://developers.facebook.com/docs/video-api/guides/reels-publishing
    """
    file_size = Path(video_path).stat().st_size

    # --- Step 1: Initialize ---
    if progress_callback:
        progress_callback(10, "מאתחל העלאת Reel...")

    init_url = f"{GRAPH_API_BASE}/{FB_PAGE_ID}/video_reels"
    init_resp = requests.post(init_url, data={
        "access_token": FB_PAGE_ACCESS_TOKEN,
        "upload_phase": "start",
    })

    if init_resp.status_code != 200:
        raise Exception(f"Facebook Reel init failed: {init_resp.text}")

    init_data = init_resp.json()
    video_id = init_data.get("video_id", "")

    if not video_id:
        raise Exception(f"Facebook Reel init returned no video_id: {init_data}")

    print(f"[FACEBOOK] Reel upload started, video_id: {video_id}")

    # --- Step 2: Upload binary ---
    if progress_callback:
        progress_callback(20, "מעלה Reel ל-Facebook...")

    upload_url = f"https://rupload.facebook.com/video-upload/v19.0/{video_id}"

    with open(video_path, "rb") as f:
        file_data = f.read()

    upload_resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {FB_PAGE_ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        },
        data=file_data,
    )

    if upload_resp.status_code != 200:
        raise Exception(f"Facebook Reel binary upload failed: {upload_resp.text}")

    print(f"[FACEBOOK] Reel binary uploaded successfully")

    if progress_callback:
        progress_callback(70, "מפרסם Reel...")

    # --- Step 3: Publish ---
    publish_resp = requests.post(init_url, data={
        "access_token": FB_PAGE_ACCESS_TOKEN,
        "upload_phase": "finish",
        "video_id": video_id,
        "title": caption[:100] if caption else "",
        "description": caption,
    })

    if publish_resp.status_code != 200:
        raise Exception(f"Facebook Reel publish failed: {publish_resp.text}")

    publish_data = publish_resp.json()

    # Reels may take a moment to process. If status is returned, poll for it.
    reel_status = publish_data.get("status", {})
    if isinstance(reel_status, dict) and reel_status.get("publishing_phase", {}).get("status") == "not_started":
        if progress_callback:
            progress_callback(80, "ממתין לעיבוד Reel...")
        # Poll for completion
        for attempt in range(MAX_POLL_ATTEMPTS):
            time.sleep(5)
            status_resp = requests.get(
                f"{GRAPH_API_BASE}/{video_id}",
                params={
                    "fields": "status",
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                }
            )
            if status_resp.status_code == 200:
                st = status_resp.json().get("status", {})
                phase = st.get("publishing_phase", {}).get("status", "")
                if phase == "complete":
                    break
                elif phase == "error":
                    raise Exception(f"Facebook Reel processing error: {st}")
            pct = min(80 + attempt, 95)
            if progress_callback:
                progress_callback(pct, "Reel בעיבוד...")

    post_id = publish_data.get("id", video_id)
    post_url = f"https://www.facebook.com/reel/{video_id}"

    if progress_callback:
        progress_callback(100, "ה-Reel פורסם בהצלחה!")

    print(f"[SUCCESS] Facebook Reel published: {post_url}")
    return {
        "status": "success",
        "post_id": post_id,
        "video_id": video_id,
        "url": post_url,
    }
