"""
Module: flm_parser.py
Description: Semantic Data Extraction Engine for FPT University Learning Materials (FLM).
Architecture: Pure Headless Parser based on BeautifulSoup and semantic DOM mapping.
             Extracts syllabus overview, sessions outline, assessment criteria, materials, and learning outcomes.
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup


def parse_flm_syllabus_html(raw_html: str) -> Dict[str, Any]:
    """
    Bóc tách toàn diện thông tin đề cương môn học từ mã nguồn HTML của trang SyllabusDetails.
    
    Args:
        raw_html (str): Chuỗi HTML thô từ trang /gui/role/student/SyllabusDetails?sylID=...
        
    Returns:
        Dict[str, Any]: Cấu trúc dữ liệu chuẩn hóa của môn học trên FLM.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    
    result: Dict[str, Any] = {
        "syllabus_info": {},
        "materials": [],
        "clos": [],
        "sessions": [],
        "assessments": []
    }
    
    # =========================================================================
    # 1. BÓC TÁCH THÔNG TIN TỔNG QUAN (table-detail)
    # =========================================================================
    tbl_detail = soup.find("table", id="table-detail")
    if tbl_detail:
        for tr in tbl_detail.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                raw_key = tds[0].get_text(separator=" ", strip=True).rstrip(":")
                raw_val = tds[1].get_text(separator="\n", strip=True)
                
                # Chuẩn hóa key thành snake_case
                clean_key = re.sub(r'[^a-zA-Z0-9]+', '_', raw_key).strip('_').lower()
                result["syllabus_info"][clean_key] = raw_val

    # =========================================================================
    # 2. BÓC TÁCH DANH MỤC TÀI LIỆU (gvMaterial)
    # =========================================================================
    tbl_material = soup.find("table", id="gvMaterial")
    if tbl_material:
        tbody = tbl_material.find("tbody") or tbl_material
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 11:
                result["materials"].append({
                    "no": tds[0].get_text(strip=True),
                    "description": tds[1].get_text(strip=True),
                    "author": tds[2].get_text(separator=" ", strip=True),
                    "publisher": tds[3].get_text(strip=True),
                    "published_date": tds[4].get_text(strip=True),
                    "edition": tds[5].get_text(strip=True),
                    "isbn": tds[6].get_text(strip=True),
                    "is_main": tds[7].get_text(strip=True).lower() == "true",
                    "is_hard_copy": tds[8].get_text(strip=True).lower() == "true",
                    "is_online": tds[9].get_text(strip=True).lower() == "true",
                    "note": tds[10].get_text(strip=True)
                })

    # =========================================================================
    # 3. BÓC TÁCH CHUẨN ĐẦU RA (gvLO)
    # =========================================================================
    tbl_lo = soup.find("table", id="gvLO")
    if tbl_lo:
        tbody = tbl_lo.find("tbody") or tbl_lo
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                result["clos"].append({
                    "no": tds[0].get_text(strip=True),
                    "clo_name": tds[1].get_text(strip=True),
                    "clo_details": tds[2].get_text(strip=True)
                })

    # =========================================================================
    # 4. BÓC TÁCH KẾ HOẠCH BUỔI HỌC THEO SYLLABUS (gvSchedule)
    # =========================================================================
    tbl_schedule = soup.find("table", id="gvSchedule")
    if tbl_schedule:
        tbody = tbl_schedule.find("tbody") or tbl_schedule
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 9:
                # Bóc tách download links trong cột S-Download
                downloads = []
                for a in tds[6].find_all("a", href=True):
                    downloads.append({
                        "name": a.get_text(strip=True),
                        "url": a["href"]
                    })
                
                result["sessions"].append({
                    "session": tds[0].get_text(strip=True),
                    "topic": tds[1].get_text(separator="\n", strip=True),
                    "learning_type": tds[2].get_text(strip=True),
                    "lo": tds[3].get_text(strip=True),
                    "itu": tds[4].get_text(strip=True),
                    "student_materials": tds[5].get_text(separator="\n", strip=True),
                    "downloads": downloads,
                    "student_tasks": tds[7].get_text(separator="\n", strip=True),
                    "urls": tds[8].get_text(strip=True)
                })

    # =========================================================================
    # 5. BÓC TÁCH HÌNH THỨC ĐÁNH GIÁ & CỘT ĐIỂM (gvAssessment)
    # =========================================================================
    tbl_assessment = soup.find("table", id="gvAssessment")
    if tbl_assessment:
        tbody = tbl_assessment.find("tbody") or tbl_assessment
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 13:
                result["assessments"].append({
                    "no": tds[0].get_text(strip=True),
                    "category": tds[1].get_text(strip=True),
                    "type": tds[2].get_text(strip=True),
                    "part": tds[3].get_text(strip=True),
                    "weight": tds[4].get_text(strip=True),
                    "completion_criteria": tds[5].get_text(strip=True),
                    "duration": tds[6].get_text(strip=True),
                    "clo": tds[7].get_text(strip=True),
                    "question_type": tds[8].get_text(strip=True),
                    "no_question": tds[9].get_text(strip=True),
                    "knowledge_skill": tds[10].get_text(separator="\n", strip=True),
                    "grading_guide": tds[11].get_text(separator="\n", strip=True),
                    "note": tds[12].get_text(separator="\n", strip=True)
                })

    return result
