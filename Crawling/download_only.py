"""
Tải PPTX về máy tính (không cần Google Drive API).
File sẽ được lưu vào thư mục: downloaded_pptx/
"""

import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

# ============================================================
SAVE_DIR = os.path.join(os.path.dirname(__file__), "downloaded_pptx")
HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
SLIDE_RE = re.compile(r"https://docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)")

SOURCES = [
    {
        "name": "thaycai.net - BÀI GIẢNG ĐIỆN TỬ TIN HỌC 10 KNTT (tất cả bài)",
        "url": "https://www.thaycai.net/2022/11/bai-giang-dien-tu-tin-hoc-10-kntt.html",
        "subfolder": "Tin10_KNTT",
        "is_index": True,
    },
    {
        "name": "thaycai.net - BÀI GIẢNG ĐIỆN TỬ TIN HỌC 11 KNTT (tất cả bài)",
        "url": "https://www.thaycai.net/2023/10/bai-giang-dien-tu-tin-hoc-11-sach-kntt-dh-thud.html",
        "subfolder": "Tin11_KNTT",
        "is_index": True,
    },
    # Lưu ý: thaycai.net chỉ có lớp 10-12, không có Tin 8.
    # Tin 8 KNTT có thể lấy từ nguồn khác nếu bạn cung cấp link.
]

# ============================================================

def safe_name(text: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", text).strip()
    return name[:180] if name else "unnamed"


def get_page_title(soup: BeautifulSoup) -> str:
    """Lấy tiêu đề trang từ <h1> hoặc <title>."""
    h1 = soup.find("h1")
    if h1:
        return safe_name(h1.get_text(strip=True))
    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        # Bỏ phần " - thaycai.net" ở cuối
        raw = re.sub(r"\s*[-|–]\s*thaycai\.net.*$", "", raw, flags=re.IGNORECASE)
        return safe_name(raw)
    return ""


def get_slides_from_page(url: str, session: requests.Session, seen: set,
                         page_title: str = "") -> list[dict]:
    """Lấy tất cả Google Slides ID từ một trang."""
    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"    [!] Lỗi tải trang {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Ưu tiên lấy tiêu đề từ trang hiện tại
    if not page_title:
        page_title = get_page_title(soup)

    items = []
    for tag in soup.find_all("a", href=True):
        m = SLIDE_RE.search(tag["href"])
        if m:
            fid = m.group(1)
            if fid not in seen:
                seen.add(fid)
                # Dùng tiêu đề trang làm tên file, không dùng text link
                title = page_title or safe_name(
                    tag.get_text(strip=True) or f"slide_{fid}"
                )
                items.append({"title": title, "file_id": fid})
    return items


def get_lesson_urls(index_url: str, session: requests.Session) -> list[str]:
    """Lấy các URL bài học từ trang index."""
    try:
        r = session.get(index_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  [!] Lỗi tải index: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    base = "https://www.thaycai.net"
    urls = []
    seen_urls = {index_url}

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if (href.startswith(base)
                and href not in seen_urls
                and re.search(r"/20\d{2}/\d{2}/", href)):
            seen_urls.add(href)
            urls.append(href)

    return urls


def download_pptx(item: dict, save_dir: str, session: requests.Session) -> bool:
    """Tải file PPTX từ Google Slides (public) về máy."""
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{item['title']}.pptx"
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 10240:
        print(f"    [>] Đã có: {filename}")
        return True

    export_url = (
        f"https://docs.google.com/presentation/d/{item['file_id']}/export/pptx"
    )
    print(f"    [↓] Tải: {filename}")

    try:
        resp = session.get(export_url, headers=HEADERS, timeout=60, stream=True)
        content_type = resp.headers.get("Content-Type", "")

        if resp.status_code != 200:
            print(f"    [!] HTTP {resp.status_code}")
            return False

        if "text/html" in content_type:
            print(f"    [!] File yêu cầu đăng nhập Google (không phải public).")
            return False

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"    [✓] OK ({size_kb:.0f} KB) → {filename}")
        return True

    except Exception as e:
        print(f"    [!] Lỗi: {e}")
        return False


# ============================================================

def main():
    print("=" * 60)
    print("  TẢI PPTX VỀ MÁY (không cần Google Drive API)")
    print(f"  Thư mục lưu: {SAVE_DIR}")
    print("=" * 60)

    session  = requests.Session()
    seen_ids = set()
    success  = 0
    fail     = 0

    for src in SOURCES:
        print(f"\n{'─' * 60}")
        print(f"[NGUỒN] {src['name']}")
        print(f"{'─' * 60}")

        save_dir = os.path.join(SAVE_DIR, src.get("subfolder", ""))
        items    = []

        if src.get("is_index"):
            # Crawl trang index → từng trang bài
            lesson_urls = get_lesson_urls(src["url"], session)
            print(f"  [*] Tìm thấy {len(lesson_urls)} trang bài con")

            for i, url in enumerate(lesson_urls, 1):
                print(f"  [*] ({i}/{len(lesson_urls)}) {url}")
                found = get_slides_from_page(url, session, seen_ids)
                items.extend(found)
                if found:
                    print(f"      → {len(found)} file: {', '.join(x['title'][:30] for x in found)}")
                time.sleep(0.5)
        else:
            # Trang đơn
            items = get_slides_from_page(src["url"], session, seen_ids)
            print(f"  [*] Tìm thấy {len(items)} file")

        if not items:
            print("  [!] Không có file để tải từ nguồn này.")
            continue

        # Xóa file cũ có tên sai (Tải về file Powerpoint.pptx)
        stale = os.path.join(save_dir, "Tải về file Powerpoint.pptx")
        if os.path.exists(stale):
            os.remove(stale)
            print("  [*] Đã xóa file cũ tên sai.")

        print(f"\n  [*] Bắt đầu tải {len(items)} file...")
        for i, item in enumerate(items, 1):
            print(f"\n  [{i}/{len(items)}] {item['title']}")
            ok = download_pptx(item, save_dir, session)
            if ok:
                success += 1
            else:
                fail += 1
            time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"  KẾT QUẢ: {success} thành công | {fail} thất bại")
    print(f"  File được lưu tại: {SAVE_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
