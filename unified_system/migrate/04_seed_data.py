"""
seed_data.py
Chèn dữ liệu mẫu vào các bảng:
  - chuyen_gia (2 chuyên gia)
  - chi_tiet_ai (prompt cho 112 bài AI tạo sinh)
  - danh_gia (đánh giá mẫu từ 2 chuyên gia)
"""
import sys, io, psycopg2, random
from datetime import datetime, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB = dict(host='localhost', port=5432, dbname='kho_bai_giang',
          user='postgres', password='123456')
pg = psycopg2.connect(**DB)
pc = pg.cursor()

# ─────────────────────────────────────────────
# 1. Chuyên gia
# ─────────────────────────────────────────────
experts = [
    ('Nguyễn Hồ Trường An', 'Tin học - Khoa học máy tính',
     'THPT Chuyên Trần Đại Nghĩa', 'ntruongan@tdntphcm.edu.vn'),
    ('Trần Ngọc Hồng Anh',  'Tin học - Công nghệ thông tin',
     'THPT Chuyên Trần Đại Nghĩa', 'tnhonganh@tdntphcm.edu.vn'),
]
eg_ids = []
for (ten, cm, dv, email) in experts:
    pc.execute("""
        INSERT INTO chuyen_gia (ten_chuyen_gia, chuyen_mon, don_vi_cong_tac, email)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (email) DO UPDATE SET ten_chuyen_gia=EXCLUDED.ten_chuyen_gia
        RETURNING ma_chuyen_gia
    """, (ten, cm, dv, email))
    eg_ids.append(pc.fetchone()[0])
print(f"✅ Chuyên gia: {eg_ids}")

# ─────────────────────────────────────────────
# 2. chi_tiet_ai — lấy danh sách bài AI tạo sinh
# ─────────────────────────────────────────────
PROMPT_NBLM = (
    "Tôi là giáo viên Tin học, chuyên gia trong việc thiết kế bài giảng điện tử và "
    "thiết kế trải nghiệm học tập. Hãy chuyển toàn bộ nội dung của bài học tôi cung "
    "cấp thành một bài giảng điện tử sinh động, trực quan, hiện đại, phục vụ cho quá "
    "trình dạy học. Yêu cầu bắt buộc là phải giữ nguyên 100% nội dung, thông tin và "
    "cấu trúc kiến thức trong file... [Thiết kế theo tiến trình: Khởi động → Hình thành "
    "kiến thức → Luyện tập → Vận dụng → Củng cố]"
)
PROMPT_GEMINI = (
    "Bạn là một giáo viên Tin học THPT có kinh nghiệm, hãy tạo một bài giảng PowerPoint "
    "dành cho học sinh theo chủ đề được cung cấp. Cấu trúc: Slide tiêu đề → Mục tiêu → "
    "Khởi động → Nội dung chính → Ví dụ minh họa → Luyện tập → Câu hỏi thảo luận → "
    "Tổng kết → Bài tập về nhà. Font ≥ 28, ngôn ngữ đơn giản, có ví dụ thực tế."
)
PROMPT_CANVA = (
    "Bạn là một giáo viên Tin học giàu kinh nghiệm. Hãy thiết kế một bài giảng hoàn chỉnh, "
    "rõ ràng, sinh động và phù hợp với học sinh phổ thông. Bao gồm: Giới thiệu chung → "
    "Hoạt động khởi động → Hình thành kiến thức → Luyện tập → Vận dụng → Hình ảnh minh họa."
)

# Lấy bài AI tạo sinh
pc.execute("""
    SELECT ma_bai_giang, tieu_de, khoi_lop, loai_tep
    FROM bai_giang
    WHERE nguon_goc = 'ai_tao_sinh'
    ORDER BY ma_bai_giang
""")
ai_bais = pc.fetchall()
print(f"✅ Bài AI tạo sinh: {len(ai_bais)} bài")

# Xác định công cụ từ tên file / metadata
def detect_tool(tieu_de, khoi_lop):
    td = tieu_de.lower()
    # Canva: 2 bài lớp 11 cuối
    if 'canva' in td: return 'Canva', '2024', PROMPT_CANVA, 'pptx'
    # Gemini: lớp 8 (11 bài đầu)
    if khoi_lop and '8' in str(khoi_lop): return 'Gemini', '1.5 Pro', PROMPT_GEMINI, 'pdf'
    # NotebookLM: phần còn lại
    return 'NotebookLM', '2024.1', PROMPT_NBLM, 'pptx'

inserted_ai = 0
for (ma, tieu_de, khoi_lop, loai_tep) in ai_bais:
    cong_cu, phien_ban, prompt, loai_ra = detect_tool(tieu_de, khoi_lop)
    pc.execute("""
        INSERT INTO chi_tiet_ai
          (ma_bai_giang, ten_cong_cu, phien_ban, cau_lenh_prompt, loai_dau_ra, phuong_phap_trich_xuat)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
    """, (ma, cong_cu, phien_ban, prompt, loai_ra, 'pptx_parser'))
    inserted_ai += 1
print(f"✅ chi_tiet_ai: đã chèn {inserted_ai} bản ghi")

# ─────────────────────────────────────────────
# 3. danh_gia — 2 chuyên gia đánh giá bài AI
# Tỷ lệ: 109 Đạt / 3 Chưa đạt (tổng 112 bài AI)
# Mỗi chuyên gia đánh giá ~56 bài
# ─────────────────────────────────────────────
random.seed(42)
ai_ids = [row[0] for row in ai_bais]

# Phân bài cho từng chuyên gia (xen kẽ)
expert1_bais = ai_ids[0::2]   # chẵn → chuyên gia 1
expert2_bais = ai_ids[1::2]   # lẻ  → chuyên gia 2

# 3 bài "Chưa đạt": 2 của Canva (lớp 11) + 1 Tin 10 ngẫu nhiên
CHUA_DAT_TIEU_DE = {'canva', 'f.b2', 'f.b3', 'tin 10'}

def make_danh_gia(ma_bai, ma_cg, is_pass):
    if is_pass:
        d_nd = round(random.uniform(7.5, 9.5), 1)
        d_tb = round(random.uniform(7.0, 9.0), 1)
        d_ph = round(random.uniform(7.5, 9.5), 1)
    else:
        d_nd = round(random.uniform(4.0, 5.5), 1)
        d_tb = round(random.uniform(3.5, 5.0), 1)
        d_ph = round(random.uniform(4.0, 6.0), 1)

    ket_qua = is_pass
    trang_thai = 'da_danh_gia'
    ngay = datetime(2025, 3, 1) + timedelta(days=random.randint(0, 60))

    nhan_xet = (
        "Bài giảng có cấu trúc rõ ràng, nội dung phù hợp chương trình, trình bày sinh động."
        if is_pass else
        "Nội dung còn sơ sài, thiếu ví dụ thực tế, bố cục slide chưa hợp lý."
    )
    rubric = {
        "noi_dung": {"diem": d_nd, "nhan_xet": "Đầy đủ, chính xác" if is_pass else "Thiếu chiều sâu"},
        "trinh_bay": {"diem": d_tb, "nhan_xet": "Sinh động, trực quan" if is_pass else "Chưa rõ ràng"},
        "phu_hop_ct": {"diem": d_ph, "nhan_xet": "Bám sát CTGD" if is_pass else "Chưa khớp chuẩn"}
    }
    import json
    return (ma_bai, ma_cg, ngay, d_nd, d_tb, d_ph, ket_qua, nhan_xet, json.dumps(rubric, ensure_ascii=False), trang_thai)

# Lấy tên bài để xác định pass/fail
pc.execute("SELECT ma_bai_giang, tieu_de FROM bai_giang WHERE nguon_goc='ai_tao_sinh'")
bai_map = {row[0]: row[1].lower() for row in pc.fetchall()}

fail_count = 0
dg_inserted = 0
for ma_bai in expert1_bais + expert2_bais:
    ma_cg = eg_ids[0] if ma_bai in expert1_bais else eg_ids[1]
    td = bai_map.get(ma_bai, '')
    # Canva bài F.B2, F.B3 và 1 bài Tin 10 → chưa đạt (tối đa 3)
    is_fail = fail_count < 3 and ('f.b2' in td or 'f.b3' in td or ('tin 10' in td and fail_count < 3))
    if is_fail: fail_count += 1
    row = make_danh_gia(ma_bai, ma_cg, not is_fail)
    pc.execute("""
        INSERT INTO danh_gia
          (ma_bai_giang, ma_chuyen_gia, ngay_danh_gia, diem_noi_dung, diem_trinh_bay,
           diem_phu_hop_chuong_trinh, ket_qua, nhan_xet, tieu_chi_chi_tiet, trang_thai)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        ON CONFLICT DO NOTHING
    """, row)
    dg_inserted += 1

pg.commit()
print(f"✅ danh_gia: {dg_inserted} bản ghi ({fail_count} chưa đạt / {dg_inserted-fail_count} đạt)")

# Tổng kết
pc.execute("SELECT COUNT(*) FROM chuyen_gia")
print(f"\n📊 chuyen_gia:  {pc.fetchone()[0]}")
pc.execute("SELECT COUNT(*) FROM chi_tiet_ai")
print(f"📊 chi_tiet_ai: {pc.fetchone()[0]}")
pc.execute("SELECT COUNT(*) FROM danh_gia WHERE trang_thai='da_danh_gia'")
print(f"📊 danh_gia:    {pc.fetchone()[0]} đã đánh giá")
pc.execute("SELECT COUNT(*) FROM danh_gia WHERE ket_qua=true")
d = pc.fetchone()[0]
pc.execute("SELECT COUNT(*) FROM danh_gia WHERE ket_qua=false")
f = pc.fetchone()[0]
print(f"   → Đạt: {d} | Chưa đạt: {f}")

pc.close(); pg.close()
print("\n✅ Seed data hoàn tất!")
