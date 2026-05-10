"""
file_router.py
Nhận dạng file (PPTX / PDF), xác định nguon_goc từ đường dẫn,
rồi dispatch sang importer tương ứng.

Cách dùng:
  # Import toàn bộ thư mục input/
  python file_router.py

  # Import 1 thư mục cụ thể
  python file_router.py --dir "input/01_thu_thap_web"

  # Import 1 file cụ thể
  python file_router.py --file "input/01_thu_thap_web/Tin10_KNTT/Bai1.pptx"

  # Tắt Gemini Vision (nhanh hơn, không tốn quota)
  python file_router.py --no-gemini

  # Xem trước (không import thực sự)
  python file_router.py --dry-run
"""
import os, sys, io, argparse
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from dotenv import load_dotenv
import psycopg2

# Thêm thư mục gốc vào sys.path để import importer_*
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv(ROOT / ".env")

from importer_pptx import import_pptx, import_folder as pptx_folder
from importer_pdf  import import_pdf,  import_folder as pdf_folder

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "kho_bai_giang"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123456"),
)

INPUT_DIR = ROOT / "input"

# ── Quét toàn bộ input/ ──────────────────────────────────────────
def scan_input(base_dir: Path) -> dict:
    """Trả về dict {ext: [Path]} sau khi quét đệ quy."""
    result = {"pptx": [], "pdf": [], "other": []}
    for f in sorted(base_dir.rglob("*")):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".pptx":
            result["pptx"].append(f)
        elif ext == ".pdf":
            result["pdf"].append(f)
        else:
            result["other"].append(f)
    return result

# ── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="File Router – tự động nhận dạng và import PPTX/PDF"
    )
    parser.add_argument("--dir",      default=None, help="Thư mục cụ thể cần import")
    parser.add_argument("--file",     default=None, help="File cụ thể cần import")
    parser.add_argument("--no-gemini",action="store_true", help="Tắt Gemini Vision cho PDF")
    parser.add_argument("--dry-run",  action="store_true", help="Chỉ liệt kê, không import")
    args = parser.parse_args()

    use_gemini = not args.no_gemini

    # ── Chế độ 1 file ──
    if args.file:
        f = Path(args.file)
        if not f.exists():
            print(f"❌ File không tồn tại: {f}")
            sys.exit(1)
        ext = f.suffix.lower()
        if args.dry_run:
            print(f"[DRY RUN] Sẽ import: {f} ({ext})")
            return
        pg = psycopg2.connect(**DB)
        pg.autocommit = False
        if ext == ".pptx":
            import_pptx(f, pg)
        elif ext == ".pdf":
            import_pdf(f, pg, use_gemini=use_gemini)
        else:
            print(f"⚠  Định dạng không hỗ trợ: {ext}")
        pg.commit()
        pg.close()
        return

    # ── Chế độ thư mục ──
    base = Path(args.dir) if args.dir else INPUT_DIR
    if not base.exists():
        print(f"❌ Thư mục không tồn tại: {base}")
        sys.exit(1)

    found = scan_input(base)
    total_files = len(found["pptx"]) + len(found["pdf"])

    print("=" * 60)
    print(f"  📦 FILE ROUTER – Kho Bài Giảng")
    print("=" * 60)
    print(f"  📂 Thư mục : {base}")
    print(f"  📊 Tìm thấy: {len(found['pptx'])} PPTX + {len(found['pdf'])} PDF = {total_files} file")
    print(f"  🤖 Gemini  : {'Bật' if use_gemini else 'Tắt'}")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN] Danh sách file sẽ được import:\n")
        for f in found["pptx"]:
            print(f"  [PPTX] {f.relative_to(base)}")
        for f in found["pdf"]:
            print(f"  [PDF ] {f.relative_to(base)}")
        print(f"\nTổng: {total_files} file")
        return

    if total_files == 0:
        print("⚠  Không tìm thấy file PPTX hoặc PDF nào.")
        return

    # ── Import PPTX ──
    if found["pptx"]:
        print(f"\n{'─'*60}")
        print(f"  [PPTX] Import {len(found['pptx'])} file PPTX...")
        print(f"{'─'*60}")
        pg = psycopg2.connect(**DB)
        pg.autocommit = False
        ok, skip, err = 0, 0, 0
        for i, f in enumerate(found["pptx"], 1):
            print(f"\n[{i}/{len(found['pptx'])}] {f.name}")
            try:
                stats = import_pptx(f, pg, verbose=True)
                pg.commit()
                if stats["skipped"]:
                    skip += 1
                else:
                    ok += 1
            except Exception as e:
                pg.rollback()
                print(f"  ❌ {e}")
                import traceback; traceback.print_exc()
                err += 1
        pg.close()
        print(f"\n  PPTX: ✅{ok} ⏭{skip} ❌{err}")

    # ── Import PDF ──
    if found["pdf"]:
        print(f"\n{'─'*60}")
        print(f"  [PDF] Import {len(found['pdf'])} file PDF...")
        print(f"{'─'*60}")
        pg = psycopg2.connect(**DB)
        pg.autocommit = False
        ok, skip, err = 0, 0, 0
        for i, f in enumerate(found["pdf"], 1):
            print(f"\n[{i}/{len(found['pdf'])}] {f.name}")
            try:
                stats = import_pdf(f, pg, use_gemini=use_gemini, verbose=True)
                pg.commit()
                if stats["skipped"]:
                    skip += 1
                else:
                    ok += 1
            except Exception as e:
                pg.rollback()
                print(f"  ❌ {e}")
                import traceback; traceback.print_exc()
                err += 1
        pg.close()
        print(f"\n  PDF:  ✅{ok} ⏭{skip} ❌{err}")

    # ── Tổng kết DB ──
    print(f"\n{'='*60}")
    print("  TỔNG KẾT DATABASE")
    print(f"{'='*60}")
    pg = psycopg2.connect(**DB)
    pc = pg.cursor()
    tables = [
        "bai_giang", "trang", "khoi_noi_dung", "tai_nguyen_media",
        "doan_van_trang", "bang_du_lieu_trang", "tu_khoa_trang",
        "chu_de_trang", "chu_de_bai_giang", "ho_so_bai_giang",
    ]
    for tbl in tables:
        pc.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = pc.fetchone()[0]
        print(f"  {tbl:<35}: {cnt:>6} bản ghi")
    pc.close()
    pg.close()
    print(f"{'='*60}\n")
    print("✅ Hoàn thành Giai đoạn 3: Pipeline Import!")


if __name__ == "__main__":
    main()
