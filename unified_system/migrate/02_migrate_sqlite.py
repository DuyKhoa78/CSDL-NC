"""
Script 02: Migrate tu SQLite lecture_store.sqlite sang PostgreSQL kho_bai_giang
Migrate: lessons, slides, slide_blocks, media_assets,
         slide_text_elements, slide_media_refs, slide_table_data,
         slide_keywords, slide_topics, lesson_topics,
         lesson_delivery_profiles, slide_delivery_profiles,
         lesson_curriculum_links, slide_curriculum_links,
         import_runs
"""
import os, sys, io, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

load_dotenv()

SQLITE_PATH = r"D:\PG KHOA HOC MAY TINH\CSDL NC\CSDL\lecture_db_output\lecture_store.sqlite"

DB = dict(
    host=os.getenv("DB_HOST","localhost"),
    port=os.getenv("DB_PORT","5432"),
    dbname=os.getenv("DB_NAME","kho_bai_giang"),
    user=os.getenv("DB_USER","postgres"),
    password=os.getenv("DB_PASSWORD","123456"),
)

def jparse(val):
    """Parse JSON string -> dict, or return None"""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return Json(val)
    try:
        parsed = json.loads(val)
        return Json(parsed)
    except Exception:
        return val

def main():
    print("=== Migrate SQLite -> kho_bai_giang ===")
    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row
    pg = psycopg2.connect(**DB)
    pg.autocommit = False
    pc = pg.cursor()

    try:
        # ── 1. lessons -> bai_giang ──────────────────────────────
        print("  [1/9] lessons -> bai_giang ...")
        rows = sq.execute("SELECT * FROM lessons").fetchall()
        id_map_lesson = {}  # sqlite id -> postgres id
        for r in rows:
            raw = jparse(r['raw_json']) if 'raw_json' in r.keys() else None
            # Xác định nguon_goc: mặc định 'thu_cong' (dữ liệu cũ)
            pc.execute("""
                INSERT INTO bai_giang
                    (tieu_de, nguon_goc, loai_tep, duong_dan_tep,
                     ma_hash_tep, mon_hoc, khoi_lop, chuong,
                     so_trang, ngay_them, trang_thai, ghi_chu)
                VALUES (%s,'thu_cong','pptx',%s,%s,%s,%s,%s,%s,%s,'hoan_thanh',%s)
                RETURNING ma_bai_giang
            """, (
                r['title'] or 'Không có tiêu đề',
                r['source_path'],
                r['source_file_hash'],
                r['subject'],
                r['grade'],
                r['chapter'],
                r['slide_count'],
                r['imported_at'],
                r['notes'] if 'notes' in r.keys() else None,
            ))
            new_id = pc.fetchone()[0]
            id_map_lesson[r['id']] = new_id
        print(f"     -> {len(rows)} bai_giang")

        # ── 2. slides -> trang ───────────────────────────────────
        print("  [2/9] slides -> trang ...")
        rows = sq.execute("SELECT * FROM slides").fetchall()
        id_map_slide = {}
        for r in rows:
            raw = jparse(r['raw_json']) if 'raw_json' in r.keys() else None
            bg_id = id_map_lesson.get(r['lesson_id'])
            if not bg_id:
                continue
            pc.execute("""
                INSERT INTO trang
                    (ma_bai_giang, so_thu_tu, tieu_de,
                     noi_dung_van_ban, noi_dung_markdown,
                     loai_trang, ten_layout, slug_url, du_lieu_json)
                VALUES (%s,%s,%s,%s,%s,'slide',%s,%s,%s)
                RETURNING ma_trang
            """, (
                bg_id, r['slide_no'], r['title'],
                r['full_text'], r['content_md'] if 'content_md' in r.keys() else None,
                r['layout_name'] if 'layout_name' in r.keys() else None,
                r['route_slug'] if 'route_slug' in r.keys() else None,
                raw,
            ))
            new_id = pc.fetchone()[0]
            id_map_slide[r['id']] = new_id
        print(f"     -> {len(id_map_slide)} trang")

        # ── 3. media_assets -> tai_nguyen_media ─────────────────
        print("  [3/9] media_assets -> tai_nguyen_media ...")
        rows = sq.execute("SELECT * FROM media_assets").fetchall()
        id_map_media = {}
        for r in rows:
            bg_id = id_map_lesson.get(r['lesson_id']) if 'lesson_id' in r.keys() else None
            pc.execute("""
                INSERT INTO tai_nguyen_media
                    (ma_bai_giang, ma_hash, duong_dan, loai_media, kich_thuoc_byte, mo_ta_alt)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ma_hash) DO NOTHING
                RETURNING ma_tai_nguyen
            """, (
                bg_id,
                r['media_hash'],
                r['stored_path'],
                'hinh_anh',
                r['size_bytes'] if 'size_bytes' in r.keys() else None,
                None,
            ))
            res = pc.fetchone()
            if res:
                id_map_media[r['id']] = res[0]
        print(f"     -> {len(id_map_media)} tai_nguyen_media")

        # ── 4. slide_blocks -> khoi_noi_dung ────────────────────
        print("  [4/9] slide_blocks -> khoi_noi_dung ...")
        rows = sq.execute("SELECT * FROM slide_blocks").fetchall()
        id_map_block = {}
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            loai = 'van_ban'
            if r['block_type'] == 'table':   loai = 'bang'
            elif r['block_type'] == 'image': loai = 'hinh_anh'
            cj = jparse(r['content_json']) if 'content_json' in r.keys() else None
            pc.execute("""
                INSERT INTO khoi_noi_dung
                    (ma_trang, loai_khoi, vai_tro, noi_dung_van_ban, noi_dung_json,
                     vi_tri_x, vi_tri_y, chieu_rong, chieu_cao, thu_tu_hien_thi)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING ma_khoi
            """, (
                t_id, loai,
                r['semantic_role'] if 'semantic_role' in r.keys() else None,
                r['content_text'] if 'content_text' in r.keys() else None,
                cj,
                r['x'] if 'x' in r.keys() else None,
                r['y'] if 'y' in r.keys() else None,
                r['w'] if 'w' in r.keys() else None,
                r['h'] if 'h' in r.keys() else None,
                r['block_no'] if 'block_no' in r.keys() else None,
            ))
            new_id = pc.fetchone()[0]
            id_map_block[r['id']] = new_id
            cnt += 1
        print(f"     -> {cnt} khoi_noi_dung")

        # ── 5. slide_text_elements -> doan_van_trang ────────────
        print("  [5/9] slide_text_elements -> doan_van_trang ...")
        rows = sq.execute("SELECT * FROM slide_text_elements").fetchall()
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            b_id = id_map_block.get(r['block_id']) if 'block_id' in r.keys() else None
            fj = jparse(r['formatting_json']) if 'formatting_json' in r.keys() else None
            pc.execute("""
                INSERT INTO doan_van_trang
                    (ma_trang, ma_khoi, so_thu_tu_khoi, so_doan, so_dong,
                     vai_tro, cap_do_bullet, noi_dung, noi_dung_chuan, dinh_dang_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                t_id, b_id,
                r['block_no'] if 'block_no' in r.keys() else None,
                r['paragraph_no'] if 'paragraph_no' in r.keys() else None,
                r['line_no'] if 'line_no' in r.keys() else None,
                r['semantic_role'] if 'semantic_role' in r.keys() else None,
                r['bullet_level'] if 'bullet_level' in r.keys() else None,
                r['text_value'] if 'text_value' in r.keys() else None,
                r['normalized_text'] if 'normalized_text' in r.keys() else None,
                fj,
            ))
            cnt += 1
        print(f"     -> {cnt} doan_van_trang")

        # ── 6. slide_table_data -> bang_du_lieu_trang ───────────
        print("  [6/9] slide_table_data -> bang_du_lieu_trang ...")
        rows = sq.execute("SELECT * FROM slide_table_data").fetchall()
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            b_id = id_map_block.get(r['block_id']) if 'block_id' in r.keys() else None
            pc.execute("""
                INSERT INTO bang_du_lieu_trang
                    (ma_trang, ma_khoi, so_hang, so_cot, noi_dung_markdown, hang_json, tieu_de_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                t_id, b_id,
                r['row_count'] if 'row_count' in r.keys() else None,
                r['column_count'] if 'column_count' in r.keys() else None,
                r['markdown_text'] if 'markdown_text' in r.keys() else None,
                jparse(r['rows_json']) if 'rows_json' in r.keys() else None,
                jparse(r['header_json']) if 'header_json' in r.keys() else None,
            ))
            cnt += 1
        print(f"     -> {cnt} bang_du_lieu_trang")

        # ── 7. slide_keywords -> tu_khoa_trang ──────────────────
        print("  [7/9] slide_keywords -> tu_khoa_trang ...")
        rows = sq.execute("SELECT * FROM slide_keywords").fetchall()
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            pc.execute("""
                INSERT INTO tu_khoa_trang
                    (ma_trang, tu_khoa, tu_khoa_chuan, trong_so, nguon, la_chu_de)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                t_id,
                r['keyword'],
                r['normalized_keyword'] if 'normalized_keyword' in r.keys() else None,
                r['weight'] if 'weight' in r.keys() else 1.0,
                r['source'] if 'source' in r.keys() else None,
                bool(r['is_topic']) if 'is_topic' in r.keys() else False,
            ))
            cnt += 1
        print(f"     -> {cnt} tu_khoa_trang")

        # ── 8. slide_topics + lesson_topics -> chu_de_trang / chu_de_bai_giang
        print("  [8/9] slide_topics -> chu_de_trang ...")
        rows = sq.execute("SELECT * FROM slide_topics").fetchall()
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            pc.execute("""
                INSERT INTO chu_de_trang (ma_trang, nhan_chu_de, loai_chu_de, trong_so, thu_tu_hien_thi)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                t_id,
                r['topic_label'],
                r['topic_type'] if 'topic_type' in r.keys() else None,
                r['weight'] if 'weight' in r.keys() else 1.0,
                r['display_order'] if 'display_order' in r.keys() else None,
            ))
            cnt += 1
        print(f"     -> {cnt} chu_de_trang")

        rows = sq.execute("SELECT * FROM lesson_topics").fetchall()
        cnt = 0
        for r in rows:
            bg_id = id_map_lesson.get(r['lesson_id'])
            if not bg_id:
                continue
            pc.execute("""
                INSERT INTO chu_de_bai_giang (ma_bai_giang, nhan_chu_de, loai_chu_de, trong_so, thu_tu_hien_thi)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                bg_id,
                r['topic_label'],
                r['topic_type'] if 'topic_type' in r.keys() else None,
                r['weight'] if 'weight' in r.keys() else 1.0,
                r['display_order'] if 'display_order' in r.keys() else None,
            ))
            cnt += 1
        print(f"     -> {cnt} chu_de_bai_giang")

        # ── 9. delivery_profiles -> ho_so_bai_giang / ho_so_trang
        print("  [9/9] delivery_profiles -> ho_so_bai/trang ...")
        rows = sq.execute("SELECT * FROM lesson_delivery_profiles").fetchall()
        cnt = 0
        for r in rows:
            bg_id = id_map_lesson.get(r['lesson_id'])
            if not bg_id:
                continue
            pc.execute("""
                INSERT INTO ho_so_bai_giang (ma_bai_giang, chu_de_bai, noi_dung_bai, yeu_cau_can_dat)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (ma_bai_giang) DO NOTHING
            """, (
                bg_id,
                r['chu_de'] if 'chu_de' in r.keys() else None,
                r['noi_dung'] if 'noi_dung' in r.keys() else None,
                r['yeu_cau_can_dat'] if 'yeu_cau_can_dat' in r.keys() else None,
            ))
            cnt += 1
        print(f"     -> {cnt} ho_so_bai_giang")

        rows = sq.execute("SELECT * FROM slide_delivery_profiles").fetchall()
        cnt = 0
        for r in rows:
            t_id = id_map_slide.get(r['slide_id'])
            if not t_id:
                continue
            pc.execute("""
                INSERT INTO ho_so_trang (ma_trang, chu_de_trang, noi_dung_trang, yeu_cau_can_dat)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (ma_trang) DO NOTHING
            """, (
                t_id,
                r['chu_de'] if 'chu_de' in r.keys() else None,
                r['noi_dung'] if 'noi_dung' in r.keys() else None,
                r['yeu_cau_can_dat'] if 'yeu_cau_can_dat' in r.keys() else None,
            ))
            cnt += 1
        print(f"     -> {cnt} ho_so_trang")

        pg.commit()
        print("\n✅ Migrate SQLite hoan thanh!")

        # Tổng kết
        for tbl in ['bai_giang','trang','khoi_noi_dung','tai_nguyen_media',
                    'doan_van_trang','bang_du_lieu_trang','tu_khoa_trang',
                    'chu_de_trang','chu_de_bai_giang','ho_so_bai_giang','ho_so_trang']:
            pc.execute(f"SELECT COUNT(*) FROM {tbl}")
            print(f"   {tbl}: {pc.fetchone()[0]}")

    except Exception as e:
        pg.rollback()
        import traceback
        traceback.print_exc()
        print(f"LOI: {e}")
    finally:
        pc.close()
        pg.close()
        sq.close()

if __name__ == "__main__":
    main()
