import re
from typing import Dict, Any, List, Optional
import fitz  # PyMuPDF
from pathlib import Path

def parse_contract_pdf(pdf_path_or_bytes) -> Dict[str, Any]:
    """
    Parses a signed Corvo Rate Contract PDF and extracts contract header and line items.
    """
    if isinstance(pdf_path_or_bytes, (str, Path)):
        doc = fitz.open(str(pdf_path_or_bytes))
    else:
        doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")

    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"

    # 1. Contract No
    c_match = re.search(r'Contract\s+No\.?\s*([A-Z0-9-]+)', full_text, re.IGNORECASE)
    contract_id = c_match.group(1).strip() if c_match else "UNKNOWN_CONTRACT"

    # 2. Supplier ID & Name
    # e.g., 'and Pneumatic Point, Pune (Supplier ID S021)'
    supp_match = re.search(r'and\s+([^,]+),\s*[^(\n]*\s*\(Supplier ID\s*([A-Z0-9]+)\)', full_text, re.IGNORECASE)
    if supp_match:
        supplier_name = supp_match.group(1).strip()
        supplier_id = supp_match.group(2).strip()
    else:
        s_id_match = re.search(r'Supplier ID\s*([A-Z0-9]+)', full_text, re.IGNORECASE)
        supplier_id = s_id_match.group(1).strip() if s_id_match else "UNKNOWN"
        supplier_name = supplier_id

    # 3. Term dates
    # e.g., 'valid from 2026-11-15 to 2027-11-14'
    term_match = re.search(r'valid from\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})', full_text, re.IGNORECASE)
    if term_match:
        start_date = term_match.group(1).strip()
        end_date = term_match.group(2).strip()
    else:
        start_date = "2026-01-01"
        end_date = "2026-12-31"

    # 4. Value cap / ceiling
    # e.g., 'shall not exceed INR 20,00,000'
    cap_match = re.search(r'exceed\s*INR\s*([\d,]+)', full_text, re.IGNORECASE)
    if cap_match:
        cap_str = cap_match.group(1).replace(",", "").strip()
        value_cap = float(cap_str)
    else:
        value_cap = 1000000.0

    # 5. Schedule A items
    # Table columns: #, Item code, Description, UoM, Rate (INR)
    lines = []
    # Pattern to match table rows: e.g. '1\nITM-1036\nPneumatic cylinder 50x100\nNOS\n3,537.76' or tab-separated
    pattern = re.compile(
        r'(\d+)\s*\n\s*(ITM-\d{4})\s*\n\s*([^\n]+)\s*\n\s*([A-Z]+)\s*\n\s*([\d,]+\.?\d*)',
        re.MULTILINE
    )
    for match in pattern.finditer(full_text):
        item_code = match.group(2).strip()
        description = match.group(3).strip()
        uom = match.group(4).strip()
        rate_str = match.group(5).replace(",", "").strip()
        lines.append({
            'contract_id': contract_id,
            'item_code': item_code,
            'description': description,
            'uom': uom,
            'rate': float(rate_str)
        })

    # If the newline pattern didn't catch, try inline row pattern:
    if not lines:
        inline_pattern = re.compile(
            r'(\d+)\s+(ITM-\d{4})\s+(.+?)\s+([A-Z]{2,4})\s+([\d,]+\.?\d*)'
        )
        for match in inline_pattern.finditer(full_text):
            item_code = match.group(2).strip()
            description = match.group(3).strip()
            uom = match.group(4).strip()
            rate_str = match.group(5).replace(",", "").strip()
            lines.append({
                'contract_id': contract_id,
                'item_code': item_code,
                'description': description,
                'uom': uom,
                'rate': float(rate_str)
            })

    return {
        'contract_id': contract_id,
        'supplier_id': supplier_id,
        'supplier_name': supplier_name,
        'start_date': start_date,
        'end_date': end_date,
        'value_cap': value_cap,
        'consumed_value': 0.0,
        'lines': lines
    }

def extract_text_from_pdf(pdf_path_or_bytes) -> str:
    """Extracts raw text from any PDF document."""
    if isinstance(pdf_path_or_bytes, (str, Path)):
        doc = fitz.open(str(pdf_path_or_bytes))
    else:
        doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text

