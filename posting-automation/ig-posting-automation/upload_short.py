"""Uploads a short video to Instagram (Reels) through a real, visible Chrome window
driven by Playwright, using a dedicated, isolated Chrome profile directory (set up
once via login_chrome_profile.py) -- no passwords handled by this script, and no
conflict with your everyday browsing Chrome window since it's a completely
separate profile directory (Chrome's single-instance lock applies per user-data
directory, not per named profile, so reusing your normal Chrome install here would
fight with whatever's already open there).

Facebook and TikTok are intentionally not implemented yet. Instagram is being
validated end-to-end first since its upload flow's exact selectors could only be
guessed at, not verified against the live site, so any step it can't do
automatically is left for you to finish by hand in the visible browser window --
each stage just waits (with a generous timeout) for the next expected screen to
show up, whether that happened because of the automated click or because you did
it yourself. Nothing here ever clicks the final Share/Post button -- that part is
always yours, and the script simply waits for you to close the tab once you're
done, so there's no terminal interaction required at any point.

Usage:
    python upload_short.py --drive-link "https://drive.google.com/file/d/XXXX/view" --caption "some caption"

Before running: log in once via login_chrome_profile.py (see that file). After
that, this script reuses the saved session automatically -- no repeated logins.
"""
import argparse
import os
import re
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_CHROME_USER_DATA_DIR = str(
    Path(os.environ.get("USERPROFILE", "")) / "ChromeAutomationProfiles" / "sparked_thor_ig"
)


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
    """
    import random
    import time

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
    it's normally present almost immediately; giving every guess the full generous
    timeout meant a wrong early guess silently ate minutes before falling through to
    the one that actually worked, which looked identical to the script being stuck.
    Returns True if an automated click succeeded, False if none matched in time --
    selectors here are best-effort guesses at Instagram's current markup and may
    not match after a UI change.
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


def select_cover_photo(page: Page, cover_image_path: Path) -> bool:
    """Upload a specific local image as the cover, via the Cover/Trim screen's
    'Select from computer' link -- confirmed present on that screen from a real
    screenshot. Using an exact pre-picked frame sidesteps guessing at which of
    Instagram's ~4 auto-generated thumbnail choices is best.
    """
    try:
        link = page.get_by_text("Select from computer", exact=False).first
        link.scroll_into_view_if_needed(timeout=5_000)
        with page.expect_file_chooser(timeout=15_000) as fc_info:
            link.click()
        fc_info.value.set_files(str(cover_image_path))
        # Give Instagram time to actually process/render the uploaded image before the
        # caller clicks Next -- clicking immediately risked a race where Next fired before
        # the new cover was accepted, silently leaving the screen unchanged (seen on a
        # larger/slower-to-process video after this worked fine on a smaller one).
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        page.wait_for_timeout(2_500)
        print(f"  [ok] cover photo uploaded ({cover_image_path.name})", flush=True)
        return True
    except Exception:
        note_needs_manual_action(
            "upload the custom cover photo",
            f"Click 'Select from computer' next to Cover photo and pick: {cover_image_path}",
        )
        return False


def select_original_aspect_ratio(page: Page) -> bool:
    """Best-effort: open the crop screen's aspect-ratio menu and pick 'Original'.

    The opener icon (bottom-left of the media preview) has no visible text, so its
    selector here is a guess at Instagram's likely aria-label rather than something
    verified against the real markup -- if it can't be found, this leaves the
    default crop alone rather than click something unintended.
    """
    opened = click_first_match(
        page,
        "aspect ratio menu icon",
        [
            '[aria-label="Select crop"]',
            '[aria-label*="crop" i]',
            'svg[aria-label*="crop" i]',
            '[aria-label*="aspect" i]',
        ],
        timeout_ms=15_000,
    )
    if not opened:
        note_needs_manual_action(
            "open the aspect ratio menu",
            "Click the icon at the bottom-left of the video preview and choose 'Original' yourself.",
        )
        return False

    picked = click_first_match(
        page,
        "Original aspect ratio option",
        ['text="Original"', '[role="menuitem"]:has-text("Original")'],
        timeout_ms=10_000,
    )
    if not picked:
        note_needs_manual_action("select 'Original' aspect ratio", "Click 'Original' in the menu yourself.")
        return False

    # The menu doesn't auto-close after picking -- it stays open and can block the
    # Next button underneath. Escape bubbles up to Instagram's own dialog and
    # triggers a "Discard post?" exit-confirmation, so instead click a neutral
    # point (the screen title) to close just the small dropdown.
    try:
        human_click(page, page.locator('text="Crop"').first)
    except Exception:
        pass
    return True


def fill_caption(page: Page, caption: str) -> bool:
    import random
    import time

    # Only the last candidate gets a long wait, same reasoning as click_first_match --
    # otherwise a wrong early guess silently burns minutes before the real one is tried.
    selectors = [
        'textarea[aria-label*="caption" i]',
        'div[aria-label*="caption" i][contenteditable="true"]',
        'div[aria-placeholder*="caption" i][contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="Write a caption" i]',
        'div[role="dialog"] div[contenteditable="true"]',
        'div[role="dialog"] textarea',
    ]
    for i, selector in enumerate(selectors):
        per_try_timeout = 8_000 if i < len(selectors) - 1 else 60_000
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=per_try_timeout)
            human_click(page, locator)
            time.sleep(random.uniform(0.1, 0.3))
            locator.fill(caption)
            print(f"  [ok] caption filled (matched: {selector})", flush=True)
            return True
        except Exception:
            continue

    # Fallback: the caption box is "Add a caption..." placeholder text, likely a custom
    # rich-text editor rather than a plain textarea/contenteditable div with the usual
    # aria attributes -- click directly on the visible placeholder text and type via
    # simulated keystrokes instead of .fill(), which needs a real form control.
    try:
        placeholder = page.get_by_text("Add a caption", exact=False).first
        placeholder.wait_for(state="visible", timeout=15_000)
        human_click(page, placeholder)
        time.sleep(random.uniform(0.1, 0.3))
        page.keyboard.type(caption, delay=random.randint(15, 45))
        print('  [ok] caption filled (matched: text="Add a caption..." + keyboard.type)', flush=True)
        return True
    except Exception:
        return False


def upload_to_instagram(page: Page, video_path: Path, caption: str, cover_image_path: Path | None) -> None:
    print("Opening Instagram...", flush=True)
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

    print("Step 1/5: opening the create-post dialog", flush=True)
    opened = click_first_match(
        page,
        "Create button",
        [
            'svg[aria-label="New post"]',
            '[aria-label="New post"]',
            'a[href="#"] svg[aria-label="New post"]',
            'span:has-text("Create")',
        ],
    )
    if not opened:
        note_needs_manual_action(
            "open the Create menu", "Click the + / Create icon yourself when you see this window."
        )
    else:
        # Clicking Create only opens a small dropdown (Post / Live video / Ad / More) --
        # the actual upload dialog needs this second click on "Post" within it.
        picked_post = click_first_match(
            page,
            "Post option in Create menu",
            ['text="Post"', '[role="menuitem"]:has-text("Post")', 'a:has-text("Post")'],
            timeout_ms=15_000,
        )
        if not picked_post:
            note_needs_manual_action(
                "click 'Post' in the Create dropdown", "Click 'Post' in the menu that opened yourself."
            )

    dialog_opened = False
    if opened:
        try:
            page.locator(
                'div[role="dialog"]:has-text("Drag photos and videos here"), '
                'div[role="dialog"] button:has-text("Select from computer")'
            ).first.wait_for(state="visible", timeout=15_000)
            dialog_opened = True
            print("  [ok] create-post dialog confirmed open", flush=True)
        except Exception:
            note_needs_manual_action(
                "confirm the create-post dialog opened",
                "The New post click didn't visibly open the upload dialog -- open it yourself.",
            )

    print("Step 2/5: selecting the video file", flush=True)
    # Scoped to the dialog specifically -- a bare page-wide input[type=file] can match an
    # unrelated hidden input elsewhere on the page (e.g. profile photo upload) and "succeed"
    # without ever touching the actual post-creation flow.
    file_input_selectors = (
        ['div[role="dialog"] input[type="file"]', 'input[type="file"]']
        if dialog_opened
        else ['input[type="file"]']
    )
    selected = False
    for i, selector in enumerate(file_input_selectors):
        per_try_timeout = 8_000 if i < len(file_input_selectors) - 1 else 60_000
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
            f"In the dialog, choose 'Select from computer' and pick: {video_path}",
        )

    print("Step 3/5: crop screen -- selecting original aspect ratio", flush=True)
    select_original_aspect_ratio(page)
    advanced = click_first_match(
        page, "Next button (crop screen)", ['button:has-text("Next")', 'div[role="button"]:has-text("Next")']
    )
    if not advanced:
        note_needs_manual_action("click Next on the crop screen")

    print("Step 4/5: cover/trim screen -- selecting cover photo", flush=True)
    if cover_image_path is not None:
        select_cover_photo(page, cover_image_path)
    else:
        print("  skipped (no --cover-image given)", flush=True)
    advanced = click_first_match(
        page, "Next button (cover/trim screen)", ['button:has-text("Next")', 'div[role="button"]:has-text("Next")']
    )
    if not advanced:
        note_needs_manual_action("click Next on the cover/trim screen")

    # Verify we actually reached the final share screen before trying to fill the caption --
    # otherwise a caption selector that's too loosely scoped can silently match some unrelated
    # contenteditable still on the cover/trim screen and report false success.
    on_final_screen = False
    for selector in ['text="New reel"', 'text="New post"']:
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=8_000)
            on_final_screen = True
            break
        except Exception:
            continue
    if not on_final_screen:
        note_needs_manual_action(
            "confirm the final share screen was reached",
            "The Next click on the cover/trim screen may not have advanced -- check the browser.",
        )

    print("Step 5/5: filling in the caption", flush=True)
    if on_final_screen and not fill_caption(page, caption):
        note_needs_manual_action("enter the caption", f"Paste this caption yourself:\n\n{caption}\n")
    elif not on_final_screen:
        print(f"  [needs manual action] Skipped caption fill -- not on the final screen. Caption:\n\n{caption}\n", flush=True)

    print(
        "\nReady to publish. The post is filled in but NOT shared yet -- switch to the "
        "browser window, double check everything (including the cover frame), and click "
        "Share yourself when ready.\n"
        "This script does not click Share and never will. It's now just waiting for you "
        "to close this browser tab (whenever you're done, whether you shared it or "
        "decided not to) so it can exit cleanly.",
        flush=True,
    )
    try:
        page.wait_for_event("close", timeout=0)
    except Exception:
        pass
    print("Tab closed. Done.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a short video to Instagram via browser automation.")
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
        help="Path to a local image file to upload as the cover photo via 'Select from computer'",
    )
    args = parser.parse_args()
    caption = args.caption if args.caption is not None else Path(args.caption_file).read_text(encoding="utf-8")
    cover_image_path = Path(args.cover_image) if args.cover_image else None

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
                upload_to_instagram(page, video_path, caption, cover_image_path)
            finally:
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
