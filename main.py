"""
Module: main.py
Description: Desktop Application Entry Point and Native WebView2 Lifecycle Controller.
Architecture: Decoupled Controller pattern bridging Python logic with the Chromium frontend.
"""

import webview
import json
import os
import sys
import threading
from pipeline import FAPSyncPipeline

# Cấu hình UTF-8 cho luồng xuất dữ liệu trên môi trường Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Định nghĩa các đường dẫn tài nguyên tĩnh và cơ sở dữ liệu cục bộ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML = os.path.join(BASE_DIR, "index.html")
FULL_SCHEDULE_JSON = os.path.join(BASE_DIR, "fap_full_semester.json")
PROFILE_DIR = os.path.join(BASE_DIR, "webview_profile")

main_window = None
popup_window = None


class AppAPI:
    """
    Controller API xử lý các yêu cầu gọi từ giao diện người dùng (JavaScript Bridge).
    """

    def check_existing_data(self):
        """
        Mục đích: Kiểm tra và nạp dữ liệu lịch học cả kỳ đã được đồng bộ từ trước.
        Trả về:
            Dict chứa cờ has_data và toàn bộ payload dữ liệu (nếu có).
        """
        if os.path.exists(FULL_SCHEDULE_JSON):
            try:
                with open(FULL_SCHEDULE_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {"has_data": True, "data": data}
            except Exception as e:
                print(f"[ERROR] Khong the doc du lieu tu tep JSON: {e}")
        return {"has_data": False}

    def login_and_sync(self):
        """
        Mục đích: Kích hoạt luồng đồng bộ thời khóa biểu FAP thông qua cửa sổ popup WebView.
        Cơ chế: Chạy pipeline bất đồng bộ trong background thread để không gây nghẽn giao diện.
        """
        global popup_window, main_window
        print("[INFO] Khoi tao cua so xac thuc FAP...")

        try:
            main_window.evaluate_js("updateSyncStatus('Dang mo cua so FAP de ket noi...');")
        except Exception:
            pass

        # Mở cửa sổ popup WebView điều hướng thẳng vào trang Attendance
        popup_window = webview.create_window(
            title="FAP Sync - Dong bo lich hoc hoc ky",
            url="https://fap.fpt.edu.vn/Report/Attendance",
            width=900,
            height=680
        )

        # Chạy pipeline trong luồng riêng biệt (Daemon Thread)
        threading.Thread(target=self._run_pipeline_worker, args=(popup_window,), daemon=True).start()
        return {"success": True, "message": "Pipeline da khoi chay."}

    def _run_pipeline_worker(self, popup):
        """
        Thực thi tiến trình nền của FAPSyncPipeline và gửi dữ liệu chuẩn hóa về UI.
        """
        global main_window

        def on_progress(message: str):
            try:
                escaped = message.replace("'", "\\'").replace("\n", " ")
                main_window.evaluate_js(f"updateSyncStatus('{escaped}');")
            except Exception:
                pass

        # Khởi tạo pipeline và thực thi
        pipeline = FAPSyncPipeline(output_file=FULL_SCHEDULE_JSON)
        result = pipeline.execute(popup, progress_cb=on_progress)

        if result:
            clean_json = json.dumps(result, ensure_ascii=False)
            try:
                main_window.evaluate_js(f"renderFullSemester({clean_json});")
            except Exception as e:
                print(f"[ERROR] Khong the gui du lieu sang giao dien: {e}")

        # Tự động giải phóng cửa sổ popup sau khi pipeline kết thúc
        try:
            popup.destroy()
            print("[INFO] Cua so xac thuc da duoc dong an toan.")
        except Exception:
            pass


def main():
    """
    Điểm khởi tạo ứng dụng: Chuẩn bị thư mục profile và nạp cửa sổ giao diện chính.
    """
    global main_window
    os.makedirs(PROFILE_DIR, exist_ok=True)

    api = AppAPI()
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html_content = f.read()

    main_window = webview.create_window(
        title="FU Study Planning",
        html=html_content,
        width=1280,
        height=850,
        js_api=api
    )

    # Sử dụng profile Chromium chung để lưu trữ cookies phiên làm việc an toàn
    webview.start(private_mode=False, storage_path=PROFILE_DIR)


if __name__ == "__main__":
    main()
