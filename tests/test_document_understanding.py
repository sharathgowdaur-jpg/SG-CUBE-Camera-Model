"""
SG CUBE 2.5 — Feature 8: Intelligent Document Understanding Automated Test Suite
Authoritative tests for document boundary detection, perspective warping,
quality gate, block classification, reading-order sorting, deterministic query engine,
PII redaction, continuous conversation context, and zero-hallucination guarantees.
"""

import time
import pytest
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

from assistive.document_understanding import (
    DocumentType,
    BlockType,
    DocumentRegion,
    DocumentBlock,
    DocumentTable,
    DocumentResult,
    DocumentUnderstandingEngine,
    redact_sensitive_document_text
)
from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActiveDocumentRef
)
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.command_router import CommandRouter


# -----------------------------------------------------------------------------
# HELPER: Synthetic Document Frame Generator
# -----------------------------------------------------------------------------
def create_synthetic_document_image(
    doc_type: str = "RECEIPT",
    width: int = 800,
    height: int = 600,
    skew_angle: float = 0.0,
    blur: bool = False,
    dark: bool = False
) -> np.ndarray:
    """
    Generates a realistic synthetic camera frame containing a rectangular document.
    """
    # Background: textured desk (dark grey)
    bg = np.full((height, width, 3), 40, dtype=np.uint8)

    # Document canvas (white paper)
    doc_w, doc_h = 360, 480
    doc_img = Image.new("RGB", (doc_w, doc_h), (250, 250, 250))
    draw = ImageDraw.Draw(doc_img)

    if doc_type == "RECEIPT":
        draw.text((20, 20), "SUPERMART STORE", fill=(0, 0, 0))
        draw.text((20, 50), "Date: 2026-09-22", fill=(0, 0, 0))
        draw.text((20, 80), "Invoice: #INV-9821", fill=(0, 0, 0))
        draw.line([(20, 110), (340, 110)], fill=(0, 0, 0), width=2)
        draw.text((20, 130), "Milk          $3.50", fill=(0, 0, 0))
        draw.text((20, 160), "Bread         $2.00", fill=(0, 0, 0))
        draw.text((20, 190), "Eggs          $4.50", fill=(0, 0, 0))
        draw.line([(20, 220), (340, 220)], fill=(0, 0, 0), width=2)
        draw.text((20, 240), "Total Amount: $10.00", fill=(0, 0, 0))
        draw.text((20, 300), "Thank you for shopping!", fill=(0, 0, 0))

    elif doc_type == "BILL":
        draw.text((20, 20), "CITY ELECTRICITY BILL", fill=(0, 0, 0))
        draw.text((20, 60), "Account No: 123456789", fill=(0, 0, 0))
        draw.text((20, 90), "Due Date: Oct 15 2026", fill=(0, 0, 0))
        draw.text((20, 130), "Current Usage: 420 kWh", fill=(0, 0, 0))
        draw.text((20, 170), "Amount Due: $84.50", fill=(0, 0, 0))
        draw.text((20, 220), "Total: $84.50", fill=(0, 0, 0))

    elif doc_type == "MENU":
        draw.text((20, 20), "BELLA CAFE MENU", fill=(0, 0, 0))
        draw.text((20, 60), "Espresso      $3.00", fill=(0, 0, 0))
        draw.text((20, 90), "Cappuccino    $4.50", fill=(0, 0, 0))
        draw.text((20, 120), "Croissant     $3.50", fill=(0, 0, 0))
        draw.text((20, 150), "Avocado Toast $7.00", fill=(0, 0, 0))

    elif doc_type == "TABLE":
        draw.text((20, 20), "QUARTERLY SALES REPORT", fill=(0, 0, 0))
        draw.text((20, 70), "Quarter | Revenue | Profit", fill=(0, 0, 0))
        draw.line([(20, 95), (340, 95)], fill=(0, 0, 0), width=2)
        draw.text((20, 110), "Q1      | $10,000 | $2,000", fill=(0, 0, 0))
        draw.text((20, 140), "Q2      | $15,000 | $3,500", fill=(0, 0, 0))
        draw.text((20, 170), "Q3      | $20,000 | $5,000", fill=(0, 0, 0))

    elif doc_type == "FORM":
        draw.text((20, 20), "PATIENT REGISTRATION FORM", fill=(0, 0, 0))
        draw.text((20, 60), "Full Name: John Doe", fill=(0, 0, 0))
        draw.text((20, 90), "Date of Birth: 1990-01-01", fill=(0, 0, 0))
        draw.text((20, 120), "Phone: 555-0199", fill=(0, 0, 0))

    doc_np = np.array(doc_img)

    # Place document at center of frame
    x_off = (width - doc_w) // 2
    y_off = (height - doc_h) // 2
    bg[y_off:y_off+doc_h, x_off:x_off+doc_w] = doc_np

    if dark:
        bg = (bg * 0.15).astype(np.uint8)

    if blur:
        bg = cv2.GaussianBlur(bg, (35, 35), 10.0)

    return bg


# =============================================================================
# TEST SUITE
# =============================================================================

# -----------------------------------------------------------------------------
# CATEGORY A: Perspective Rectification & Corner Ordering
# -----------------------------------------------------------------------------
class TestCategoryA_PerspectiveRectification:
    def test_A1_order_corners_clockwise(self):
        engine = DocumentUnderstandingEngine()
        pts = np.array([[300, 400], [100, 100], [300, 100], [100, 400]], dtype=np.float32)
        ordered = engine.order_corners(pts)
        assert np.array_equal(ordered[0], [100, 100])  # Top-Left
        assert np.array_equal(ordered[1], [300, 100])  # Top-Right
        assert np.array_equal(ordered[2], [300, 400])  # Bottom-Right
        assert np.array_equal(ordered[3], [100, 400])  # Bottom-Left

    def test_A2_warp_perspective_dimensions(self):
        engine = DocumentUnderstandingEngine()
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        corners = np.array([[100, 100], [400, 100], [400, 400], [100, 400]], dtype=np.float32)
        warped = engine.warp_perspective(img, corners)
        assert warped is not None
        assert warped.shape[0] > 200
        assert warped.shape[1] > 200

    def test_A3_warp_perspective_invalid_corners(self):
        engine = DocumentUnderstandingEngine()
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Less than 4 corners
        pts = np.array([[100, 100], [200, 200]], dtype=np.float32)
        warped = engine.warp_perspective(img, pts)
        assert warped is not None
        assert np.array_equal(warped, img)

    def test_A4_detect_document_region(self):
        engine = DocumentUnderstandingEngine()
        frame = create_synthetic_document_image(doc_type="RECEIPT")
        region = engine.detect_document_region(frame)
        assert region is not None
        assert len(region.corners) == 4
        assert region.bounding_box[2] > 200  # width
        assert region.bounding_box[3] > 300  # height


# -----------------------------------------------------------------------------
# CATEGORY B: Document Quality Assessment & Blur Gate
# -----------------------------------------------------------------------------
class TestCategoryB_QualityGate:
    def test_B1_sharp_image_passes_quality_gate(self):
        engine = DocumentUnderstandingEngine()
        frame = create_synthetic_document_image(doc_type="RECEIPT")
        is_blurry, var = engine.assess_blur(frame)
        assert not is_blurry
        assert var > 50.0

    def test_B2_blurry_image_detected(self):
        engine = DocumentUnderstandingEngine()
        frame = create_synthetic_document_image(doc_type="RECEIPT", blur=True)
        is_blurry, var = engine.assess_blur(frame)
        assert is_blurry
        assert var < 50.0

    def test_B3_dark_image_detected(self):
        engine = DocumentUnderstandingEngine()
        frame = create_synthetic_document_image(doc_type="RECEIPT", dark=True)
        is_dark, b_val, c_val = engine.assess_lighting(frame)
        assert is_dark
        assert b_val < 50.0

    def test_B4_process_frame_blurry_returns_quality_warning(self):
        engine = DocumentUnderstandingEngine()
        frame = create_synthetic_document_image(doc_type="RECEIPT", blur=True)
        res = engine.process_frame(frame)
        assert res.has_document
        assert res.region.is_blurry
        # Quality warning in query
        ans = engine.answer_document_query("DOCUMENT_READ", doc_result=res)
        assert "blurry" in ans.lower() or "hold the document still" in ans.lower()


# -----------------------------------------------------------------------------
# CATEGORY C: Reading-Order Sorting & Spatial Geometry
# -----------------------------------------------------------------------------
class TestCategoryC_ReadingOrder:
    def test_C1_single_column_top_to_bottom(self):
        engine = DocumentUnderstandingEngine()
        blocks = [
            DocumentBlock(block_id=1, text="Bottom Line", bounding_box=(20, 300, 100, 20)),
            DocumentBlock(block_id=2, text="Top Title", bounding_box=(20, 20, 100, 20)),
            DocumentBlock(block_id=3, text="Middle Line", bounding_box=(20, 150, 100, 20)),
        ]
        sorted_b = engine.sort_reading_order(blocks)
        assert sorted_b[0].text == "Top Title"
        assert sorted_b[1].text == "Middle Line"
        assert sorted_b[2].text == "Bottom Line"

    def test_C2_multi_column_left_to_right(self):
        engine = DocumentUnderstandingEngine()
        blocks = [
            DocumentBlock(block_id=1, text="Right Column", bounding_box=(400, 50, 100, 20)),
            DocumentBlock(block_id=2, text="Left Column", bounding_box=(50, 50, 100, 20)),
        ]
        sorted_b = engine.sort_reading_order(blocks)
        assert sorted_b[0].text == "Left Column"
        assert sorted_b[1].text == "Right Column"

    def test_C3_reading_order_indices_sequential(self):
        engine = DocumentUnderstandingEngine()
        blocks = [
            DocumentBlock(block_id=1, text="C", bounding_box=(20, 200, 100, 20)),
            DocumentBlock(block_id=2, text="A", bounding_box=(20, 20, 100, 20)),
            DocumentBlock(block_id=3, text="B", bounding_box=(20, 100, 100, 20)),
        ]
        sorted_b = engine.sort_reading_order(blocks)
        assert [b.reading_order for b in sorted_b] == [0, 1, 2]

    def test_C4_empty_blocks_sorting(self):
        engine = DocumentUnderstandingEngine()
        assert engine.sort_reading_order([]) == []


# -----------------------------------------------------------------------------
# CATEGORY D: Document Layout Categorization / Block Types
# -----------------------------------------------------------------------------
class TestCategoryD_LayoutCategorization:
    def test_D1_title_block_classification(self):
        engine = DocumentUnderstandingEngine()
        block = DocumentBlock(block_id=1, text="SUPERMART INVOICE", bounding_box=(50, 20, 300, 40))
        classified = engine.classify_block(block, doc_height=600)
        assert classified.block_type in (BlockType.TITLE, BlockType.HEADING)

    def test_D2_key_value_block_classification(self):
        engine = DocumentUnderstandingEngine()
        block = DocumentBlock(block_id=1, text="Total: $45.00", bounding_box=(50, 200, 200, 20))
        classified = engine.classify_block(block, doc_height=600)
        assert classified.block_type == BlockType.KEY_VALUE
        assert classified.key == "total"
        assert classified.value == "$45.00"

    def test_D3_list_block_classification(self):
        engine = DocumentUnderstandingEngine()
        block = DocumentBlock(block_id=1, text="1. Fresh Apples", bounding_box=(50, 150, 200, 20))
        classified = engine.classify_block(block, doc_height=600)
        assert classified.block_type == BlockType.LIST

    def test_D4_footer_block_classification(self):
        engine = DocumentUnderstandingEngine()
        block = DocumentBlock(block_id=1, text="Thank you for your visit!", bounding_box=(50, 560, 300, 20))
        classified = engine.classify_block(block, doc_height=600)
        assert classified.block_type == BlockType.FOOTER


# -----------------------------------------------------------------------------
# CATEGORY E: Deterministic Document Type Classification
# -----------------------------------------------------------------------------
class TestCategoryE_DocumentClassification:
    def test_E1_classify_receipt(self):
        engine = DocumentUnderstandingEngine()
        text = "SUPERMART STORE\nDate: 2026-09-22\nInvoice: #1234\nSubtotal: $10.00\nTax: $0.80\nTotal Amount: $10.80\nThank you"
        dtype = engine.classify_document_type(text)
        assert dtype == DocumentType.RECEIPT

    def test_E2_classify_bill(self):
        engine = DocumentUnderstandingEngine()
        text = "ELECTRICITY UTILITY BILL\nAccount Number: 987654321\nDue Date: Oct 20\nAmount Due: $125.40\nTotal Due: $125.40"
        dtype = engine.classify_document_type(text)
        assert dtype == DocumentType.BILL

    def test_E3_classify_menu(self):
        engine = DocumentUnderstandingEngine()
        text = "CAFE MENU\nBeverages\nCappuccino $4.00\nLatte $4.50\nDessert\nCheesecake $6.00"
        dtype = engine.classify_document_type(text)
        assert dtype == DocumentType.MENU

    def test_E4_classify_form(self):
        engine = DocumentUnderstandingEngine()
        text = "PATIENT APPLICATION FORM\nFull Name: [       ]\nDate of Birth: [       ]\nSignature: _______"
        dtype = engine.classify_document_type(text)
        assert dtype == DocumentType.FORM

    def test_E5_classify_table(self):
        engine = DocumentUnderstandingEngine()
        text = "QUARTERLY FINANCIAL REPORT\nQuarter | Revenue | Profit\nQ1 | $1000 | $200\nQ2 | $1500 | $300\nQ3 | $2000 | $400"
        dtype = engine.classify_document_type(text)
        assert dtype == DocumentType.TABLE

    def test_E6_classify_page_fallback(self):
        engine = DocumentUnderstandingEngine()
        text = "Chapter 1. Introduction to artificial intelligence and perception."
        dtype = engine.classify_document_type(text)
        assert dtype in (DocumentType.PAGE, DocumentType.UNKNOWN)


# -----------------------------------------------------------------------------
# CATEGORY F: Table Structure Extraction
# -----------------------------------------------------------------------------
class TestCategoryF_TableExtraction:
    def test_F1_extract_pipe_separated_table(self):
        engine = DocumentUnderstandingEngine()
        raw_text = "Item | Qty | Price\nMilk | 2 | $4.00\nBread | 1 | $2.50\nEggs | 12 | $3.00"
        table = engine.extract_table_from_text(raw_text)
        assert table is not None
        assert len(table.headers) == 3
        assert len(table.rows) == 3
        assert table.rows[0] == ["Milk", "2", "$4.00"]

    def test_F2_extract_aligned_column_table(self):
        engine = DocumentUnderstandingEngine()
        raw_text = "Product       Qty    Price\nApple         5      $5.00\nOrange        3      $3.00"
        table = engine.extract_table_from_text(raw_text)
        assert table is not None
        assert len(table.rows) >= 2

    def test_F3_read_table_verbal_format(self):
        table = DocumentTable(
            headers=["Item", "Price"],
            rows=[["Milk", "$3.50"], ["Bread", "$2.00"]]
        )
        verbal = table.to_verbal_summary()
        assert "Table has 2 rows" in verbal
        assert "Row 1: Item is Milk, Price is $3.50" in verbal
        assert "Row 2: Item is Bread, Price is $2.00" in verbal

    def test_F4_no_table_detected_graceful_handling(self):
        engine = DocumentUnderstandingEngine()
        raw_text = "This is just a regular paragraph of plain text without columns or tables."
        table = engine.extract_table_from_text(raw_text)
        assert table is None


# -----------------------------------------------------------------------------
# CATEGORY G: Deterministic Spoken Query Answering
# -----------------------------------------------------------------------------
class TestCategoryG_DeterministicQueryAnswering:
    @pytest.fixture
    def sample_receipt_result(self):
        return DocumentResult(
            has_document=True,
            document_type=DocumentType.RECEIPT,
            title="Supermart Store",
            raw_text="Supermart Store\nDate: 2026-09-22\nInvoice: #9821\nMilk: $3.50\nBread: $2.00\nTotal: $5.50\nThank you!",
            summary="Receipt from Supermart Store with total $5.50.",
            key_values={"date": "2026-09-22", "invoice": "#9821", "total": "$5.50"},
            total="$5.50"
        )

    def test_G1_query_document_read(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_READ", doc_result=sample_receipt_result)
        assert "The document says" in ans
        assert "Supermart Store" in ans
        assert "Total: $5.50" in ans

    def test_G2_query_document_summary(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_SUMMARY", doc_result=sample_receipt_result)
        assert "Receipt" in ans
        assert "Supermart Store" in ans
        assert "$5.50" in ans

    def test_G3_query_document_title(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_TITLE", doc_result=sample_receipt_result)
        assert "Supermart Store" in ans

    def test_G4_query_document_total(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_TOTAL", doc_result=sample_receipt_result)
        assert "$5.50" in ans

    def test_G5_query_document_fields(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_FIELDS", doc_result=sample_receipt_result)
        assert "date: 2026-09-22" in ans.lower()
        assert "total: $5.50" in ans.lower()

    def test_G6_query_document_table(self):
        engine = DocumentUnderstandingEngine()
        table_doc = DocumentResult(
            has_document=True,
            document_type=DocumentType.TABLE,
            title="Sales Report",
            raw_text="Quarter | Revenue\nQ1 | $1000\nQ2 | $2000",
            tables=[DocumentTable(headers=["Quarter", "Revenue"], rows=[["Q1", "$1000"], ["Q2", "$2000"]])]
        )
        ans = engine.answer_document_query("DOCUMENT_TABLE", doc_result=table_doc)
        assert "Table has 2 rows" in ans
        assert "Q1" in ans

    def test_G7_query_document_search(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_SEARCH", params={"query": "Milk"}, doc_result=sample_receipt_result)
        assert "Found 'Milk'" in ans
        assert "$3.50" in ans

    def test_G8_query_document_repeat(self, sample_receipt_result):
        engine = DocumentUnderstandingEngine()
        # First query
        engine.answer_document_query("DOCUMENT_SUMMARY", doc_result=sample_receipt_result)
        # Repeat query
        repeat_ans = engine.answer_document_query("DOCUMENT_REPEAT", doc_result=sample_receipt_result)
        assert "Receipt" in repeat_ans


# -----------------------------------------------------------------------------
# CATEGORY H: Conversation Context & Multi-Turn Pronoun Resolution
# -----------------------------------------------------------------------------
class TestCategoryH_ConversationContext:
    def test_H1_active_document_set_and_summary(self):
        ctx = ConversationContextManager()
        ctx.set_active_document(
            doc_type="RECEIPT",
            title="Supermart Store",
            summary="Receipt from Supermart Store with total $10.00.",
            total="$10.00"
        )
        summary = ctx.get_context_summary()
        assert summary["topic"] == "Document Understanding"
        assert summary["active_entity"] == "Supermart Store"
        assert summary["is_active"]

    def test_H2_resolve_document_pronoun_reference(self):
        ctx = ConversationContextManager()
        ctx.set_active_document(
            doc_type="RECEIPT",
            title="Supermart Store",
            total="$10.00"
        )
        target, ent_type, is_amb, prompt = ctx.resolve_reference("What is the total on that document?")
        assert target == "Supermart Store"
        assert ent_type == "document"
        assert not is_amb

    def test_H3_resolve_followup_document_query(self):
        ctx = ConversationContextManager()
        ctx.set_active_document(
            doc_type="RECEIPT",
            title="Supermart Store",
            total="$10.00"
        )
        followup = ctx.resolve_followup_intent("What is the total?")
        assert followup["is_followup"]
        assert followup["intent"] == "DOCUMENT_TOTAL"
        assert followup["resolved_target"] == "Supermart Store"

    def test_H4_document_context_ttl_expiration(self):
        ctx = ConversationContextManager()
        t0 = 1000.0
        ctx.set_active_document(doc_type="BILL", title="Electric Bill", current_time=t0)
        # Check within TTL (300s)
        ctx.prune_stale(current_time=t0 + 200.0)
        assert ctx.active_document is not None
        # Check past TTL
        ctx.prune_stale(current_time=t0 + 350.0)
        assert ctx.active_document is None


# -----------------------------------------------------------------------------
# CATEGORY I: Sensitive PII & Secret Redaction
# -----------------------------------------------------------------------------
class TestCategoryI_SensitiveRedaction:
    def test_I1_redact_credit_card_number(self):
        raw = "Payment Card: 4532 1188 9922 4433 Total: $50"
        redacted = redact_sensitive_document_text(raw)
        assert "4532 1188 9922 4433" not in redacted
        assert "[REDACTED_CARD]" in redacted

    def test_I2_redact_aadhaar_number(self):
        raw = "Resident Aadhaar: 9876 5432 1098 DOB: 1990"
        redacted = redact_sensitive_document_text(raw)
        assert "9876 5432 1098" not in redacted
        assert "[REDACTED_AADHAAR]" in redacted

    def test_I3_redact_pan_card(self):
        raw = "Tax Identifier PAN: ABCDE1234F Status: Active"
        redacted = redact_sensitive_document_text(raw)
        assert "ABCDE1234F" not in redacted
        assert "[REDACTED_PAN]" in redacted

    def test_I4_redact_passwords_and_api_keys(self):
        raw = "WiFi Password: SecretPass123! and API Key: AIzaSyD98234712093847"
        redacted = redact_sensitive_document_text(raw)
        assert "SecretPass123!" not in redacted
        assert "[REDACTED_CREDENTIAL]" in redacted


# -----------------------------------------------------------------------------
# CATEGORY J: Security Manager SAFE Policy Integration
# -----------------------------------------------------------------------------
class TestCategoryJ_SecurityPolicy:
    def test_J1_document_queries_are_safe_level(self):
        sec = SecurityManager()
        doc_intents = [
            "DOCUMENT_READ",
            "DOCUMENT_SUMMARY",
            "DOCUMENT_TITLE",
            "DOCUMENT_FIELDS",
            "DOCUMENT_TABLE",
            "DOCUMENT_TOTAL",
            "DOCUMENT_SEARCH",
            "DOCUMENT_REPEAT",
            "DOCUMENT_CLEAR"
        ]
        for intent in doc_intents:
            assert sec.get_security_level(intent) == SecurityLevel.SAFE

    def test_J2_command_router_maps_document_intents(self):
        router = CommandRouter()
        queries = [
            ("read this document", "DOCUMENT_READ"),
            ("summarize this receipt", "DOCUMENT_SUMMARY"),
            ("what is the total amount", "DOCUMENT_TOTAL"),
            ("what is the title", "DOCUMENT_TITLE"),
            ("read the table", "DOCUMENT_TABLE"),
            ("extract fields", "DOCUMENT_FIELDS"),
            ("clear document", "DOCUMENT_CLEAR"),
            ("repeat that document", "DOCUMENT_REPEAT")
        ]
        for q, expected_intent in queries:
            route = router.route_intent(q)
            assert route["intent"] == expected_intent, f"Failed for query: '{q}'"

    def test_J3_router_in_document_search(self):
        router = CommandRouter()
        route = router.route_intent("search for invoice in the document")
        assert route["intent"] == "DOCUMENT_SEARCH"
        assert route["target"] == "invoice"


# -----------------------------------------------------------------------------
# CATEGORY K: Truthful Uncertainty & Zero Hallucination
# -----------------------------------------------------------------------------
class TestCategoryK_TruthfulUncertainty:
    def test_K1_no_document_in_view(self):
        engine = DocumentUnderstandingEngine()
        ans = engine.answer_document_query("DOCUMENT_READ", doc_result=None)
        assert "I cannot see a clear document" in ans

    def test_K2_missing_total_truthful_response(self):
        engine = DocumentUnderstandingEngine()
        doc = DocumentResult(
            has_document=True,
            document_type=DocumentType.PAGE,
            title="General Notes",
            raw_text="Just some notes without any numbers or totals.",
            total=None
        )
        ans = engine.answer_document_query("DOCUMENT_TOTAL", doc_result=doc)
        assert "couldn't reliably read the total" in ans.lower()

    def test_K3_missing_table_truthful_response(self):
        engine = DocumentUnderstandingEngine()
        doc = DocumentResult(
            has_document=True,
            document_type=DocumentType.PAGE,
            title="Plain Page",
            raw_text="Simple paragraph.",
            tables=[]
        )
        ans = engine.answer_document_query("DOCUMENT_TABLE", doc_result=doc)
        assert "couldn't reliably determine the table structure" in ans.lower()

    def test_K4_search_term_not_found_truthful_response(self):
        engine = DocumentUnderstandingEngine()
        doc = DocumentResult(
            has_document=True,
            document_type=DocumentType.RECEIPT,
            title="Supermart",
            raw_text="Milk $3.50, Bread $2.00"
        )
        ans = engine.answer_document_query("DOCUMENT_SEARCH", params={"query": "Shampoo"}, doc_result=doc)
        assert "could not find 'Shampoo'" in ans
