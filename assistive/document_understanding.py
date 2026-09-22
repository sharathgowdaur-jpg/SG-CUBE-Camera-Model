"""
SG CUBE 2.5 — Feature 8: Intelligent Document Understanding Engine
Authoritative local structured document perception, layout analysis,
type classification, deterministic query answering, and PII redaction.
"""

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from assistive.ocr_engine import OCREngine


class DocumentType(str, Enum):
    UNKNOWN = "UNKNOWN"
    PAGE = "PAGE"
    RECEIPT = "RECEIPT"
    BILL = "BILL"
    MENU = "MENU"
    FORM = "FORM"
    LABEL = "LABEL"
    SIGN = "SIGN"
    TABLE = "TABLE"
    OTHER = "OTHER"


class BlockType(str, Enum):
    TITLE = "TITLE"
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    LIST = "LIST"
    KEY_VALUE = "KEY_VALUE"
    TABLE = "TABLE"
    FOOTER = "FOOTER"
    UNKNOWN = "UNKNOWN"


@dataclass
class DocumentRegion:
    """
    Detected document bounding region with 4 polygon corners and quality metrics.
    """
    bounding_box: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, w, h)
    corners: List[Tuple[int, int]] = field(default_factory=list)  # [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    confidence: float = 0.0
    quality_score: float = 1.0
    is_blurry: bool = False
    is_dark: bool = False
    is_partial: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bounding_box": list(self.bounding_box),
            "corners": [list(c) for c in self.corners],
            "confidence": round(self.confidence, 3),
            "quality_score": round(self.quality_score, 3),
            "is_blurry": self.is_blurry,
            "is_dark": self.is_dark,
            "is_partial": self.is_partial,
            "timestamp": self.timestamp
        }


@dataclass
class DocumentBlock:
    """
    A semantic block of extracted text with reading order and layout classification.
    """
    block_id: int
    text: str
    block_type: BlockType = BlockType.UNKNOWN
    bounding_box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: float = 1.0
    reading_order: int = 0
    key: Optional[str] = None
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "text": self.text,
            "block_type": self.block_type.value if hasattr(self.block_type, "value") else str(self.block_type),
            "bounding_box": list(self.bounding_box),
            "confidence": round(self.confidence, 3),
            "reading_order": self.reading_order,
            "key": self.key,
            "value": self.value
        }


@dataclass
class DocumentTable:
    """
    Structured tabular data extracted from document grids or columnar alignment.
    """
    table_id: int = 1
    rows: List[List[str]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    cells: List[Dict[str, Any]] = field(default_factory=list)
    bounding_box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: float = 1.0

    def __post_init__(self):
        if not self.columns and self.headers:
            self.columns = list(self.headers)
        elif not self.headers and self.columns:
            self.headers = list(self.columns)

    def to_verbal_summary(self) -> str:
        """
        Formats table contents for clear screen-reader / TTS recitation.
        """
        if not self.rows:
            return "Empty table."
        header_names = self.headers or [f"Column {i+1}" for i in range(len(self.rows[0]))]
        summary_lines = [f"Table has {len(self.rows)} rows."]
        for r_idx, row in enumerate(self.rows, 1):
            row_parts = []
            for c_idx, cell in enumerate(row):
                col_name = header_names[c_idx] if c_idx < len(header_names) else f"Column {c_idx+1}"
                row_parts.append(f"{col_name} is {cell}")
            summary_lines.append(f"Row {r_idx}: " + ", ".join(row_parts))
        return " ".join(summary_lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "rows": self.rows,
            "columns": self.columns,
            "headers": self.headers,
            "cells": self.cells,
            "bounding_box": list(self.bounding_box),
            "confidence": round(self.confidence, 3)
        }


@dataclass
class DocumentResult:
    """
    Authoritative structured document understanding result.
    """
    document_id: str = field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:8]}")
    document_type: DocumentType = DocumentType.UNKNOWN
    title: Optional[str] = None
    blocks: List[DocumentBlock] = field(default_factory=list)
    tables: List[DocumentTable] = field(default_factory=list)
    key_values: Dict[str, str] = field(default_factory=dict)
    extracted_text: str = ""
    raw_text: str = ""
    summary: str = ""
    total: Optional[str] = None
    has_document: bool = True
    has_table: bool = False
    confidence: float = 0.0
    quality_status: str = "READY"  # "READY", "BLURRY", "DARK", "LOW_QUALITY", "NO_DOCUMENT"
    is_blurry: bool = False
    is_valid: bool = True
    reason: Optional[str] = None
    region: Optional[DocumentRegion] = None
    timestamp: float = field(default_factory=time.time)
    source_type: str = "CAMERA"

    def __post_init__(self):
        if self.raw_text and not self.extracted_text:
            self.extracted_text = self.raw_text
        elif self.extracted_text and not self.raw_text:
            self.raw_text = self.extracted_text

        if self.tables and not self.has_table:
            self.has_table = True

        if not self.total and self.key_values:
            for k in ["total", "grand total", "net amount", "amount payable", "total amount", "amount", "total due"]:
                if k in self.key_values:
                    self.total = self.key_values[k]
                    break

        if not self.is_valid or self.quality_status in ("NO_DOCUMENT", "BLURRY", "DARK"):
            if self.quality_status == "NO_DOCUMENT":
                self.has_document = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.value if hasattr(self.document_type, "value") else str(self.document_type),
            "title": self.title,
            "has_document": self.has_document,
            "blocks": [b.to_dict() for b in self.blocks],
            "tables": [t.to_dict() for t in self.tables],
            "key_values": self.key_values,
            "extracted_text": self.extracted_text,
            "summary": self.summary,
            "total": self.total,
            "has_table": self.has_table,
            "confidence": round(self.confidence, 3),
            "quality_status": self.quality_status,
            "is_blurry": self.is_blurry,
            "is_valid": self.is_valid,
            "reason": self.reason,
            "region": self.region.to_dict() if self.region else None,
            "timestamp": self.timestamp,
            "source_type": self.source_type
        }


# =============================================================================
# SENSITIVE PII & SECRET REDACTION UTILITIES
# =============================================================================

def redact_sensitive_document_text(text: str) -> str:
    """
    Redacts or masks high-risk PII, authentication credentials, and payment data:
    - Passwords, recovery codes, API keys, tokens, OTPs
    - Credit/Debit card numbers ([REDACTED_CARD])
    - Aadhaar numbers ([REDACTED_AADHAAR])
    - PAN numbers ([REDACTED_PAN])
    """
    if not text:
        return ""

    redacted = text

    # 1. Mask Payment Card Numbers (13-19 digits) -> [REDACTED_CARD]
    redacted = re.sub(r'\b(?:\d{4}[ -]?){3}\d{4}\b', '[REDACTED_CARD]', redacted)
    redacted = re.sub(r'\b\d{16}\b', '[REDACTED_CARD]', redacted)

    # 2. Redact Aadhaar Numbers (12 digits in 4-4-4 format) -> [REDACTED_AADHAAR]
    redacted = re.sub(r'\b\d{4}\s\d{4}\s\d{4}\b', '[REDACTED_AADHAAR]', redacted)

    # 3. Redact Indian PAN Card Numbers (5 uppercase letters, 4 digits, 1 uppercase letter) -> [REDACTED_PAN]
    redacted = re.sub(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', '[REDACTED_PAN]', redacted)

    # 4. Redact OTP / Verification codes
    redacted = re.sub(r'\b(?:otp|one[- ]time[- ]password|verification code)\s*[:=-]?\s*([0-9]{4,8})\b', r'OTP: [REDACTED]', redacted, flags=re.IGNORECASE)

    # 5. Redact Passwords / Tokens / Keys
    redacted = re.sub(r'(?i)\b(?:wifi\s+password|password|passwd|pwd|recovery code|secret key|api[_-]?key|access[_-]?token|bearer)\s*[:=-]\s*([^\s,;]+)', r'\g<0>', redacted)
    # Generic replacement of credential values following trigger keywords
    redacted = re.sub(
        r'(?i)\b((?:wifi\s+password|password|passwd|pwd|recovery code|secret key|api[_-]?key|access[_-]?token|bearer)\s*[:=-]\s*)([^\s,;]+)',
        r'\1[REDACTED_CREDENTIAL]',
        redacted
    )

    return redacted


# =============================================================================
# DOCUMENT UNDERSTANDING ENGINE
# =============================================================================

class DocumentUnderstandingEngine:
    """
    Intelligent Document Understanding Engine for SG CUBE 2.5.
    Performs document boundary detection, perspective rectification, quality assessment,
    OCR layout analysis, reading-order reconstruction, document classification,
    deterministic query answering, and PII redaction.
    """

    def __init__(self, ocr_engine: Optional[OCREngine] = None):
        self.ocr_engine = ocr_engine or OCREngine()
        self.last_result: Optional[DocumentResult] = None
        self.last_read_block_index: int = 0
        self.min_blur_threshold: float = 50.0  # Laplacian variance threshold
        self.min_brightness: float = 30.0
        self.max_brightness: float = 245.0

    # -------------------------------------------------------------------------
    # 1. IMAGE PROCESSING & RECTIFICATION
    # -------------------------------------------------------------------------

    def detect_document_region(self, frame: np.ndarray) -> Optional[DocumentRegion]:
        """
        Detects rectangular page / document contour in the frame.
        """
        if frame is None or frame.size == 0:
            return None

        h_img, w_img = frame.shape[:2]
        frame_area = float(w_img * h_img)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Morphological edges
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < frame_area * 0.05:
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            if len(approx) == 4 and cv2.isContourConvex(approx):
                corners = [tuple(p[0]) for p in approx]
                x, y, w, h = cv2.boundingRect(approx)
                ordered_corners = self._order_corners(corners)
                is_blurry, var = self.assess_blur(frame[y:y+h, x:x+w] if h > 10 and w > 10 else frame)
                is_dark, _, _ = self.assess_lighting(frame[y:y+h, x:x+w] if h > 10 and w > 10 else frame)
                return DocumentRegion(
                    bounding_box=(x, y, w, h),
                    corners=ordered_corners,
                    confidence=min(0.98, round(area / frame_area + 0.5, 2)),
                    is_blurry=is_blurry,
                    is_dark=is_dark,
                    timestamp=time.time()
                )

        # Fallback: Check if large salient rectangle exists
        if contours:
            x, y, w, h = cv2.boundingRect(contours[0])
            area = w * h
            if area >= frame_area * 0.08:
                corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                is_blurry, _ = self.assess_blur(frame[y:y+h, x:x+w] if h > 10 and w > 10 else frame)
                is_dark, _, _ = self.assess_lighting(frame[y:y+h, x:x+w] if h > 10 and w > 10 else frame)
                return DocumentRegion(
                    bounding_box=(x, y, w, h),
                    corners=corners,
                    confidence=0.75,
                    is_blurry=is_blurry,
                    is_dark=is_dark,
                    timestamp=time.time()
                )

        return None

    def _order_corners(self, pts: Any) -> Any:
        """
        Orders 4 corners as: [top-left, top-right, bottom-right, bottom-left].
        """
        pts_arr = np.array(pts, dtype="float32")
        if len(pts_arr) != 4:
            return pts_arr
        s = pts_arr.sum(axis=1)
        top_left = pts_arr[np.argmin(s)]
        bottom_right = pts_arr[np.argmax(s)]

        diff = np.diff(pts_arr, axis=1)
        top_right = pts_arr[np.argmin(diff)]
        bottom_left = pts_arr[np.argmax(diff)]

        if isinstance(pts, list) and len(pts) > 0 and isinstance(pts[0], tuple):
            return [
                (int(top_left[0]), int(top_left[1])),
                (int(top_right[0]), int(top_right[1])),
                (int(bottom_right[0]), int(bottom_right[1])),
                (int(bottom_left[0]), int(bottom_left[1]))
            ]
        return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)

    order_corners = _order_corners

    def rectify_document(self, frame: np.ndarray, corners: Any) -> np.ndarray:
        """
        Applies a 4-point perspective transform to extract a flattened document image.
        """
        if frame is None or len(corners) != 4:
            return frame

        ordered = self._order_corners(corners)
        tl, tr, br, bl = ordered

        # Compute width of new image
        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_w = max(int(width_a), int(width_b))

        # Compute height of new image
        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_h = max(int(height_a), int(height_b))

        if max_w < 10 or max_h < 10:
            return frame

        dst = np.array([
            [0, 0],
            [max_w - 1, 0],
            [max_w - 1, max_h - 1],
            [0, max_h - 1]
        ], dtype="float32")

        src = np.array(ordered, dtype="float32")
        matrix = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(frame, matrix, (max_w, max_h))
        return warped

    warp_perspective = rectify_document

    def assess_blur(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Returns (is_blurry, laplacian_variance).
        """
        if frame is None or frame.size == 0:
            return True, 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return (var < self.min_blur_threshold), var

    def assess_lighting(self, frame: np.ndarray) -> Tuple[bool, float, float]:
        """
        Returns (is_dark, mean_brightness, contrast).
        """
        if frame is None or frame.size == 0:
            return True, 0.0, 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        mean_b = float(np.mean(gray))
        std_c = float(np.std(gray))
        return (mean_b < self.min_brightness), mean_b, std_c

    def assess_quality(self, frame: np.ndarray) -> Tuple[bool, str, float, Optional[str]]:
        """
        Evaluates image quality, blurriness, and illumination.
        Returns: (is_valid, quality_status, score, failure_reason)
        """
        if frame is None or frame.size == 0:
            return False, "NO_DOCUMENT", 0.0, "No image provided."

        is_blurry, var = self.assess_blur(frame)
        if is_blurry:
            return False, "BLURRY", round(var, 1), "The document is too blurry to read clearly. Please hold the camera still."

        is_dark, b_val, _ = self.assess_lighting(frame)
        if is_dark:
            return False, "DARK", round(b_val, 1), "The image is too dark to read the document. Please add more lighting."

        if b_val > self.max_brightness:
            return False, "LOW_QUALITY", round(b_val, 1), "The document has too much glare or overexposure."

        return True, "READY", 1.0, None

    # -------------------------------------------------------------------------
    # 2. DOCUMENT STRUCTURE & READING-ORDER EXTRACTION
    # -------------------------------------------------------------------------

    def sort_reading_order(self, blocks: List[DocumentBlock]) -> List[DocumentBlock]:
        """
        Sorts document blocks into natural reading order:
        First divides into vertical columns if multi-column, then top-to-bottom.
        """
        if not blocks:
            return []

        # Sort by y first (top-to-bottom), then x (left-to-right) with line tolerance
        # If bounding boxes are present, cluster into lines
        def sort_key(b: DocumentBlock):
            x, y, w, h = b.bounding_box
            # Bucket y with 25px line height tolerance
            line_bucket = y // 30
            return (line_bucket, x)

        sorted_blocks = sorted(blocks, key=sort_key)
        for idx, b in enumerate(sorted_blocks):
            b.reading_order = idx
        return sorted_blocks

    def classify_block(self, block: DocumentBlock, doc_height: int = 600) -> DocumentBlock:
        """
        Determines semantic block type (TITLE, HEADING, PARAGRAPH, KEY_VALUE, LIST, FOOTER).
        """
        text = block.text.strip()
        x, y, w, h = block.bounding_box

        # Key-Value match
        kv_match = re.match(r'^([^:\-\=]{2,30})\s*[:\-\=]\s*(.+)$', text)
        if kv_match and not text.lower().startswith("http"):
            block.block_type = BlockType.KEY_VALUE
            block.key = kv_match.group(1).strip().lower()
            block.value = kv_match.group(2).strip()
            return block

        # List match
        if re.match(r'^(?:\d+[\.\)]|\*|-|•)\s+(.+)$', text):
            block.block_type = BlockType.LIST
            return block

        # Footer match (near bottom of document)
        if y > doc_height * 0.85 or any(term in text.lower() for term in ["thank you", "visit again", "authorized sign", "terms & conditions"]):
            block.block_type = BlockType.FOOTER
            return block

        # Title match (near top, short or uppercase)
        if y < doc_height * 0.2 and (h >= 30 or text.isupper() or len(text.split()) <= 5):
            block.block_type = BlockType.TITLE if y < doc_height * 0.1 else BlockType.HEADING
            return block

        if text.endswith(":"):
            block.block_type = BlockType.HEADING
            return block

        block.block_type = BlockType.PARAGRAPH
        return block

    def extract_table_from_text(self, text: str) -> Optional[DocumentTable]:
        """
        Attempts to parse tabular structure from text lines.
        """
        if not text:
            return None

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        table_lines = []

        for line in lines:
            if "|" in line and line.count("|") >= 2:
                table_lines.append(line)
            elif "\t" in line or bool(re.search(r'[A-Za-z0-9$]+\s{3,}[A-Za-z0-9$]+', line)):
                table_lines.append(line)

        if len(table_lines) < 2:
            return None

        t_rows = []
        headers = []

        for idx, t_line in enumerate(table_lines):
            if "|" in t_line:
                parts = [p.strip() for p in t_line.split("|") if p.strip() and not set(p.strip()) <= {'-', '='}]
            elif "\t" in t_line:
                parts = [p.strip() for p in t_line.split("\t") if p.strip()]
            else:
                parts = [p.strip() for p in re.split(r'\s{2,}', t_line) if p.strip()]

            if parts:
                if idx == 0 and not headers:
                    headers = parts
                else:
                    t_rows.append(parts)

        if not t_rows:
            return None

        return DocumentTable(
            table_id=1,
            rows=t_rows,
            columns=headers or [f"Col {i+1}" for i in range(len(t_rows[0]))],
            headers=headers or [f"Col {i+1}" for i in range(len(t_rows[0]))]
        )

    def extract_structure(
        self,
        text_lines: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
        rectified_image: Optional[np.ndarray] = None
    ) -> Tuple[List[DocumentBlock], List[DocumentTable], Dict[str, str], Optional[str]]:
        """
        Constructs semantic blocks, reading order, key-values, lists, tables, and title.
        """
        lines: List[str] = []
        if text_lines:
            lines = [l.strip() for l in text_lines if l.strip()]
        elif raw_text:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        elif rectified_image is not None:
            ocr_res = self.ocr_engine.process_ocr(rectified_image)
            raw = ocr_res.get("text", "")
            lines = [l.strip() for l in raw.splitlines() if l.strip()]

        if not lines:
            return [], [], {}, None

        blocks: List[DocumentBlock] = []
        tables: List[DocumentTable] = []
        key_values: Dict[str, str] = {}
        title: Optional[str] = None

        # Check for table
        full_text = "\n".join(lines)
        table_obj = self.extract_table_from_text(full_text)
        if table_obj:
            tables.append(table_obj)

        reading_order = 0
        for line_idx, line in enumerate(lines):
            clean_line = redact_sensitive_document_text(line)

            # Key-Value Pattern
            kv_match = re.match(r'^([^:\-\=]{2,30})\s*[:\-\=]\s*(.+)$', clean_line)
            if kv_match and not clean_line.lower().startswith("http"):
                k_raw = kv_match.group(1).strip()
                v_raw = kv_match.group(2).strip()
                k_norm = k_raw.lower()
                key_values[k_norm] = v_raw
                block = DocumentBlock(
                    block_id=len(blocks) + 1,
                    text=clean_line,
                    block_type=BlockType.KEY_VALUE,
                    reading_order=reading_order,
                    key=k_norm,
                    value=v_raw
                )
                blocks.append(block)
                reading_order += 1
                continue

            # List Pattern
            list_match = re.match(r'^(?:\d+[\.\)]|\*|-|•)\s+(.+)$', clean_line)
            if list_match:
                block = DocumentBlock(
                    block_id=len(blocks) + 1,
                    text=clean_line,
                    block_type=BlockType.LIST,
                    reading_order=reading_order
                )
                blocks.append(block)
                reading_order += 1
                continue

            # Heading / Section Header
            if clean_line.endswith(":") or (clean_line.isupper() and len(clean_line.split()) <= 4 and len(clean_line) <= 25):
                if line_idx == 0 and not title:
                    title = clean_line.rstrip(":").strip()
                    block_t = BlockType.TITLE
                else:
                    block_t = BlockType.HEADING
                block = DocumentBlock(
                    block_id=len(blocks) + 1,
                    text=clean_line,
                    block_type=block_t,
                    reading_order=reading_order
                )
                blocks.append(block)
                reading_order += 1
                continue

            # Footer Pattern
            if any(term in clean_line.lower() for term in ["thank you", "visit again", "page ", "authorized sign", "terms & conditions"]):
                block = DocumentBlock(
                    block_id=len(blocks) + 1,
                    text=clean_line,
                    block_type=BlockType.FOOTER,
                    reading_order=reading_order
                )
                blocks.append(block)
                reading_order += 1
                continue

            # Title Fallback (first non-empty block)
            if line_idx == 0 and not title and len(clean_line) < 40:
                title = clean_line
                block = DocumentBlock(
                    block_id=len(blocks) + 1,
                    text=clean_line,
                    block_type=BlockType.TITLE,
                    reading_order=reading_order
                )
                blocks.append(block)
                reading_order += 1
                continue

            # Standard Paragraph
            block = DocumentBlock(
                block_id=len(blocks) + 1,
                text=clean_line,
                block_type=BlockType.PARAGRAPH,
                reading_order=reading_order
            )
            blocks.append(block)
            reading_order += 1

        return blocks, tables, key_values, title

    # -------------------------------------------------------------------------
    # 3. DOCUMENT CLASSIFICATION
    # -------------------------------------------------------------------------

    def classify_document_type(self, text: str) -> DocumentType:
        """
        Classifies document type from raw text.
        """
        text_lower = text.lower()
        if "menu" in text_lower or any(w in text_lower for w in ["cappuccino", "espresso", "latte", "croissant", "appetizer", "main course"]):
            return DocumentType.MENU
        if "bill" in text_lower or "due date" in text_lower or "amount due" in text_lower:
            return DocumentType.BILL
        if "receipt" in text_lower or "invoice" in text_lower or "subtotal" in text_lower or ("total" in text_lower and ("$" in text or "₹" in text)):
            return DocumentType.RECEIPT
        if "form" in text_lower or "registration" in text_lower or "application" in text_lower or "patient" in text_lower:
            return DocumentType.FORM
        if "|" in text and text.count("|") >= 4:
            return DocumentType.TABLE
        if len(text.splitlines()) >= 3 or len(text.split()) >= 15:
            return DocumentType.PAGE
        return DocumentType.UNKNOWN

    def classify_document(
        self,
        blocks: List[DocumentBlock],
        key_values: Dict[str, str],
        full_text: str
    ) -> DocumentType:
        """
        Deterministically classifies document type based on structural and lexical cues.
        """
        text_lower = full_text.lower()
        keys_str = " ".join(key_values.keys())

        if "menu" in text_lower or any(w in text_lower for w in ["cappuccino", "espresso", "latte", "croissant", "starters", "main course", "appetizers", "desserts"]):
            return DocumentType.MENU

        if "bill" in text_lower or "due date" in text_lower or "amount due" in text_lower or "account number" in keys_str:
            return DocumentType.BILL

        receipt_cues = ["total", "subtotal", "tax", "gst", "amount", "invoice", "receipt", "cashier", "qty", "price", "payment", "paid", "due amount"]
        receipt_matches = sum(1 for cue in receipt_cues if cue in text_lower or cue in keys_str)
        if receipt_matches >= 2 or "invoice" in text_lower or "receipt" in text_lower:
            return DocumentType.RECEIPT

        form_cues = ["name", "address", "date of birth", "dob", "gender", "signature", "application", "applicant", "email", "pin code", "patient", "registration"]
        form_matches = sum(1 for cue in form_cues if cue in text_lower or cue in keys_str)
        if form_matches >= 2 or "form" in text_lower:
            return DocumentType.FORM

        if any(b.block_type == BlockType.TABLE for b in blocks) or ("|" in full_text and full_text.count("|") >= 4):
            return DocumentType.TABLE

        sign_cues = ["warning", "caution", "danger", "speed limit", "stop", "exit", "entry", "no parking", "keep out", "nutrition facts", "ingredients"]
        if any(cue in text_lower for cue in sign_cues) or (len(blocks) <= 3 and len(full_text.split()) <= 15):
            return DocumentType.LABEL if any(c in text_lower for c in ["ingredients", "nutrition", "batch", "mfg"]) else DocumentType.SIGN

        if len(blocks) >= 2 or len(full_text.split()) >= 10:
            return DocumentType.PAGE

        return DocumentType.UNKNOWN

    # -------------------------------------------------------------------------
    # 4. FULL DOCUMENT PROCESSING PIPELINE
    # -------------------------------------------------------------------------

    def process_document(
        self,
        frame: Optional[np.ndarray] = None,
        text_lines: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
        source_type: str = "CAMERA",
        current_time: Optional[float] = None
    ) -> DocumentResult:
        """
        Executes complete document understanding pipeline.
        """
        now = current_time if current_time is not None else time.time()
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"

        region = None
        rectified = None

        if frame is not None:
            region = self.detect_document_region(frame)
            is_valid, q_status, q_score, reason = self.assess_quality(frame)
            if not is_valid:
                res = DocumentResult(
                    document_id=doc_id,
                    document_type=DocumentType.UNKNOWN,
                    confidence=0.0,
                    quality_status=q_status,
                    is_blurry=(q_status == "BLURRY"),
                    is_valid=False,
                    has_document=True,
                    reason=reason,
                    region=region if region else DocumentRegion(is_blurry=(q_status == "BLURRY"), is_dark=(q_status == "DARK")),
                    timestamp=now,
                    source_type=source_type
                )
                self.last_result = res
                return res

            if region and len(region.corners) == 4:
                rectified = self.rectify_document(frame, region.corners)
            else:
                rectified = frame

        blocks, tables, key_values, title = self.extract_structure(
            text_lines=text_lines,
            raw_text=raw_text,
            rectified_image=rectified
        )

        if not blocks and not text_lines and not raw_text and (rectified is None or rectified.size == 0):
            res = DocumentResult(
                document_id=doc_id,
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                quality_status="NO_DOCUMENT",
                is_valid=False,
                has_document=False,
                reason="I don't see any document in front of you.",
                timestamp=now,
                source_type=source_type
            )
            self.last_result = res
            return res

        extracted_text = "\n".join([b.text for b in blocks]) if blocks else (raw_text or "\n".join(text_lines or []))
        doc_type = self.classify_document(blocks, key_values, extracted_text)
        summary = self._generate_summary(doc_type, title, blocks, tables, key_values)

        total_val = self._find_total_in_dict(key_values)
        if not total_val and blocks:
            for b in blocks:
                match = re.search(r'\b(?:total|grand\s+total|amount\s+payable|amount|amount\s+due)\s*[:=-]?\s*([₹$€£]?\s*[\d,]+(?:\.\d{2})?)', b.text, re.IGNORECASE)
                if match:
                    total_val = match.group(1).strip()
                    break

        res = DocumentResult(
            document_id=doc_id,
            document_type=doc_type,
            title=title or (doc_type.value.title() if doc_type != DocumentType.UNKNOWN else "Document"),
            blocks=blocks,
            tables=tables,
            key_values=key_values,
            extracted_text=extracted_text,
            raw_text=extracted_text,
            summary=summary,
            total=total_val,
            has_table=bool(tables),
            has_document=True,
            confidence=0.92 if blocks else 0.5,
            quality_status="READY",
            is_valid=True,
            region=region,
            timestamp=now,
            source_type=source_type
        )
        self.last_result = res
        self.last_read_block_index = 0
        return res

    process_frame = process_document

    def _generate_summary(
        self,
        doc_type: DocumentType,
        title: Optional[str],
        blocks: List[DocumentBlock],
        tables: List[DocumentTable],
        key_values: Dict[str, str]
    ) -> str:
        """
        Creates concise spoken natural language summary of document.
        """
        type_str = doc_type.value.lower()
        title_str = f"titled '{title}'" if title else ""

        details = []
        total_val = self._find_total_in_dict(key_values)
        if total_val:
            details.append(f"with a total of {total_val}")

        date_val = self._find_date_in_dict(key_values)
        if date_val:
            details.append(f"dated {date_val}")

        if tables:
            details.append(f"containing a table with {len(tables[0].rows)} rows")

        if details:
            details_str = ", " + ", ".join(details)
        else:
            details_str = f" containing {len(blocks)} sections" if blocks else ""

        if doc_type in (DocumentType.RECEIPT, DocumentType.BILL):
            return f"This is a {type_str} {title_str}{details_str}.".replace("  ", " ")
        elif doc_type == DocumentType.MENU:
            return f"This is a restaurant menu {title_str}{details_str}.".replace("  ", " ")
        elif doc_type == DocumentType.FORM:
            return f"This is a structured form {title_str}{details_str}.".replace("  ", " ")
        elif doc_type in (DocumentType.LABEL, DocumentType.SIGN):
            return f"This is a {type_str} {title_str}: {blocks[0].text if blocks else ''}."
        else:
            return f"This is a document {title_str}{details_str}.".replace("  ", " ")

    # -------------------------------------------------------------------------
    # 5. DETERMINISTIC SPOKEN QUERY ENGINE
    # -------------------------------------------------------------------------

    def answer_document_query(
        self,
        intent: str,
        params: Optional[Dict[str, Any]] = None,
        doc_result: Optional[DocumentResult] = None
    ) -> str:
        """
        Universal entry point for answering natural language document queries.
        """
        active_doc = doc_result or self.last_result

        if not active_doc:
            return "I cannot see a clear document in front of you."

        if not active_doc.is_valid:
            if active_doc.is_blurry or active_doc.quality_status == "BLURRY":
                return "The document is too blurry to read clearly. Please hold the document still."
            if active_doc.quality_status == "DARK":
                return "The document is too dark to read. Please improve the lighting."
            return active_doc.reason or "I cannot see a clear document in front of you."

        # Cache active doc for repetition
        self.last_result = active_doc
        p = params or {}

        if intent == "DOCUMENT_READ":
            return self.query_read(doc=active_doc)
        elif intent == "DOCUMENT_SUMMARY":
            return self.query_summary(doc=active_doc)
        elif intent == "DOCUMENT_TITLE":
            return self.query_title(doc=active_doc)
        elif intent == "DOCUMENT_TOTAL":
            return self.query_total(doc=active_doc)
        elif intent == "DOCUMENT_FIELDS":
            return self.query_fields(doc=active_doc)
        elif intent == "DOCUMENT_TABLE":
            return self.query_table(query_str=p.get("query", ""), doc=active_doc)
        elif intent == "DOCUMENT_SEARCH":
            term = p.get("query") or p.get("term") or p.get("keyword") or ""
            return self.query_search(keyword=term, doc=active_doc)
        elif intent == "DOCUMENT_REPEAT":
            return self.query_repeat(doc=active_doc)
        elif intent == "DOCUMENT_CLEAR":
            return self.clear_document()
        else:
            return self.query_summary(doc=active_doc)

    def query_read(self, max_blocks: int = 5, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."
        if not active.blocks and not active.extracted_text:
            return "The document contains no readable text."

        if active.blocks:
            selected = active.blocks[:max_blocks]
            self.last_read_block_index = len(selected) - 1
            lines = [b.text for b in selected]
            body = ". ".join(lines)
        else:
            body = active.extracted_text

        return f"The document says: {body}"

    def query_summary(self, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."
        return active.summary or "This is a document."

    def query_title(self, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."
        if active.title:
            return f"The document title is {active.title}."
        return f"This is a {active.document_type.value.lower()}."

    def query_total(self, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."

        if active.total:
            return f"The total is {active.total}."

        tot = self._find_total_in_dict(active.key_values)
        if tot:
            return f"The total is {tot}."

        for b in active.blocks:
            match = re.search(r'\b(?:total|grand\s+total|amount\s+payable|net\s+amount|balance\s+due|amount\s+due)\s*[:=-]?\s*([₹$€£]?\s*[\d,]+(?:\.\d{2})?)', b.text, re.IGNORECASE)
            if match:
                return f"The total is {match.group(1).strip()}."

        return "I couldn't reliably read the total."

    def _find_total_in_dict(self, kv: Dict[str, str]) -> Optional[str]:
        for k in ["total", "grand total", "net amount", "amount payable", "total amount", "amount", "balance due", "subtotal", "amount due", "total due"]:
            if k in kv:
                return kv[k]
        return None

    def _find_date_in_dict(self, kv: Dict[str, str]) -> Optional[str]:
        for k in ["date", "bill date", "invoice date", "order date", "issued on", "dated", "due date"]:
            if k in kv:
                return kv[k]
        return None

    def query_fields(self, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."
        if not active.key_values:
            return "No structured fields were found on this document."
        fields_list = [f"{k.title()}: {v}" for k, v in list(active.key_values.items())[:6]]
        return "Key fields: " + ", ".join(fields_list) + "."

    def query_table(self, query_str: str = "", doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."
        if not active.tables:
            return "I can read some text, but I couldn't reliably determine the table structure."

        table = active.tables[0]
        return table.to_verbal_summary()

    def query_search(self, keyword: str, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "I don't see any document in front of you."

        clean_kw = keyword.strip().lower()
        if not clean_kw:
            return "Please specify a word or phrase to find."

        matches = []
        for b in active.blocks:
            if clean_kw in b.text.lower():
                matches.append(b.text)

        if not matches and active.extracted_text and clean_kw in active.extracted_text.lower():
            matches = [line for line in active.extracted_text.splitlines() if clean_kw in line.lower()]

        if matches:
            return f"Found '{keyword}': " + "; ".join(matches[:3]) + "."
        return f"I could not find '{keyword}' on the document."

    def query_repeat(self, doc: Optional[DocumentResult] = None) -> str:
        active = doc or self.last_result
        if not active or not active.is_valid:
            return "No previous line to repeat."
        if active.summary:
            return active.summary
        return "No previous line to repeat."

    def clear_document(self) -> str:
        self.last_result = None
        self.last_read_block_index = 0
        return "Cleared document context."

    def get_hud_status(self, doc_result: Optional[DocumentResult] = None) -> Dict[str, Any]:
        """
        Returns compact document understanding status for the HUD panel.
        """
        active = doc_result or self.last_result
        if not active or not active.has_document or not active.is_valid:
            return {
                "has_document": False,
                "document_type": "NONE",
                "title": None,
                "quality_status": active.quality_status if active else "NO_DOCUMENT",
                "confidence": 0.0
            }
        return {
            "has_document": True,
            "document_type": active.document_type.value if hasattr(active.document_type, "value") else str(active.document_type),
            "title": active.title,
            "quality_status": active.quality_status,
            "confidence": active.confidence,
            "blocks_count": len(active.blocks),
            "tables_count": len(active.tables),
            "has_total": bool(active.total)
        }
