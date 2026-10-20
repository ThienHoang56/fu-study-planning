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
        Mục đích: Kích hoạt luồng đồng bộ HỢP NHẤT TOÀN DIỆN (FAP + FLM) qua 1 cửa sổ popup duy nhất.
        """
        global popup_window, main_window, flm_sync_running
        if flm_sync_running:
            return {"success": False, "message": "Tiến trình đồng bộ đang chạy, vui lòng chờ."}

        print("[INFO] Khoi tao cua so xac thuc dong bo hop nhat (FAP + FLM)...")

        try:
            main_window.evaluate_js("updateSyncStatus('Dang mo cua so ket noi FAP...');")
        except Exception:
            pass

        popup_window = webview.create_window(
            title="FU Sync - Dong bo toan dien FAP & FLM",
            url="https://fap.fpt.edu.vn/Report/Attendance",
            width=950,
            height=700
        )

        threading.Thread(target=self._run_unified_worker, args=(popup_window,), daemon=True).start()
        return {"success": True, "message": "Pipeline hop nhat da khoi chay."}

    def _run_unified_worker(self, popup):
        """
        Thực thi tiến trình nền tuần tự 2 Phase:
          1. Phase 1: Đồng bộ lịch học cả kỳ từ FAP
          2. Phase 2: Tự động chuyển tiếp sang FLM đồng bộ Đề cương & Cột điểm
        """
        global main_window, flm_sync_running
        flm_sync_running = True

        def on_progress(message: str):
            try:
                escaped = message.replace("'", "\\'").replace("\n", " ")
                main_window.evaluate_js(f"updateSyncStatus('{escaped}');")
                main_window.evaluate_js(f"updateFLMSyncStatus('{escaped}');")
            except Exception:
                pass

        try:
            # PHASE 1: FAP SYNC
            on_progress("FAP (1/2): Kiem tra phien lam viec va lay lich hoc ca ky...")
            pipeline_fap = FAPSyncPipeline(output_file=FULL_SCHEDULE_JSON)
            result_fap = pipeline_fap.execute(popup, progress_cb=on_progress)

            if not result_fap or not result_fap.get("courses"):
                on_progress("Loi: Khong lay duoc du lieu FAP.")
                return

            clean_fap_json = json.dumps(result_fap, ensure_ascii=False)
            try:
                main_window.evaluate_js(f"renderFullSemester({clean_fap_json});")
            except Exception as e:
                print(f"[ERROR] Khong the gui du lieu FAP sang UI: {e}")

            course_codes = [c.get("short_name", "").strip() for c in result_fap.get("courses", {}).values() if c.get("short_name")]

            # PHASE 2: FLM SYNC (CHUYỂN TIẾP TRÊN CÙNG CỬA SỔ POPUP)
            on_progress("FAP hoan tat! Tu dong chuyen tiep sang FLM de lay De cuong & Cot diem...")
            time.sleep(1.5)

            from flm_pipeline import FLMSyncPipeline
            pipeline_flm = FLMSyncPipeline(output_file=FLM_COURSES_JSON, course_codes=course_codes)
            result_flm = pipeline_flm.execute(popup, progress_cb=on_progress)

            if result_flm:
                clean_flm_json = json.dumps(result_flm, ensure_ascii=False)
                try:
                    main_window.evaluate_js(f"renderFLMData({clean_flm_json});")
                except Exception as e:
                    print(f"[ERROR] Khong the gui du lieu FLM sang UI: {e}")

            on_progress("Dong bo thanh cong toan bo FAP & FLM!")
        finally:
            flm_sync_running = False
            try:
                popup.destroy()
                print("[INFO] Cua so popup da duoc dong an toan.")
            except Exception:
                pass

    def sync_flm(self):
        """
        Mục đích: Đồng bộ riêng lẻ FLM (khi người dùng chỉ muốn lấy lại dữ liệu FLM).
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
        Thực thi riêng lẻ tiến trình nền của FLMSyncPipeline.
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
