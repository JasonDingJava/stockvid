# StockVid CLI 🎬

>A command-line tool to search and download free stock videos from **Pexels**, **Pixabay**, and **Mixkit** in batch — perfect for content creators, video editors, and AI video workflows.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## ✨ Features

- 🔍 **Search & download** — Query stock video sites by keyword
- 📦 **Batch mode** — Download multiple videos at once by category
- 🗂️ **Auto-organize** — Saves videos into category folders
- 📋 **Inventory export** — Generates CSV/TXT manifest of all downloaded assets
- 🧹 **Deduplication** — Skips already-downloaded URLs automatically
- 🚦 **Rate limiting** — Respectful to source servers
- 🌐 **Multi-source** — Pexels · Pixabay · Mixkit

## 🚀 Quick Start

```bash
# Install
pip install -r requirements.txt

# Search and download by keyword
python stockvid.py search "mafia boss" --source pexels --count 10

# Batch download from a keyword list
python stockvid.py batch keywords.txt --output ./videos

# Download from multiple sources
python stockvid.py search "rainy city night" --source all --count 15
```

## 📦 Output Structure

```
./videos/
├── mafia_boss/
│   ├── video_01.mp4
│   └── ...
├── rain_city/
├── romantic_tension/
├── inventory.csv
└── inventory.txt
```

## 📋 Keyword File Format

Create a `keywords.txt`:

```
mafia boss
luxury car
rain city night
romantic couple
```

## 🔧 Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`

## 📄 License

MIT
