@echo off
cd /d "%~dp0"
REM Optional: preview cover-frame choices first, without posting:
REM   python upload_short.py --drive-link "PASTE_DRIVE_LINK_HERE" --caption "PASTE_CAPTION_HERE" --preview-covers
REM Then add --cover-timestamp-ms <ms> below once you've picked one from cover_previews/.
python upload_short.py --drive-link "PASTE_DRIVE_LINK_HERE" --caption "PASTE_CAPTION_HERE"
pause
