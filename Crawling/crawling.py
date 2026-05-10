"""
Crawl file PPTX/Google Slides từ nhiều nguồn và lưu lên Google Drive.

Nguồn hỗ trợ:
  1. thaycai.net - Bài 1 Hệ điều hành (Tin 11)
  2. thaycai.net - BÀI GIẢNG ĐIỆN TỬ TIN HỌC 11 (crawl tất cả bài từ trang index)
  3. tailieugiaovien.edu.vn - PowerPoint Tin 8 (lấy từ Google Drive folder công khai)

Yêu cầu cài đặt:
    pip install requests beautifulsoup4 google-auth google-auth-oauthlib google-api-python-client

Hướng dẫn thiết lập Google Drive API:
    1. Vào https://console.cloud.google.com/
    2. Tạo project -> Bật Google Drive API
    3. Tạo OAuth 2.0 Client ID (Desktop App)
    4. Tải credentials.json vào cùng thư mục với script
"""

import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup

# Google API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# ============================================================
# CẤU HÌNH
# ============================================================

# --- Thư mục Drive đích ---
DRIVE_FOLDER_ID = "1jESEon3PyJj-1e0tqpxsAvIJRUY--wQl"

# --- Thư mục local tạm ---
LOCAL_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloaded_pptx")

# --- File xác thực Google ---
TOKEN_FILE      = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")

# --- Quyền truy cập Drive ---
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# --- Header giả lập trình duyệt ---
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ============================================================
# DANH SÁCH NGUỒN CẦN CÀO
# Sources = list of dict:
#   name   : tên hiển thị
#   type   : "thaycai_single" | "thaycai_index" | "drive_folder"
#   url    : URL trang (dùng cho thaycai_*)
#   folder_id : Google Drive folder ID (dùng cho drive_folder)
#   subfolder  : tên subfolder trong Drive đích (tùy chọn)
# ============================================================

SOURCES = [
    {
        "name": "thaycai.net - Bài 1 Hệ điều hành (Tin 11)",
        "type": "thaycai_single",
        "url": "https://www.thaycai.net/2023/10/bai-1-he-dieu-hanh-sach-kntt-dh-thud.html",
        "subfolder": "Tin11_Bai1",
    },
    {
        "name": "thaycai.net - BÀI GIẢNG ĐIỆN TỬ TIN HỌC 11 (tất cả bài)",
        "type": "thaycai_index",
        "url": "https://www.thaycai.net/2023/10/bai-giang-dien-tu-tin-hoc-11-sach-kntt-dh-thud.html",
        "subfolder": "Tin11_TatCaBai",
    },
    {
        "name": "tailieugiaovien.edu.vn - PowerPoint Tin 8 (Drive folder công khai)",
        "type": "drive_folder",
        "folder_id": "1hJ10coz1A_rfwVl81MeCRVzpwj06OEqR",
        "subfolder": "Tin8_KNTT",
    },
]


# ============================================================
# HELPER: Trích xuất Google Slides ID từ HTML
# ============================================================

SLIDE_PATTERN = re.compile(
    r"https://docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)"
)

def make_safe_name(text: str) -> str:
    """Làm sạch tên file, loại bỏ ký tự đặc biệt."""
    name = re.sub(r'[\\/*?:"<>|]', "_", text).strip()
    return name or "unnamed"


# ============================================================
# NGUỒN 1: thaycai_single
# Cào 1 trang, lấy link Google Slides trực tiếp
# ============================================================

def crawl_thaycai_single(url: str, session: requests.Session) -> list[dict]:
    """Cào 1 trang thaycai.net, trả về danh sách Google Slides items."""
    print(f"  [*] Cào trang đơn: {url}")
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [!] Lỗi tải trang: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        m = SLIDE_PATTERN.search(tag["href"])
        if m:
            fid = m.group(1)
            if fid in seen:
                continue
            seen.add(fid)
            title = make_safe_name(tag.get_text(strip=True) or f"slide_{fid}")
            items.append({
                "title": title,
                "file_id": fid,
                "export_url": f"https://docs.google.com/presentation/d/{fid}/export/pptx",
                "source": "google_slides",
            })
            print(f"    [+] Tìm thấy Slides: {title}")

    if not items:
        print("  [!] Không tìm thấy Google Slides nào trên trang này.")
    return items


# ============================================================
# NGUỒN 2: thaycai_index
# Trang index → crawl từng trang bài → lấy Google Slides
# ============================================================

def crawl_thaycai_index(index_url: str, session: requests.Session) -> list[dict]:
    """
    Cào trang index thaycai.net, lấy tất cả link bài học,
    sau đó vào từng trang bài để lấy Google Slides.
    """
    print(f"  [*] Cào trang index: {index_url}")
    base_domain = "https://www.thaycai.net"

    try:
        resp = session.get(index_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [!] Lỗi tải trang index: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Thu thập các link bài học (trang con cùng domain, không phải trang index)
    lesson_urls = []
    seen_urls = {index_url}
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if (
            href.startswith(base_domain)
            and href not in seen_urls
            and "/2023/" in href or "/2024/" in href or "/2025/" in href
        ):
            # Chỉ lấy các bài học cùng chuỗi năm/tháng
            if re.search(r"/20\d{2}/\d{2}/", href) and href not in seen_urls:
                seen_urls.add(href)
                lesson_urls.append(href)

    # Lọc bỏ trang index chính và các trang không liên quan
    lesson_urls = [u for u in lesson_urls if u != index_url]
    print(f"  [*] Tìm thấy {len(lesson_urls)} trang bài học con.")

    all_items = []
    seen_slide_ids = set()

    for i, lesson_url in enumerate(lesson_urls, 1):
        print(f"  [*] ({i}/{len(lesson_urls)}) Cào bài: {lesson_url}")
        try:
            r = session.get(lesson_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"    [!] Lỗi: {e}")
            time.sleep(1)
            continue

        page_soup = BeautifulSoup(r.text, "html.parser")

        # Lấy tiêu đề trang
        h1 = page_soup.find("h1")
        page_title = make_safe_name(h1.get_text(strip=True)) if h1 else f"bai_{i}"

        found_on_page = 0
        for tag in page_soup.find_all("a", href=True):
            m = SLIDE_PATTERN.search(tag["href"])
            if m:
                fid = m.group(1)
                if fid in seen_slide_ids:
                    continue
                seen_slide_ids.add(fid)
                link_text = tag.get_text(strip=True)
                title = make_safe_name(link_text or page_title or f"slide_{fid}")
                all_items.append({
                    "title": title,
                    "file_id": fid,
                    "export_url": f"https://docs.google.com/presentation/d/{fid}/export/pptx",
                    "source": "google_slides",
                })
                found_on_page += 1
                print(f"    [+] Slides: {title}")

        if found_on_page == 0:
            print(f"    [-] Không có Google Slides trên trang này.")

        time.sleep(0.8)  # Tránh bị rate limit

    print(f"  [*] Tổng cộng: {len(all_items)} file từ thaycai_index")
    return all_items


# ============================================================
# NGUỒN 3: drive_folder
# Liệt kê file PPTX từ Google Drive folder công khai
# ============================================================

def crawl_drive_folder(folder_id: str, drive_service) -> list[dict]:
    """
    Liệt kê tất cả file PPTX/PPT trong Google Drive folder công khai.
    Trả về danh sách items với thông tin tải về.
    """
    print(f"  [*] Liệt kê file từ Drive folder: {folder_id}")
    items = []
    page_token = None

    pptx_mimes = {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.google-apps.presentation",  # Google Slides
    }

    try:
        while True:
            query = f"'{folder_id}' in parents and trashed = false"
            response = drive_service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=100,
            ).execute()

            for f in response.get("files", []):
                mime = f.get("mimeType", "")
                name = f.get("name", "unnamed")
                fid  = f.get("id")

                if mime in pptx_mimes or name.lower().endswith((".pptx", ".ppt")):
                    # Google Slides → export PPTX
                    if mime == "application/vnd.google-apps.presentation":
                        items.append({
                            "title": make_safe_name(name),
                            "file_id": fid,
                            "export_url": None,
                            "source": "drive_slides",
                            "drive_service": True,
                        })
                    else:
                        items.append({
                            "title": make_safe_name(os.path.splitext(name)[0]),
                            "file_id": fid,
                            "export_url": None,
                            "source": "drive_pptx",
                            "drive_service": True,
                        })
                    print(f"    [+] {name}")

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    except Exception as e:
        print(f"  [!] Lỗi khi đọc Drive folder: {e}")

    print(f"  [*] Tìm thấy {len(items)} file trong Drive folder")
    return items


# ============================================================
# TẢI FILE VỀ LOCAL
# ============================================================

def download_item(item: dict, session: requests.Session, drive_service) -> str | None:
    """
    Tải file về máy theo loại nguồn.
    Trả về đường dẫn file đã tải, hoặc None nếu thất bại.
    """
    os.makedirs(LOCAL_DOWNLOAD_DIR, exist_ok=True)
    filename = f"{item['title']}.pptx"
    # Giới hạn độ dài tên file
    if len(filename) > 200:
        filename = filename[:196] + ".pptx"
    filepath = os.path.join(LOCAL_DOWNLOAD_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        print(f"    [>] Đã có local: {filename}")
        return filepath

    source = item.get("source", "")

    # --- Google Slides export ---
    if source == "google_slides":
        print(f"    [*] Tải Google Slides: {filename}")
        try:
            resp = session.get(item["export_url"], headers=HEADERS, timeout=60, stream=True)
            content_type = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and "text/html" not in content_type:
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                size_kb = os.path.getsize(filepath) / 1024
                print(f"    [+] OK ({size_kb:.1f} KB): {filename}")
                return filepath
            else:
                print(f"    [!] File yêu cầu đăng nhập Google hoặc không tải được.")
                return None
        except Exception as e:
            print(f"    [!] Lỗi: {e}")
            return None

    # --- Google Drive PPTX file ---
    elif source == "drive_pptx":
        print(f"    [*] Tải Drive PPTX: {filename}")
        try:
            request = drive_service.files().get_media(fileId=item["file_id"])
            fh = io.FileIO(filepath, "wb")
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.close()
            size_kb = os.path.getsize(filepath) / 1024
            print(f"    [+] OK ({size_kb:.1f} KB): {filename}")
            return filepath
        except Exception as e:
            print(f"    [!] Lỗi tải Drive file: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None

    # --- Google Drive Slides (export PPTX) ---
    elif source == "drive_slides":
        print(f"    [*] Export Drive Slides → PPTX: {filename}")
        try:
            data = drive_service.files().export(
                fileId=item["file_id"],
                mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ).execute()
            with open(filepath, "wb") as f:
                f.write(data)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"    [+] OK ({size_kb:.1f} KB): {filename}")
            return filepath
        except Exception as e:
            print(f"    [!] Lỗi export Drive Slides: {e}")
            return None

    print(f"    [!] Loại nguồn không xác định: {source}")
    return None


# ============================================================
# XÁC THỰC GOOGLE DRIVE
# ============================================================

def authenticate_google_drive():
    """Xác thực Google Drive API bằng OAuth 2.0."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[*] Làm mới token xác thực...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"\n[!] THIẾU FILE: {CREDENTIALS_FILE}")
                print("    1. Vào https://console.cloud.google.com/")
                print("    2. Bật Google Drive API")
                print("    3. Tạo OAuth 2.0 Client ID (Desktop App)")
                print(f"    4. Tải credentials.json vào: {os.path.dirname(CREDENTIALS_FILE)}")
                raise FileNotFoundError(f"Không tìm thấy {CREDENTIALS_FILE}")

            print("[*] Đang mở trình duyệt để xác thực Google Drive...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("[+] Token đã lưu.")

    return build("drive", "v3", credentials=creds)


# ============================================================
# UPLOAD LÊN GOOGLE DRIVE
# ============================================================

def get_or_create_subfolder(drive_service, parent_id: str, folder_name: str) -> str:
    """Tạo subfolder trong Drive nếu chưa có, trả về folder ID."""
    query = (
        f"name='{folder_name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    results = drive_service.files().list(
        q=query, fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive_service.files().create(body=meta, fields="id").execute()
    print(f"  [+] Tạo subfolder: {folder_name}")
    return folder["id"]


def upload_to_drive(drive_service, filepath: str, folder_id: str) -> str | None:
    """Upload file PPTX lên Google Drive."""
    filename = os.path.basename(filepath)
    print(f"    [*] Upload: {filename}")

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }
    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    try:
        with open(filepath, "rb") as f:
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype=mime, resumable=True)
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        ).execute()
        link = uploaded.get("webViewLink", "")
        print(f"    [+] Xong! Link: {link}")
        return uploaded.get("id")
    except Exception as e:
        print(f"    [!] Lỗi upload: {e}")
        return None


# ============================================================
# HÀM CHÍNH
# ============================================================

def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 65)
    print("  CRAWL PPTX ĐA NGUỒN -> GOOGLE DRIVE")
    print("=" * 65)

    # Xác thực Drive
    print("\n[BƯỚC 1] Xác thực Google Drive...")
    try:
        drive_service = authenticate_google_drive()
        print("[+] Xác thực thành công!")
    except FileNotFoundError as e:
        print(f"\n[LỖI] {e}")
        return

    session = requests.Session()
    total_success = 0
    total_fail    = 0

    # Xử lý từng nguồn
    for src_idx, source in enumerate(SOURCES, 1):
        print(f"\n{'=' * 65}")
        print(f"[NGUỒN {src_idx}/{len(SOURCES)}] {source['name']}")
        print(f"{'=' * 65}")

        # Xác định folder đích trên Drive
        subfolder_name = source.get("subfolder", "")
        if subfolder_name:
            target_folder_id = get_or_create_subfolder(
                drive_service, DRIVE_FOLDER_ID, subfolder_name
            )
        else:
            target_folder_id = DRIVE_FOLDER_ID

        # Thu thập items theo loại nguồn
        src_type = source["type"]
        items = []

        if src_type == "thaycai_single":
            items = crawl_thaycai_single(source["url"], session)

        elif src_type == "thaycai_index":
            items = crawl_thaycai_index(source["url"], session)

        elif src_type == "drive_folder":
            items = crawl_drive_folder(source["folder_id"], drive_service)

        else:
            print(f"  [!] Loại nguồn không được hỗ trợ: {src_type}")
            continue

        if not items:
            print(f"  [!] Không có file để tải từ nguồn này.")
            continue

        print(f"\n  [*] Tải và upload {len(items)} file...")

        for i, item in enumerate(items, 1):
            print(f"\n  [{i}/{len(items)}] {item['title']}")

            # Tải về local
            filepath = download_item(item, session, drive_service)
            if not filepath:
                total_fail += 1
                continue

            # Upload lên Drive
            result = upload_to_drive(drive_service, filepath, target_folder_id)
            if result:
                total_success += 1
            else:
                total_fail += 1

            time.sleep(1)

    # Kết quả cuối
    print(f"\n{'=' * 65}")
    print(f"  HOÀN TẤT: {total_success} thành công | {total_fail} thất bại")
    print(f"  Drive: https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
