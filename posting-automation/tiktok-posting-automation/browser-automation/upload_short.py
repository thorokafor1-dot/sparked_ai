"""Uploads a short video to TikTok through a real, visible Chrome window driven
by Playwright, using a dedicated, isolated Chrome profile directory (set up
once via login_chrome_profile.py) -- no passwords handled by this script, and
no conflict with your everyday browsing Chrome window or with the Instagram/
Facebook automations, since each uses a completely separate profile directory
(Chrome's single-instance lock applies per user-data directory, not per named
profile).

Like the Facebook automation, TikTok's upload-composer selectors here are
best-effort guesses, not verified against the live site. Every automated step
falls back to "pause and ask you to do it by hand in the visible browser
window" if its guessed selector doesn't match. A screenshot is saved after
every step (see --debug-dir) so selectors can get fixed against reality
instead of guessed at. Nothing here ever clicks the final Post button -- that
part is always yours, and the script simply waits for you to close the tab
once you're done.

Usage:
    python upload_short.py --drive-link "https://drive.google.com/file/d/XXXX/view" --caption "some caption"

Before running: log in once via login_chrome_profile.py (see that file), using
the Sparked Thor TikTok account. After that, this script reuses the saved
session automatically -- no repeated logins.
"""
import argparse
import os
import re
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_CHROME_USER_DATA_DIR = str(
    Path(os.environ.get("USERPROFILE", "")) / "ChromeAutomationProfiles" / "sparked_thor_tiktok"
)
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=upload"


def resolve_drive_file_id(url_or_id: str) -> str:
    for pattern in (r"/d/([a-zA-Z0-9_-]+)", r"[?&]id=([a-zA-Z0-9_-]+)"):
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def download_from_drive(drive_link: str, dest_dir: Path) -> Path:
    import gdown

    file_id = resolve_drive_file_id(drive_link)
    dest_path = dest_dir / f"{file_id}.mp4"
    gdown.download(id=file_id, output=str(dest_path), quiet=False)
    if not dest_path.exists():
        raise RuntimeError(
            f"Download failed for Drive file {file_id}. Confirm sharing is set to "
            "'Anyone with the link' and the link points to a single file."
        )
    return dest_path


def human_click(page: Page, locator) -> None:
    """Click with a rough approximation of human movement instead of Playwright's
    instant jump-to-center -- move toward the element in a couple of steps, pause
    briefly, then press and release with a small hold time.

    Scrolls the element into view first -- unlike Playwright's own .click(), which
    does this automatically, driving the mouse to raw bounding_box() coordinates
    does not (see the same bug documented in the Facebook automation's version of
    this function).
    """
    import random
    import time

    try:
        locator.scroll_into_view_if_needed(timeout=5_000)
    except Exception:
        pass
    box = locator.bounding_box()
    if not box:
        locator.click()
        return
    target_x = box["x"] + box["width"] * random.uniform(0.35, 0.65)
    target_y = box["y"] + box["height"] * random.uniform(0.35, 0.65)
    page.mouse.move(target_x + random.uniform(-40, 40), target_y + random.uniform(-40, 40), steps=3)
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.move(target_x, target_y, steps=random.randint(4, 8))
    time.sleep(random.uniform(0.05, 0.2))
    page.mouse.down()
    time.sleep(random.uniform(0.03, 0.09))
    page.mouse.up()


def click_first_match(page: Page, step_name: str, selectors: list[str], timeout_ms: int = 120_000) -> bool:
    """Try each selector in turn and click the first one that becomes visible.

    Only the LAST selector in the list gets the full timeout_ms wait (long enough
    for a human to notice and do the step by hand in the visible window) -- earlier
    candidates get a short wait, since if one of several guessed selectors is right,
    it's normally present almost immediately. Returns True if an automated click
    succeeded, False if none matched in time -- selectors here are best-effort
    guesses at TikTok's current markup and may not match after a UI change.
    """
    for i, selector in enumerate(selectors):
        is_last = i == len(selectors) - 1
        per_try_timeout = timeout_ms if is_last else min(timeout_ms, 8_000)
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=per_try_timeout)
            human_click(page, locator)
            print(f"  [ok] {step_name} (matched: {selector})", flush=True)
            return True
        except Exception:
            continue
    return False


def note_needs_manual_action(step_name: str, extra: str = "") -> None:
    print(f"  [needs manual action] Couldn't do '{step_name}' automatically. {extra}".rstrip(), flush=True)


def debug_screenshot(page: Page, debug_dir: Path, name: str) -> None:
    """Save a full-page screenshot for later inspection while iterating on
    selectors -- this is how selectors get fixed against the real site instead
    of guessed at, without needing someone to click through the UI by hand.
    """
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        out_path = debug_dir / f"{name}.png"
        page.screenshot(path=str(out_path), full_page=False)
        print(f"  [debug] screenshot saved: {out_path}", flush=True)
    except Exception as exc:
        print(f"  [debug] screenshot failed for {name}: {exc}", flush=True)


def select_cover_photo(page: Page, cover_image_path: Path, debug_dir: Path) -> bool:
    """Upload a specific local image as the cover/thumbnail.

    Unverified guess: TikTok's upload page shows a cover thumbnail with an
    "Edit cover" / "Select cover" control that opens a second picker dialog
    (with its own upload tab), rather than a native file chooser directly --
    same two-step shape as the Facebook automation's cover picker. This tries
    the direct case first, then falls back to hunting for an upload trigger
    inside whatever opened, and takes a debug screenshot either way so the
    real control can be identified if this guess is wrong.
    """
    def _find_upload_trigger():
        for text in ("Upload", "Upload cover", "Upload from computer", "Choose from computer", "Select from computer"):
            candidate = page.get_by_text(text, exact=False).first
            try:
                candidate.wait_for(state="visible", timeout=3_000)
                return candidate
            except Exception:
                continue
        return None

    try:
        cover_trigger = None
        for selector in (
            '[data-testid="cover_edit_photo"]',
            'div:has-text("Select cover")',
            'div:has-text("Edit cover")',
            '[aria-label*="cover" i]',
        ):
            candidate = page.locator(selector).first
            try:
                candidate.wait_for(state="visible", timeout=5_000)
                cover_trigger = candidate
                break
            except Exception:
                continue

        if cover_trigger is None:
            raise RuntimeError("no cover picker control found")

        try:
            with page.expect_file_chooser(timeout=6_000) as fc_info:
                human_click(page, cover_trigger)
            fc_info.value.set_files(str(cover_image_path))
            page.wait_for_timeout(2_500)
            print(f"  [ok] cover photo uploaded directly ({cover_image_path.name})", flush=True)
            return True
        except Exception:
            pass

        debug_screenshot(page, debug_dir, "cover_picker_opened")
        upload_trigger = _find_upload_trigger()
        if upload_trigger is None:
            raise RuntimeError("cover picker opened but no upload trigger found in it")

        with page.expect_file_chooser(timeout=10_000) as fc_info:
            human_click(page, upload_trigger)
        fc_info.value.set_files(str(cover_image_path))
        page.wait_for_timeout(2_500)
        print(f"  [ok] cover photo uploaded via secondary picker ({cover_image_path.name})", flush=True)
        return True
    except Exception as exc:
        note_needs_manual_action(
            "upload the custom cover photo",
            f"Find the cover/thumbnail picker and pick: {cover_image_path}  [{exc}]",
        )
        return False


def fill_caption(page: Page, caption: str) -> bool:
    import random
    import time

    selectors = [
        'div[data-testid="editor"][contenteditable="true"]',
        'div.public-DraftEditor-content[contenteditable="true"]',
        'div[aria-label*="caption" i][contenteditable="true"]',
        'div[role="dialog"] div[contenteditable="true"]',
    ]
    for i, selector in enumerate(selectors):
        per_try_timeout = 8_000 if i < len(selectors) - 1 else 60_000
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=per_try_timeout)
            human_click(page, locator)
            time.sleep(random.uniform(0.1, 0.3))
            # TikTok's caption box is a rich-text editor (Draft.js-style), not a
            # plain textarea/contenteditable that accepts .fill() reliably -- type
            # via simulated keystrokes instead, same fallback approach used for
            # both Facebook's and Instagram's rich-text caption boxes.
            page.keyboard.type(caption, delay=random.randint(15, 45))
            print(f"  [ok] caption filled (matched: {selector})", flush=True)
            return True
        except Exception:
            continue
    return False


def upload_to_tiktok(page: Page, video_path: Path, caption: str, cover_image_path: Path | None, debug_dir: Path) -> None:
    print(f"Opening TikTok upload page: {UPLOAD_URL}", flush=True)
    page.goto(UPLOAD_URL, wait_until="domcontentloaded")
    debug_screenshot(page, debug_dir, "01_upload_page_opened")

    print("Step 1/4: selecting the video file", flush=True)
    selected = False
    file_input_selectors = ['input[type="file"][accept*="video" i]', 'input[type="file"]']
    for i, selector in enumerate(file_input_selectors):
        per_try_timeout = 10_000 if i < len(file_input_selectors) - 1 else 60_000
        file_input = page.locator(selector).first
        try:
            file_input.wait_for(state="attached", timeout=per_try_timeout)
            file_input.set_input_files(str(video_path))
            print(f"  [ok] selected {video_path.name} (matched: {selector})", flush=True)
            selected = True
            break
        except Exception:
            continue
    if not selected:
        note_needs_manual_action(
            "select the video file",
            f"On the upload page, choose 'Select video' and pick: {video_path}",
        )
    debug_screenshot(page, debug_dir, "02_after_video_selected")

    print("Step 2/4: waiting for the video to upload and process", flush=True)
    # TikTok's processing step (transcoding + generating the caption/cover panel)
    # is typically slower than Facebook's or Instagram's -- wait for something that
    # only renders once processing is done (the caption editor) rather than a fixed
    # short sleep, with a generous timeout since this varies a lot with video length.
    processed = False
    for selector in (
        'div[data-testid="editor"][contenteditable="true"]',
        'div.public-DraftEditor-content[contenteditable="true"]',
    ):
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=180_000)
            processed = True
            break
        except Exception:
            continue
    if not processed:
        note_needs_manual_action(
            "confirm the video finished processing",
            "The caption editor never appeared -- check the browser; processing may still be running.",
        )
    debug_screenshot(page, debug_dir, "03_after_processing")

    print("Step 3/4: cover -- selecting cover photo", flush=True)
    if cover_image_path is not None:
        select_cover_photo(page, cover_image_path, debug_dir)
    else:
        print("  skipped (no --cover-image given)", flush=True)
    debug_screenshot(page, debug_dir, "04_after_cover_photo")

    print("Step 4/4: filling in the caption", flush=True)
    if not fill_caption(page, caption):
        note_needs_manual_action("enter the caption", f"Paste this yourself:\n\n{caption}\n")
    debug_screenshot(page, debug_dir, "05_after_caption")

    print(
        "\nReady to publish. The post is filled in but NOT posted yet -- switch to the "
        "browser window, double check everything (including the account it's posting as, "
        "and the cover frame), and click Post yourself when ready.\n"
        "This script does not click Post and never will. It's now just waiting for you "
        "to close this browser tab (whenever you're done, whether you posted it or "
        "decided not to) so it can exit cleanly.",
        flush=True,
    )
    try:
        page.wait_for_event("close", timeout=0)
    except Exception:
        pass
    print("Tab closed. Done.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a short video to TikTok via browser automation.")
    parser.add_argument("--drive-link", required=True, help="Google Drive share link (or file ID) for the video")
    caption_group = parser.add_mutually_exclusive_group(required=True)
    caption_group.add_argument("--caption", help="Caption text for the post")
    caption_group.add_argument(
        "--caption-file", help="Path to a text file containing the caption (avoids shell-quoting multi-line captions)"
    )
    parser.add_argument(
        "--chrome-user-data-dir",
        default=os.getenv("CHROME_USER_DATA_DIR", DEFAULT_CHROME_USER_DATA_DIR),
        help="Path to your Chrome 'User Data' directory",
    )
    parser.add_argument(
        "--profile-directory",
        default=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
        help="Chrome profile folder name inside User Data (e.g. 'Default', 'Profile 1')",
    )
    parser.add_argument(
        "--cover-image",
        default=None,
        help="Path to a local image file to upload as the cover/thumbnail photo",
    )
    parser.add_argument(
        "--debug-dir",
        default=None,
        help="Directory to save a screenshot after each step (for fixing selectors against the live site). "
        "Defaults to a 'debug_screenshots' folder next to this script.",
    )
    args = parser.parse_args()
    caption = args.caption if args.caption is not None else Path(args.caption_file).read_text(encoding="utf-8")
    cover_image_path = Path(args.cover_image) if args.cover_image else None
    debug_dir = Path(args.debug_dir) if args.debug_dir else Path(__file__).parent / "debug_screenshots"

    with tempfile.TemporaryDirectory(prefix="upload_short_") as tmp_dir:
        video_path = download_from_drive(args.drive_link, Path(tmp_dir))

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.chrome_user_data_dir,
                channel="chrome",
                headless=False,
                args=[f"--profile-directory={args.profile_directory}"],
            )
            try:
                page = context.new_page()
                upload_to_tiktok(page, video_path, caption, cover_image_path, debug_dir)
            finally:
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
