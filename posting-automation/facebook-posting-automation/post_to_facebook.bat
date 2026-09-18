@echo off
cd /d "%~dp0"
python upload_short.py --page-url "https://www.facebook.com/SparkedThor" --drive-link "PASTE_DRIVE_LINK_HERE" --caption "PASTE_CAPTION_HERE" --cover-image "PASTE_COVER_IMAGE_PATH_HERE"
pause
