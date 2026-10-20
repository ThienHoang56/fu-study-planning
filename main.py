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
FLM_COURSES_JSON = os.path.join(BASE_DIR, "flm_courses.json")
PROFILE_DIR = os.path.join(BASE_DIR, "webview_profile")

main_window = None
popup_window = None


flm_sync_running = False


class AppAPI:
    """
    Controller API xử lý các yêu cầu gọi từ giao diện người dùng (JavaScript Bridge).
    """

    def check_existing_data(self):
        """
        Mục đích: Kiểm tra và nạp dữ liệu lịch học cả kỳ (FAP) và dữ liệu đề cương (FLM).
        """
        response = {"has_data": False, "has_flm": False}
        if os.path.exists(FULL_SCHEDULE_JSON):
            try:
                with open(FULL_SCHEDULE_JSON, "r", encoding="utf-8") as f:
                    response["has_data"] = True
                    response["data"] = json.load(f)
            except Exception as e:
                print(f"[ERROR] Khong the doc du lieu tu tep FAP JSON: {e}")

        if os.path.exists(FLM_COURSES_JSON):
            try:
                with open(FLM_COURSES_JSON, "r", encoding="utf-8") as f:
                    response["has_flm"] = True
                    response["flm_data"] = json.load(f)
            except Exception as e:
                print(f"[ERROR] Khong the doc du lieu tu tep FLM JSON: {e}")

        return response

    def login_and_sync(self):
        """
        Mục đích: Kích hoạt luồng đồng bộ thời khóa biểu FAP thông qua cửa sổ popup WebView.
        """
        global popup_window, main_window
        print("[INFO] Khoi tao cua so xac thuc FAP...")

        try:
            main_window.evaluate_js("updateSyncStatus('Dang mo cua so FAP de ket noi...');")
        except Exception:
            pass

        popup_window = webview.create_window(
            title="FAP Sync - Dong bo lich hoc hoc ky",
            url="https://fap.fpt.edu.vn/Report/Attendance",
            width=900,
            height=680
        )

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

        pipeline = FAPSyncPipeline(output_file=FULL_SCHEDULE_JSON)
        result = pipeline.execute(popup, progress_cb=on_progress)

        if result:
            clean_json = json.dumps(result, ensure_ascii=False)
            try:
                main_window.evaluate_js(f"renderFullSemester({clean_json});")
            except Exception as e:
                print(f"[ERROR] Khong the gui du lieu sang giao dien: {e}")

        try:
            popup.destroy()
            print("[INFO] Cua so xac thuc FAP da duoc dong an toan.")
        except Exception:
            pass

    def sync_flm(self):
        """
        Mục đích: Kích hoạt luồng đồng bộ Đề cương & Cột điểm FLM theo các mã môn từ FAP.
        Cơ chế: Chạy Zero-DOM FLMSyncPipeline trong background daemon thread.
        """
        global popup_window, main_window, flm_sync_running
        if flm_sync_running:
            return {"success": False, "message": "Tiến trình đồng bộ FLM đang chạy, vui lòng chờ."}

        print("[INFO] Khoi tao cua so xac thuc FLM...")

        course_codes = []
        if os.path.exists(FULL_SCHEDULE_JSON):
            try:
                with open(FULL_SCHEDULE_JSON, "r", encoding="utf-8") as f:
                    fap_data = json.load(f)
                    for item in fap_data.get("courses", {}).values():
                        code = item.get("short_name", "").strip()
                        if code and code not in course_codes:
                            course_codes.append(code)
            except Exception as e:
                print(f"[ERROR] Khong the doc ma mon tu FAP: {e}")

        if not course_codes:
            return {"success": False, "message": "Chua co danh sach mon tu FAP. Vui long dong bo FAP truoc."}

        flm_sync_running = True
        try:
            main_window.evaluate_js("updateFLMSyncStatus('Dang mo cua so FLM de ket noi...');")
        except Exception:
            pass

        from flm_pipeline import FLMSyncPipeline

        popup_window = webview.create_window(
            title="FLM Sync - Dong bo De cuong & Cot diem",
            url="https://flm.fpt.edu.vn/Login",
            width=950,
            height=700
        )

        threading.Thread(target=self._run_flm_pipeline_worker, args=(popup_window, course_codes), daemon=True).start()
        return {"success": True, "message": "FLM Pipeline da khoi chay."}

    def _run_flm_pipeline_worker(self, popup, course_codes):
        """
        Thực thi tiến trình nền của FLMSyncPipeline và gửi dữ liệu chuẩn hóa về UI.
        """
        global main_window, flm_sync_running
        from flm_pipeline import FLMSyncPipeline

        def on_progress(message: str):
            try:
                escaped = message.replace("'", "\\'").replace("\n", " ")
                main_window.evaluate_js(f"updateFLMSyncStatus('{escaped}');")
            except Exception:
                pass

        try:
            pipeline = FLMSyncPipeline(output_file=FLM_COURSES_JSON, course_codes=course_codes)
            result = pipeline.execute(popup, progress_cb=on_progress)

            if result:
                clean_json = json.dumps(result, ensure_ascii=False)
                try:
                    main_window.evaluate_js(f"renderFLMData({clean_json});")
                except Exception as e:
                    print(f"[ERROR] Khong the gui du lieu FLM sang giao dien: {e}")
        finally:
            flm_sync_running = False
            try:
                popup.destroy()
                print("[INFO] Cua so xac thuc FLM da duoc dong an toan.")
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
