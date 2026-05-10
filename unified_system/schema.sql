-- ============================================================
-- SCHEMA: KHO BÀI GIẢNG THỐNG NHẤT
-- Database: kho_bai_giang  |  PostgreSQL 14+
-- Tổng: 22 bảng (đã chuẩn hóa 1NF · 2NF · 3NF · BCNF)
-- ============================================================
-- Chuẩn hóa đã áp dụng:
--  [1NF]  Xóa cột đa trị yeu_cau_can_dat trong ho_so_bai_giang & ho_so_trang
--  [1NF]  bai_giang.chuong VARCHAR(200) → ma_noi_dung CHAR(5) FK (tham chiếu nguyên tử)
--  [2NF]  Tách bảng chuyen_gia khỏi danh_gia (loại bỏ lặp thông tin chuyên gia)
--  [3NF]  Xóa khoi_noi_dung.noi_dung_json (trùng noi_dung_van_ban)
--  [3NF]  Thêm UNIQUE, CHECK constraints
--  [BCNF] Tách bang_tu_vung (từ điển) khỏi tu_khoa_trang
--         vì: tu_khoa → tu_khoa_chuan vi phạm BCNF (tu_khoa không phải superkey)
-- ============================================================


-- ── NHÓM 1: CHƯƠNG TRÌNH HỌC (3 bảng) ──────────────────────

-- Bảng 1: Chủ đề (chủ đề học theo khối lớp)
CREATE TABLE chu_de (
    ma_chu_de       CHAR(5)      PRIMARY KEY,
    khoi_lop        VARCHAR(20)  NOT NULL,
    ten_chu_de      VARCHAR(255) NOT NULL
);

-- Bảng 2: Nội dung (chủ đề con trong mỗi chủ đề lớn)
CREATE TABLE noi_dung (
    ma_noi_dung     CHAR(5)      PRIMARY KEY,
    ten_noi_dung    VARCHAR(255) NOT NULL,
    ma_chu_de       CHAR(5)      NOT NULL REFERENCES chu_de(ma_chu_de)
);
CREATE INDEX idx_noi_dung_chu_de ON noi_dung(ma_chu_de);

-- Bảng 3: Yêu cầu cần đạt
CREATE TABLE yeu_cau_can_dat (
    ma_yccd         CHAR(5)      PRIMARY KEY,
    noi_dung_yccd   TEXT         NOT NULL,
    ma_noi_dung     CHAR(5)      NOT NULL REFERENCES noi_dung(ma_noi_dung)
);
CREATE INDEX idx_yccd_noi_dung ON yeu_cau_can_dat(ma_noi_dung);


-- ── NHÓM 2: BÀI GIẢNG (4 bảng) ─────────────────────────────

-- Bảng 4: Bài giảng
-- [1NF] chuong VARCHAR(200) → ma_noi_dung CHAR(5) FK (tránh lưu chuỗi ghép nhiều chương)
CREATE TABLE bai_giang (
    ma_bai_giang    SERIAL        PRIMARY KEY,
    tieu_de         VARCHAR(500)  NOT NULL,
    nguon_goc       VARCHAR(20)   NOT NULL
                    CHECK (nguon_goc IN ('thu_thap_web','ai_tao_sinh','thu_cong')),
    loai_tep        VARCHAR(10)   NOT NULL
                    CHECK (loai_tep IN ('pptx','pdf')),
    duong_dan_tep   VARCHAR(1000),
    url_nguon       VARCHAR(1000),
    ma_hash_tep     VARCHAR(64)   UNIQUE,          -- SHA-256, chống import trùng
    mon_hoc         VARCHAR(100),
    khoi_lop        VARCHAR(20),
    ma_noi_dung     CHAR(5)       REFERENCES noi_dung(ma_noi_dung), -- [1NF] thay chuong
    so_trang        INTEGER,
    ngay_them       TIMESTAMP     DEFAULT NOW(),
    trang_thai      VARCHAR(20)   DEFAULT 'cho_xu_ly'
                    CHECK (trang_thai IN ('cho_xu_ly','dang_xu_ly','hoan_thanh','loi')),
    ghi_chu         TEXT
);
CREATE INDEX idx_bai_giang_noi_dung ON bai_giang(ma_noi_dung);

-- Bảng 5: Trang / Slide
-- [3NF] UNIQUE(ma_bai_giang, so_thu_tu): một bài không có 2 trang cùng số thứ tự
CREATE TABLE trang (
    ma_trang            SERIAL        PRIMARY KEY,
    ma_bai_giang        INTEGER       NOT NULL
                        REFERENCES bai_giang(ma_bai_giang) ON DELETE CASCADE,
    so_thu_tu           INTEGER       NOT NULL,
    tieu_de             VARCHAR(500),
    noi_dung_van_ban    TEXT,                       -- text trích từ PPTX / PDF
    noi_dung_markdown   TEXT,                       -- markdown để render
    loai_trang          VARCHAR(20)   NOT NULL
                        CHECK (loai_trang IN ('slide','trang_pdf')),
    ten_layout          VARCHAR(100),               -- layout gốc PPTX
    duong_dan_anh       VARCHAR(500),               -- thumbnail ảnh
    van_ban_ocr         TEXT,                       -- OCR thô (PDF phức tạp)
    mo_ta_gemini        TEXT,                       -- Gemini Vision mô tả
    slug_url            VARCHAR(255),
    du_lieu_json        JSONB,
    -- Full-Text Search (tự động cập nhật)
    vector_tim_kiem     TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple',
            coalesce(tieu_de,'')          || ' ' ||
            coalesce(noi_dung_van_ban,'') || ' ' ||
            coalesce(van_ban_ocr,'')      || ' ' ||
            coalesce(mo_ta_gemini,'')
        )
    ) STORED,
    CONSTRAINT uq_trang_bai_sothutu UNIQUE (ma_bai_giang, so_thu_tu)
);
CREATE INDEX idx_trang_fts ON trang USING GIN(vector_tim_kiem);
CREATE INDEX idx_trang_bai ON trang(ma_bai_giang);

-- Bảng 6: Khối nội dung (slide_blocks)
-- [3NF] Xóa noi_dung_json (trùng noi_dung_van_ban) → dùng du_lieu_json cho dữ liệu cấu trúc
CREATE TABLE khoi_noi_dung (
    ma_khoi             SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    loai_khoi           VARCHAR(20)
                        CHECK (loai_khoi IN ('van_ban','bang','hinh_anh','ocr')),
    vai_tro             VARCHAR(50),                -- 'tieu_de','noi_dung','bang','hinh'
    noi_dung_van_ban    TEXT,                       -- nội dung văn bản (duy nhất)
    du_lieu_json        JSONB,                      -- dành cho dữ liệu có cấu trúc (bảng…)
    vi_tri_x            FLOAT,
    vi_tri_y            FLOAT,
    chieu_rong          FLOAT,
    chieu_cao           FLOAT,
    thu_tu_hien_thi     INTEGER
);
CREATE INDEX idx_khoi_trang ON khoi_noi_dung(ma_trang);

-- Bảng 7: Tài nguyên media
CREATE TABLE tai_nguyen_media (
    ma_tai_nguyen       SERIAL        PRIMARY KEY,
    ma_bai_giang        INTEGER       REFERENCES bai_giang(ma_bai_giang),
    ma_trang            INTEGER       REFERENCES trang(ma_trang),
    ma_hash             VARCHAR(64)   UNIQUE,       -- chống lưu trùng
    duong_dan           VARCHAR(500)  NOT NULL,
    loai_media          VARCHAR(20)
                        CHECK (loai_media IN ('hinh_anh','video','anh_trang_pdf','gif')),
    kich_thuoc_byte     INTEGER,
    mo_ta_alt           TEXT
);


-- ── NHÓM 3: CHI TIẾT TRANG (3 bảng) ────────────────────────

-- Bảng 8: Đoạn văn trang
CREATE TABLE doan_van_trang (
    ma_doan_van         SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    ma_khoi             INTEGER       REFERENCES khoi_noi_dung(ma_khoi),
    so_thu_tu_khoi      INTEGER,                    -- block_no
    so_doan             INTEGER,                    -- paragraph_no trong block
    so_dong             INTEGER,                    -- line_no
    vai_tro             VARCHAR(50),                -- semantic_role
    cap_do_bullet       INTEGER,
    noi_dung            TEXT,
    noi_dung_chuan      TEXT,                       -- lowercase, chuẩn hoá
    dinh_dang_json      JSONB                       -- font, bold, color…
);
CREATE INDEX idx_doan_van_trang ON doan_van_trang(ma_trang);

-- Bảng 9: Tham chiếu media trong trang
CREATE TABLE tham_chieu_media_trang (
    ma_tham_chieu       SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    ma_khoi             INTEGER       REFERENCES khoi_noi_dung(ma_khoi),
    ma_tai_nguyen       INTEGER       REFERENCES tai_nguyen_media(ma_tai_nguyen),
    loai_tai_san        VARCHAR(50),
    nhan_tai_san        VARCHAR(100),
    van_ban_alt         TEXT,
    chu_thich           TEXT,
    duong_dan_nguon     VARCHAR(500)
);

-- Bảng 10: Dữ liệu bảng trong trang
CREATE TABLE bang_du_lieu_trang (
    ma_bang             SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    ma_khoi             INTEGER       REFERENCES khoi_noi_dung(ma_khoi),
    so_hang             INTEGER,
    so_cot              INTEGER,
    noi_dung_markdown   TEXT,
    hang_json           JSONB,
    tieu_de_json        JSONB
);


-- ── NHÓM 4: NGỮ NGHĨA & TỪVỰNG (4 bảng) ────────────────────

-- Bảng 11: Từ điển từ khóa — [BCNF]
-- Tách ra khỏi tu_khoa_trang vì: tu_khoa → tu_khoa_chuan (vi phạm BCNF)
-- 107.369 bản ghi → chỉ 3.562 từ khóa duy nhất (tiết kiệm 96.7% dư thừa)
CREATE TABLE bang_tu_vung (
    ma_tu_vung          SERIAL        PRIMARY KEY,
    tu_khoa             VARCHAR(255)  NOT NULL UNIQUE,
    tu_khoa_chuan       VARCHAR(255)            -- lowercase, bỏ dấu
);
CREATE INDEX idx_tu_vung_chuan ON bang_tu_vung(tu_khoa_chuan);

-- Bảng 12: Từ khóa trang (junction: trang ↔ từ vựng)
CREATE TABLE tu_khoa_trang (
    ma_tu_khoa          SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    ma_tu_vung          INTEGER       NOT NULL
                        REFERENCES bang_tu_vung(ma_tu_vung),
    trong_so            FLOAT         DEFAULT 1.0,
    nguon               VARCHAR(50),               -- 'title','content','notes','ocr'
    la_chu_de           BOOLEAN       DEFAULT FALSE
);
CREATE INDEX idx_tu_khoa_trang ON tu_khoa_trang(ma_trang);
CREATE INDEX idx_tk_trang_vung ON tu_khoa_trang(ma_tu_vung);

-- Bảng 13: Chủ đề trang
CREATE TABLE chu_de_trang (
    ma_chu_de_trang     SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    nhan_chu_de         VARCHAR(255)  NOT NULL,
    loai_chu_de         VARCHAR(50),
    trong_so            FLOAT         DEFAULT 1.0,
    thu_tu_hien_thi     INTEGER
);

-- Bảng 14: Chủ đề bài giảng
CREATE TABLE chu_de_bai_giang (
    ma_chu_de_bai       SERIAL        PRIMARY KEY,
    ma_bai_giang        INTEGER       NOT NULL
                        REFERENCES bai_giang(ma_bai_giang) ON DELETE CASCADE,
    nhan_chu_de         VARCHAR(255)  NOT NULL,
    loai_chu_de         VARCHAR(50),
    trong_so            FLOAT         DEFAULT 1.0,
    thu_tu_hien_thi     INTEGER
);


-- ── NHÓM 5: PROFILE TRÌNH BÀY (2 bảng) ─────────────────────

-- Bảng 15: Hồ sơ bài giảng
-- [1NF] Đã xóa yeu_cau_can_dat TEXT (đa trị) → dùng lien_ket_bai_chuong_trinh
CREATE TABLE ho_so_bai_giang (
    ma_ho_so            SERIAL        PRIMARY KEY,
    ma_bai_giang        INTEGER       UNIQUE NOT NULL
                        REFERENCES bai_giang(ma_bai_giang) ON DELETE CASCADE,
    chu_de_bai          TEXT,
    noi_dung_bai        TEXT
);

-- Bảng 16: Hồ sơ trang
-- [1NF] Đã xóa yeu_cau_can_dat TEXT (đa trị) → dùng lien_ket_trang_chuong_trinh
CREATE TABLE ho_so_trang (
    ma_ho_so_trang      SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       UNIQUE NOT NULL
                        REFERENCES trang(ma_trang) ON DELETE CASCADE,
    chu_de_trang        TEXT,
    noi_dung_trang      TEXT
);


-- ── NHÓM 6: AI & ĐÁNH GIÁ (3 bảng) ─────────────────────────

-- Bảng 17: Chi tiết AI
CREATE TABLE chi_tiet_ai (
    ma_chi_tiet             SERIAL        PRIMARY KEY,
    ma_bai_giang            INTEGER       NOT NULL
                            REFERENCES bai_giang(ma_bai_giang),
    ten_cong_cu             VARCHAR(100),
    phien_ban               VARCHAR(50),
    cau_lenh_prompt         TEXT,
    loai_dau_ra             VARCHAR(10)
                            CHECK (loai_dau_ra IN ('pptx','pdf')),
    phuong_phap_trich_xuat  VARCHAR(50)
);

-- Bảng 18: Chuyên gia đánh giá — [2NF]
-- Tách ra để tránh lặp thông tin khi 1 chuyên gia đánh giá nhiều bài
CREATE TABLE chuyen_gia (
    ma_chuyen_gia       SERIAL        PRIMARY KEY,
    ten_chuyen_gia      VARCHAR(200)  NOT NULL,
    chuyen_mon          VARCHAR(200),
    don_vi_cong_tac     VARCHAR(200),
    email               VARCHAR(200)  UNIQUE
);

-- Bảng 19: Đánh giá
-- [2NF] Thay ten_chuyen_gia/chuyen_mon/don_vi bằng FK ma_chuyen_gia
CREATE TABLE danh_gia (
    ma_danh_gia                 SERIAL        PRIMARY KEY,
    ma_bai_giang                INTEGER       NOT NULL
                                REFERENCES bai_giang(ma_bai_giang),
    ma_chuyen_gia               INTEGER       REFERENCES chuyen_gia(ma_chuyen_gia),
    ngay_danh_gia               TIMESTAMP,
    diem_noi_dung               FLOAT
                                CONSTRAINT chk_diem_nd CHECK (diem_noi_dung IS NULL OR diem_noi_dung BETWEEN 0 AND 10),
    diem_trinh_bay              FLOAT
                                CONSTRAINT chk_diem_tb CHECK (diem_trinh_bay IS NULL OR diem_trinh_bay BETWEEN 0 AND 10),
    diem_phu_hop_chuong_trinh   FLOAT
                                CONSTRAINT chk_diem_ph CHECK (diem_phu_hop_chuong_trinh IS NULL OR diem_phu_hop_chuong_trinh BETWEEN 0 AND 10),
    ket_qua                     BOOLEAN,
    nhan_xet                    TEXT,
    tieu_chi_chi_tiet           JSONB,
    trang_thai                  VARCHAR(20)   DEFAULT 'cho_danh_gia'
                                CHECK (trang_thai IN ('cho_danh_gia','da_danh_gia'))
);


-- ── NHÓM 7: LIÊN KẾT CHƯƠNG TRÌNH (2 bảng) ─────────────────

-- Bảng 20: Liên kết bài giảng ↔ chương trình
CREATE TABLE lien_ket_bai_chuong_trinh (
    ma_lien_ket         SERIAL        PRIMARY KEY,
    ma_bai_giang        INTEGER       NOT NULL REFERENCES bai_giang(ma_bai_giang),
    ma_noi_dung         CHAR(5)       REFERENCES noi_dung(ma_noi_dung),
    ma_yccd             CHAR(5)       REFERENCES yeu_cau_can_dat(ma_yccd),
    kieu_lien_ket       VARCHAR(20)   CHECK (kieu_lien_ket IN ('tu_dong','thu_cong')),
    diem_phu_hop        FLOAT
                        CONSTRAINT chk_diem_lkb CHECK (diem_phu_hop IS NULL OR diem_phu_hop BETWEEN 0 AND 1),
    ly_do               TEXT,
    ngay_tao            TIMESTAMP     DEFAULT NOW(),
    CONSTRAINT uq_lkb   UNIQUE (ma_bai_giang, ma_noi_dung, ma_yccd)
);
CREATE INDEX idx_lkb_bai ON lien_ket_bai_chuong_trinh(ma_bai_giang);
CREATE INDEX idx_lkb_nd  ON lien_ket_bai_chuong_trinh(ma_noi_dung);

-- Bảng 21: Liên kết trang ↔ chương trình
CREATE TABLE lien_ket_trang_chuong_trinh (
    ma_lien_ket         SERIAL        PRIMARY KEY,
    ma_trang            INTEGER       NOT NULL REFERENCES trang(ma_trang),
    ma_noi_dung         CHAR(5)       REFERENCES noi_dung(ma_noi_dung),
    ma_yccd             CHAR(5)       REFERENCES yeu_cau_can_dat(ma_yccd),
    kieu_lien_ket       VARCHAR(20)   CHECK (kieu_lien_ket IN ('tu_dong','thu_cong')),
    diem_phu_hop        FLOAT
                        CONSTRAINT chk_diem_lkt CHECK (diem_phu_hop IS NULL OR diem_phu_hop BETWEEN 0 AND 1),
    CONSTRAINT uq_lkt   UNIQUE (ma_trang, ma_noi_dung, ma_yccd)
);
CREATE INDEX idx_lkt_trang ON lien_ket_trang_chuong_trinh(ma_trang);


-- ── NHÓM 8: LOG (1 bảng) ────────────────────────────────────

-- Bảng 22: Lịch sử nhập
CREATE TABLE lich_su_nhap (
    ma_nhap             SERIAL        PRIMARY KEY,
    thoi_diem_bat_dau   TIMESTAMP     DEFAULT NOW(),
    thoi_diem_ket_thuc  TIMESTAMP,
    nguon_goc           VARCHAR(20)
                        CHECK (nguon_goc IN ('thu_thap_web','ai_tao_sinh','thu_cong')),
    tong_so_tep         INTEGER       DEFAULT 0,
    so_thanh_cong       INTEGER       DEFAULT 0,
    so_bo_qua           INTEGER       DEFAULT 0,
    so_that_bai         INTEGER       DEFAULT 0,
    bao_cao_json        JSONB
);


-- ── VIEWS ───────────────────────────────────────────────────

-- View: Thông tin trang đầy đủ cho frontend
CREATE VIEW v_trang_day_du AS
SELECT
    t.ma_trang,
    t.ma_bai_giang,
    t.so_thu_tu,
    t.tieu_de,
    t.noi_dung_van_ban,
    t.noi_dung_markdown,
    t.loai_trang,
    t.duong_dan_anh,
    t.mo_ta_gemini,
    t.slug_url,
    h.chu_de_trang,
    h.noi_dung_trang,
    b.tieu_de     AS tieu_de_bai,
    b.nguon_goc,
    b.mon_hoc,
    b.khoi_lop
FROM trang t
LEFT JOIN ho_so_trang h ON h.ma_trang      = t.ma_trang
LEFT JOIN bai_giang   b ON b.ma_bai_giang  = t.ma_bai_giang;

-- View: Tìm kiếm full-text
CREATE VIEW v_tim_kiem AS
SELECT
    t.ma_trang,
    t.ma_bai_giang,
    t.so_thu_tu,
    t.tieu_de,
    b.tieu_de     AS tieu_de_bai,
    b.nguon_goc,
    t.vector_tim_kiem
FROM trang t
JOIN bai_giang b ON b.ma_bai_giang = t.ma_bai_giang;

-- View: Tra cứu bài giảng theo chương trình học
CREATE VIEW v_bai_theo_chuong_trinh AS
SELECT
    b.ma_bai_giang,
    b.tieu_de,
    b.nguon_goc,
    b.khoi_lop,
    n.ma_noi_dung,
    n.ten_noi_dung,
    c.ten_chu_de,
    y.ma_yccd,
    y.noi_dung_yccd,
    l.diem_phu_hop,
    l.kieu_lien_ket
FROM lien_ket_bai_chuong_trinh l
JOIN bai_giang            b ON b.ma_bai_giang = l.ma_bai_giang
LEFT JOIN noi_dung        n ON n.ma_noi_dung  = l.ma_noi_dung
LEFT JOIN chu_de          c ON c.ma_chu_de    = n.ma_chu_de
LEFT JOIN yeu_cau_can_dat y ON y.ma_yccd      = l.ma_yccd;
