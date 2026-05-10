# -*- coding: utf-8 -*-
"""
Kho Bài Giảng Thống Nhất — Ứng dụng Quản trị & Khai thác
Sử dụng PostgreSQL
"""
import sys, os, subprocess, json
from pathlib import Path
import streamlit as st
import pandas as pd

# Thêm db.py vào sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from db import q, q1, df, execute, conn

TOOL_DIR = BASE_DIR.parent / "ppt_batch_lecture_tool"

# Cài đặt giao diện
st.set_page_config(page_title="Kho Bài Giảng Thống Nhất", layout="wide", page_icon="📚")

# Inject chính xác CSS từ app cũ
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    :root {
        --bg: #0c111b;
        --bg-soft: #131a27;
        --panel: rgba(18, 24, 38, 0.88);
        --panel-strong: rgba(24, 31, 48, 0.96);
        --ink: #edf2ff;
        --muted: #96a2bf;
        --accent: #5eead4;
        --accent-2: #60a5fa;
        --line: rgba(151, 163, 184, 0.16);
        --card: rgba(16, 23, 37, 0.88);
        --card-hover: rgba(24, 33, 52, 0.96);
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(94, 234, 212, 0.14), transparent 28%),
            radial-gradient(circle at top right, rgba(96, 165, 250, 0.16), transparent 24%),
            linear-gradient(180deg, #0b1018 0%, #0d1320 45%, #101827 100%);
        color: var(--ink);
    }

    [data-testid="stHeader"] { background: #0b1018; border-bottom: 1px solid var(--line); }
    [data-testid="stToolbar"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1320 0%, #111827 100%);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] * { color: var(--ink); }

    .block-container { padding-top: 4rem; padding-bottom: 2rem; }

    .section-card {
        background: rgba(12, 18, 30, 0.72);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }
    .section-card h3, .section-card p { margin: 0; }

    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(16, 23, 37, 0.68);
        border: 1px solid var(--line);
        border-radius: 999px;
        color: var(--muted);
        padding: 0.55rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.16), rgba(96, 165, 250, 0.20));
        color: var(--ink);
    }

    div[data-testid="stMetric"] {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 0.9rem 1rem;
    }

    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        border: 1px solid var(--line);
        border-radius: 18px;
        overflow: hidden;
    }

    .stButton > button, .stFormSubmitButton > button {
        background: linear-gradient(135deg, #182338, #22304b) !important;
        color: #edf2ff !important;
        border: 1px solid rgba(151, 163, 184, 0.24) !important;
        border-radius: 18px !important;
        font-weight: 600 !important;
        min-height: 3rem !important;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: rgba(94, 234, 212, 0.48) !important;
        background: linear-gradient(135deg, #223252, #2c4268) !important;
    }

    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    div[data-baseweb="select"] > div {
        background: rgba(15, 23, 42, 0.92) !important;
        color: #edf2ff !important;
        border-color: rgba(151, 163, 184, 0.18) !important;
    }
    
    details[data-testid="stExpander"] {
        background: rgba(16, 23, 37, 0.72) !important;
        border: 1px solid var(--line) !important;
        border-radius: 18px !important;
    }
    details[data-testid="stExpander"] summary {
        background: linear-gradient(135deg, #131c2d, #1a263a) !important;
        color: #edf2ff !important;
        border-bottom: 1px solid rgba(151, 163, 184, 0.12);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


import re
import unicodedata

def safe_text(t):
    if t is None: return ""
    t = str(t)
    t = t.replace('\x0b', ' ').replace('\r', '')
    return re.sub(r'[\x00-\x08\x0c\x0e-\x1f]', '', t)

def sanitize_filename(f):
    if not f: return "bai_giang.pptx"
    f = unicodedata.normalize('NFKD', str(f)).encode('ASCII', 'ignore').decode('ASCII')
    f = re.sub(r'[^a-zA-Z0-9\s\.\-_]', '', f)
    f = re.sub(r'\s+', ' ', f).strip()
    return f or "bai_giang.pptx"

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📚 Kho Bài Giảng\n**Tin học THPT · PostgreSQL**")
    st.divider()
    try:
        t = q1("SELECT COUNT(*) AS n FROM bai_giang")["n"]
        s = q1("SELECT COUNT(*) AS n FROM trang")["n"]
        st.markdown(f"**{t}** bài giảng")
        st.markdown(f"**{s}** trang slide")
        st.caption("Dữ liệu trực tiếp từ DB kho_bai_giang (Chuẩn BCNF)")
    except Exception as e:
        st.error(f"Lỗi DB: {e}")

tabs = st.tabs([
    "📥 Nhập bài giảng", 
    "📊 Tổng quan", 
    "📚 Thư viện", 
    "🔍 Tìm kiếm", 
    "📤 Xuất dữ liệu", 
    "🎯 Khớp chương trình", 
    "⭐ Đánh giá chuyên gia"
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: NHẬP BÀI GIẢNG
# ═══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("📥 Nhập dữ liệu (PostgreSQL Pipeline)")
    up_tab, folder_tab = st.tabs(["Tải lên nhiều file PowerPoint", "Quét cả thư mục bài giảng"])

    with up_tab:
        st.markdown('<div class="section-card"><h3>Tải lên nhiều file PowerPoint</h3><p>Đưa tài liệu trực tiếp vào hệ cơ sở dữ liệu hợp nhất.</p></div>', unsafe_allow_html=True)
        # Không dùng st.form để các dropdown có thể cập nhật trạng thái động (cascading)
        uploaded = st.file_uploader("Chọn file .pptx / .pdf", type=["pptx","pdf"], accept_multiple_files=True)
        
        grade = st.selectbox("Lớp", ["8", "9", "10", "11", "12"])
        
        # Lấy Chủ đề theo lớp
        chu_des = q("SELECT ma_chu_de, ten_chu_de FROM chu_de WHERE khoi_lop ILIKE %s ORDER BY ma_chu_de", (f"%{grade}%",))
        cd_opts = {c['ten_chu_de']: c['ma_chu_de'] for c in chu_des}
        sel_cd = st.selectbox("Chủ đề", ["(Không chọn)"] + list(cd_opts.keys()))
        ma_cd = cd_opts.get(sel_cd)
        
        # Lấy Nội dung theo Chủ đề
        ma_nd = None
        if ma_cd:
            nds = q("SELECT ma_noi_dung, ten_noi_dung FROM noi_dung WHERE ma_chu_de = %s ORDER BY ma_noi_dung", (ma_cd,))
            nd_opts = {nd['ten_noi_dung']: nd['ma_noi_dung'] for nd in nds}
            sel_nd = st.selectbox("Nội dung", ["(Không chọn)"] + list(nd_opts.keys()))
            ma_nd = nd_opts.get(sel_nd)
        else:
            st.selectbox("Nội dung", ["(Chọn Chủ đề trước)"], disabled=True)
            
        # Lấy Yêu cầu cần đạt theo Nội dung
        ma_yccd = None
        if ma_nd:
            yccds = q("SELECT ma_yccd, noi_dung_yccd FROM yeu_cau_can_dat WHERE ma_noi_dung = %s ORDER BY ma_yccd", (ma_nd,))
            yccd_opts = {yc['noi_dung_yccd']: yc['ma_yccd'] for yc in yccds}
            sel_yc = st.selectbox("Yêu cầu cần đạt", ["(Không chọn)"] + list(yccd_opts.keys()))
            ma_yccd = yccd_opts.get(sel_yc)
        else:
            st.selectbox("Yêu cầu cần đạt", ["(Chọn Nội dung trước)"], disabled=True)
            
        nguon = st.selectbox("Nguồn gốc", ["thu_cong", "ai_tao_sinh", "thu_thap_web"])
        
        submit = st.button("Đưa vào kho dữ liệu", use_container_width=True, type="primary")
        
        if submit and uploaded:
            import tempfile, hashlib
            router = BASE_DIR / "importers" / "file_router.py"
            tmp = Path(tempfile.mkdtemp())
            progress = st.progress(0)
            
            for i, f in enumerate(uploaded, 1):
                grade_str = f"K{grade}" if grade else "K_Unknown"
                source_dir = tmp / nguon / grade_str
                source_dir.mkdir(parents=True, exist_ok=True)
                fp = source_dir / f.name
                
                file_bytes = f.getvalue()
                fp.write_bytes(file_bytes)
                
                cmd = [sys.executable, str(router), "--file", str(fp)]
                # Đặt PYTHONUTF8=1 để tiến trình con xử lý đúng tên file tiếng Việt
                import os as _os
                env = _os.environ.copy()
                env["PYTHONUTF8"] = "1"
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
                
                # Gắn nhãn thủ công
                if r.returncode == 0 and ma_nd and ma_yccd:
                    h = hashlib.sha256()
                    h.update(file_bytes)
                    hash_val = h.hexdigest()
                    
                    bg = q1("SELECT ma_bai_giang FROM bai_giang WHERE ma_hash_tep = %s", (hash_val,))
                    if bg:
                        execute("""INSERT INTO lien_ket_bai_chuong_trinh (ma_bai_giang, ma_noi_dung, ma_yccd, kieu_lien_ket, diem_phu_hop, ly_do) 
                                   VALUES (%s,%s,%s,'thu_cong',1.0,'Người dùng gắn nhãn khi tải lên')
                                   ON CONFLICT (ma_bai_giang, ma_noi_dung, ma_yccd) DO UPDATE SET diem_phu_hop=1.0, kieu_lien_ket='thu_cong'""", 
                                (bg['ma_bai_giang'], ma_nd, ma_yccd))
                
                progress.progress(i/len(uploaded), text=safe_text(f.name))
                if r.returncode != 0:
                    err_msg = safe_text((r.stderr or r.stdout or "")[:300])
                    st.warning(f"⚠️ Lỗi ở {safe_text(f.name)}:\n```\n{err_msg}\n```")
                
            st.success(f"Đã xử lý {len(uploaded)} file!")
            st.cache_resource.clear()

    with folder_tab:
        st.markdown('<div class="section-card"><h3>Quét cả thư mục bài giảng</h3><p>Hữu ích khi bạn đã có sẵn thư mục chứa nhiều file.</p></div>', unsafe_allow_html=True)
        with st.form("folder_form"):
            input_dir = st.text_input("Thư mục chứa PPT", value=str(BASE_DIR.parent / "PPT_INPUT"))
            nguon2 = st.selectbox("Nguồn gốc chung", ["thu_cong", "ai_tao_sinh", "thu_thap_web"])
            dry = st.checkbox("Chạy thử (Không ghi DB)", value=True)
            if st.form_submit_button("Quét và đưa vào kho", use_container_width=True):
                adapter = BASE_DIR / "crawling" / "crawling_adapter.py"
                cmd = [sys.executable, str(adapter), "--dir", input_dir, "--source", nguon2]
                if dry: cmd.append("--dry-run")
                with st.spinner("Đang quét..."):
                    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
                st.code(r.stdout[-3000:])
                if r.returncode != 0: st.error(r.stderr[-1000:])
                st.cache_resource.clear()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: TỔNG QUAN
# ═══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Tổng quan kho dữ liệu")
    try:
        row = q1("SELECT COUNT(*) AS bai, SUM(so_trang) AS trang, COUNT(DISTINCT khoi_lop) AS khoi FROM bai_giang")
        lk = q1("SELECT COUNT(DISTINCT ma_bai_giang) AS khop FROM lien_ket_bai_chuong_trinh")
        dg = q1("SELECT COUNT(*) AS n, SUM(CASE WHEN ket_qua THEN 1 ELSE 0 END) AS dat FROM danh_gia")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Bài giảng", row["bai"], "Tổng số file PPT")
        c2.metric("Slides", row["trang"] or 0, "Tổng số trang")
        c3.metric("Khớp chương trình", lk["khop"], f"{(lk['khop']/(row['bai'] or 1))*100:.1f}%")
        c4.metric("Đánh giá Đạt", dg["dat"] or 0, f"Trên {dg['n']} bài đã đánh giá")

        c1, c2 = st.columns([1.05, 0.95])
        with c1:
            st.markdown("**Phân bố theo khối lớp**")
            d1 = df("SELECT khoi_lop AS k, COUNT(*) AS n FROM bai_giang WHERE khoi_lop IS NOT NULL GROUP BY k")
            if not d1.empty: st.bar_chart(d1.set_index("k"))
        with c2:
            st.markdown("**Thành phần nội dung (Block)**")
            d2 = df("SELECT loai_khoi AS k, COUNT(*) AS n FROM khoi_noi_dung GROUP BY k ORDER BY n DESC")
            if not d2.empty: st.bar_chart(d2.set_index("k"))

        st.markdown("**Bài giảng mới cập nhật**")
        d3 = df("SELECT ma_bai_giang, tieu_de, nguon_goc, khoi_lop, so_trang, to_char(ngay_them,'DD/MM/YYYY') as ngay FROM bai_giang ORDER BY ngay_them DESC LIMIT 10")
        st.dataframe(d3, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Lỗi: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: THƯ VIỆN BÀI GIẢNG
# ═══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Thư viện bài giảng")
    try:
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
        khoi_opts = ["Tất cả"] + sorted([x["khoi_lop"] for x in q("SELECT DISTINCT khoi_lop FROM bai_giang WHERE khoi_lop IS NOT NULL")], key=lambda x: int(x) if x.isdigit() else x)
        src_opts  = ["Tất cả", "thu_cong", "ai_tao_sinh", "thu_thap_web"]
        loai_opts = ["Tất cả", "pptx", "pdf"]
        
        fkhoi = c1.selectbox("Lớp", khoi_opts)
        fsrc  = c2.selectbox("Nguồn", src_opts)
        floai = c3.selectbox("Định dạng", loai_opts)
        fkw   = c4.text_input("Lọc theo từ khoá")

        w, p = ["1=1"], []
        if fkhoi != "Tất cả": w.append("khoi_lop=%s"); p.append(fkhoi)
        if fsrc != "Tất cả": w.append("nguon_goc=%s"); p.append(fsrc)
        if floai != "Tất cả": w.append("loai_tep=%s"); p.append(floai)
        if fkw.strip(): w.append("tieu_de ILIKE %s"); p.append(f"%{fkw}%")

        d4 = df(f"SELECT ma_bai_giang AS id, tieu_de AS title, nguon_goc AS source, loai_tep AS type, khoi_lop AS grade, so_trang AS slides FROM bai_giang WHERE {' AND '.join(w)} ORDER BY ngay_them DESC LIMIT 500", p)
        st.caption(f"Tìm thấy {len(d4)} bài giảng phù hợp.")
        st.dataframe(d4, use_container_width=True, hide_index=True)

        if not d4.empty:
            labels = {f"#{int(r.id)} - {safe_text(r.title)} ({int(r.slides)} slide)": int(r.id) for r in d4.itertuples()}
            sel_id = st.selectbox("Chọn bài giảng", list(labels.keys()))
            bg_id = labels[sel_id]

            # Lấy thông tin chi tiết
            bai = q1("SELECT * FROM bai_giang WHERE ma_bai_giang=%s", (bg_id,))
            hs = q1("SELECT * FROM ho_so_bai_giang WHERE ma_bai_giang=%s", (bg_id,))
            
            st.markdown(f"### {safe_text(bai.get('tieu_de'))}")
            
            if bai and bai.get('duong_dan_tep') and os.path.exists(bai['duong_dan_tep']):
                file_path = bai['duong_dan_tep']
                raw_name = os.path.basename(file_path)
                
                # Nút mở trực tiếp bằng PowerPoint/ứng dụng mặc định
                col_open, col_dir = st.columns(2)
                with col_open:
                    if st.button("🖥️ Mở bằng PowerPoint", use_container_width=True, type="primary"):
                        import subprocess
                        subprocess.Popen(['start', '', file_path], shell=True)
                        st.toast("✅ Đang mở file bằng PowerPoint...", icon="🖥️")
                with col_dir:
                    if st.button("📂 Mở thư mục chứa file", use_container_width=True):
                        import subprocess
                        subprocess.Popen(['explorer', '/select,', file_path])
                        st.toast("📂 Đang mở thư mục...", icon="📂")
                
                # Hiển thị đường dẫn để copy thủ công
                st.markdown("**📋 Đường dẫn file (copy để mở thủ công):**")
                st.code(file_path, language=None)
                st.caption(f"💡 Kéo đường dẫn trên vào thanh địa chỉ Windows Explorer hoặc hộp thoại Mở file của PowerPoint")
                
            elif bai and bai.get('duong_dan_tep'):
                st.warning(f"⚠️ Không tìm thấy file tại:\n`{bai['duong_dan_tep']}`")

            
            with st.expander("Thông tin bài giảng trực tuyến", expanded=True):
                with st.form(f"bg_form_{bg_id}"):
                    c_cd = st.text_input("Chủ đề bài giảng", value=safe_text(hs.get('chu_de_bai')))
                    c_nd = st.text_area("Nội dung giới thiệu", value=safe_text(hs.get('noi_dung_bai')), height=100)
                    if st.form_submit_button("Lưu thông tin", use_container_width=True):
                        execute("INSERT INTO ho_so_bai_giang (ma_bai_giang,chu_de_bai,noi_dung_bai) VALUES (%s,%s,%s) ON CONFLICT(ma_bai_giang) DO UPDATE SET chu_de_bai=EXCLUDED.chu_de_bai, noi_dung_bai=EXCLUDED.noi_dung_bai", (bg_id, c_cd, c_nd))
                        st.success("Đã lưu!")
            
            with st.expander("Xoá bài giảng"):
                st.warning("Xoá sẽ ảnh hưởng đến tất cả các bảng liên quan (Cascade).")
                if st.checkbox("Xác nhận xoá bài giảng", key=f"del_{bg_id}"):
                    if st.button("Xoá ngay"):
                        execute("DELETE FROM bai_giang WHERE ma_bai_giang=%s", (bg_id,))
                        st.success("Đã xoá!"); st.rerun()

            # Danh sách slide
            slides = df("SELECT so_thu_tu, tieu_de, loai_trang, LEFT(noi_dung_van_ban,100) as noi_dung FROM trang WHERE ma_bai_giang=%s ORDER BY so_thu_tu", (bg_id,))
            if not slides.empty:
                st.dataframe(slides, use_container_width=True, hide_index=True)
                
                # Chi tiết 1 slide
                s_map = {f"Slide {int(r.so_thu_tu):03d} - {safe_text(r.tieu_de)}": int(r.so_thu_tu) for r in slides.itertuples()}
                sel_s = st.selectbox("Chọn slide để xem chi tiết", list(s_map.keys()))
                s_num = s_map[sel_s]
                
                slide = q1("SELECT * FROM trang WHERE ma_bai_giang=%s AND so_thu_tu=%s", (bg_id, s_num))
                if slide:
                    c1, c2 = st.columns([1.2, 0.8])
                    with c1:
                        st.markdown(f"#### {safe_text(slide.get('tieu_de'))}")
                        st.info(f"Loại: {safe_text(slide.get('loai_trang'))}")
                        st.markdown(safe_text(slide.get('noi_dung_van_ban')) or "_Không có text_")
                    with c2:
                        st.markdown("#### Khối nội dung")
                        blocks = df("SELECT so_thu_tu_khoi, loai_khoi, LEFT(noi_dung_van_ban,100) AS nd FROM khoi_noi_dung WHERE ma_trang=%s ORDER BY so_thu_tu_khoi", (slide['ma_trang'],))
                        if not blocks.empty: st.dataframe(blocks, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: TÌM KIẾM (FTS5 -> TSVECTOR)
# ═══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Tìm kiếm trong kho bài giảng")
    st.caption("Tìm kiếm Full-text (TSVECTOR) cực nhanh trên cơ sở dữ liệu PostgreSQL.")
    
    with st.form("search_form"):
        query = st.text_input("Nhập từ khoá (vd: lập trình, internet, máy tính...)", value="")
        limit = st.slider("Số kết quả tối đa", min_value=5, max_value=100, value=20)
        submit = st.form_submit_button("Tìm kiếm", use_container_width=True)
        
    if submit and query:
        res = q("""
            SELECT b.tieu_de AS lesson_title, t.so_thu_tu AS slide_no, 
                   t.tieu_de AS slide_title, b.duong_dan_tep,
                   ts_headline('simple', t.noi_dung_van_ban, plainto_tsquery('simple', %s), 'StartSel=**, StopSel=**') AS snippet
            FROM trang t JOIN bai_giang b ON t.ma_bai_giang = b.ma_bai_giang
            WHERE t.vector_tim_kiem @@ plainto_tsquery('simple', %s)
            ORDER BY ts_rank(t.vector_tim_kiem, plainto_tsquery('simple', %s)) DESC
            LIMIT %s
        """, (query, query, query, limit))
        
        if not res:
            st.info("Không tìm thấy kết quả phù hợp.")
        else:
            st.success(f"Tìm thấy {len(res)} kết quả.")
            for i, r in enumerate(res):
                with st.container(border=True):
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1:
                        st.markdown(f"**Slide {int(r['slide_no'])}: {safe_text(r['slide_title'])}**")
                        st.caption(f"Bài giảng: {safe_text(r['lesson_title'])}")
                        st.write(safe_text(r['snippet']))
                    with c2:
                        file_path = r.get('duong_dan_tep')
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                raw_name = os.path.basename(file_path)
                                clean_name = safe_text(raw_name)
                                if raw_name.lower().endswith('.pptx') and not clean_name.lower().endswith('.pptx'): clean_name += '.pptx'
                                if raw_name.lower().endswith('.pdf') and not clean_name.lower().endswith('.pdf'): clean_name += '.pdf'
                                
                                st.download_button(
                                    label="📥 Tải PPT",
                                    data=f.read(),
                                    file_name=sanitize_filename(clean_name),
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation" if clean_name.endswith('.pptx') else "application/pdf",
                                    use_container_width=True,
                                    key=f"dl_search_{i}"
                                )

    st.divider()
    st.markdown("### Tìm kiếm bằng từ điển (bang_tu_vung)")
    kw2 = st.text_input("Từ khóa chuẩn (CPU, RAM, ROM...)")
    if kw2:
        tv = df("SELECT tu_khoa, tu_khoa_chuan FROM bang_tu_vung WHERE tu_khoa ILIKE %s OR tu_khoa_chuan ILIKE %s", (f"%{kw2}%", f"%{kw2}%"))
        st.dataframe(tv, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5: XUẤT DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Xuất dữ liệu")
    st.markdown('<div class="section-card"><h3>Xuất kho dữ liệu ra nhiều định dạng</h3><p>Hỗ trợ xuất CSV cho phân tích và JSONL cho huấn luyện AI/RAG.</p></div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Xuất danh sách bài giảng (CSV)**")
        if st.button("Tạo CSV Bài Giảng", use_container_width=True):
            d = df("SELECT * FROM bai_giang")
            st.download_button("⬇️ Tải CSV", d.to_csv(index=False).encode('utf-8-sig'), "bai_giang.csv", "text/csv")
    with c2:
        st.markdown("**Xuất danh sách kết quả matching (CSV)**")
        if st.button("Tạo CSV Matching", use_container_width=True):
            d = df("SELECT * FROM lien_ket_bai_chuong_trinh")
            st.download_button("⬇️ Tải CSV", d.to_csv(index=False).encode('utf-8-sig'), "matching.csv", "text/csv")
    with c3:
        st.markdown("**Xuất kho RAG (JSONL)**")
        if st.button("Tạo File JSONL", use_container_width=True):
            trangs = q("SELECT b.tieu_de as bg, t.tieu_de, t.noi_dung_van_ban as nd FROM trang t JOIN bai_giang b ON t.ma_bai_giang=b.ma_bai_giang WHERE t.noi_dung_van_ban IS NOT NULL")
            lines = [json.dumps({"title": f"{r['bg']} - {r['tieu_de']}", "content": r['nd']}, ensure_ascii=False) for r in trangs]
            out = "\n".join(lines)
            st.download_button("⬇️ Tải JSONL", out.encode('utf-8'), "rag_dataset.jsonl", "application/jsonl")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 6: KHỚP CHƯƠNG TRÌNH (NEW)
# ═══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("🎯 Khớp Chương trình học (Curriculum Matching)")
    try:
        r = q1("SELECT COUNT(DISTINCT ma_bai_giang) AS khop, COUNT(*) AS links, ROUND(AVG(diem_phu_hop)::numeric,3) AS diem FROM lien_ket_bai_chuong_trinh")
        total = q1("SELECT COUNT(*) AS n FROM bai_giang")["n"]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng số bài", total)
        c2.metric("Số bài đã khớp", r["khop"])
        c3.metric("Tỷ lệ khớp", f"{(r['khop']/(total or 1))*100:.1f}%")
        c4.metric("Tổng liên kết", r["links"])
        
        st.markdown("**Chạy hệ thống Auto-Matching (TF-IDF)**")
        if st.button("Chạy lại thuật toán", type="primary"):
            matcher_path = BASE_DIR / "curriculum" / "matcher.py"
            with st.spinner("Đang chạy thuật toán Matching..."):
                ret = subprocess.run([sys.executable, str(matcher_path)], capture_output=True, text=True, encoding='utf-8')
            if ret.returncode == 0:
                st.success("Hoàn tất!")
                st.code(ret.stdout[-2000:])
            else:
                st.error(ret.stderr[-1000:])
                
        st.markdown("**Kết quả khớp**")
        d_khop = df("SELECT b.tieu_de, b.khoi_lop, c.ten_chu_de, LEFT(y.noi_dung_yccd, 150) as yccd, ROUND(l.diem_phu_hop::numeric,3) as diem FROM lien_ket_bai_chuong_trinh l JOIN bai_giang b ON b.ma_bai_giang=l.ma_bai_giang LEFT JOIN noi_dung n ON n.ma_noi_dung=l.ma_noi_dung LEFT JOIN chu_de c ON c.ma_chu_de=n.ma_chu_de LEFT JOIN yeu_cau_can_dat y ON y.ma_yccd=l.ma_yccd ORDER BY l.diem_phu_hop DESC LIMIT 200")
        st.dataframe(d_khop, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(e)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 7: ĐÁNH GIÁ CHUYÊN GIA (NEW)
# ═══════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("⭐ Đánh giá chuyên gia")
    try:
        dg_list = df("SELECT c.ten_chuyen_gia, b.tieu_de, d.diem_noi_dung, d.diem_trinh_bay, CASE WHEN d.ket_qua THEN 'Đạt' ELSE 'Chưa đạt' END as ket_qua, d.nhan_xet, to_char(d.ngay_danh_gia,'DD/MM/YYYY') as ngay FROM danh_gia d JOIN chuyen_gia c ON d.ma_chuyen_gia=c.ma_chuyen_gia JOIN bai_giang b ON b.ma_bai_giang=d.ma_bai_giang ORDER BY d.ngay_danh_gia DESC")
        if not dg_list.empty:
            st.dataframe(dg_list, use_container_width=True, hide_index=True)
            
        with st.expander("➕ Thêm đánh giá mới"):
            with st.form("form_danh_gia"):
                cg_opts = {f"{r['ten_chuyen_gia']} ({r['don_vi_cong_tac']})": r['ma_chuyen_gia'] for r in q("SELECT * FROM chuyen_gia")}
                bg_opts = {f"{r['tieu_de'][:80]}": r['ma_bai_giang'] for r in q("SELECT * FROM bai_giang ORDER BY ngay_them DESC LIMIT 100")}
                
                s_cg = st.selectbox("Chọn chuyên gia", list(cg_opts.keys()))
                s_bg = st.selectbox("Chọn bài giảng", list(bg_opts.keys()))
                
                c1, c2, c3 = st.columns(3)
                d1 = c1.slider("Điểm nội dung", 0.0, 10.0, 8.0, 0.5)
                d2 = c2.slider("Điểm trình bày", 0.0, 10.0, 8.0, 0.5)
                d3 = c3.slider("Điểm phù hợp CT", 0.0, 10.0, 8.0, 0.5)
                kq = st.radio("Kết quả", ["Đạt", "Chưa đạt"], horizontal=True)
                nx = st.text_area("Nhận xét")
                
                if st.form_submit_button("Lưu đánh giá"):
                    execute("INSERT INTO danh_gia(ma_bai_giang, ma_chuyen_gia, ngay_danh_gia, diem_noi_dung, diem_trinh_bay, diem_phu_hop_chuong_trinh, ket_qua, nhan_xet, trang_thai) VALUES (%s,%s,NOW(),%s,%s,%s,%s,%s,'da_danh_gia')", (bg_opts[s_bg], cg_opts[s_cg], d1, d2, d3, kq=="Đạt", nx))
                    st.success("Đã thêm đánh giá!"); st.rerun()
    except Exception as e:
        st.error(e)
