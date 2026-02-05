# Metadata Cleaner for Windows

A fast, modern, privacy‑focused metadata cleaning tool built with Python and PySide6.  
Supports images, videos, audio files, and PDFs with both **lossless** and **full** cleaning modes.

## ✨ Features
- Clean metadata from images, videos, audio, and PDFs  
- Lossless mode (preserves image quality and safe tags)  
- Full clean mode (removes all metadata)  
- Auto‑resizing preview panel  
- Drag‑and‑drop support  
- Logging system with separate log viewer  
- Power User rules engine (GPS, timestamps, camera info, XMP, IPTC, etc.)  
- Dark/light theme toggle  
- Windows‑friendly UI  

## 📦 Installation (Source)
```bash
pip install -r requirements.txt
python main.py

[Note]: ExifTool is required for media metadata cleaning.
Download it here: https://exiftool.org/