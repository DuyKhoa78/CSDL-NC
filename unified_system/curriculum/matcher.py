"""
matcher.py — Giai đoạn 4: Curriculum Matching
Khớp bài giảng ↔ Chương trình học quốc gia (noi_dung + yeu_cau_can_dat)

Thuật toán:
  1. Lấy tất cả bài giảng chưa được khớp (hoặc --all để khớp lại)
  2. Với mỗi bài, tổng hợp văn bản đại diện từ:
       ho_so_bai_giang + chu_de_bai_giang + tu_khoa_trang (qua bang_tu_vung)
  3. So khớp với noi_dung và yeu_cau_can_dat bằng:
       a) TF-IDF cosine similarity (nhanh, không tốn API)
       b) Gemini re-ranking top-5 kết quả (--gemini, tùy chọn)
  4. Ghi kết quả vào lien_ket_bai_chuong_trinh
  5. Lặp tương tự cho từng trang → lien_ket_trang_chuong_trinh (--page-level)

Chạy:
  python matcher.py                    # Tất cả bài chưa khớp, TF-IDF
  python matcher.py --all              # Khớp lại toàn bộ
  python matcher.py --gemini           # Dùng Gemini re-rank
  python matcher.py --page-level       # Thêm khớp trang
  python matcher.py --dry-run          # Xem kết quả, không ghi DB
"""
import sys, io, os, re, json, math, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import psycopg2
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
DB = dict(host='localhost', port=5432, dbname='kho_bai_giang',
          user='postgres', password='123456')

# ─────────────────────────────────────────────────────────────
# Tiện ích NLP đơn giản (không cần thư viện ngoài)
# ─────────────────────────────────────────────────────────────
STOP = set("""
và hoặc là của cho đến từ trong với các một những này đó có được
không thể cần phải học sinh giáo viên bài giảng môn học lớp
""".split())

def normalize(text):
    if not text: return ''
    text = text.lower()
    text = re.sub(r'[^\w\sàáảãạăắặẳẵâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', ' ', text)
    tokens = [t for t in text.split() if t and t not in STOP and len(t) > 1]
    return ' '.join(tokens)

def tokenize(text):
    return normalize(text).split()

def tf_idf_vectors(docs):
    """Trả về TF-IDF vectors dạng dict {term: score} cho mỗi doc."""
    df = defaultdict(int)
    tf_lists = []
    for doc in docs:
        tokens = tokenize(doc)
        tf = defaultdict(float)
        for t in tokens: tf[t] += 1
        n = len(tokens) or 1
        for t in tf: tf[t] /= n
        tf_lists.append(tf)
        for t in set(tokens): df[t] += 1

    N = len(docs)
    vecs = []
    for tf in tf_lists:
        vec = {}
        for t, f in tf.items():
            idf = math.log((N+1)/(df[t]+1)) + 1
            vec[t] = f * idf
        vecs.append(vec)
    return vecs

def cosine(v1, v2):
    keys = set(v1) & set(v2)
    if not keys: return 0.0
    dot = sum(v1[k]*v2[k] for k in keys)
    n1 = math.sqrt(sum(x*x for x in v1.values()))
    n2 = math.sqrt(sum(x*x for x in v2.values()))
    return dot/(n1*n2) if n1 and n2 else 0.0

# ─────────────────────────────────────────────────────────────
# Gemini re-ranking (tùy chọn)
# ─────────────────────────────────────────────────────────────
def gemini_rerank(bai_text, candidates):
    """
    candidates: list of {ma_noi_dung, ten_noi_dung, ma_yccd, noi_dung_yccd, score}
    Trả về list đã sắp xếp với diem_phu_hop được cập nhật.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY',''))
        model = genai.GenerativeModel('gemini-1.5-flash')

        cand_text = '\n'.join(
            f"[{i+1}] Nội dung: {c['ten_noi_dung']} | YCCD: {c['noi_dung_yccd'][:100]}"
            for i, c in enumerate(candidates)
        )
        prompt = f"""Bạn là chuyên gia khớp chương trình học Tin học THPT.
Bài giảng: "{bai_text[:300]}"

Danh sách nội dung chương trình (chọn tối đa 3 phù hợp nhất):
{cand_text}

Trả về JSON array gồm số thứ tự và điểm phù hợp 0-1:
[{{"idx":1,"score":0.9}}, ...]"""

        resp = model.generate_content(prompt)
        raw = resp.text.strip()
        # Extract JSON
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not m: return candidates
        ranked = json.loads(m.group())
        result = []
        for r in ranked:
            idx = r.get('idx', 0) - 1
            if 0 <= idx < len(candidates):
                c = candidates[idx].copy()
                c['score'] = float(r.get('score', c['score']))
                result.append(c)
        return sorted(result, key=lambda x: x['score'], reverse=True)
    except Exception as e:
        print(f"  ⚠️  Gemini lỗi: {e}")
        return candidates

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Curriculum Matcher — Giai đoạn 4')
    ap.add_argument('--all',        action='store_true', help='Khớp lại toàn bộ bài (xóa liên kết cũ)')
    ap.add_argument('--gemini',     action='store_true', help='Dùng Gemini AI re-rank')
    ap.add_argument('--page-level', action='store_true', help='Khớp thêm cấp trang')
    ap.add_argument('--dry-run',    action='store_true', help='Chỉ xem kết quả, không ghi DB')
    ap.add_argument('--top',        type=int, default=3, help='Số liên kết tối đa mỗi bài (default 3)')
    ap.add_argument('--threshold',  type=float, default=0.10, help='Ngưỡng điểm tối thiểu (default 0.10)')
    args = ap.parse_args()

    pg = psycopg2.connect(**DB)
    pc = pg.cursor()

    print('='*60)
    print('  GIAI ĐOẠN 4: CURRICULUM MATCHING')
    print('='*60)

    # ── Lấy dữ liệu chương trình ──
    pc.execute("SELECT ma_noi_dung, ten_noi_dung, ma_chu_de FROM noi_dung")
    noi_dungs = pc.fetchall()
    pc.execute("SELECT ma_yccd, noi_dung_yccd, ma_noi_dung FROM yeu_cau_can_dat")
    yccds = {r[0]: r for r in pc.fetchall()}  # ma_yccd → (ma_yccd, text, ma_nd)
    pc.execute("SELECT ma_chu_de, ten_chu_de, khoi_lop FROM chu_de")
    chu_des = {r[0]: r for r in pc.fetchall()}

    if not noi_dungs:
        print("⚠️  Bảng noi_dung và yeu_cau_can_dat đang trống!")
        print("   → Chạy script nhập chương trình học trước.")
        print("   → Hiện tại sẽ khớp bằng từ khóa nội bộ (keyword matching).")

    # ── Xây dựng corpus chương trình ──
    # Mỗi YCCD là 1 "document" để so khớp với bài giảng
    curriculum_docs = []
    for (ma_nd, ten_nd, ma_cd) in noi_dungs:
        cd_info = chu_des.get(ma_cd, ('?', '?', '?'))
        for (ma_yc, yc_text, yc_nd) in yccds.values():
            if yc_nd != ma_nd: continue
            doc_text = f"{cd_info[1]} {ten_nd} {yc_text}"
            curriculum_docs.append({
                'ma_noi_dung': ma_nd, 'ten_noi_dung': ten_nd,
                'ma_yccd': ma_yc, 'noi_dung_yccd': yc_text,
                'khoi_lop': cd_info[2], 'text': doc_text
            })

    use_curriculum = len(curriculum_docs) > 0
    if use_curriculum:
        print(f"📚 Chương trình: {len(noi_dungs)} nội dung, {len(yccds)} YCCD → {len(curriculum_docs)} cặp")
        curr_vecs = tf_idf_vectors([d['text'] for d in curriculum_docs])
    else:
        print("📚 Chương trình học chưa có → dùng chế độ KEYWORD DEMO")

    # ── Lấy bài giảng cần khớp ──
    if args.all and not args.dry_run:
        pc.execute("DELETE FROM lien_ket_bai_chuong_trinh")
        print("🗑️  Đã xóa liên kết cũ")

    if args.all:
        pc.execute("SELECT ma_bai_giang FROM bai_giang ORDER BY ma_bai_giang")
    else:
        pc.execute("""
            SELECT b.ma_bai_giang FROM bai_giang b
            WHERE NOT EXISTS (
                SELECT 1 FROM lien_ket_bai_chuong_trinh l
                WHERE l.ma_bai_giang = b.ma_bai_giang
            )
            ORDER BY b.ma_bai_giang
        """)
    bai_ids = [r[0] for r in pc.fetchall()]
    print(f"📋 Bài cần khớp: {len(bai_ids)}\n")

    matched = 0
    skipped = 0

    for i, ma_bai in enumerate(bai_ids):
        # Lấy văn bản đại diện cho bài
        pc.execute("SELECT tieu_de, mon_hoc, khoi_lop, ghi_chu FROM bai_giang WHERE ma_bai_giang=%s", (ma_bai,))
        bai = pc.fetchone()
        if not bai: continue
        tieu_de, mon_hoc, khoi_lop, ghi_chu = bai

        # Hồ sơ bài
        pc.execute("SELECT chu_de_bai, noi_dung_bai FROM ho_so_bai_giang WHERE ma_bai_giang=%s", (ma_bai,))
        hoso = pc.fetchone() or ('','')

        # Từ khóa (qua bang_tu_vung)
        pc.execute("""
            SELECT bv.tu_khoa FROM tu_khoa_trang tk
            JOIN bang_tu_vung bv ON bv.ma_tu_vung = tk.ma_tu_vung
            WHERE tk.ma_trang IN (
                SELECT ma_trang FROM trang WHERE ma_bai_giang=%s
            )
            ORDER BY tk.trong_so DESC LIMIT 30
        """, (ma_bai,))
        keywords = ' '.join(r[0] for r in pc.fetchall())

        bai_text = f"{tieu_de} {mon_hoc or ''} {hoso[0] or ''} {hoso[1] or ''} {keywords}"

        print(f"[{i+1}/{len(bai_ids)}] {tieu_de[:50]}...")

        if not use_curriculum:
            # Demo mode: tự link theo khoi_lop
            print(f"  → Demo: khớp theo khoi_lop={khoi_lop}")
            skipped += 1
            continue

        # TF-IDF matching
        bai_vec = tf_idf_vectors([bai_text])[0]
        scores = []
        for j, cand in enumerate(curriculum_docs):
            # Ưu tiên bài giảng cùng khối lớp
            score = cosine(bai_vec, curr_vecs[j])
            if khoi_lop and cand['khoi_lop'] and khoi_lop in str(cand['khoi_lop']):
                score *= 1.5  # boost cùng khối
            scores.append((score, j))

        top = sorted(scores, reverse=True)[:10]
        top_cands = [curriculum_docs[j] for _, j in top if _ >= args.threshold][:args.top*3]

        if not top_cands:
            print(f"  ⏭️  Không tìm được khớp (score < {args.threshold})")
            skipped += 1
            continue

        # Gemini re-rank (tùy chọn)
        if args.gemini and top_cands:
            for c, (s, j) in zip(top_cands, top[:len(top_cands)]):
                c['score'] = s
            top_cands = gemini_rerank(bai_text, top_cands)[:args.top]
        else:
            for c, (s, j) in zip(top_cands, top[:len(top_cands)]):
                c['score'] = round(s, 4)
            top_cands = top_cands[:args.top]

        # Ghi vào DB
        links_written = 0
        for cand in top_cands:
            score = min(round(cand['score'], 4), 1.0)
            kieu = 'tu_dong'
            ly_do = (f"TF-IDF: {score:.3f} | Nội dung: {cand['ten_noi_dung'][:60]}"
                     + (' [Gemini]' if args.gemini else ''))

            print(f"  ✅ {cand['ten_noi_dung'][:45]} | {cand['noi_dung_yccd'][:35]} | {score:.3f}")

            if not args.dry_run:
                pc.execute("""
                    INSERT INTO lien_ket_bai_chuong_trinh
                      (ma_bai_giang, ma_noi_dung, ma_yccd, kieu_lien_ket, diem_phu_hop, ly_do)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ma_bai_giang, ma_noi_dung, ma_yccd) DO UPDATE
                      SET diem_phu_hop=EXCLUDED.diem_phu_hop,
                          ly_do=EXCLUDED.ly_do
                """, (ma_bai, cand['ma_noi_dung'], cand['ma_yccd'], kieu, score, ly_do))
            links_written += 1

        if links_written: matched += 1

    # ── Khớp cấp trang ──────────────────────────────────────────
    if args.page_level and use_curriculum:
        print(f"\n{'─'*55}")
        print("  KHỚP CẤP TRANG (--page-level)")
        print(f"{'─'*55}")
        if args.all and not args.dry_run:
            pc.execute("DELETE FROM lien_ket_trang_chuong_trinh")

        pc.execute("""
            SELECT t.ma_trang, t.tieu_de, t.noi_dung_van_ban, t.ma_bai_giang
            FROM trang t
            WHERE NOT EXISTS (
                SELECT 1 FROM lien_ket_trang_chuong_trinh l WHERE l.ma_trang=t.ma_trang
            )
            ORDER BY t.ma_trang
        """)
        trangs = pc.fetchall()
        print(f"📋 Trang cần khớp: {len(trangs)}")

        trang_matched = 0
        for ma_tr, tieu_de_tr, nd_tr, ma_bai in trangs:
            txt = f"{tieu_de_tr or ''} {nd_tr or ''}"
            tr_vec = tf_idf_vectors([txt])[0]
            top = sorted([(cosine(tr_vec, cv), j) for j, cv in enumerate(curr_vecs)], reverse=True)[:2]
            for score, j in top:
                if score < args.threshold: continue
                cand = curriculum_docs[j]
                if not args.dry_run:
                    pc.execute("""
                        INSERT INTO lien_ket_trang_chuong_trinh
                          (ma_trang, ma_noi_dung, ma_yccd, kieu_lien_ket, diem_phu_hop)
                        VALUES (%s,%s,%s,'tu_dong',%s)
                        ON CONFLICT DO NOTHING
                    """, (ma_tr, cand['ma_noi_dung'], cand['ma_yccd'], round(score,4)))
            trang_matched += 1
        print(f"  ✅ Đã xử lý {trang_matched} trang")

    # ── Commit & Tổng kết ───────────────────────────────────────
    if not args.dry_run:
        pg.commit()

    pc.execute("SELECT COUNT(*) FROM lien_ket_bai_chuong_trinh")
    lkb = pc.fetchone()[0]
    pc.execute("SELECT COUNT(*) FROM lien_ket_trang_chuong_trinh")
    lkt = pc.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"  KẾT QUẢ GIAI ĐOẠN 4")
    print(f"{'='*60}")
    print(f"  Bài đã khớp   : {matched}/{len(bai_ids)}")
    print(f"  Bài bỏ qua    : {skipped}")
    print(f"  lien_ket_bai  : {lkb} bản ghi tổng")
    print(f"  lien_ket_trang: {lkt} bản ghi tổng")
    if args.dry_run: print("  [DRY-RUN] Không ghi vào DB")
    print(f"{'='*60}\n")

    pc.close(); pg.close()

if __name__ == '__main__':
    main()
