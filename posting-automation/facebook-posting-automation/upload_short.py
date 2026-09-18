"""Uploads a short video as a Reel to the Sparked Thor Facebook Page through a
real, visible Chrome window driven by Playwright, using a dedicated, isolated
Chrome profile directory (set up once via login_chrome_profile.py) -- no
passwords handled by this script, and no conflict with your everyday browsing
Chrome window or with the Instagram automation, since each uses a completely
separate profile directory (Chrome's single-instance lock applies per
user-data directory, not per named profile).

Steps through Step 3 (opening the Reels tab, clicking Create Reel, attaching
the video) are confirmed against the live site. Steps past that (cover photo,
Next, caption) are still best-effort -- any step that can't be done
automatically is left for you to finish by hand in the visible browser window.
A screenshot is saved after every step (see --debug-dir) so selectors can keep
getting fixed against reality instead of guessed at. Nothing here ever clicks
the final Publish/Share button -- that part is always yours, and the script
simply waits for you to close the tab once you're done.

The Reel composer here is only reachable from the Page's own Reels management
tab, with no identity-switcher, so there's no realistic path for it to end up
posting as your personal profile -- see confirm_posting_as_page().

Usage:
    python upload_short.py --page-url "https://www.facebook.com/SparkedThor" --drive-link "https://drive.google.com/file/d/XXXX/view" --caption "some caption"

Before running: log in once via login_chrome_profile.py (see that file), using
an account that's an admin/editor of the Sparked Thor Page. After that, this
script reuses the saved session automatically -- no repeated logins.
"""
import argparse
import os
import re
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_CHROME_USER_DATA_DIR = str(
    Path(os.environ.get("USERPROFILE", "")) / "ChromeAutomationProfiles" / "sparked_thor_fb"
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

    Scrolls the element into view first -- unlike Playwright's own .click(),
    which does this automatically, driving the mouse to raw bounding_box()
    coordinates does not. Confirmed as a real bug here: after scrolling the page
    down, a target element sat off-screen (negative y in its bounding box), and
    this function clicked those stale coordinates -- blank space -- while still
    reporting success, because mouse.down()/up() don't verify what they hit.
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


def human_scroll(page: Page, total_px: int) -> None:
    """Scroll down gradually in small mouse-wheel increments with randomized
    pauses, instead of jumping straight to a position -- both to look like a
    real person scrolling and because Facebook's Page timeline appears to lazy
    -render the Reels section (including the 'Create reel' link) only once it's
    scrolled near, so a single instant jump doesn't reliably trigger it.
    """
    import random
    import time

    scrolled = 0
    while scrolled < total_px:
        step = random.randint(120, 280)
        page.mouse.wheel(0, step)
        scrolled += step
        time.sleep(random.uniform(0.08, 0.22))


def click_first_match(page: Page, step_name: str, selectors: list[str], timeout_ms: int = 120_000) -> bool:
    """Try each selector in turn and click the first one that becomes visible.

    Only the LAST selector in the list gets the full timeout_ms wait (long enough
    for a human to notice and do the step by hand in the visible window) -- earlier
    candidates get a short wait, since if one of several guessed selectors is right,
    it's normally present almost immediately. Returns True if an automated click
    succeeded, False if none matched in time -- selectors here are best-effort
    guesses at Facebook's current markup and may not match after a UI change.
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


def confirm_posting_as_page(page: Page, page_url: str, pause_ms: int = 5_000) -> None:
    """Brief informational pause, not a hard gate. Confirmed against the live
    site: the 'Create reel' entry point only exists on the Page's own Reels
    management tab (inside 'Manage Page'), reached by this script's own
    page.goto(<page_id>/reels) -- there's no identity-switcher in that dialog
    the way a general-purpose composer might have, so there's no realistic path
    for this to end up posting as a personal profile. Still pauses briefly and
    logs the page identity for a final visual gut-check, but doesn't block on a
    keypress (this script normally runs with no interactive stdin, so input()
    would just hit EOF and fall through instantly anyway). The real safety net
    is still the final pre-Publish review at the end of the run.
    """
    print(
        f"  [info] Composer opened from the Page's own Reels tab ({page_url}) -- "
        f"posting as a personal profile isn't reachable from this entry point. "
        f"Pausing {pause_ms // 1000}s for a visual gut-check anyway.",
        flush=True,
    )
    try:
        page.wait_for_timeout(pause_ms)
    except Exception:
        pass


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
    """Upload a specific local image as the Reel cover/thumbnail.

    Confirmed against the live site (final 'Reel settings' screen): the cover
    control is a small 'Edit' badge overlaid on the thumbnail preview in the
    top-left of the settings panel, not a 'Choose photo'-style text link the
    way Instagram's is. Clicking it is expected to open a second picker UI
    (probably with its own 'Upload photo' / 'Choose from computer' trigger)
    rather than a native file chooser directly -- that second step is still a
    guess, so this takes a debug screenshot right after opening the picker to
    make that guess easy to fix if it's wrong.
    """
    def _find_upload_trigger():
        for text in ("Upload photo", "Upload from computer", "Choose from computer", "Select from computer", "Upload"):
            candidate = page.get_by_text(text, exact=False).first
            try:
                candidate.wait_for(state="visible", timeout=3_000)
                return candidate
            except Exception:
                continue
        return None

    try:
        # The Reel settings panel renders in with a loading skeleton first (same
        # pattern confirmed on the Create Reel dialog) -- wait for something known
        # to render late and reliably (the caption placeholder) before searching
        # for the Edit badge, otherwise this can run mid-skeleton and find nothing.
        try:
            page.get_by_text("Describe your reel", exact=False).first.wait_for(state="visible", timeout=15_000)
        except Exception:
            pass

        # Confirmed via DOM dump: an exact-text "Edit" match only ever finds
        # Facebook's own "Edit profile" link (aria-label "Edit profile")
        # elsewhere on the page, at x~1036 -- well outside the settings modal
        # (roughly x 0-400). The real in-modal badge never showed up under an
        # exact match at all, meaning its element must carry extra text beyond
        # the visible "Edit" (e.g. a screen-reader-only label) -- exact=False
        # (substring match) is needed to find it, with the x<400 filter still
        # doing the work of rejecting the "Edit profile" decoy.
        edit_badge = None
        for text in ("Edit", "Choose photo", "Custom thumbnail", "Add thumbnail", "Change thumbnail"):
            candidates = page.get_by_text(text, exact=False)
            try:
                count = candidates.count()
            except Exception:
                count = 0
            found = False
            for i in range(count):
                candidate = candidates.nth(i)
                try:
                    candidate.wait_for(state="visible", timeout=3_000)
                    box = candidate.bounding_box()
                    if box and box["x"] < 400:
                        edit_badge = candidate
                        found = True
                        break
                except Exception:
                    continue
            if found:
                break
        if edit_badge is None:
            try:
                dump = page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('*'))
                        .filter(el => (el.textContent || '').includes('Edit'))
                        .slice(0, 8)
                        .map(el => {
                            const r = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return {
                                tag: el.tagName, role: el.getAttribute('role'),
                                ariaLabel: el.getAttribute('aria-label'),
                                rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                                display: style.display, visibility: style.visibility, opacity: style.opacity,
                            };
                        })
                    """
                )
                print(f"  [debug] 'Edit' element dump (edit_badge search failed): {dump}", flush=True)
            except Exception:
                pass
            raise RuntimeError("no thumbnail-picker control found")

        # Try the simple case first: clicking the badge itself opens a native file
        # chooser directly (like Instagram's equivalent control does).
        try:
            with page.expect_file_chooser(timeout=6_000) as fc_info:
                human_click(page, edit_badge)
            fc_info.value.set_files(str(cover_image_path))
            page.wait_for_timeout(2_500)
            print(f"  [ok] cover photo uploaded directly ({cover_image_path.name})", flush=True)
            return True
        except Exception:
            pass

        # Screenshot right away to check whether the click actually did anything --
        # confirmed flaky the same way the Create Reel button was: an identical
        # click sometimes silently does nothing. If the screen looks unchanged
        # (no upload trigger findable), retry once with Playwright's own native
        # .click() before giving up.
        debug_screenshot(page, debug_dir, "07b_cover_picker_opened")
        upload_trigger = _find_upload_trigger()

        if upload_trigger is None:
            print("  [retry] cover picker didn't visibly open -- retrying Edit badge with a native click", flush=True)
            try:
                page.locator('text="Edit"').first.click(timeout=8_000)
            except Exception:
                pass
            debug_screenshot(page, debug_dir, "07c_cover_picker_retry")
            upload_trigger = _find_upload_trigger()

        if upload_trigger is None:
            # Still nothing -- dump every element containing "Edit" (tag, role,
            # aria-label, rect) so the real control can be identified from the log
            # instead of guessed at again, same approach that found the real
            # Create Reel button after two failed guesses.
            try:
                dump = page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('*'))
                        .filter(el => (el.textContent || '').trim() === 'Edit')
                        .slice(0, 6)
                        .map(el => {
                            const r = el.getBoundingClientRect();
                            return {
                                tag: el.tagName, role: el.getAttribute('role'),
                                ariaLabel: el.getAttribute('aria-label'),
                                rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                            };
                        })
                    """
                )
                print(f"  [debug] 'Edit' element dump: {dump}", flush=True)
            except Exception:
                pass
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
            f"Find the thumbnail/cover picker (Edit badge) and pick: {cover_image_path}  [{exc}]",
        )
        return False


def fill_caption(page: Page, caption: str) -> bool:
    import random
    import time

    selectors = [
        'div[aria-label*="description" i][contenteditable="true"]',
        'div[aria-placeholder*="description" i][contenteditable="true"]',
        'div[aria-label*="Write a description" i][contenteditable="true"]',
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

    try:
        placeholder = page.get_by_text("Write a description", exact=False).first
        placeholder.wait_for(state="visible", timeout=15_000)
        human_click(page, placeholder)
        time.sleep(random.uniform(0.1, 0.3))
        page.keyboard.type(caption, delay=random.randint(15, 45))
        print('  [ok] caption filled (matched: text="Write a description..." + keyboard.type)', flush=True)
        return True
    except Exception:
        return False


def build_reels_url(page_url: str) -> str:
    """Append /reels to a Page URL. Pages without a claimed vanity name are
    addressed as https://www.facebook.com/profile.php?id=<id> -- naively
    appending /reels after that query string would produce a broken URL, so
    for that form this pulls the numeric id out and addresses the page as
    https://www.facebook.com/<id>/reels instead, which Facebook accepts as an
    equivalent path for both vanity and non-vanity pages.
    """
    match = re.search(r"[?&]id=(\d+)", page_url)
    if match:
        return f"https://www.facebook.com/{match.group(1)}/reels"
    return page_url.rstrip("/") + "/reels"


def upload_to_facebook(
    page: Page, page_url: str, video_path: Path, caption: str, cover_image_path: Path | None, debug_dir: Path
) -> None:
    reels_url = build_reels_url(page_url)
    print(f"Opening Facebook Page: {reels_url}", flush=True)
    page.goto(reels_url, wait_until="domcontentloaded")

    # A modest scroll to get the Reels panel roughly into view (belt-and-suspenders
    # in case any part of it needs to be near-viewport to finish rendering) --
    # human_click's own scroll_into_view_if_needed handles the actual precision, so
    # this no longer needs to land exactly on target the way it did before that fix.
    human_scroll(page, 500)
    debug_screenshot(page, debug_dir, "01_scrolled_to_reels_tab")

    print("Step 1/8: opening the Create Reel dialog", flush=True)
    # Confirmed via DOM inspection (_diagnose_create_reel.py): the real control is
    # <div role="button" aria-label="Create reel">, not a link or plain text node --
    # a bare text="Create reel" locator matched this same element but human_click
    # was clicking stale off-screen coordinates for it (see human_click's docstring),
    # which looked like success without ever opening the dialog.
    opened = click_first_match(
        page,
        "Create Reel button",
        [
            'div[role="button"][aria-label="Create reel"]',
            'div[aria-label*="Create reel" i]',
            'text="Create reel"',
        ],
    )
    if not opened:
        note_needs_manual_action(
            "open the Create Reel dialog",
            f"Navigate to {page_url} yourself and click 'Create reel'.",
        )
    debug_screenshot(page, debug_dir, "02_create_reel_dialog")

    # Verify the real dialog actually opened before doing anything else -- an
    # earlier run's file-input selector matched some unrelated hidden input on
    # the page and silently reported "success" even though no dialog was open,
    # so this check exists specifically to catch that failure mode instead of
    # trusting the click result alone. Not scoped to role="dialog" -- confirmed
    # via screenshot that Facebook's modal here doesn't necessarily expose that
    # role, and content renders in with a loading skeleton first, so this also
    # needs a longer timeout than a simple visibility check.
    #
    # Confirmed flaky even on the exact right selector: one run's click matched
    # div[role="button"][aria-label="Create reel"] correctly but the dialog still
    # didn't open, while an identical match on a different run worked fine --
    # looks like an occasional timing/event race with the manual mouse-simulation
    # in human_click(). Retries once with Playwright's own native .click() (which
    # does its own actionability waiting and auto-scroll) rather than repeating
    # the same manual click that just failed.
    def _dialog_opened() -> bool:
        try:
            page.locator('text="Add video"').first.wait_for(state="visible", timeout=20_000)
            return True
        except Exception:
            return False

    dialog_opened = _dialog_opened()
    if dialog_opened:
        print("  [ok] Create Reel dialog confirmed open", flush=True)
    else:
        print("  [retry] dialog didn't open -- retrying with a native (non-simulated) click", flush=True)
        try:
            page.locator('div[role="button"][aria-label="Create reel"]').first.click(timeout=10_000)
        except Exception:
            pass
        dialog_opened = _dialog_opened()
        if dialog_opened:
            print("  [ok] Create Reel dialog confirmed open (after retry)", flush=True)
        else:
            note_needs_manual_action(
                "confirm the Create Reel dialog opened",
                "Both click attempts failed to visibly open the dialog -- skipping the remaining automated "
                "steps rather than risk uploading into the wrong element. Open it yourself and continue by hand.",
            )

    print("Step 2/8: confirming you're posting as the Page (info only)", flush=True)
    confirm_posting_as_page(page, page_url)

    if not dialog_opened:
        debug_screenshot(page, debug_dir, "03_after_video_selected")
        print("Steps 3-8 skipped: dialog wasn't confirmed open.", flush=True)
        return

    print("Step 3/8: selecting the video file", flush=True)
    # Scoped by accept="video/*" rather than a dialog wrapper role (confirmed this
    # modal doesn't reliably expose role="dialog") -- disambiguates from any other
    # unrelated hidden file input on the page (e.g. the Page's own cover-photo
    # upload, which would accept images, not video). This is what previously
    # caused a false "success" that silently uploaded into the wrong input.
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
            f"In the dialog, choose 'Add video' and pick: {video_path}",
        )

    print("Step 4/8: waiting for the video to process", flush=True)
    try:
        page.wait_for_timeout(5_000)
    except Exception:
        pass
    debug_screenshot(page, debug_dir, "03_after_video_selected")

    # Confirmed against the live site: the flow is three screens, not two --
    # (1) upload/preview -> Next -> (2) 'Edit reel' tools screen (Trim/Captions/
    # Audio/Music, no cover or caption control here) -> Next -> (3) the actual
    # Share screen with cover photo + description. The first version of this
    # script only clicked Next once and then tried to fill the caption while
    # still on screen (2), which silently failed since nothing there matched.
    next_button_selectors = ['button:has-text("Next")', 'div[role="button"]:has-text("Next")']

    print("Step 5/8: clicking Next (upload screen -> Edit reel tools screen)", flush=True)
    advanced = click_first_match(page, "Next button (1 of 2)", next_button_selectors)
    if not advanced:
        note_needs_manual_action("click Next on the upload screen")
    debug_screenshot(page, debug_dir, "05_edit_reel_tools_screen")

    print("Step 6/8: clicking Next (Edit reel tools screen -> Share screen)", flush=True)
    advanced = click_first_match(page, "Next button (2 of 2)", next_button_selectors)
    if not advanced:
        note_needs_manual_action(
            "click Next on the Edit reel tools screen",
            "Facebook's Reel composer flow may have changed -- check the browser.",
        )
    debug_screenshot(page, debug_dir, "06_share_screen")

    print("Step 7/8: cover/thumbnail -- selecting cover photo", flush=True)
    if cover_image_path is not None:
        select_cover_photo(page, cover_image_path, debug_dir)
    else:
        print("  skipped (no --cover-image given)", flush=True)
    debug_screenshot(page, debug_dir, "07_after_cover_photo")

    print("Step 8/8: filling in the description", flush=True)
    if not fill_caption(page, caption):
        note_needs_manual_action("enter the caption/description", f"Paste this yourself:\n\n{caption}\n")
    debug_screenshot(page, debug_dir, "08_after_caption")

    print(
        "\nReady to publish. The post is filled in but NOT shared yet -- switch to the "
        "browser window, double check everything (including that it's posting as the "
        "Page, and the cover frame), and click Publish/Share yourself when ready.\n"
        "This script does not click Publish and never will. It's now just waiting for you "
        "to close this browser tab (whenever you're done, whether you published it or "
        "decided not to) so it can exit cleanly.",
        flush=True,
    )
    try:
        page.wait_for_event("close", timeout=0)
    except Exception:
        pass
    print("Tab closed. Done.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a short video as a Reel to a Facebook Page via browser automation.")
    parser.add_argument(
        "--page-url",
        required=True,
        help="URL of the Facebook Page to post as, e.g. https://www.facebook.com/SparkedThor",
    )
    parser.add_argument("--drive-link", required=True, help="Google Drive share link (or file ID) for the video")
    caption_group = parser.add_mutually_exclusive_group(required=True)
    caption_group.add_argument("--caption", help="Caption/description text for the post")
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
                upload_to_facebook(page, args.page_url, video_path, caption, cover_image_path, debug_dir)
            finally:
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
