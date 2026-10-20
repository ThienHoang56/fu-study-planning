"""
Module: parser.py
Description: Semantic Data Extraction Engine for FAP Attendance Reports.
Architecture: Pure functional parser based on token patterns, resilient to DOM/CSS refactoring.
"""

import re
from typing import List, Dict, Any, Optional


def parse_fap_attendance_html(raw_html: str) -> List[Dict[str, Any]]:
    """
    Trích xuất danh sách các buổi học từ mã nguồn HTML thô nhận về từ tầng Network.

    Phương pháp: Semantic Data Pattern Matching
    - Miễn nhiễm hoàn toàn với thay đổi tên class CSS, màu sắc, font hay layout DOM.
    - Nhận diện các thuộc tính học tập dựa trên cấu trúc dữ liệu bản thể:
        + Ngày học: Định dạng dd/mm/yyyy kèm thứ.
        + Khung giờ (Slot): Định dạng khoảng thời gian HH:mm - HH:mm.
        + Phòng học, Giảng viên, Mã lớp, Trạng thái: Ánh xạ tương đối theo ma trận hàng.

    Args:
        raw_html (str): Chuỗi HTML thô nhận từ HTTP Response của server FAP.

    Returns:
        List[Dict[str, Any]]: Danh sách các session buổi học đã được chuẩn hóa.
    """
    sessions: List[Dict[str, Any]] = []

    # BƯỚC 1: Bóc tách tất cả các hàng dữ liệu (tr) trong tài liệu
    tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', raw_html, re.DOTALL | re.IGNORECASE)

    for tr in tr_matches:
        # BƯỚC 2: Bóc tách tất cả các ô dữ liệu (td) trong hàng
        cells = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)

        # Loại bỏ các thẻ định dạng HTML con lồng nhau (span, a, font, b, etc.)
        clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

        # Bỏ qua các hàng tiêu đề hoặc hàng không đủ số cột dữ liệu tối thiểu
        if len(clean_cells) < 4:
            continue

        # BƯỚC 3: Quét tìm vị trí Date và Slot bằng biểu thức chính quy (Regex Pattern)
        date_val: Optional[str] = None
        slot_val: Optional[str] = None

        for c in clean_cells:
            if re.search(r'\d{1,2}/\d{1,2}/\d{4}', c) and not date_val:
                date_val = c
            elif re.search(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', c) and not slot_val:
                slot_val = c

        # BƯỚC 4: Khi hàng thỏa mãn cả Ngày và Khung giờ, trích xuất vào Canonical Model
        if date_val and slot_val:
            date_idx = clean_cells.index(date_val)
            slot_idx = clean_cells.index(slot_val)

            stt = clean_cells[0] if date_idx > 0 else str(len(sessions) + 1)
            room = clean_cells[slot_idx + 1] if len(clean_cells) > slot_idx + 1 else ""
            lecturer = clean_cells[slot_idx + 2] if len(clean_cells) > slot_idx + 2 else ""
            class_name = clean_cells[slot_idx + 3] if len(clean_cells) > slot_idx + 3 else ""
            status = clean_cells[slot_idx + 4] if len(clean_cells) > slot_idx + 4 else ""

            sessions.append({
                "stt": stt,
                "date": date_val,
                "slot": slot_val,
                "room": room,
                "lecturer": lecturer,
                "class_name": class_name,
                "status": status
            })

    return sessions
