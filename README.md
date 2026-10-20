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

### Cài đặt môi trường ảo (venv) & Thư viện

**Trên Windows (PowerShell / Command Prompt):**
```bash
# 1. Tạo môi trường ảo
python -m venv .venv

# 2. Kích hoạt môi trường ảo
# Trên PowerShell:
.\.venv\Scripts\Activate.ps1
# Hoặc trên Command Prompt (cmd):
.\.venv\Scripts\activate.bat

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### Chạy ứng dụng
Sau khi đã kích hoạt môi trường ảo:
```bash
python main.py
```
Hoặc chạy trực tiếp qua Python của môi trường ảo:
```bash
.\.venv\Scripts\python.exe main.py
```
