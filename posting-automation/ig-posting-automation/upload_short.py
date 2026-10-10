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
import sys
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
    # Preferred: the cover screen carries its own image file input (accept=image/jpeg,image/png, verified
    # 2026-10-01), so set it directly. Clicking the link to get a file chooser failed when it ran before
    # the screen finished loading.
    try:
        cover_input = page.locator('div[role="dialog"] input[type="file"][accept*="image"]').first
        cover_input.wait_for(state="attached", timeout=20_000)
        cover_input.set_input_files(str(cover_image_path))
        page.wait_for_timeout(3_000)
        print(f"  [ok] cover photo uploaded ({cover_image_path.name}, via the dialog's image input)", flush=True)
        return True
    except Exception:
        pass
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


def set_schedule(page: Page, when) -> bool:
    """Verified live 2026-10-02 on the final (caption) screen: a 'Schedule content' toggle (the dialog's
    second input[role=switch]; the first is 'Add AI label') reveals a Date dropdown button ("Fri, Oct 2,
    2026") that opens a month grid of button[role=gridcell] days, and a Time field made of three
    spinbuttons (aria-label Hours / Minutes / AM PM) that take typed digits ("07", "00", "P"). With the
    toggle on, the dialog's Share button becomes Schedule, which stays the user's click."""
    d = page.locator('div[role="dialog"]')
    try:
        switch = d.locator('input[role="switch"]').nth(1)
        switch.scroll_into_view_if_needed()
        if not switch.is_checked():
            switch.click(force=True)
            page.wait_for_timeout(1500)
        hour12 = when.strftime("%I")
        for label, value in (("Hours", hour12), ("Minutes", when.strftime("%M")), ("AM PM", when.strftime("%p")[0])):
            d.locator(f'input[role="spinbutton"][aria-label="{label}"]').click()
            page.keyboard.type(value, delay=80)
            page.wait_for_timeout(300)
        d.locator('div[role="button"]:has-text(", 20")').first.click()  # the date dropdown ("Fri, Oct 2, 2026")
        page.wait_for_timeout(1200)
        month = when.strftime("%B %Y")
        if not page.get_by_text(month, exact=True).count():
            print(f"  [warn] date picker isn't showing {month}; pick the date by hand", flush=True)
            return False
        page.locator('button[role="gridcell"][aria-disabled="false"]').filter(
            has_text=re.compile(rf"^{when.day}$")
        ).first.click()
        page.wait_for_timeout(800)
        date_text = d.locator('div[role="button"]:has-text(", 20")').first.inner_text().strip()
        got = tuple(
            d.locator(f'input[aria-label="{l}"]').get_attribute("aria-valuenow") for l in ("Hours", "Minutes")
        )
    except Exception as e:
        print(f"  [warn] schedule fields: {e}", flush=True)
        return False
    want_date = f"{when.strftime('%a, %b')} {when.day}, {when.year}"
    if date_text != want_date or got != (str(int(hour12)), str(when.minute)):
        print(f"  [warn] schedule reads {date_text} {got}, wanted {want_date} {when:%I:%M %p}", flush=True)
        return False
    print(f"  [ok] scheduled for {date_text} {when:%I:%M %p}; the button now says Schedule", flush=True)
    return True


def upload_to_instagram(
    page: Page, video_path: Path, caption: str, cover_image_path: Path | None, schedule_at=None
) -> None:
    print("Opening Instagram...", flush=True)
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    # An expired session lands on the login page; wait for the user to log in rather than clicking around
    # it (a generic "Create" text match then hit a feed element and opened someone else's post).
    try:
        page.wait_for_selector('svg[aria-label="New post"]', timeout=10_000)
    except Exception:
        print("  [needs manual action] Log in to Instagram in the window that opened; continuing once the "
              "home feed loads (up to 5 minutes).", flush=True)
        page.wait_for_selector('svg[aria-label="New post"]', timeout=300_000)
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

    print("Step 1/5: opening the create-post dialog", flush=True)
    opened = click_first_match(
        page,
        "Create button",
        [
            'svg[aria-label="New post"]',
            '[aria-label="New post"]',
            'a[href="#"] svg[aria-label="New post"]',
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
    # A "video posts are now shared as reels" notice with an OK button sits over the crop screen and
    # swallows the clicks on the crop menu (verified 2026-10-01). Dismiss it first when it's there.
    try:
        ok = page.locator('div[role="dialog"] button:has-text("OK")').first
        ok.wait_for(state="visible", timeout=8_000)
        ok.click()
        page.wait_for_timeout(800)
        print("  [ok] dismissed the reels notice", flush=True)
    except Exception:
        pass
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
    # Seen 2026-10-02: right after a cover upload the first Next click can be swallowed (the dialog is still
    # busy with the image), leaving it on the Edit screen. Retry Next once before giving up.
    on_final_screen = False
    for attempt in range(2):
        for selector in ['text="New reel"', 'text="New post"']:
            try:
                page.locator(selector).first.wait_for(state="visible", timeout=8_000)
                on_final_screen = True
                break
            except Exception:
                continue
        if on_final_screen or attempt:
            break
        print("  [retry] still on the cover/trim screen -- clicking Next again", flush=True)
        page.wait_for_timeout(2_000)
        click_first_match(page, "Next button (retry)", ['div[role="dialog"] div[role="button"]:has-text("Next")'], 10_000)
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

    if schedule_at is not None:
        print(f"Step 6/6: scheduling for {schedule_at:%a %d %b %I:%M %p}", flush=True)
        if not (on_final_screen and set_schedule(page, schedule_at)):
            note_needs_manual_action(
                "set the schedule", f"Turn on 'Schedule content' and pick {schedule_at:%a %d %b, %I:%M %p}."
            )
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
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--drive-link", help="Google Drive share link (or file ID) for the video")
    source_group.add_argument("--video", help="Local video file (skips the Drive round-trip for a fresh render)")
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
    parser.add_argument(
        "--schedule",
        default=None,
        help='Local time "YYYY-MM-DD HH:MM" to schedule the reel for; the script fills it in, you click Schedule',
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=0,
        help="Expose Chrome's DevTools port so a second process can inspect the live composer (selector work)",
    )
    args = parser.parse_args()
    # captions carry emoji; a redirected stdout on Windows defaults to cp1252 and crashed mid-flow
    sys.stdout.reconfigure(encoding="utf-8")
    caption = args.caption if args.caption is not None else Path(args.caption_file).read_text(encoding="utf-8")
    schedule_at = None
    if args.schedule:
        from datetime import datetime
        schedule_at = datetime.fromisoformat(args.schedule)
        if schedule_at <= datetime.now():
            parser.error(f"--schedule {args.schedule} is in the past")

    # Project-wide pre-flight (qa/preflight_post.py): abort before anything is uploaded.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "qa"))
    from preflight_post import caption_problems, enforce, vertical_video_problems
    enforce(caption_problems("instagram", caption), "caption")
    cover_image_path = Path(args.cover_image) if args.cover_image else None

    with tempfile.TemporaryDirectory(prefix="upload_short_") as tmp_dir:
        video_path = Path(args.video).resolve() if args.video else download_from_drive(args.drive_link, Path(tmp_dir))
        enforce(vertical_video_problems("instagram", Path(video_path)), "video file")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.chrome_user_data_dir,
                channel="chrome",
                headless=False,
                args=[f"--profile-directory={args.profile_directory}"]
                + ([f"--remote-debugging-port={args.debug_port}"] if args.debug_port else []),
            )
            try:
                page = context.new_page()
                upload_to_instagram(page, video_path, caption, cover_image_path, schedule_at)
            finally:
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
