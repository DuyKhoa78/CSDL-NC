"""
Script 01: Migrate du lieu tu PPT.sql sang PostgreSQL kho_bai_giang
Migrate: chu_de, noi_dung, yeu_cau_can_dat
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DB = dict(
    host=os.getenv("DB_HOST","localhost"),
    port=os.getenv("DB_PORT","5432"),
    dbname=os.getenv("DB_NAME","kho_bai_giang"),
    user=os.getenv("DB_USER","postgres"),
    password=os.getenv("DB_PASSWORD","123456"),
)

# ── Toàn bộ dữ liệu từ PPT.sql ──────────────────────────────

CHU_DE = [
    # Lớp 8
    ('C08A','Lớp 8','Máy tính và cộng đồng'),
    ('C08C','Lớp 8','Tổ chức lưu trữ, tìm kiếm và trao đổi thông tin'),
    ('C08D','Lớp 8','Đạo đức, pháp luật và văn hoá trong môi trường số'),
    ('C08E','Lớp 8','Ứng dụng tin học'),
    ('C08F','Lớp 8','Giải quyết vấn đề với sự trợ giúp của máy tính'),
    ('C08G','Lớp 8','Hướng nghiệp với tin học'),
    # Lớp 9
    ('C09A','Lớp 9','Máy tính và cộng đồng'),
    ('C09C','Lớp 9','Tổ chức lưu trữ, tìm kiếm và trao đổi thông tin'),
    ('C09D','Lớp 9','Đạo đức, pháp luật và văn hoá trong môi trường số'),
    ('C09E','Lớp 9','Ứng dụng tin học'),
    ('C09F','Lớp 9','Giải quyết vấn đề với sự trợ giúp của máy tính'),
    ('C09G','Lớp 9','Hướng nghiệp với tin học'),
    # Lớp 10
    ('C10A','Lớp 10','Máy tính và xã hội tri thức'),
    ('C10B','Lớp 10','Mạng máy tính và Internet'),
    ('C10C','Lớp 10','Tổ chức lưu trữ, tìm kiếm và trao đổi thông tin'),
    ('C10D','Lớp 10','Đạo đức, pháp luật và văn hoá trong môi trường số'),
    ('C10E','Lớp 10','Ứng dụng tin học'),
    ('C10F','Lớp 10','Giải quyết vấn đề với sự trợ giúp của máy tính'),
    ('C10G','Lớp 10','Hướng nghiệp với tin học'),
    # Lớp 11
    ('C11A','Lớp 11','Máy tính và xã hội tri thức'),
    ('C11C','Lớp 11','Tổ chức lưu trữ, tìm kiếm và trao đổi thông tin'),
    ('C11D','Lớp 11','Đạo đức, pháp luật và văn hoá trong môi trường số'),
    ('C11E','Lớp 11','Ứng dụng tin học'),
    ('C11F','Lớp 11','Giải quyết vấn đề với sự trợ giúp của máy tính'),
    ('C11G','Lớp 11','Hướng nghiệp với tin học'),
]

NOI_DUNG = [
    # Lớp 8
    ('N08A1','Sơ lược về lịch sử phát triển máy tính','C08A'),
    ('N08C1','Đặc điểm của thông tin trong môi trường số','C08C'),
    ('N08C2','Thông tin với giải quyết vấn đề','C08C'),
    ('N08D1','Đạo đức và văn hoá trong sử dụng công nghệ kĩ thuật số','C08D'),
    ('N08E1','Xử lí và trực quan hoá dữ liệu bằng bảng tính điện tử','C08E'),
    ('N08E2','Soạn thảo văn bản và phần mềm trình chiếu nâng cao','C08E'),
    ('N08E3','Làm quen với phần mềm chỉnh sửa ảnh','C08E'),
    ('N08F1','Lập trình trực quan','C08F'),
    ('N08G1','Tin học và ngành nghề','C08G'),
    # Lớp 9
    ('N09A1','Vai trò của máy tính trong đời sống','C09A'),
    ('N09C1','Đánh giá chất lượng thông tin trong giải quyết vấn đề','C09C'),
    ('N09D1','Một số vấn đề pháp lí về sử dụng dịch vụ Internet','C09D'),
    ('N09E1','Phần mềm mô phỏng và khám phá tri thức','C09E'),
    ('N09E2','Trình bày thông tin trong trao đổi và hợp tác','C09E'),
    ('N09E3','Sử dụng bảng tính điện tử nâng cao','C09E'),
    ('N09E4','Làm quen với phần mềm làm video','C09E'),
    ('N09F1','Giải bài toán bằng máy tính','C09F'),
    ('N09G1','Tin học và định hướng nghề nghiệp','C09G'),
    # Lớp 10
    ('N10A1','Tin học và xử lí thông tin; Thế giới thiết bị số','C10A'),
    ('N10A2','Biểu diễn thông tin (CS)','C10A'),
    ('N10B1','Internet hôm nay và ngày mai','C10B'),
    ('N10C1','Sử dụng dịch vụ web và tự bảo vệ khi tham gia mạng','C10C'),
    ('N10D1','Nghĩa vụ tuân thủ pháp lí trong môi trường số','C10D'),
    ('N10E1','Phần mềm thiết kế đồ hoạ','C10E'),
    ('N10F1','Lập trình cơ bản','C10F'),
    ('N10G1','Giới thiệu nhóm nghề thiết kế và lập trình','C10G'),
    # Lớp 11
    ('N11A1','Hệ điều hành và phần mềm ứng dụng','C11A'),
    ('N11A2','Thế giới thiết bị số','C11A'),
    ('N11C1','Tìm kiếm và trao đổi thông tin trên mạng','C11C'),
    ('N11D1','Ứng xử văn hoá và an toàn trên mạng','C11D'),
    ('N11E1','Phần mềm chỉnh sửa ảnh và làm video','C11E'),
    ('N11F1','Giới thiệu các hệ Cơ sở dữ liệu','C11F'),
    ('N11F2','Thực hành tạo và khai thác Cơ sở dữ liệu','C11F'),
    ('N11F3','Kĩ thuật lập trình','C11F'),
    ('N11G1','Giới thiệu nghề Quản trị cơ sở dữ liệu','C11G'),
]

YCCD = [
    # Lớp 8
    ('Y8A01','Trình bày được sơ lược lịch sử phát triển máy tính.','N08A1'),
    ('Y8A02','Nêu được ví dụ cho thấy sự phát triển máy tính đã đem đến những thay đổi lớn lao cho xã hội loài người.','N08A1'),
    ('Y8C01','Nêu được các đặc điểm của thông tin số: đa dạng, thu thập nhanh nhiều, dung lượng khổng lồ, có tính bản quyền, độ tin cậy khác nhau...','N08C1'),
    ('Y8C02','Trình bày được tầm quan trọng của việc biết khai thác các nguồn thông tin đáng tin cậy.','N08C1'),
    ('Y8C03','Sử dụng được công cụ tìm kiếm, xử lí và trao đổi thông tin trong môi trường số.','N08C1'),
    ('Y8C04','Chủ động tìm kiếm được thông tin để thực hiện nhiệm vụ.','N08C2'),
    ('Y8C05','Đánh giá được lợi ích của thông tin tìm được trong giải quyết vấn đề.','N08C2'),
    ('Y8D01','Nhận biết và giải thích được một số biểu hiện vi phạm đạo đức và pháp luật, biểu hiện thiếu văn hoá khi sử dụng công nghệ kĩ thuật số.','N08D1'),
    ('Y8D02','Bảo đảm được các sản phẩm số do bản thân tạo ra thể hiện được đạo đức, tính văn hoá và không vi phạm pháp luật.','N08D1'),
    ('Y8E01','Thực hiện được các thao tác tạo biểu đồ, lọc và sắp xếp dữ liệu. Nêu được tình huống thực tế cần sử dụng.','N08E1'),
    ('Y8E02','Giải thích được sự khác nhau giữa địa chỉ tương đối và địa chỉ tuyệt đối của một ô tính.','N08E1'),
    ('Y8E03','Giải thích được sự thay đổi địa chỉ tương đối trong công thức khi sao chép công thức.','N08E1'),
    ('Y8E04','Sao chép được dữ liệu từ các tệp văn bản, trang trình chiếu sang trang tính.','N08E1'),
    ('Y8E05','Sử dụng được phần mềm bảng tính trợ giúp giải quyết bài toán thực tế.','N08E1'),
    ('Y8E06','Thực hiện thao tác: chèn thêm, xoá bỏ, co dãn hình ảnh, vẽ hình đồ hoạ, tạo danh sách liệt kê, đánh số trang, thêm đầu trang/chân trang.','N08E2'),
    ('Y8E07','Tạo được một số sản phẩm là văn bản có tính thẩm mĩ phục vụ nhu cầu thực tế.','N08E2'),
    ('Y8E08','Chọn đặt màu sắc/cỡ chữ hài hoà; đưa đường dẫn video vào trang chiếu; tạo bản mẫu; tạo sản phẩm số phục vụ học tập, giao lưu.','N08E2'),
    ('Y8E09','Nêu được một vài chức năng chính và thực hiện được một số thao tác cơ bản với phần mềm chỉnh sửa ảnh.','N08E3'),
    ('Y8E10','Tạo được một vài sản phẩm số đơn giản đáp ứng nhu cầu cá nhân, gia đình, trường học và địa phương.','N08E3'),
    ('Y8F01','Mô tả được kịch bản đơn giản dưới dạng thuật toán và tạo được một chương trình đơn giản.','N08F1'),
    ('Y8F02','Hiểu được chương trình là dãy các lệnh điều khiển máy tính thực hiện một thuật toán.','N08F1'),
    ('Y8F03','Thể hiện được cấu trúc tuần tự, rẽ nhánh và lặp ở chương trình trong môi trường lập trình trực quan.','N08F1'),
    ('Y8F04','Nêu được khái niệm hằng, biến, kiểu dữ liệu, biểu thức và sử dụng được các khái niệm này.','N08F1'),
    ('Y8F05','Chạy thử, tìm lỗi và sửa được lỗi cho chương trình.','N08F1'),
    ('Y8G01','Nêu được một số nghề nghiệp mà ứng dụng tin học sẽ làm tăng hiệu quả công việc.','N08G1'),
    ('Y8G02','Nêu được tên một số nghề thuộc lĩnh vực tin học và một số nghề liên quan đến ứng dụng tin học.','N08G1'),
    ('Y8G03','Nhận thức và trình bày được vấn đề bình đẳng giới trong việc sử dụng máy tính và trong ứng dụng tin học, nêu được ví dụ minh hoạ.','N08G1'),
    # Lớp 9
    ('Y9A01','Nhận biết sự có mặt của thiết bị có gắn bộ xử lí thông tin ở khắp nơi, nêu ví dụ.','N09A1'),
    ('Y9A02','Nêu được khả năng của máy tính và chỉ ra một số ứng dụng thực tế trong đời sống.','N09A1'),
    ('Y9A03','Giải thích tác động của công nghệ thông tin lên giáo dục và xã hội qua ví dụ.','N09A1'),
    ('Y9C01','Giải thích được sự cần thiết phải quan tâm đến chất lượng thông tin khi tìm kiếm, trao đổi.','N09C1'),
    ('Y9C02','Giải thích được tính mới, chính xác, đầy đủ, sử dụng được của thông tin.','N09C1'),
    ('Y9D01','Trình bày được một số tác động tiêu cực của công nghệ số đối với đời sống, xã hội.','N09D1'),
    ('Y9D02','Nêu một số nội dung liên quan đến luật CNTT, nghị định dịch vụ Internet, bản quyền.','N09D1'),
    ('Y9D03','Nêu một số hành vi vi phạm pháp luật, trái đạo đức, thiếu văn hoá trong môi trường số.','N09D1'),
    ('Y9E01','Nêu được ví dụ phần mềm mô phỏng và kiến thức thu nhận từ việc khai thác chúng.','N09E1'),
    ('Y9E02','Nhận biết mô phỏng thế giới thực nhờ máy tính giúp khám phá tri thức và giải quyết vấn đề.','N09E1'),
    ('Y9E03','Biết khả năng đính kèm văn bản, ảnh, video, trang tính vào sơ đồ tư duy; sử dụng hợp lí.','N09E2'),
    ('Y9E04','Sử dụng được bài trình chiếu và sơ đồ tư duy trong trao đổi thông tin và hợp tác.','N09E2'),
    ('Y9E05','Thực hiện dự án sử dụng bảng tính điện tử giải quyết bài toán quản lí (tài chính, dân số...).','N09E3'),
    ('Y9E06','Nêu một số chức năng và thực hiện thao tác cơ bản trong sử dụng phần mềm làm video.','N09E4'),
    ('Y9E07','Tạo được một vài đoạn video đáp ứng nhu cầu cuộc sống, gia đình, trường học.','N09E4'),
    ('Y9F01','Trình bày quá trình giải quyết vấn đề và mô tả giải pháp dưới dạng thuật toán (sơ đồ khối).','N09F1'),
    ('Y9F02','Sử dụng được cấu trúc tuần tự, rẽ nhánh, lặp trong mô tả thuật toán.','N09F1'),
    ('Y9F03','Giải thích trong quy trình giải quyết vấn đề có những bước có thể giao cho máy tính.','N09F1'),
    ('Y9F04','Giải thích khái niệm bài toán trong tin học và khái niệm chương trình máy tính.','N09F1'),
    ('Y9F05','Nêu được quy trình con người giao bài toán cho máy tính giải quyết.','N09F1'),
    ('Y9G01','Trình bày công việc đặc thù và sản phẩm chính của người làm tin học trong ít nhất 3 nhóm nghề.','N09G1'),
    ('Y9G02','Nêu và giải thích được ý kiến cá nhân (thích hay không thích) về một nhóm nghề nào đó.','N09G1'),
    ('Y9G03','Nhận biết đặc trưng cơ bản của nhóm nghề hướng Tin học ứng dụng và Khoa học máy tính.','N09G1'),
    ('Y9G04','Tìm hiểu được công việc ở một số doanh nghiệp, công ty có sử dụng nhân lực tin học.','N09G1'),
    ('Y9G05','Giải thích được cả nam và nữ đều có thể thích hợp với các ngành nghề trong lĩnh vực tin học.','N09G1'),
    # Lớp 10
    ('Y10A1','Nêu được đóng góp cơ bản của tin học đối với xã hội, ví dụ minh hoạ.','N10A1'),
    ('Y10A2','Nhận biết và khởi động được thiết bị số thông dụng, sử dụng ứng dụng cơ bản.','N10A1'),
    ('Y10A3','Thực hiện được các phép tính cơ bản AND, OR, NOT, ứng dụng hệ nhị phân.','N10A2'),
    ('Y10A4','Giải thích được sơ lược về chức năng của bảng mã chuẩn quốc tế.','N10A2'),
    ('Y10B1','Trình bày thay đổi về phương thức học tập, làm việc nhờ mạng máy tính.','N10B1'),
    ('Y10B2','So sánh được mạng LAN và Internet; Nêu được dịch vụ đám mây, khái niệm IoT.','N10B1'),
    ('Y10C1','Sử dụng chức năng xử lí thông tin trên PC/thiết bị số, khai thác học liệu mở.','N10C1'),
    ('Y10C2','Nêu nguy cơ, tác hại và cách phòng vệ trên Internet; Biết tự bảo vệ dữ liệu.','N10C1'),
    ('Y10C3','Trình bày sơ lược về phần mềm độc hại, sử dụng công cụ ngăn ngừa và diệt.','N10C1'),
    ('Y10D1','Nêu vấn đề nảy sinh về pháp luật, đạo đức; ví dụ vi phạm bản quyền và hậu quả.','N10D1'),
    ('Y10D2','Giải thích nội dung cơ bản của Luật CNTT, Luật An ninh mạng.','N10D1'),
    ('Y10D3','Vận dụng Luật xác định tính hợp pháp của hành vi và an toàn khi chia sẻ thông tin.','N10D1'),
    ('Y10E1','Sử dụng được một số chức năng cơ bản của phần mềm thiết kế đồ hoạ.','N10E1'),
    ('Y10E2','Tạo được sản phẩm số đơn giản, thiết thực (logo, banner, áp phích, poster...).','N10E1'),
    ('Y10F1','Viết và thực hiện được chương trình có: hằng, biến, cấu trúc điều khiển, mảng.','N10F1'),
    ('Y10F2','Viết được chương trình có sử dụng chương trình con.','N10F1'),
    ('Y10F3','Đọc hiểu, kiểm thử, gỡ lỗi và viết chương trình giải quyết bài toán đơn giản.','N10F1'),
    ('Y10G1','Trình bày thông tin hướng nghiệp nhóm nghề Thiết kế và Lập trình.','N10G1'),
    ('Y10G2','Tự tìm kiếm thông tin và giao lưu để tìm hiểu các ngành nghề lĩnh vực tin học.','N10G1'),
    # Lớp 11
    ('Y11A1','Trình bày sơ lược lịch sử phát triển của hệ điều hành trên PC và thiết bị di động.','N11A1'),
    ('Y11A2','Khái quát mối quan hệ giữa phần cứng, hệ điều hành và phần mềm ứng dụng.','N11A1'),
    ('Y11A3','So sánh được phần mềm nguồn mở với phần mềm thương mại.','N11A1'),
    ('Y11A4','Kích hoạt và sử dụng chức năng cơ bản của phần mềm chạy trên Internet.','N11A1'),
    ('Y11A5','Nhận diện hình dạng và chức năng các bộ phận chính bên trong máy tính (CPU, RAM).','N11A2'),
    ('Y11A6','Nhận biết mạch logic AND, OR, NOT và tuỳ chỉnh một vài chức năng thiết bị số.','N11A2'),
    ('Y11C1','Sử dụng công cụ trực tuyến như Google Drive hay Dropbox để lưu trữ, chia sẻ tệp.','N11C1'),
    ('Y11C2','Sử dụng máy tìm kiếm và xác lập tiêu chí tìm kiếm hiệu quả.','N11C1'),
    ('Y11C3','Biết cách phân loại và đánh dấu các email.','N11C1'),
    ('Y11D1','Nêu một số dạng lừa đảo phổ biến trên mạng và biện pháp phòng tránh.','N11D1'),
    ('Y11D2','Giao tiếp trên mạng văn minh, phù hợp với quy tắc và văn hoá ứng xử.','N11D1'),
    ('Y11E1','Thực hiện thao tác xử lí ảnh cơ bản, cắt, phóng to, thu nhỏ và tạo ảnh động.','N11E1'),
    ('Y11E2','Tạo đoạn phim, hoạt hình từ ảnh, biên tập video kết hợp âm thanh và phụ đề.','N11E1'),
    ('Y11F1','Nhận biết nhu cầu lưu trữ dữ liệu; diễn đạt khái niệm cơ sở dữ liệu, bảng, khoá.','N11F1'),
    ('Y11F2','Phân biệt kiến trúc hệ CSDL tập trung và phân tán; nêu tầm quan trọng của bảo mật.','N11F1'),
    ('Y11F3','Thực hành tạo lập CSDL, chỉ định khoá, cập nhật và thiết lập mối quan hệ.','N11F2'),
    ('Y11F4','Sử dụng truy vấn để tìm kiếm và kết xuất thông tin từ CSDL.','N11F2'),
    ('Y11F5','Viết chương trình cho các thuật toán sắp xếp và tìm kiếm cơ bản.','N11F3'),
    ('Y11F6','Kiểm thử, đánh giá độ phức tạp thời gian và sử dụng phương pháp làm mịn dần.','N11F3'),
    ('Y11G1','Trình bày thông tin hướng nghiệp nghề Quản trị cơ sở dữ liệu (yêu cầu kĩ năng, nhu cầu).','N11G1'),
    ('Y11G2','Tìm kiếm thông tin và giao lưu để tìm hiểu các ngành nghề khác trong lĩnh vực tin học.','N11G1'),
]


def main():
    print("=== Migrate PPT.sql → kho_bai_giang ===")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # chu_de
        print(f"  Inserting {len(CHU_DE)} chu_de...")
        cur.executemany(
            "INSERT INTO chu_de (ma_chu_de, khoi_lop, ten_chu_de) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            CHU_DE
        )

        # noi_dung
        print(f"  Inserting {len(NOI_DUNG)} noi_dung...")
        cur.executemany(
            "INSERT INTO noi_dung (ma_noi_dung, ten_noi_dung, ma_chu_de) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            NOI_DUNG
        )

        # yeu_cau_can_dat
        print(f"  Inserting {len(YCCD)} yeu_cau_can_dat...")
        cur.executemany(
            "INSERT INTO yeu_cau_can_dat (ma_yccd, noi_dung_yccd, ma_noi_dung) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            YCCD
        )

        conn.commit()
        print("✅ Migrate PPT.sql hoàn thành!")

        # Kiểm tra
        for tbl in ['chu_de','noi_dung','yeu_cau_can_dat']:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            print(f"   {tbl}: {cur.fetchone()[0]} bản ghi")

    except Exception as e:
        conn.rollback()
        print(f"❌ Lỗi: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
