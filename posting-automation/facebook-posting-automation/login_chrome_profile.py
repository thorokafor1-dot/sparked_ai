"""One-time helper: opens a real Chrome window backed by a dedicated, isolated
profile directory (separate from your normal Chrome install, and separate from
the Instagram automation's profile) so upload_short.py never conflicts with your
everyday browsing Chrome window/tabs or with the IG automation. Log into the
Sparked Thor Facebook Page manually in the window this opens, then close the
tab -- the session is saved in that directory for future automated runs.

Usage:
    python login_chrome_profile.py --chrome-user-data-dir "C:\\path\\to\\dedicated\\dir" --url "https://www.facebook.com/login"
"""
import argparse

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description="Open an isolated Chrome profile for a one-time manual login.")
    parser.add_argument("--chrome-user-data-dir", required=True, help="Dedicated profile directory (will be created if missing)")
    parser.add_argument("--url", default="https://www.facebook.com/login", help="Page to open for login")
    args = parser.parse_args()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=args.chrome_user_data_dir,
            channel="chrome",
            headless=False,
        )
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        print("Log in manually in the window that just opened. Close the tab/window when you're done.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass
        print("Login window closed. Session saved.")


if __name__ == "__main__":
    main()
