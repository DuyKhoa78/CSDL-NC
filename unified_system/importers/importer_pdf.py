"""
importer_pdf.py
Nhập file PDF vào bảng:
  bai_giang, trang, tai_nguyen_media,
  doan_van_trang, tu_khoa_trang, chu_de_trang, chu_de_bai_giang, ho_so_bai_giang
Xử lý: pdf2image (thumbnail) → pdfminer (text) → Gemini Vision (nếu text rỗng)
"""
import os, sys, io, json, hashlib, re, base64, tempfile


from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "kho_bai_giang"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123456"),
)

MEDIA_DIR = Path(__file__).parent.parent / "media" / "pdf_thumbnails"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ── Kiểm tra thư viện ────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False
    print("⚠  Thiếu pdf2image: pip install pdf2image  (cần poppler)")

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False
    print("⚠  Thiếu pdfminer.six: pip install pdfminer.six")

try:
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    HAS_GEMINI = bool(GEMINI_API_KEY)
except ImportError:
    HAS_GEMINI = False
    print("⚠  Thiếu google-generativeai: pip install google-generativeai")

# ── Helpers ──────────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def detect_nguon_goc(filepath: Path) -> str:
    parts = [p.lower() for p in filepath.parts]
    for p in parts:
        if "01_thu_thap_web" in p or "thu_thap" in p:
            return "thu_thap_web"
        if "02_ai_tao_sinh" in p or "ai_tao" in p or "gemini" in p or "canva" in p:
            return "ai_tao_sinh"
    return "thu_cong"

def extract_keywords(text: str) -> list:
    words = re.findall(r'[A-Za-zÀ-ỹà-ỹ]{4,}', text or "")
    seen, result = set(), []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
        if len(result) >= 20:
            break
    return result

# ── Gemini Vision ─────────────────────────────────────────────────
def gemini_describe_image(img_path: Path) -> str:
    """Gọi Gemini Vision để mô tả nội dung ảnh trang PDF."""
    if not HAS_GEMINI:
        return ""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        with open(img_path, "rb") as f:
            img_data = f.read()
        img_b64 = base64.b64encode(img_data).decode()
        prompt = (
            "Đây là một trang tài liệu học tập (bài giảng Tin học). "
            "Hãy mô tả ngắn gọn (tối đa 200 từ) nội dung chính của trang này bằng tiếng Việt. "
            "Bao gồm: tiêu đề (nếu có), các ý chính, bảng/sơ đồ (nếu có)."
        )
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": img_b64}
        ])
        return response.text.strip()
    except Exception as e:
        print(f"     ⚠  Gemini lỗi: {e}")
        return ""

# ── Import 1 file PDF ─────────────────────────────────────────────
def import_pdf(filepath: Path, pg_conn, use_gemini=True, verbose=True) -> dict:
    stats = {"slides": 0, "texts": 0, "media": 0, "skipped": False}
    filepath = Path(filepath)

    hash_val = file_hash(filepath)
    pc = pg_conn.cursor()

    pc.execute("SELECT ma_bai_giang FROM bai_giang WHERE ma_hash_tep = %s", (hash_val,))
    if pc.fetchone():
        if verbose:
            print(f"  ⏭  Bỏ qua (đã có): {filepath.name}")
        stats["skipped"] = True
        pc.close()
        return stats

    nguon_goc = detect_nguon_goc(filepath)

    # Trích toàn bộ text từ PDF bằng pdfminer
    full_text_all = ""
    if HAS_PDFMINER:
        try:
            full_text_all = pdfminer_extract(str(filepath)) or ""
        except Exception as e:
            print(f"     ⚠  pdfminer lỗi: {e}")

    # Render từng trang thành ảnh
    page_images = []
    if HAS_PDF2IMAGE:
        try:
            imgs = convert_from_path(str(filepath), dpi=150, fmt="jpeg")
            for idx, img in enumerate(imgs):
                img_name = f"{hash_val[:16]}_p{idx+1:03d}.jpg"
                img_path = MEDIA_DIR / img_name
                img.save(str(img_path), "JPEG", quality=85)
                page_images.append(img_path)
        except Exception as e:
            print(f"     ⚠  pdf2image lỗi: {e}")

    total_pages = max(len(page_images), 1)

    # Tạo bản ghi bai_giang
    pc.execute("""
        INSERT INTO bai_giang
            (tieu_de, nguon_goc, loai_tep, duong_dan_tep,
             ma_hash_tep, so_trang, ngay_them, trang_thai)
        VALUES (%s,%s,'pdf',%s,%s,%s,%s,'hoan_thanh')
        RETURNING ma_bai_giang
    """, (
        filepath.stem, nguon_goc, str(filepath),
        hash_val, total_pages, datetime.now(),
    ))
    ma_bg = pc.fetchone()[0]

    # Chia text theo trang (ước tính đều)
    pages_text = []
    if full_text_all.strip():
        lines = full_text_all.splitlines()
        chunk_size = max(1, len(lines) // total_pages)
        for i in range(total_pages):
            start = i * chunk_size
            end = start + chunk_size if i < total_pages - 1 else len(lines)
            pages_text.append("\n".join(lines[start:end]).strip())
    else:
        pages_text = [""] * total_pages

    page_titles = []
    for p_idx in range(total_pages):
        page_text = pages_text[p_idx] if p_idx < len(pages_text) else ""
        img_path = page_images[p_idx] if p_idx < len(page_images) else None
        img_rel = str(img_path) if img_path else None

        # Gemini Vision nếu text trống
        gemini_desc = ""
        if use_gemini and HAS_GEMINI and img_path and not page_text.strip():
            if verbose:
                print(f"     🤖 Gemini Vision trang {p_idx+1}...")
            gemini_desc = gemini_describe_image(img_path)

        # Tiêu đề trang: dòng đầu không rỗng
        title_candidate = ""
        for line in (page_text or gemini_desc).splitlines():
            line = line.strip()
            if line and len(line) > 3:
                title_candidate = line[:200]
                break

        # Tạo bản ghi trang
        pc.execute("""
            INSERT INTO trang
                (ma_bai_giang, so_thu_tu, tieu_de,
                 noi_dung_van_ban, loai_trang, duong_dan_anh, mo_ta_gemini)
            VALUES (%s,%s,%s,%s,'trang_pdf',%s,%s)
            RETURNING ma_trang
        """, (
            ma_bg, p_idx + 1, title_candidate or None,
            page_text or None, img_rel,
            gemini_desc or None,
        ))
        ma_trang = pc.fetchone()[0]

        # Media record (thumbnail)
        if img_path:
            pc.execute("""
                INSERT INTO tai_nguyen_media
                    (ma_bai_giang, ma_trang, duong_dan, loai_media)
                VALUES (%s,%s,%s,'anh_trang_pdf')
                RETURNING ma_tai_nguyen
            """, (ma_bg, ma_trang, img_rel))
            stats["media"] += 1

        # doan_van_trang: mỗi dòng là 1 đoạn
        combined = (page_text or gemini_desc or "").strip()
        for line_no, line in enumerate(combined.splitlines()):
            line = line.strip()
            if not line:
                continue
            pc.execute("""
                INSERT INTO doan_van_trang
                    (ma_trang, so_doan, so_dong, noi_dung, noi_dung_chuan, vai_tro)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                ma_trang, line_no, line_no, line, line.lower(),
                "tieu_de" if line_no == 0 and title_candidate else "noi_dung",
            ))
            stats["texts"] += 1

        # tu_khoa_trang
        for kw in extract_keywords(combined):
            pc.execute("""
                INSERT INTO tu_khoa_trang (ma_trang, tu_khoa, tu_khoa_chuan, nguon)
                VALUES (%s,%s,%s,'content')
            """, (ma_trang, kw, kw.lower()))

        # chu_de_trang
        if title_candidate:
            pc.execute("""
                INSERT INTO chu_de_trang (ma_trang, nhan_chu_de, loai_chu_de, thu_tu_hien_thi)
                VALUES (%s,%s,'title',%s)
            """, (ma_trang, title_candidate, p_idx + 1))

        page_titles.append(title_candidate)
        stats["slides"] += 1

        if verbose and (p_idx + 1) % 5 == 0:
            print(f"     ... đã xử lý {p_idx+1}/{total_pages} trang")

    # chu_de_bai_giang & ho_so_bai_giang
    main_topic = page_titles[0] if page_titles and page_titles[0] else filepath.stem
    pc.execute("""
        UPDATE bai_giang SET tieu_de=%s WHERE ma_bai_giang=%s
    """, (main_topic, ma_bg))
    pc.execute("""
        INSERT INTO chu_de_bai_giang (ma_bai_giang, nhan_chu_de, loai_chu_de, thu_tu_hien_thi)
        VALUES (%s,%s,'title',1)
    """, (ma_bg, main_topic))
    pc.execute("""
        INSERT INTO ho_so_bai_giang (ma_bai_giang, chu_de_bai, noi_dung_bai)
        VALUES (%s,%s,%s)
        ON CONFLICT (ma_bai_giang) DO NOTHING
    """, (ma_bg, main_topic, full_text_all[:2000] if full_text_all else None))

    pc.close()
    if verbose:
        print(f"  ✅ {filepath.name}: {stats['slides']} trang, {stats['texts']} đoạn, {stats['media']} ảnh")
    return stats


# ── Batch ─────────────────────────────────────────────────────────
def import_folder(folder: Path, recursive=True, use_gemini=True, verbose=True):
    folder = Path(folder)
    pattern = "**/*.pdf" if recursive else "*.pdf"
    files = sorted(folder.glob(pattern))
    if not files:
        print(f"Không tìm thấy file PDF trong: {folder}")
        return

    print(f"\n📂 Import thư mục PDF: {folder}")
    print(f"   Tìm thấy {len(files)} file PDF\n")

    pg = psycopg2.connect(**DB)
    pg.autocommit = False
    total = {"slides": 0, "texts": 0, "media": 0, "ok": 0, "skip": 0, "err": 0}

    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name}")
        try:
            stats = import_pdf(f, pg, use_gemini=use_gemini, verbose=verbose)
            pg.commit()
            if stats["skipped"]:
                total["skip"] += 1
            else:
                total["ok"] += 1
                for k in ["slides", "texts", "media"]:
                    total[k] += stats.get(k, 0)
        except Exception as e:
            pg.rollback()
            print(f"  ❌ Lỗi: {e}")
            import traceback; traceback.print_exc()
            total["err"] += 1

    pg.close()
    print(f"""
╔══════════════════════════════════════╗
║  KẾT QUẢ IMPORT PDF                 ║
╠══════════════════════════════════════╣
║  ✅ Thành công  : {total['ok']:>5} file           ║
║  ⏭  Bỏ qua     : {total['skip']:>5} file (đã có) ║
║  ❌ Lỗi         : {total['err']:>5} file           ║
║  📄 Trang PDF   : {total['slides']:>5}               ║
║  📝 Đoạn văn    : {total['texts']:>5}               ║
║  🖼  Ảnh trang  : {total['media']:>5}               ║
╚══════════════════════════════════════╝
""")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import PDF vào kho_bai_giang")
    parser.add_argument("path", help="File .pdf hoặc thư mục chứa .pdf")
    parser.add_argument("--no-recurse", action="store_true")
    parser.add_argument("--no-gemini",  action="store_true", help="Tắt Gemini Vision")
    args = parser.parse_args()

    p = Path(args.path)
    use_g = not args.no_gemini
    if p.is_file() and p.suffix.lower() == ".pdf":
        pg = psycopg2.connect(**DB)
        pg.autocommit = False
        import_pdf(p, pg, use_gemini=use_g)
        pg.commit()
        pg.close()
    elif p.is_dir():
        import_folder(p, recursive=not args.no_recurse, use_gemini=use_g)
    else:
        print("Lỗi: Đường dẫn không hợp lệ")
        sys.exit(1)
