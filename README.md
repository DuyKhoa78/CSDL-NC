# Kho Bài Giảng Điện Tử(CSDL-NC)

Hệ thống quản lý kho bài giảng Tin học THPT theo chương trình GDPT 2018, sử dụng **PostgreSQL** + **Streamlit**.

---

## Yêu cầu hệ thống

| Phần mềm | Phiên bản |
|---|---|
| Python | 3.10+ |
| PostgreSQL | 14+ |
| pip | mới nhất |

---

## Cài đặt và chạy

### Bước 1 — Clone mã nguồn

```bash
git clone https://github.com/DuyKhoa78/CSDL-NC.git
cd CSDL-NC
```

### Bước 2 — Cài thư viện Python

```bash
pip install streamlit psycopg2-binary python-pptx python-dotenv
```

### Bước 3 — Tạo cơ sở dữ liệu PostgreSQL

Mở **pgAdmin** hoặc **psql**, chạy lệnh sau để tạo DB:

```sql
CREATE DATABASE kho_bai_giang;
```

Sau đó import schema:

```bash
psql -U postgres -d kho_bai_giang -f unified_system/schema.sql
```

### Bước 4 — Cấu hình kết nối DB

Tạo file `unified_system/.env` với nội dung sau:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kho_bai_giang
DB_USER=postgres
DB_PASSWORD=your_password_here
```

> hay `your_password_here` bằng mật khẩu PostgreSQL của bạn.

### Bước 5 — Chạy ứng dụng

```bash
streamlit run unified_system/app.py
```

Mở trình duyệt tại: **http://localhost:8501**

---

## Cấu trúc thư mục

```
CSDL-NC/
├── unified_system/          # Hệ thống chính
│   ├── app.py               # Giao diện Streamlit
│   ├── schema.sql           # Schema PostgreSQL (22 bảng)
│   ├── db.py                # Kết nối database
│   ├── importers/
│   │   ├── file_router.py   # Tự động nhận dạng PPTX/PDF
│   │   ├── importer_pptx.py # Nhập file PowerPoint
│   │   └── importer_pdf.py  # Nhập file PDF
│   ├── crawling/
│   │   └── crawling_adapter.py  # Thu thập bài giảng từ web
│   ├── curriculum/
│   │   └── matcher.py       # Gắn nhãn theo GDPT 2018
│   └── migrate/             # Script chuyển đổi dữ liệu cũ
└── Crawling/                # Công cụ crawl PPTX
    ├── crawling.py
    └── download_only.py
```

---

## Cách sử dụng

### Nhập bài giảng thủ công (qua giao diện)
1. Mở app → Tab **"Nhập Liệu"**
2. Chọn lớp, chủ đề, nội dung, yêu cầu cần đạt
3. Upload file `.pptx`
4. Bấm **"Đưa vào kho dữ liệu"**

### Nhập hàng loạt (qua dòng lệnh)
```bash
# Nhập 1 file cụ thể
python unified_system/importers/file_router.py --file "đường_dẫn/file.pptx"

# Nhập cả thư mục
python unified_system/importers/file_router.py --dir "đường_dẫn/thư_mục"
```

### Thu thập bài giảng từ web
```bash
python Crawling/crawling.py
```

---

## Cơ sở dữ liệu

Hệ thống sử dụng **22 bảng** đã chuẩn hóa theo 1NF · 2NF · 3NF · BCNF:

| Nhóm | Bảng | Mô tả |
|---|---|---|
| Chương trình học | `chu_de`, `noi_dung`, `yeu_cau_can_dat` | GDPT 2018 Tin học lớp 10–12 |
| Bài giảng | `bai_giang`, `trang`, `khoi_noi_dung` | Thông tin file + nội dung slide |
| Văn bản | `doan_van_trang`, `bang_du_lieu_trang` | Đoạn văn, bảng dữ liệu |
| Từ khóa | `bang_tu_vung`, `tu_khoa_trang` | Từ điển + từ khóa từng trang |
| Liên kết | `lien_ket_bai_chuong_trinh` | Gắn bài giảng với chương trình |
| Tổng hợp | `ho_so_bai_giang`, `chu_de_bai_giang` | Hồ sơ bài giảng |

---

## Thư viện cần thiết

```
streamlit
psycopg2-binary
python-pptx
python-dotenv
```

Cài thêm nếu muốn nhập PDF:
```bash
pip install pdfminer.six pdf2image google-generativeai
```

---

> 💡 **Lưu ý**: File `.env` chứa mật khẩu DB đã được loại khỏi Git. Mỗi máy cần tạo file `.env` riêng theo hướng dẫn ở Bước 4.
