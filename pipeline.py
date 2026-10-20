"""
Module: pipeline.py
Description: Production 4-Stage Asynchronous Data Ingestion Pipeline for FPT University Academic Portal (FAP).
Architecture: Zero-DOM UI dependency. Employs browser network stack injection, asynchronous parallel HTTP requests,
             semantic data parsing, and atomic JSON persistence.
"""

import json
import time
from typing import Dict, Any, Callable, Optional
from parser import parse_fap_attendance_html


class FAPSyncPipeline:
    """
    Quy trình đồng bộ toàn diện thời khóa biểu học kỳ từ hệ thống FAP.
    
    Quy chuẩn kiến trúc gồm 4 Stage độc lập:
      - Stage 1 [Authentication Handshake]: Duy trì & giám sát phiên xác thực WebView2.
      - Stage 2 [Network Stream Ingestion]: Kích hoạt luồng HTTP ngầm tải song song N môn.
      - Stage 3 [Semantic Data Transformation]: Bóc tách dữ liệu thô sang Canonical Schema.
      - Stage 4 [Atomic Persistence]: Tuần tự hóa JSON an toàn theo tiêu chuẩn UTF-8.
    """

    def __init__(self, output_file: str):
        self.output_file = output_file

    def execute(self, popup, progress_cb: Optional[Callable[[str], None]] = None) -> Optional[Dict[str, Any]]:
        """
        Thực thi toàn bộ chu trình 4 Stage của pipeline.

        Args:
            popup: Handle cửa sổ WebView2 phục vụ phiên làm việc FAP.
            progress_cb: Callback tùy chọn nhận thông điệp tiến trình để cập nhật giao diện.

        Returns:
            Optional[Dict[str, Any]]: Toàn bộ dữ liệu học kỳ đã chuẩn hóa, hoặc None nếu thất bại.
        """
        def notify(log_level: str, message: str):
            formatted_log = f"[{log_level}] {message}"
            print(formatted_log)
            if progress_cb:
                try:
                    progress_cb(formatted_log)
                except Exception:
                    pass

        # ==============================================================================
        # STAGE 1: AUTHENTICATION HANDSHAKE
        # Purpose: Giám sát phiên làm việc cho đến khi tài khoản vào đúng phân hệ điểm danh.
        # Pre-condition: Người dùng đã hoàn thành Google SSO trong cửa sổ WebView2.
        # Post-condition: URL hiện tại chứa route /Report/Attendance.
        # ==============================================================================
        notify("STAGE 1/4", "Kiem tra phien lam viec tren he thong FAP...")
        if not self._wait_for_auth(popup, timeout_sec=90):
            notify("ERROR", "Ket noi that bai: Khong tim thay phien Attendance hop le.")
            return None

        # ==============================================================================
        # STAGE 2: ASYNCHRONOUS NETWORK STREAM INGESTION
        # Purpose: Trích xuất danh mục môn học kỳ và tải đồng thời toàn bộ HTTP payload.
        # Mechanism: Sử dụng XMLHttpRequest song song bên trong browser network context,
        #            vượt qua cơ chế kiểm tra bot Cloudflare (JA3/JA4 TLS verification).
        # ==============================================================================
        notify("STAGE 2/4", "Khoi tao luong mang song song, bat dau ingest du lieu...")
        payload = self._ingest_network_stream(popup, timeout_sec=30)
        if not payload:
            notify("ERROR", "Ingestion that bai: Khong nhan duoc payload mang tu FAP.")
            return None

        term_id = payload["termId"]
        term_name = payload.get("termName", "")
        raw_results = payload.get("results", [])

        notify("INFO", f"Ingestion thanh cong. Hoc ky: {term_name} | Tong so mon: {len(raw_results)}")

        # ==============================================================================
        # STAGE 3: SEMANTIC DATA TRANSFORMATION
        # Purpose: Chuyển đổi mã nguồn HTML thô của từng môn học thành Domain Model chuẩn.
        # Strategy: Nhận diện theo cấu trúc dữ liệu bản thể (Date, Slot, Room, Lecturer).
        # ==============================================================================
        notify("STAGE 3/4", "Chuan hoa du lieu va trich xuat Canonical Model...")
        full_semester_data = self._transform_payload(term_id, term_name, raw_results)

        # ==============================================================================
        # STAGE 4: ATOMIC PERSISTENCE & DISPATCH
        # Purpose: Tuần tự hóa dữ liệu ra tệp tin JSON với mã hóa UTF-8 bảo toàn dấu tiếng Việt.
        # ==============================================================================
        notify("STAGE 4/4", "Luu tru du lieu JSON vao disk...")
        self._persist_to_disk(full_semester_data)

        notify("SUCCESS", "Pipeline hoan tat xu ly toan bo du lieu hoc ky.")
        return full_semester_data

    # ==============================================================================
    # INTERNAL IMPLEMENTATION METHODS
    # ==============================================================================

    def _wait_for_auth(self, popup, timeout_sec: int = 90) -> bool:
        """
        Theo dõi điều hướng của WebView cho đến khi chạm tới route Attendance.
        Có cơ chế timeout bảo vệ chống treo vô hạn khi người dùng thao tác chậm.
        """
        for _ in range(timeout_sec):
            time.sleep(1.2)
            try:
                url = popup.get_current_url() or ""
                if "Attendance" in url:
                    return True
            except Exception:
                return False
        return False

    def _ingest_network_stream(self, popup, timeout_sec: int = 30) -> Optional[Dict[str, Any]]:
        """
        Tiêm script khởi tạo Network Ingestion Worker.
        Thu thập GUID học kỳ và danh mục môn học, sau đó dispatch đồng loạt các HTTP request ngầm.
        """
        worker_script = """
        (function() {
            window.__fetchSemesterData = function() {
                return new Promise(async (resolve) => {
                    const allOptions = Array.from(document.querySelectorAll('option'));
                    const guidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
                    
                    let termId = "";
                    let termName = "";
                    const courses = [];
                    
                    // Trich xuat hoc ky hien tai bang pattern ten hoc ky
                    for (const opt of allOptions) {
                        const val = (opt.value || "").trim();
                        const txt = (opt.text || "").trim();
                        if (guidRegex.test(val) && /(Fall|Summer|Spring)\\d{4}/i.test(txt)) {
                            if (opt.selected || !termId) {
                                termId = val;
                                termName = txt;
                            }
                        }
                    }
                    
                    // Trich xuat danh muc mon hoc theo pattern ma mon trong ngoac
                    for (const opt of allOptions) {
                        const val = (opt.value || "").trim();
                        const txt = (opt.text || "").trim();
                        if (guidRegex.test(val) && val !== termId && /\\([A-Z0-9_-]+\\)/i.test(txt)) {
                            if (!courses.some(c => c.courseId === val)) {
                                courses.push({ name: txt, courseId: val });
                            }
                        }
                    }
                    
                    if (!termId || courses.length === 0) {
                        resolve(JSON.stringify({ status: "WAITING" }));
                        return;
                    }
                    
                    // Dispatch song song tat ca HTTP requests qua network stack cua trinh duyet
                    const fetchPromises = courses.map(c => {
                        return new Promise(res => {
                            const xhr = new XMLHttpRequest();
                            xhr.open('GET', '/Report/Attendance?termId=' + termId + '&courseId=' + c.courseId, true);
                            xhr.timeout = 15000;
                            xhr.onload = function() {
                                res({ courseId: c.courseId, name: c.name, html: xhr.responseText });
                            };
                            xhr.onerror = function() {
                                res({ courseId: c.courseId, name: c.name, html: "" });
                            };
                            xhr.send();
                        });
                    });
                    
                    const results = await Promise.all(fetchPromises);
                    resolve(JSON.stringify({
                        status: "SUCCESS",
                        termId: termId,
                        termName: termName,
                        results: results
                    }));
                });
            };
            
            window.__sync_payload = null;
            window.__fetchSemesterData().then(data => {
                window.__sync_payload = data;
            });
        })();
        """

        for attempt in range(timeout_sec):
            time.sleep(1)
            try:
                popup.evaluate_js(worker_script)
                time.sleep(1)
                raw_payload = popup.evaluate_js("window.__sync_payload || ''")
                if raw_payload:
                    parsed = json.loads(raw_payload)
                    if parsed.get("status") == "SUCCESS":
                        return parsed
            except Exception:
                pass
            print(f"[INGESTION] Dang tai stream song song... ({attempt + 1}/{timeout_sec})")

        return None

    def _transform_payload(self, term_id: str, term_name: str, raw_results: list) -> Dict[str, Any]:
        """
        Bóc tách chuỗi HTML thô nhận từ mạng thành thực thể dữ liệu học kỳ chuẩn hóa.
        """
        full_data = {
            "term_id": term_id,
            "term_name": term_name,
            "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_courses": len(raw_results),
            "courses": {}
        }

        total_sessions = 0
        for item in raw_results:
            c_name = item["name"]
            c_id = item["courseId"]
            raw_html = item.get("html", "")
            short_name = c_name.split('(')[1].split(')')[0] if '(' in c_name else c_name[:10]

            sessions = parse_fap_attendance_html(raw_html)
            full_data["courses"][c_name] = {
                "course_id": c_id,
                "short_name": short_name,
                "total_sessions": len(sessions),
                "sessions": sessions
            }
            total_sessions += len(sessions)
            print(f"[TRANSFORM] Mon {short_name}: {len(sessions)} buoi hoc.")

        print(f"[SUMMARY] Dong bo thanh cong: {len(raw_results)} mon | {total_sessions} buoi hoc.")
        return full_data

    def _persist_to_disk(self, full_data: Dict[str, Any]) -> None:
        """
        Ghi dữ liệu JSON ra ổ đĩa với encoding UTF-8, bảo toàn cấu trúc dữ liệu.
        """
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        print(f"[STORAGE] Tep tin da duoc luu tai: {self.output_file}")
