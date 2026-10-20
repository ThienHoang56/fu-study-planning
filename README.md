# fu-study-planning

Ứng dụng desktop hỗ trợ đồng bộ và quản lý kế hoạch học tập FAP (FPT University) sử dụng Python và pywebview (WebView2).

## Tính năng chính
- Tự động đồng bộ và parse dữ liệu lịch học cả kỳ từ FAP.
- Giao diện trực quan hiển thị danh sách môn học, số buổi học, slot, phòng học và giảng viên.
- Lưu trữ cục bộ dữ liệu học kỳ (`fap_full_semester.json`).

## Cài đặt & Khởi chạy

### Yêu cầu
- Python 3.10+
- Microsoft Edge WebView2 Runtime (có sẵn trên Windows 10/11)

### Cài đặt thư viện
```bash
pip install pywebview beautifulsoup4
```

### Chạy ứng dụng
```bash
python main.py
```
