"""
YouTube Upload Service
Handles video upload to YouTube using the YouTube Data API v3.

SETUP INSTRUCTIONS:
1. Go to https://console.cloud.google.com/
2. Create a project (or select existing one)
3. Enable "YouTube Data API v3"
4. Go to Credentials -> Create OAuth 2.0 Client ID (type: Web Application)
5. Set redirect URI to: http://localhost:8000/oauth/callback
6. Copy CLIENT_ID and CLIENT_SECRET into your .env file
7. To get REFRESH_TOKEN, run the one-time auth flow:
      python services/youtube_upload_service.py
   This will open a browser, ask you to log in, and save the refresh token.
"""

import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Google OAuth Credentials
# Fill these in your .env file (see SETUP INSTRUCTIONS above)
# =============================================================================
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# YouTube API constants
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
MAX_RETRIES = 3
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


def _get_authenticated_service():
    """
    Build an authenticated YouTube API service using OAuth2 credentials.
    Uses refresh_token flow (no browser needed after initial setup).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET or not YOUTUBE_REFRESH_TOKEN:
        raise ValueError(
            "YouTube credentials not configured. "
            "Please set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN in your .env file. "
            "See services/youtube_upload_service.py for setup instructions."
        )

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )

    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=credentials,
    )


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    thumbnail_path: str = None,
    category_id: str = "22",  # 22 = People & Blogs
    privacy_status: str = "private",
    is_short: bool = False,
    progress_callback=None,
):
    """
    Upload a video to YouTube with resumable upload support.

    Args:
        video_path: Path to the video file (mp4)
        title: Video title
        description: Video description
        tags: List of tags/keywords
        thumbnail_path: Path to thumbnail image (jpg/png)
        category_id: YouTube category ID (default: 22 = People & Blogs)
        privacy_status: "private", "unlisted", or "public"
        is_short: If True, adds #Shorts to title/description
        progress_callback: Optional callback(percent, message) for progress updates

    Returns:
        dict with upload result: {"status": "success", "video_id": "...", "url": "..."}
    """
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    # Validate video file exists
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # For Shorts, add #Shorts hashtag
    if is_short:
        if "#Shorts" not in title:
            title = f"{title} #Shorts"
        if "#Shorts" not in description:
            description = f"{description}\n\n#Shorts"

    if tags is None:
        tags = []

    if progress_callback:
        progress_callback(5, "מתחבר ל-YouTube...")

    print(f"[YOUTUBE] Starting upload: {title}")
    print(f"[YOUTUBE] File: {video_path}")
    print(f"[YOUTUBE] Tags: {tags}")
    print(f"[YOUTUBE] Privacy: {privacy_status}")
    print(f"[YOUTUBE] Short: {is_short}")

    # Build authenticated service
    youtube = _get_authenticated_service()

    if progress_callback:
        progress_callback(10, "מכין את הסרטון להעלאה...")

    # Video metadata
    body = {
        "snippet": {
            "title": title[:100],  # YouTube limit: 100 chars
            "description": description[:5000],  # YouTube limit: 5000 chars
            "tags": tags[:500],  # YouTube limit: 500 tags
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Resumable upload with MediaFileUpload
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    # Create the insert request
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    if progress_callback:
        progress_callback(15, "מעלה סרטון ל-YouTube...")

    # Execute resumable upload with retry logic
    response = None
    retry_count = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                percent = int(status.progress() * 70) + 15  # Map 0-100% to 15-85%
                if progress_callback:
                    progress_callback(percent, f"מעלה... {int(status.progress() * 100)}%")
                print(f"[YOUTUBE] Upload progress: {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    raise Exception(f"YouTube upload failed after {MAX_RETRIES} retries: {e}")
                wait_time = 2 ** retry_count
                print(f"[YOUTUBE] Retriable error {e.resp.status}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"YouTube upload error: {e}")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[SUCCESS] Video uploaded: {video_url}")

    if progress_callback:
        progress_callback(85, "הסרטון הועלה בהצלחה!")

    # =========================================================================
    # Upload thumbnail (if provided)
    # =========================================================================
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            if progress_callback:
                progress_callback(90, "מעלה תמונה ממוזערת...")

            print(f"[YOUTUBE] Setting thumbnail: {thumbnail_path}")

            thumbnail_media = MediaFileUpload(
                thumbnail_path,
                mimetype="image/jpeg" if thumbnail_path.endswith(".jpg") else "image/png",
                resumable=False,
            )

            youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumbnail_media,
            ).execute()

            print(f"[SUCCESS] Thumbnail set for video {video_id}")
        except HttpError as e:
            # Thumbnail upload requires a verified YouTube channel
            # Don't fail the whole upload if thumbnail fails
            print(f"[WARNING] Thumbnail upload failed (channel may need verification): {e}")
        except Exception as e:
            print(f"[WARNING] Thumbnail upload failed: {e}")

    if progress_callback:
        progress_callback(100, "ההעלאה הושלמה!")

    return {
        "status": "success",
        "video_id": video_id,
        "url": video_url,
        "title": title,
    }


# =============================================================================
# One-time OAuth flow to get REFRESH_TOKEN
# Run this file directly: python services/youtube_upload_service.py
# =============================================================================
if __name__ == "__main__":
    """
    Run this script once to get your YOUTUBE_REFRESH_TOKEN.
    It will open a browser for Google login and print the refresh token.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print("ERROR: Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first!")
        print("See the top of this file for setup instructions.")
        exit(1)

    client_config = {
        "installed": {
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "redirect_uris": ["http://localhost:8080"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )

    credentials = flow.run_local_server(port=8080, prompt="consent")

    print("\n" + "=" * 60)
    print("SUCCESS! Copy this refresh token to your .env file:")
    print("=" * 60)
    print(f"\nYOUTUBE_REFRESH_TOKEN={credentials.refresh_token}\n")
    print("=" * 60)
