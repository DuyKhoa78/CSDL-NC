"""
migrate_normalize.py
Áp dụng chuẩn hóa 1NF / 2NF / 3NF / BCNF lên database kho_bai_giang hiện có.

Thứ tự:
  1NF  – Xóa cột đa trị, đổi chuong → ma_noi_dung
  2NF  – Tách bảng chuyen_gia
  3NF  – Xóa cột nội dung trùng lặp, thêm UNIQUE, CHECK
  BCNF – Tách bảng bang_tu_vung (vocabulary) từ tu_khoa_trang
"""
import sys, io, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB = dict(host='localhost', port=5432, dbname='kho_bai_giang',
          user='postgres', password='123456')

def run_step(pg, label, sql_list):
    print(f"\n{'─'*55}")
    print(f"  {label}")
    print(f"{'─'*55}")
    for sql in sql_list:
        short = sql.strip()[:80].replace('\n', ' ')
        pc = pg.cursor()
        try:
            pc.execute("SAVEPOINT sp")
            pc.execute(sql)
            pc.execute("RELEASE SAVEPOINT sp")
            print(f"  ✅ {short}")
        except Exception as e:
            pc.execute("ROLLBACK TO SAVEPOINT sp")
            print(f"  ⚠️  {short}")
            print(f"      → {e}")
        finally:
            pc.close()

pg = psycopg2.connect(**DB)
pg.autocommit = False

# ══════════════════════════════════════════════════════════════
# 1NF – Xóa cột đa trị, đổi chuong → ma_noi_dung
# ══════════════════════════════════════════════════════════════
run_step(pg, "1NF – Xóa cột đa trị trong ho_so_bai_giang & ho_so_trang", [
    # Phải DROP VIEW trước vì nó phụ thuộc vào cột yeu_cau_can_dat
    "DROP VIEW IF EXISTS v_trang_day_du",
    "ALTER TABLE ho_so_bai_giang DROP COLUMN IF EXISTS yeu_cau_can_dat",
    "ALTER TABLE ho_so_trang    DROP COLUMN IF EXISTS yeu_cau_can_dat",
])

run_step(pg, "1NF – Đổi bai_giang.chuong → ma_noi_dung (FK)", [
    # Backup giá trị chuong vào ghi_chu trước
    """UPDATE bai_giang
       SET ghi_chu = COALESCE(ghi_chu || ' | ', '') || '[chuong_cu]: ' || chuong
       WHERE chuong IS NOT NULL AND chuong != ''""",
    # Xóa cột cũ
    "ALTER TABLE bai_giang DROP COLUMN IF EXISTS chuong",
    # Thêm FK ma_noi_dung
    "ALTER TABLE bai_giang ADD COLUMN IF NOT EXISTS ma_noi_dung CHAR(5) REFERENCES noi_dung(ma_noi_dung)",
    "CREATE INDEX IF NOT EXISTS idx_bai_giang_noi_dung ON bai_giang(ma_noi_dung)",
])

# ══════════════════════════════════════════════════════════════
# 2NF – Tách bảng chuyen_gia
# ══════════════════════════════════════════════════════════════
run_step(pg, "2NF – Tạo bảng chuyen_gia", [
    """CREATE TABLE IF NOT EXISTS chuyen_gia (
        ma_chuyen_gia   SERIAL      PRIMARY KEY,
        ten_chuyen_gia  VARCHAR(200) NOT NULL,
        chuyen_mon      VARCHAR(200),
        don_vi_cong_tac VARCHAR(200),
        email           VARCHAR(200) UNIQUE
    )""",
    # Di chuyển data từ danh_gia sang chuyen_gia (nếu có)
    """INSERT INTO chuyen_gia (ten_chuyen_gia, chuyen_mon, don_vi_cong_tac)
       SELECT DISTINCT ten_chuyen_gia, chuyen_mon, don_vi_cong_tac
       FROM danh_gia
       WHERE ten_chuyen_gia IS NOT NULL
       ON CONFLICT DO NOTHING""",
    # Thêm FK vào danh_gia
    "ALTER TABLE danh_gia ADD COLUMN IF NOT EXISTS ma_chuyen_gia INTEGER REFERENCES chuyen_gia(ma_chuyen_gia)",
    # Cập nhật FK
    """UPDATE danh_gia d
       SET ma_chuyen_gia = cg.ma_chuyen_gia
       FROM chuyen_gia cg
       WHERE d.ten_chuyen_gia = cg.ten_chuyen_gia
         AND d.ten_chuyen_gia IS NOT NULL""",
])

# ══════════════════════════════════════════════════════════════
# 3NF – Xóa cột trùng trong khoi_noi_dung, thêm UNIQUE / CHECK
# ══════════════════════════════════════════════════════════════
run_step(pg, "3NF – khoi_noi_dung: xóa noi_dung_json (trùng van_ban), thêm du_lieu_json", [
    "ALTER TABLE khoi_noi_dung DROP COLUMN IF EXISTS noi_dung_json",
    "ALTER TABLE khoi_noi_dung ADD COLUMN IF NOT EXISTS du_lieu_json JSONB",
])

run_step(pg, "3NF – UNIQUE & CHECK constraints", [
    # trang: mỗi bài không có 2 trang cùng số thứ tự
    "ALTER TABLE trang DROP CONSTRAINT IF EXISTS uq_trang_bai_sothutu",
    "ALTER TABLE trang ADD CONSTRAINT uq_trang_bai_sothutu UNIQUE (ma_bai_giang, so_thu_tu)",
    # danh_gia: giới hạn điểm số
    "ALTER TABLE danh_gia DROP CONSTRAINT IF EXISTS chk_diem_nd",
    """ALTER TABLE danh_gia ADD CONSTRAINT chk_diem_nd
       CHECK (diem_noi_dung IS NULL OR diem_noi_dung BETWEEN 0 AND 10)""",
    "ALTER TABLE danh_gia DROP CONSTRAINT IF EXISTS chk_diem_tb",
    """ALTER TABLE danh_gia ADD CONSTRAINT chk_diem_tb
       CHECK (diem_trinh_bay IS NULL OR diem_trinh_bay BETWEEN 0 AND 10)""",
    "ALTER TABLE danh_gia DROP CONSTRAINT IF EXISTS chk_diem_ph",
    """ALTER TABLE danh_gia ADD CONSTRAINT chk_diem_ph
       CHECK (diem_phu_hop_chuong_trinh IS NULL OR diem_phu_hop_chuong_trinh BETWEEN 0 AND 10)""",
    # lien_ket: diem_phu_hop trong [0,1]
    "ALTER TABLE lien_ket_bai_chuong_trinh   DROP CONSTRAINT IF EXISTS chk_diem_lkb",
    """ALTER TABLE lien_ket_bai_chuong_trinh
       ADD CONSTRAINT chk_diem_lkb CHECK (diem_phu_hop IS NULL OR diem_phu_hop BETWEEN 0 AND 1)""",
    "ALTER TABLE lien_ket_trang_chuong_trinh DROP CONSTRAINT IF EXISTS chk_diem_lkt",
    """ALTER TABLE lien_ket_trang_chuong_trinh
       ADD CONSTRAINT chk_diem_lkt CHECK (diem_phu_hop IS NULL OR diem_phu_hop BETWEEN 0 AND 1)""",
    # UNIQUE trên lien_ket (không import trùng)
    "ALTER TABLE lien_ket_bai_chuong_trinh   DROP CONSTRAINT IF EXISTS uq_lkb",
    """ALTER TABLE lien_ket_bai_chuong_trinh
       ADD CONSTRAINT uq_lkb UNIQUE (ma_bai_giang, ma_noi_dung, ma_yccd)""",
    "ALTER TABLE lien_ket_trang_chuong_trinh DROP CONSTRAINT IF EXISTS uq_lkt",
    """ALTER TABLE lien_ket_trang_chuong_trinh
       ADD CONSTRAINT uq_lkt UNIQUE (ma_trang, ma_noi_dung, ma_yccd)""",
])

# ══════════════════════════════════════════════════════════════
# BCNF – Tách từ điển từ khóa ra khỏi tu_khoa_trang
#
# Vi phạm: tu_khoa → tu_khoa_chuan
# (tu_khoa_chuan phụ thuộc vào tu_khoa, không phụ thuộc vào PK ma_tu_khoa)
# 107.369 bản ghi nhưng chỉ 3.562 từ khóa duy nhất → 96.7% lặp
# ══════════════════════════════════════════════════════════════
pc = pg.cursor()
print(f"\n{'─'*55}")
print("  BCNF – Tách bảng bang_tu_vung (vocabulary)")
print(f"{'─'*55}")

try:
    # Bước 1: Tạo bảng từ điển
    pc.execute("""
        CREATE TABLE IF NOT EXISTS bang_tu_vung (
            ma_tu_vung      SERIAL       PRIMARY KEY,
            tu_khoa         VARCHAR(255) NOT NULL UNIQUE,
            tu_khoa_chuan   VARCHAR(255)
        )
    """)
    print("  ✅ Tạo bảng bang_tu_vung")

    # Bước 2: Điền từ điển với DISTINCT từ khóa
    # Ưu tiên tu_khoa_chuan có nhiều ký tự nhất (tránh NULL hoặc rỗng)
    pc.execute("""
        INSERT INTO bang_tu_vung (tu_khoa, tu_khoa_chuan)
        SELECT
            tu_khoa,
            (SELECT t2.tu_khoa_chuan
             FROM tu_khoa_trang t2
             WHERE t2.tu_khoa = t1.tu_khoa
               AND t2.tu_khoa_chuan IS NOT NULL
             ORDER BY length(t2.tu_khoa_chuan) DESC
             LIMIT 1) AS tu_khoa_chuan
        FROM (SELECT DISTINCT tu_khoa FROM tu_khoa_trang WHERE tu_khoa IS NOT NULL) t1
        ON CONFLICT (tu_khoa) DO NOTHING
    """)
    cnt = pc.rowcount
    print(f"  ✅ Chèn {cnt} từ khóa vào bang_tu_vung")

    # Bước 3: Thêm FK ma_tu_vung vào tu_khoa_trang
    pc.execute("""
        ALTER TABLE tu_khoa_trang
        ADD COLUMN IF NOT EXISTS ma_tu_vung INTEGER REFERENCES bang_tu_vung(ma_tu_vung)
    """)
    print("  ✅ Thêm cột ma_tu_vung FK vào tu_khoa_trang")

    # Bước 4: Cập nhật FK từ bảng tu_khoa_trang → bang_tu_vung
    pc.execute("""
        UPDATE tu_khoa_trang tk
        SET ma_tu_vung = bv.ma_tu_vung
        FROM bang_tu_vung bv
        WHERE tk.tu_khoa = bv.tu_khoa
    """)
    print(f"  ✅ Cập nhật FK cho {pc.rowcount} bản ghi tu_khoa_trang")

    # Bước 5: Xóa cột tu_khoa, tu_khoa_chuan khỏi tu_khoa_trang (bây giờ ở bang_tu_vung)
    pc.execute("ALTER TABLE tu_khoa_trang DROP COLUMN IF EXISTS tu_khoa")
    pc.execute("ALTER TABLE tu_khoa_trang DROP COLUMN IF EXISTS tu_khoa_chuan")
    print("  ✅ Xóa tu_khoa, tu_khoa_chuan khỏi tu_khoa_trang (đã chuyển sang bang_tu_vung)")

    # Bước 6: Index
    pc.execute("CREATE INDEX IF NOT EXISTS idx_tu_vung_chuan ON bang_tu_vung(tu_khoa_chuan)")
    pc.execute("CREATE INDEX IF NOT EXISTS idx_tk_trang_vung ON tu_khoa_trang(ma_tu_vung)")
    print("  ✅ Tạo index")

except Exception as e:
    print(f"  ❌ Lỗi BCNF: {e}")
    pg.rollback()
    pg.close()
    sys.exit(1)

pc.close()

# ══════════════════════════════════════════════════════════════
# Index bổ sung
# ══════════════════════════════════════════════════════════════
run_step(pg, "Index – Thêm các index còn thiếu", [
    "CREATE INDEX IF NOT EXISTS idx_noi_dung_chu_de ON noi_dung(ma_chu_de)",
    "CREATE INDEX IF NOT EXISTS idx_yccd_noi_dung   ON yeu_cau_can_dat(ma_noi_dung)",
    "CREATE INDEX IF NOT EXISTS idx_lkb_bai          ON lien_ket_bai_chuong_trinh(ma_bai_giang)",
    "CREATE INDEX IF NOT EXISTS idx_lkb_nd           ON lien_ket_bai_chuong_trinh(ma_noi_dung)",
    "CREATE INDEX IF NOT EXISTS idx_lkt_trang        ON lien_ket_trang_chuong_trinh(ma_trang)",
    "CREATE INDEX IF NOT EXISTS idx_khoi_trang       ON khoi_noi_dung(ma_trang)",
    "CREATE INDEX IF NOT EXISTS idx_doan_van_trang   ON doan_van_trang(ma_trang)",
])

# ══════════════════════════════════════════════════════════════
# View cập nhật
# ══════════════════════════════════════════════════════════════
run_step(pg, "View – Tái tạo v_trang_day_du (bỏ yeu_cau_can_dat) & v_bai_theo_chuong_trinh", [
    # Tái tạo view v_trang_day_du không có cột yeu_cau_can_dat
    """CREATE OR REPLACE VIEW v_trang_day_du AS
       SELECT
           t.ma_trang, t.ma_bai_giang, t.so_thu_tu, t.tieu_de,
           t.noi_dung_van_ban, t.noi_dung_markdown, t.loai_trang,
           t.duong_dan_anh, t.mo_ta_gemini, t.slug_url,
           h.chu_de_trang, h.noi_dung_trang,
           b.tieu_de AS tieu_de_bai, b.nguon_goc, b.mon_hoc, b.khoi_lop
       FROM trang t
       LEFT JOIN ho_so_trang h ON h.ma_trang = t.ma_trang
       LEFT JOIN bai_giang   b ON b.ma_bai_giang = t.ma_bai_giang""",
    """CREATE OR REPLACE VIEW v_bai_theo_chuong_trinh AS
       SELECT
           b.ma_bai_giang, b.tieu_de, b.nguon_goc, b.khoi_lop,
           n.ma_noi_dung, n.ten_noi_dung, c.ten_chu_de,
           y.ma_yccd, y.noi_dung_yccd,
           l.diem_phu_hop, l.kieu_lien_ket
       FROM lien_ket_bai_chuong_trinh l
       JOIN bai_giang            b ON b.ma_bai_giang = l.ma_bai_giang
       LEFT JOIN noi_dung        n ON n.ma_noi_dung  = l.ma_noi_dung
       LEFT JOIN chu_de          c ON c.ma_chu_de    = n.ma_chu_de
       LEFT JOIN yeu_cau_can_dat y ON y.ma_yccd      = l.ma_yccd""",
])

# ══════════════════════════════════════════════════════════════
# Commit & Báo cáo
# ══════════════════════════════════════════════════════════════
pg.commit()

pc = pg.cursor()
print(f"\n{'='*55}")
print("  TỔNG KẾT SAU CHUẨN HÓA")
print(f"{'='*55}")

tables = [
    ("bai_giang",                    "Bài giảng"),
    ("trang",                        "Trang / Slide"),
    ("khoi_noi_dung",               "Khối nội dung"),
    ("doan_van_trang",              "Đoạn văn trang"),
    ("tai_nguyen_media",            "Tài nguyên media"),
    ("tu_khoa_trang",               "Từ khóa trang (junction)"),
    ("bang_tu_vung",                "Từ điển từ khóa (BCNF mới)"),
    ("chu_de_trang",                "Chủ đề trang"),
    ("chu_de_bai_giang",           "Chủ đề bài giảng"),
    ("ho_so_bai_giang",            "Hồ sơ bài giảng"),
    ("ho_so_trang",                 "Hồ sơ trang"),
    ("chuyen_gia",                  "Chuyên gia (2NF mới)"),
    ("danh_gia",                    "Đánh giá"),
    ("chi_tiet_ai",                 "Chi tiết AI"),
    ("lien_ket_bai_chuong_trinh",  "Liên kết bài-CT"),
    ("lien_ket_trang_chuong_trinh","Liên kết trang-CT"),
    ("lich_su_nhap",               "Lịch sử nhập"),
]
for tbl, name in tables:
    pc.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = pc.fetchone()[0]
    print(f"  {name:<35} ({tbl}): {cnt:>7} bản ghi")

print(f"\n{'='*55}")
print("  ✅ CHUẨN HÓA HOÀN TẤT: 1NF · 2NF · 3NF · BCNF")
print(f"{'='*55}\n")

pc.close()
pg.close()
