#!/usr/bin/env python3
"""
StockVid CLI — Search & download free stock videos from Pexels, Pixabay, and Mixkit.

Usage:
    python stockvid.py search <keyword> [--source pexels|pixabay|mixkit|all] [--count 10] [--output ./downloads]
    python stockvid.py batch <keyword_file> [--source all] [--count 10] [--output ./downloads]
"""

import argparse
import csv
import json
import os
import re
import sys
import textwrap
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ───── User‑agent ───────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ───── Dataclass ────────────────────────────────────────────


@dataclass
class VideoAsset:
    title: str
    url: str
    source: str
    resolution: str = ""
    category: str = ""
    filename: str = ""


# ───── Download Tracking ────────────────────────────────────


class DownloadTracker:
    """Persist download state so resuming is safe."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.state_file = output_dir / ".download_state.json"
        self.downloaded: set = set()
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.downloaded = set(data.get("downloaded", []))
            except Exception:
                self.downloaded = set()

    def is_downloaded(self, url: str) -> bool:
        return url in self.downloaded

    def mark_downloaded(self, url: str):
        self.downloaded.add(url)

    def save(self):
        self.state_file.write_text(
            json.dumps({"downloaded": list(self.downloaded)}, indent=2)
        )


# ───── Video Searchers ──────────────────────────────────────


class PexelsSearcher:
    """Search and download from Pexels video pages."""

    BASE = "https://www.pexels.com/search/videos/"

    def search(self, keyword: str, count: int = 10) -> List[VideoAsset]:
        url = f"{self.BASE}{urllib.parse.quote(keyword)}/"
        print(f"  [Pexels] Searching: {keyword}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [Pexels] HTTP {resp.status_code}, skipping")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        video_links = set()
        # Look for video page links
        for a in soup.select('a[href*="/video/"]'):
            href = a.get("href", "")
            if href.startswith("/video/"):
                video_links.add(urljoin("https://www.pexels.com", href))

        assets = []
        for vurl in list(video_links)[:count]:
            title, video_file = self._extract_video(vurl)
            if video_file:
                assets.append(
                    VideoAsset(
                        title=title or "pexels_video",
                        url=video_file,
                        source="pexels",
                        filename=video_file.split("/")[-1],
                    )
                )
            time.sleep(0.5)  # be polite
        return assets

    def _extract_video(self, page_url: str) -> tuple:
        """Visit a video page and find the download link."""
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return None, None
            soup = BeautifulSoup(resp.text, "html.parser")
            # Find the HD download link
            for a in soup.select("a"):
                href = a.get("href", "")
                if "video-files" in href and href.endswith(".mp4"):
                    title_tag = soup.find("h1") or soup.find("title")
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    return title, href
        except Exception as e:
            print(f"    [Pexels] Error: {e}")
        return None, None


class PixabaySearcher:
    """Search and download from Pixabay videos."""

    BASE = "https://pixabay.com/videos/search/"

    def search(self, keyword: str, count: int = 10) -> List[VideoAsset]:
        url = f"{self.BASE}{urllib.parse.quote(keyword)}/"
        print(f"  [Pixabay] Searching: {keyword}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [Pixabay] HTTP {resp.status_code}, skipping")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        assets = []

        # Pixabay video cards often have data‑attrs or specific selectors
        for item in soup.select("[class*='item'], article, [class*='video']"):
            a_tag = item.find("a")
            img = item.find("img")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if "/videos/" not in href and "/video/" not in href:
                continue
            full_url = urljoin("https://pixabay.com", href)
            title = img.get("alt", "") if img else ""

            # Try to find a direct download link on the page
            vid_url = self._extract_video(full_url)
            if vid_url:
                assets.append(
                    VideoAsset(
                        title=self._slugify(title) or "pixabay_video",
                        url=vid_url,
                        source="pixabay",
                        filename=vid_url.split("/")[-1],
                    )
                )
                if len(assets) >= count:
                    break
            time.sleep(0.5)
        return assets

    def _extract_video(self, page_url: str) -> Optional[str]:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return None
            # Look for video source files
            soup = BeautifulSoup(resp.text, "html.parser")
            for source in soup.select("video source"):
                src = source.get("src", "")
                if src.endswith(".mp4"):
                    return src
            # Fallback: look for download links
            for a in soup.select("a[download]"):
                href = a.get("href", "")
                if href.endswith(".mp4"):
                    return href
        except Exception as e:
            print(f"    [Pixabay] Error: {e}")
        return None

    @staticmethod
    def _slugify(text: str, maxlen: int = 60) -> str:
        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        text = re.sub(r"[\s_]+", "_", text)
        return text[:maxlen]


class MixkitSearcher:
    """Search from Mixkit (limited — heavy JS site)."""

    BASE = "https://mixkit.co/free-stock-video/"

    def search(self, keyword: str, count: int = 10) -> List[VideoAsset]:
        url = f"{self.BASE}{urllib.parse.quote(keyword)}/"
        print(f"  [Mixkit] Searching: {keyword}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  [Mixkit] HTTP {resp.status_code}, skipping")
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            assets = []
            for a in soup.select("a[href*='/free-stock-video/']"):
                href = a.get("href", "")
                if href.count("/") < 4:
                    continue
                full_url = urljoin("https://mixkit.co", href)
                title = a.get_text(strip=True) or "mixkit_video"
                vid_url = self._extract_video(full_url)
                if vid_url:
                    assets.append(
                        VideoAsset(
                            title=title,
                            url=vid_url,
                            source="mixkit",
                            filename=vid_url.split("/")[-1],
                        )
                    )
                    if len(assets) >= count:
                        break
                time.sleep(0.5)
            return assets
        except Exception as e:
            print(f"  [Mixkit] Error: {e}")
            return []

    def _extract_video(self, page_url: str) -> Optional[str]:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            for source in soup.select("video source"):
                src = source.get("src", "")
                if src.endswith(".mp4"):
                    return src
        except Exception:
            pass
        return None


# ───── Downloader ───────────────────────────────────────────


def download_video(asset: VideoAsset, dest: Path, tracker: DownloadTracker) -> bool:
    """Download a single video file. Returns True on success."""
    if tracker.is_downloaded(asset.url):
        print(f"  ⏭️  Already downloaded: {asset.filename}")
        return True

    dest_path = dest / asset.filename
    if dest_path.exists():
        tracker.mark_downloaded(asset.url)
        tracker.save()
        print(f"  ⏭️  Exists: {asset.filename}")
        return True

    try:
        print(f"  ⬇️  Downloading: {asset.filename} ...", end=" ", flush=True)
        resp = requests.get(asset.url, headers=HEADERS, timeout=60, stream=True)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return False
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        size_mb = downloaded / (1024 * 1024)
        print(f"✅ {size_mb:.1f}MB")
        tracker.mark_downloaded(asset.url)
        tracker.save()
        return True
    except Exception as e:
        print(f"❌ {e}")
        return False


# ───── Inventory Writer ─────────────────────────────────────


def write_inventory(assets: List[VideoAsset], output_dir: Path):
    """Write inventory.csv and inventory.txt."""
    csv_path = output_dir / "inventory.csv"
    txt_path = output_dir / "inventory.txt"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "source", "filename", "url"])
        for a in assets:
            w.writerow([a.category, a.source, a.filename, a.url])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Inventory — {len(assets)} videos\n")
        f.write("=" * 50 + "\n\n")
        cats = {}
        for a in assets:
            cats.setdefault(a.category, []).append(a)
        for cat, items in cats.items():
            f.write(f"[{cat}] ({len(items)} videos)\n")
            for a in items:
                f.write(f"  • {a.filename} ({a.source})\n")
            f.write("\n")

    print(f"  📋 Inventory: {csv_path}")
    print(f"  📋 Manifest:  {txt_path}")


# ───── CLI ──────────────────────────────────────────────────


def cmd_search(args):
    keyword = args.keyword
    sources = {
        "pexels": PexelsSearcher(),
        "pixabay": PixabaySearcher(),
        "mixkit": MixkitSearcher(),
    }
    active = sources if args.source == "all" else {args.source: sources[args.source]}

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    tracker = DownloadTracker(output_dir)

    all_assets: List[VideoAsset] = []
    cat_name = keyword.lower().replace(" ", "_")[:30]

    for name, searcher in active.items():
        assets = searcher.search(keyword, args.count)
        for a in assets:
            a.category = cat_name
        all_assets.extend(assets)
        print(f"  Found {len(assets)} from {name}")

        cat_dir = output_dir / cat_name
        cat_dir.mkdir(parents=True, exist_ok=True)

        for asset in assets:
            download_video(asset, cat_dir, tracker)

    if all_assets:
        write_inventory(all_assets, output_dir)

    print(f"\n✅ Done! {len(all_assets)} videos saved to {output_dir}")


def cmd_batch(args):
    """Read keywords from a file, search each one."""
    kws = Path(args.keyword_file).read_text().strip().splitlines()
    kws = [k.strip() for k in kws if k.strip()]
    print(f"📋 Batch: {len(kws)} keywords loaded from {args.keyword_file}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_assets: List[VideoAsset] = []

    for kw in kws:
        print(f"\n{'─' * 50}\n🔍 Keyword: {kw}\n{'─' * 50}")
        # Re‑use search logic
        ns_args = argparse.Namespace(
            keyword=kw,
            source=args.source,
            count=args.count,
            output=str(output_dir),
        )
        cmd_search(ns_args)

    print(f"\n🎉 Batch complete! Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="StockVid CLI — Download free stock videos in batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python stockvid.py search "mafia boss" --source pexels --count 10
              python stockvid.py batch keywords.txt --source all --count 15
            """
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = sub.add_parser("search", help="Search and download videos by keyword")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument(
        "--source",
        choices=["pexels", "pixabay", "mixkit", "all"],
        default="all",
        help="Source site (default: all)",
    )
    p_search.add_argument(
        "--count", type=int, default=10, help="Videos per source (default: 10)"
    )
    p_search.add_argument(
        "--output",
        "-o",
        default="./downloads",
        help="Output directory (default: ./downloads)",
    )

    # batch
    p_batch = sub.add_parser("batch", help="Batch download from keyword file")
    p_batch.add_argument("keyword_file", help="Text file with one keyword per line")
    p_batch.add_argument(
        "--source",
        choices=["pexels", "pixabay", "mixkit", "all"],
        default="all",
    )
    p_batch.add_argument("--count", type=int, default=10)
    p_batch.add_argument("--output", "-o", default="./downloads")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "batch":
        cmd_batch(args)


if __name__ == "__main__":
    main()
