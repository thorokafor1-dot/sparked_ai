# Landing Page

The static site served at `https://sparked.thorokafor.com`: the main Sparked page (`index.html`, `styles.css`, `script.js`, `assets/`), plus the legal and OAuth pages that live platform integrations depend on.

## Pages that other systems depend on (never rename or move these)
- `tos.html`, `privacy.html`: referenced by the TikTok app review.
- `tiktok-oauth-callback.html`: the HTTPS OAuth redirect relay for TikTok login. It must match the registered callback URL.
- `tiktok<token>.txt`: TikTok domain verification.
- `outlier-tracker-tos.html`, `outlier-tracker-privacy.html`: legal pages for the outlier tracker.

## Quality gates (automatic, see `qa/checks_web.py`)
`landing-local-links`: every local `href`/`src`/`url()` must resolve to a real file, and every page needs a `<title>`. After deploying, spot-check that the pages above return HTTP 200 (`curl -sI <url>`).

## Scope rules
- Plain static HTML/CSS/JS with no build step. Keep it that way unless there's a real need.
- Page copy follows the root brand voice: confident, charming, emotionally intelligent, and no em dashes.
