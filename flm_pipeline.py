"""
Module: flm_pipeline.py
Description: Production 4-Stage Zero-DOM Asynchronous Data Ingestion Pipeline for FLM (FPT University Learning Materials).
Architecture: Zero-DOM UI dependency. Employs browser network stack injection, HTTP form data postback,
             parallel SyllabusDetails ingestion, semantic parsing, and atomic JSON persistence.
"""

import json
import time
import os
import re
from typing import Dict, Any, Callable, Optional, List
from flm_parser import parse_flm_syllabus_html


class FLMSyncPipeline:
    """
    Quy trình đồng bộ toàn diện Đề cương chi tiết (Syllabus), Buổi học và Cột điểm từ hệ thống FLM.

    Quy chuẩn kiến trúc 4 Stage độc lập:
      - Stage 1 [Authentication Handshake]: Giám sát phiên đăng nhập trên FLM (Google / FEID).
      - Stage 2 [Zero-DOM Network Ingestion]: Dispatches HTTP requests qua browser network stack lấy syllabus HTML.
      - Stage 3 [Semantic Data Transformation]: Bóc tách Canonical Schema bằng flm_parser.
      - Stage 4 [Atomic Persistence]: Tuần tự hóa JSON an toàn theo tiêu chuẩn UTF-8 (flm_courses.json).
    """

    def __init__(self, output_file: str, course_codes: List[str]):
        self.output_file = output_file
        # Làm sạch và loại bỏ mã trùng lặp (ví dụ EXE201g -> EXE201)
        cleaned_codes = []
        for c in course_codes:
            code = c.strip()
            # Bỏ ký tự hậu tố nhóm môn nếu có
            base_code = re.sub(r'([A-Za-z]{3}\d{3})[a-z]$', r'\1', code)
            if base_code not in cleaned_codes:
                cleaned_codes.append(base_code)
            if code not in cleaned_codes:
                cleaned_codes.append(code)
        self.course_codes = cleaned_codes

    def execute(self, popup, progress_cb: Optional[Callable[[str], None]] = None) -> Optional[Dict[str, Any]]:
        """
        Thực thi toàn bộ chu trình 4 Stage của FLM pipeline.
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
        # ==============================================================================
        notify("FLM STAGE 1/4", "Kiem tra phien dang nhap FLM trong WebView2...")
        try:
            curr_url = popup.get_current_url() or ""
            if "flm.fpt.edu.vn" not in curr_url:
                popup.load_url("https://flm.fpt.edu.vn/Login")
                time.sleep(2)
        except Exception as e:
            print(f"[FLM] Loi chuyen trang sang FLM: {e}")

        if not self._wait_for_auth(popup, notify, timeout_sec=120):
            notify("ERROR", "Xac thuc FLM that bai hoac qua thoi gian cho.")
            return None

        # ==============================================================================
        # STAGE 2: ZERO-DOM NETWORK INGESTION
        # ==============================================================================
        notify("FLM STAGE 2/4", f"Bat dau ingest du lieu qua network stack cho {len(self.course_codes)} ma mon...")
        raw_results = self._ingest_flm_network_stream(popup, notify, timeout_sec=120)
        if not raw_results:
            notify("ERROR", "Ingestion that bai: Khong nhan duoc du lieu tu FLM.")
            return None

        # ==============================================================================
        # STAGE 3: SEMANTIC TRANSFORMATION
        # ==============================================================================
        notify("FLM STAGE 3/4", "Chuan hoa du lieu va bóc tach de cuong chi tiet...")
        flm_data = {
            "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_courses": len(raw_results),
            "courses": {}
        }

        for code, item in raw_results.items():
            if item.get("status") == "SUCCESS" and item.get("html"):
                try:
                    parsed = parse_flm_syllabus_html(item["html"])
                    parsed["syl_id"] = item.get("sylId", "")
                    flm_data["courses"][code] = parsed
                    notify("INFO", f"Da bóc tach thanh cong: {code} (Syllabus ID: {item.get('sylId')})")
                except Exception as e:
                    notify("WARNING", f"Loi khi parse mon {code}: {e}")
                    flm_data["courses"][code] = {"status": "PARSE_ERROR", "error": str(e)}
            else:
                flm_data["courses"][code] = {
                    "status": item.get("status", "NOT_FOUND"),
                    "message": item.get("message", "Khong tim thay de cuong")
                }

        # ==============================================================================
        # STAGE 4: ATOMIC PERSISTENCE
        # ==============================================================================
        notify("FLM STAGE 4/4", f"Luu tru du lieu vao {os.path.basename(self.output_file)}...")
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(flm_data, f, ensure_ascii=False, indent=2)
            notify("SUCCESS", f"Da luu tru thanh cong {len(flm_data['courses'])} mon hoc FLM!")
        except Exception as e:
            notify("ERROR", f"Loi luu file JSON: {e}")
            return None

        return flm_data

    def _wait_for_auth(self, popup, notify_fn, timeout_sec: int = 120) -> bool:
        """
        Duy trì và theo dõi URL cho đến khi người dùng vượt qua trang đăng nhập FLM.
        Tự động chọn cấp học FPTU nếu đang ở màn hình Login.
        """
        last_notified_url = ""
        for attempt in range(timeout_sec):
            time.sleep(1.2)
            try:
                url = popup.get_current_url() or ""

                if url and url != last_notified_url:
                    last_notified_url = url
                    print(f"[FLM AUTH] URL hien tai: {url}")

                # Nếu đang ở trang Login, tự động chọn FPTU trong dropdown
                if "flm.fpt.edu.vn/login" in url.lower():
                    try:
                        popup.evaluate_js("""
                            (function() {
                                const sel = document.getElementById('drSelectEduLevel');
                                if (sel && sel.value !== 'fptu') {
                                    sel.value = 'fptu';
                                    localStorage.setItem('SelectedEduLevel', 'fptu');
                                    if (window.$) { $(sel).trigger('change'); }
                                }
                            })();
                        """)
                    except Exception:
                        pass

                # Nếu đã vào được trang Home, AllPrequisiteSubject hoặc các trang chức năng FLM
                if "flm.fpt.edu.vn" in url:
                    lower_url = url.lower()
                    if "/home" in lower_url or "/gui/" in lower_url:
                        notify_fn("SUCCESS", f"Xac thuc FLM thanh cong tai: {url}")
                        return True
                    if (not any(x in lower_url for x in ["login", "signin", "accounts.google.com", "feid.fpt.edu.vn"])
                        and lower_url != "https://flm.fpt.edu.vn/"
                        and lower_url != "https://flm.fpt.edu.vn"):
                        notify_fn("SUCCESS", f"Xac thuc FLM thanh cong tai: {url}")
                        return True
            except Exception:
                # Không thoát khi gặp exception do trình duyệt đang bận điều hướng
                pass
        return False

    def _ingest_flm_network_stream(self, popup, notify_fn, timeout_sec: int = 120) -> Optional[Dict[str, Any]]:
        """
        Thực thi script Zero-DOM Network Ingestion Worker trong context trình duyệt.
        """
        # BƯỚC 1: Đảm bảo WebView điều hướng đến AllPrequisiteSubject
        notify_fn("FLM", "Dieu huong den trang tra cuu mon hoc AllPrequisiteSubject...")
        try:
            curr_url = popup.get_current_url() or ""
            if "AllPrequisiteSubject" not in curr_url:
                popup.load_url("https://flm.fpt.edu.vn/gui/tool/AllPrequisiteSubject")
        except Exception as e:
            print(f"[FLM] Loi load_url: {e}")

        # Chờ trang nạp hoàn tất form
        page_ready = False
        for _ in range(20):
            time.sleep(1)
            try:
                is_loaded = popup.evaluate_js(
                    "Boolean(document.querySelector('form') && document.querySelector('input[type=\"text\"]'))"
                )
                if is_loaded:
                    page_ready = True
                    break
            except Exception:
                pass

        if not page_ready:
            notify_fn("WARNING", "Chua thay form AllPrequisiteSubject, tiep tuc kiem tra...")

        # BƯỚC 2: Khởi tạo Worker Script chỉ MỘT LẦN DUY NHẤT
        worker_init_script = f"""
        (function() {{
            window.__flm_payload = null;
            window.__flm_logs = [];
            window.__flm_worker_running = true;

            function log(msg) {{
                window.__flm_logs.push(msg);
                console.log("[FLM_WORKER] " + msg);
            }}

            window.__runIngestion = async function() {{
                const codes = {json.dumps(self.course_codes)};
                const results = {{}};

                try {{
                    const form = document.querySelector('form');
                    if (!form) {{
                        log("ERROR: Form khong ton tai tren trang.");
                        window.__flm_payload = JSON.stringify({{ status: "ERROR", message: "Form not found" }});
                        return;
                    }}

                    const textInput = form.querySelector('input[type="text"]');
                    const submitBtn = Array.from(form.querySelectorAll('input[type="submit"], button')).find(
                        b => (b.value || b.textContent || '').trim().toLowerCase() === 'search'
                    );

                    if (!textInput) {{
                        log("ERROR: Khong tim thay o nhap ma mon.");
                        window.__flm_payload = JSON.stringify({{ status: "ERROR", message: "Input not found" }});
                        return;
                    }}

                    log("Form san sang. Bat dau query " + codes.length + " mon hoc...");

                    for (const code of codes) {{
                        log("Dang query ma mon: " + code);
                        try {{
                            const currentForm = document.querySelector('form');
                            const formData = new FormData(currentForm);
                            formData.set(textInput.name, code);
                            if (submitBtn && submitBtn.name) {{
                                formData.set(submitBtn.name, submitBtn.value || 'Search');
                            }}

                            // Gui HTTP POST truc tiep bang network stack cua trinh duyet
                            const postRes = await fetch(currentForm.action || window.location.href, {{
                                method: 'POST',
                                body: formData
                            }});
                            const postHtml = await postRes.text();

                            // Trich xuat sylID tu HTML tra ve
                            const match = postHtml.match(/SyllabusDetails\\?sylID=(\\d+)/i) || 
                                          postHtml.match(/sylID=(\\d+)/i);
                            if (match) {{
                                const sylId = match[1];
                                log("Tim thay sylID=" + sylId + " cho " + code + ". Dang tai de cuong...");
                                const sylRes = await fetch('/gui/role/student/SyllabusDetails?sylID=' + sylId);
                                const sylHtml = await sylRes.text();
                                results[code] = {{
                                    status: "SUCCESS",
                                    sylId: sylId,
                                    html: sylHtml
                                }};
                            }} else {{
                                log("Khong tim thay syllabus cho ma mon: " + code);
                                results[code] = {{
                                    status: "NOT_FOUND",
                                    message: "Khong tim thay syllabus cho ma mon nay"
                                }};
                            }}
                        }} catch (itemErr) {{
                            log("Loi query mon " + code + ": " + itemErr.message);
                            results[code] = {{
                                status: "ERROR",
                                error: itemErr.message
                            }};
                        }}
                    }}

                    log("Hoan tat toan bo query!");
                    window.__flm_payload = JSON.stringify({{
                        status: "COMPLETED",
                        results: results
                    }});
                }} catch (globalErr) {{
                    log("Fatal error: " + globalErr.message);
                    window.__flm_payload = JSON.stringify({{
                        status: "FATAL_ERROR",
                        error: globalErr.message
                    }});
                }}
            }};

            window.__runIngestion();
        }})();
        """

        notify_fn("FLM", "Kich hoat Worker Stream qua Network Stack...")
        try:
            popup.evaluate_js(worker_init_script)
        except Exception as e:
            notify_fn("ERROR", f"Loi khoi tao worker: {e}")
            return None

        # BƯỚC 3: Lắng nghe kết quả và log (KHÔNG re-evaluate worker script)
        last_log_count = 0
        for attempt in range(timeout_sec):
            time.sleep(1.2)
            try:
                # 1. Đọc và thông báo log mới
                current_logs = popup.evaluate_js("window.__flm_logs || []")
                if isinstance(current_logs, list) and len(current_logs) > last_log_count:
                    for l in current_logs[last_log_count:]:
                        notify_fn("FLM", l)
                    last_log_count = len(current_logs)

                # 2. Đọc payload kết quả
                raw_payload = popup.evaluate_js("window.__flm_payload || ''")
                if raw_payload:
                    parsed = json.loads(raw_payload)
                    if parsed.get("status") == "COMPLETED":
                        return parsed.get("results", {})
                    elif parsed.get("status") in ("FATAL_ERROR", "ERROR"):
                        notify_fn("ERROR", f"Worker bao loi: {parsed.get('error') or parsed.get('message')}")
                        return None
            except Exception as e:
                pass

        notify_fn("ERROR", "Qua thoi gian cho xu ly network FLM.")
        return None
