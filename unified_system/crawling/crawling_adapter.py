"""
crawling_adapter.py — Giai đoạn 5: Tích hợp Crawling
======================================================
Adapter kết nối crawler cũ với pipeline nhập liệu (file_router.py).

Chức năng:
  1. Nhận danh sách URL hoặc thư mục chứa file đã tải về từ crawler
  2. Gắn metadata nguon_goc = 'crawled' (hoặc 'manual' / 'ai_tao_sinh')
  3. Cập nhật bảng lich_su_nhap để theo dõi từng phiên crawl
  4. Gọi file_router.py để nhập từng file vào PostgreSQL
  5. Xuất báo cáo kết quả nhập liệu

Sử dụng:
  python crawling_adapter.py --dir ./input/crawled
  python crawling_adapter.py --dir ./input/ai --source ai_tao_sinh
  python crawling_adapter.py --urls urls.txt --source crawled
  python crawling_adapter.py --dir ./input --dry-run
"""

import sys, io, os, re, json, argparse, shutil
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding='utf-8')

# Thêm thư mục cha vào path để import file_router
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import psycopg2
from dotenv import load_dotenv

load_dotenv(BASE / '.env')

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 5432)),
    dbname=os.getenv('DB_NAME', 'kho_bai_giang'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASS', '123456'),
)

SUPPORTED_EXT = {'.pptx', '.pdf'}
VALID_SOURCES = {'crawled', 'manual', 'ai_tao_sinh'}

# ─────────────────────────────────────────────────────────────
# Tiện ích
# ─────────────────────────────────────────────────────────────

def detect_source_from_path(path: Path) -> str:
    """Tự động nhận dạng nguon_goc từ tên thư mục / tên file."""
    parts = path.parts
    name_lower = path.stem.lower()

    if any('ai' in p.lower() or 'gemini' in p.lower()
           or 'notebooklm' in p.lower() or 'canva' in p.lower()
           for p in parts):
        return 'ai_tao_sinh'
    if any('crawl' in p.lower() or 'web' in p.lower() for p in parts):
        return 'crawled'
    if 'ai_tao_sinh' in name_lower or 'gemini' in name_lower:
        return 'ai_tao_sinh'
    return 'manual'


def collect_files(src_dir: Path) -> list[Path]:
    """Quét đệ quy lấy tất cả file PPTX/PDF."""
    files = []
    for ext in SUPPORTED_EXT:
        files.extend(src_dir.rglob(f'*{ext}'))
    return sorted(files)


def collect_from_urls(url_file: Path, dest_dir: Path) -> list[Path]:
    """
    Tải file từ danh sách URL (mỗi dòng 1 URL).
    Yêu cầu: requests
    """
    try:
        import requests
    except ImportError:
        print("  ⚠️  Cài requests: pip install requests")
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    urls = [u.strip() for u in url_file.read_text(encoding='utf-8').splitlines() if u.strip()]
    downloaded = []

    for url in urls:
        fname = re.sub(r'[^\w.\-]', '_', url.split('/')[-1]) or 'file'
        ext = Path(fname).suffix.lower()
        if ext not in SUPPORTED_EXT:
            print(f"  ⏭️  Bỏ qua (không hỗ trợ): {url}")
            continue

        dest = dest_dir / fname
        if dest.exists():
            print(f"  ✅ Đã có: {fname}")
            downloaded.append(dest)
            continue

        try:
            r = requests.get(url, timeout=30, stream=True)
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            print(f"  ⬇️  Tải về: {fname} ({dest.stat().st_size // 1024} KB)")
            downloaded.append(dest)
        except Exception as e:
            print(f"  ❌ Lỗi tải {url}: {e}")

    return downloaded


# ─────────────────────────────────────────────────────────────
# Ghi lich_su_nhap
# ─────────────────────────────────────────────────────────────

def begin_session(pg, source: str) -> int:
    """Tạo bản ghi phiên nhập mới trong lich_su_nhap."""
    pc = pg.cursor()
    pc.execute("""
        INSERT INTO lich_su_nhap (thoi_diem_bat_dau, nguon_goc, tong_so_tep,
                                   so_thanh_cong, so_bo_qua, so_that_bai)
        VALUES (NOW(), %s, 0, 0, 0, 0)
        RETURNING ma_nhap
    """, (source,))
    ma = pc.fetchone()[0]
    pg.commit()
    return ma


def end_session(pg, ma_nhap: int, stats: dict):
    """Cập nhật kết quả vào lich_su_nhap."""
    pc = pg.cursor()
    pc.execute("""
        UPDATE lich_su_nhap
        SET thoi_diem_ket_thuc = NOW(),
            tong_so_tep = %s,
            so_thanh_cong = %s,
            so_bo_qua = %s,
            so_that_bai = %s,
            bao_cao_json = %s::jsonb
        WHERE ma_nhap = %s
    """, (
        stats['total'], stats['ok'], stats['skip'], stats['fail'],
        json.dumps(stats.get('detail', []), ensure_ascii=False),
        ma_nhap
    ))
    pg.commit()


# ─────────────────────────────────────────────────────────────
# Pipeline nhập liệu (gọi file_router)
# ─────────────────────────────────────────────────────────────

def run_router(file_path: Path, source: str, khoi_lop: str = None, dry_run: bool = False) -> dict:
    """
    Gọi file_router để nhập 1 file vào DB.
    Trả về {'status': 'ok'|'skip'|'fail', 'msg': str}
    """
    if dry_run:
        return {'status': 'ok', 'msg': f'[DRY-RUN] {file_path.name}'}

    try:
        from importers.file_router import route_file
        result = route_file(
            file_path=str(file_path),
            nguon_goc=source,
            khoi_lop=khoi_lop,
        )
        return result
    except ImportError:
        # Fallback: gọi subprocess
        import subprocess
        router = BASE / 'importers' / 'file_router.py'
        cmd = [sys.executable, str(router), str(file_path),
               '--source', source]
        if khoi_lop:
            cmd += ['--khoi', khoi_lop]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if r.returncode == 0:
            return {'status': 'ok', 'msg': r.stdout.strip()}
        else:
            return {'status': 'fail', 'msg': r.stderr.strip() or r.stdout.strip()}
    except Exception as e:
        return {'status': 'fail', 'msg': str(e)}


# ─────────────────────────────────────────────────────────────
# Phát hiện khối lớp từ tên file / đường dẫn
# ─────────────────────────────────────────────────────────────

def detect_khoi(path: Path) -> str | None:
    text = str(path).lower()
    for grade in ['10', '11', '12', '8', '9']:
        patterns = [
            f'lop{grade}', f'lop_{grade}', f'lop-{grade}',
            f'khoi{grade}', f'khoi_{grade}',
            f'grade{grade}', f'class{grade}',
            f'tin{grade}', f'tin_{grade}',
            f'k{grade}', f'k_{grade}', f'k-{grade}'
        ]
        if any(p in text for p in patterns):
            return str(grade)
    return None


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Giai đoạn 5: Crawling Adapter')
    ap.add_argument('--dir',     type=Path, help='Thư mục chứa file PPTX/PDF đã tải về')
    ap.add_argument('--urls',    type=Path, help='File text chứa danh sách URL (mỗi dòng 1 URL)')
    ap.add_argument('--source',  default=None,
                    choices=['thu_thap_web', 'thu_cong', 'ai_tao_sinh'],
                    help='Nguồn gốc (tự nhận dạng nếu bỏ trống)')
    ap.add_argument('--khoi',    default=None, help='Khối lớp (tự nhận dạng nếu bỏ trống)')
    ap.add_argument('--dry-run', action='store_true', help='Chỉ liệt kê file, không ghi DB')
    ap.add_argument('--move-done', type=Path, default=None,
                    help='Thư mục đích để di chuyển file đã nhập thành công')
    args = ap.parse_args()

    if not args.dir and not args.urls:
        ap.error('Cần ít nhất --dir hoặc --urls')

    print('=' * 60)
    print('  GIAI ĐOẠN 5: CRAWLING ADAPTER')
    print('=' * 60)

    # ── Thu thập file ──────────────────────────────────────────
    files: list[Path] = []

    if args.urls:
        dest_dir = (args.dir or BASE / 'input' / 'crawled')
        print(f"🌐 Tải file từ URL list: {args.urls}")
        files = collect_from_urls(args.urls, dest_dir)

    if args.dir:
        extra = collect_files(args.dir)
        print(f"📁 Quét thư mục: {args.dir} → {len(extra)} file")
        # Tránh trùng lặp nếu đã tải về vào args.dir
        existing = {f.resolve() for f in files}
        files += [f for f in extra if f.resolve() not in existing]

    if not files:
        print("⚠️  Không tìm thấy file PPTX/PDF nào.")
        return

    print(f"\n📋 Tổng file sẽ xử lý: {len(files)}")
    print(f"{'─'*60}")

    # ── Kết nối DB ─────────────────────────────────────────────
    if not args.dry_run:
        try:
            pg = psycopg2.connect(**DB)
        except Exception as e:
            print(f"❌ Không kết nối được DB: {e}")
            sys.exit(1)
        source_global = args.source or detect_source_from_path(files[0] if files else Path('.'))
        ma_nhap = begin_session(pg, source_global)
        print(f"📝 Phiên nhập #ma_nhap={ma_nhap} | nguon_goc={source_global}\n")
    else:
        pg = None
        ma_nhap = None
        print("  [DRY-RUN MODE]\n")

    # ── Nhập từng file ─────────────────────────────────────────
    stats = {'total': len(files), 'ok': 0, 'skip': 0, 'fail': 0, 'detail': []}

    for i, fpath in enumerate(files, 1):
        source = args.source or detect_source_from_path(fpath)
        khoi   = args.khoi or detect_khoi(fpath)
        ext    = fpath.suffix.lower()

        print(f"[{i:3d}/{len(files)}] {fpath.name[:55]}")
        print(f"         nguon={source} | khoi={khoi or '?'} | {ext.upper()}")

        result = run_router(fpath, source, khoi, args.dry_run)
        status = result.get('status', 'fail')
        msg    = result.get('msg', '')

        icon = {'ok': '✅', 'skip': '⏭️', 'fail': '❌'}.get(status, '?')
        print(f"         {icon} {status.upper()} — {msg[:80]}\n")

        stats[status] = stats.get(status, 0) + 1
        stats['detail'].append({
            'file': fpath.name,
            'source': source,
            'khoi_lop': khoi,
            'status': status,
            'msg': msg[:200],
        })

        # Di chuyển file đã nhập thành công
        if status == 'ok' and args.move_done and not args.dry_run:
            args.move_done.mkdir(parents=True, exist_ok=True)
            dest = args.move_done / fpath.name
            shutil.move(str(fpath), str(dest))
            print(f"         📦 Đã di chuyển → {dest}")

    # ── Cập nhật lich_su_nhap ──────────────────────────────────
    if not args.dry_run and pg:
        end_session(pg, ma_nhap, stats)
        pg.close()

    # ── Tổng kết ───────────────────────────────────────────────
    print('=' * 60)
    print('  KẾT QUẢ GIAI ĐOẠN 5')
    print('=' * 60)
    print(f"  Tổng file    : {stats['total']}")
    print(f"  ✅ Thành công: {stats['ok']}")
    print(f"  ⏭️  Bỏ qua   : {stats['skip']}")
    print(f"  ❌ Thất bại  : {stats['fail']}")
    if args.dry_run:
        print("  [DRY-RUN] Không ghi vào DB")
    else:
        print(f"  📝 Đã lưu vào lich_su_nhap (ma_nhap={ma_nhap})")

    # Xuất báo cáo JSON
    report_path = BASE / 'crawling' / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps({'session': ma_nhap, 'stats': stats}, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"  📄 Báo cáo : {report_path}")
    print('=' * 60)


if __name__ == '__main__':
    main()
