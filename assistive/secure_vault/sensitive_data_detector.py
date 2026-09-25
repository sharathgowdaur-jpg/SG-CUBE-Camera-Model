"""
SG CUBE Secure Memory — Isolated Sensitive Data Detector
Provides offline, deterministic classification and detection of sensitive personal,
financial, identity, credential, and confidential information.

This module is completely isolated and does not modify, call, or depend on
existing SG CUBE modules, normal memory, or external cloud services.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple, NamedTuple


class SensitiveCategory(str, Enum):
    CREDENTIAL = "CREDENTIAL"            # Passwords, passcodes, recovery codes, auth tokens
    PIN = "PIN"                          # Numeric PINs (ATM, UPI, app PINs)
    AADHAAR = "AADHAAR"                  # Indian 12-digit Aadhaar UIDAI numbers
    PAN = "PAN"                          # Indian 10-character alphanumeric PAN cards
    BANK_ACCOUNT = "BANK_ACCOUNT"        # Bank accounts, IBAN, SWIFT, routing codes, IFSC
    CARD_NUMBER = "CARD_NUMBER"          # Credit / Debit card numbers (15-16 digits)
    API_KEY = "API_KEY"                  # API tokens, secret keys, private keys, bearer tokens
    CONFIDENTIAL = "CONFIDENTIAL"        # User-marked confidential / sensitive notes
    GENERAL = "GENERAL"                  # Non-sensitive personal facts or statements


class SensitiveClassification(NamedTuple):
    is_sensitive: bool
    category: SensitiveCategory
    confidence: float
    detected_pattern_name: str
    redacted_preview: str  # Safe preview with all sensitive numbers/secrets replaced by masks


def _validate_verhoeff(num_str: str) -> bool:
    """
    Validates a 12-digit Aadhaar number using the Verhoeff multiplication & permutation table.
    """
    d_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]
    p_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]
    digits = [int(c) for c in reversed(num_str) if c.isdigit()]
    if len(digits) != 12:
        return False
    c = 0
    for i, digit in enumerate(digits):
        c = d_table[c][p_table[i % 8][digit]]
    return c == 0


def _validate_luhn(card_str: str) -> bool:
    """ Validates 13 to 19 digit card numbers using Luhn checksum algorithm """
    digits = [int(c) for c in card_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class SensitiveDataDetector:
    """
    Offline detector identifying sensitive data patterns without network calls or LLM dependencies.
    """

    # 1. API Keys & Secrets
    API_KEY_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("GOOGLE_API_KEY", re.compile(r'\bAIza[0-9A-Za-z\-_]{35}\b')),
        ("AWS_ACCESS_KEY", re.compile(r'\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b')),
        ("PRIVATE_KEY_HEADER", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
        ("RECOVERY_CODE", re.compile(r'\bRC-[A-Z0-9]{4}-[A-Z0-9]{4}\b', re.IGNORECASE)),
        ("GENERIC_SECRET_LABEL", re.compile(
            r'\b(?:api[_\s]?key|secret[_\s]?key|access[_\s]?token|auth[_\s]?token|private[_\s]?key|jwt[_\s]?token|bearer[_\s]?token)\b',
            re.IGNORECASE
        )),
    ]

    # 2. Passwords & Passcodes
    CREDENTIAL_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("PASSWORD_KEYWORD", re.compile(
            r'\b(?:password|passcode|voice security password|master password|login password|wifi password|app password)\b',
            re.IGNORECASE
        )),
    ]

    # 3. Numeric PINs
    PIN_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("PIN_KEYWORD", re.compile(
            r'\b(?:pin number|atm pin|upi pin|security pin|secret pin)\b',
            re.IGNORECASE
        )),
        ("PIN_DECLARATION", re.compile(
            r'\b(?:pin|passcode)\s+(?:is\s+|:\s*)?([0-9]{4,8})\b',
            re.IGNORECASE
        )),
    ]

    # 4. Indian Identity: Aadhaar
    AADHAAR_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("AADHAAR_KEYWORD", re.compile(r'\b(?:aadhaar|aadhar|uidai|adhaar)\b', re.IGNORECASE)),
        ("AADHAAR_NUMBER_FORMAT", re.compile(r'\b[2-9][0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b')),
    ]

    # 5. Indian Identity: PAN Card
    PAN_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("PAN_KEYWORD", re.compile(r'\b(?:pan card|pan number|permanent account number)\b', re.IGNORECASE)),
        ("PAN_FORMAT", re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', re.IGNORECASE)),
    ]

    # 6. Financial & Bank Accounts
    BANK_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("BANK_KEYWORD", re.compile(
            r'\b(?:bank account|account number|checking account|savings account|routing number|iban|swift code|ifsc code)\b',
            re.IGNORECASE
        )),
        ("IFSC_FORMAT", re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', re.IGNORECASE)),
        ("IBAN_FORMAT", re.compile(r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b', re.IGNORECASE)),
    ]

    # 7. Credit & Debit Cards
    CARD_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("CARD_KEYWORD", re.compile(r'\b(?:credit card|debit card|cvv|cvv2|card security code|exp date|expiration date)\b', re.IGNORECASE)),
        ("CARD_NUMBER_16", re.compile(r'\b(?:4[0-9]{3}|5[1-5][0-9]{2}|6011|3[47][0-9]{2})[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{3,4}\b')),
    ]

    # 8. User-Marked Confidential Notes
    CONFIDENTIAL_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("CONFIDENTIAL_KEYWORD", re.compile(
            r'\b(?:confidential note|private note|sensitive note|top secret|strictly confidential|keep this secret|keep this confidential|store in secure vault|save in secure vault)\b',
            re.IGNORECASE
        )),
        ("INTERNATIONAL_ID", re.compile(
            r'\b(?:social security|ssn|national id|passport number|driver[s\']?\s*license)\b',
            re.IGNORECASE
        )),
    ]

    @classmethod
    def detect(cls, text: str) -> SensitiveClassification:
        """
        Analyzes the given text for sensitive data and returns a classification.
        Does NOT store or log the input text.
        """
        if not text or not text.strip():
            return SensitiveClassification(
                is_sensitive=False,
                category=SensitiveCategory.GENERAL,
                confidence=0.0,
                detected_pattern_name="EMPTY_INPUT",
                redacted_preview=""
            )

        clean = text.strip()

        # 1. API Keys & Secrets
        for name, pat in cls.API_KEY_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.API_KEY,
                    confidence=0.98,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 2. Passwords / Passcodes
        for name, pat in cls.CREDENTIAL_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.CREDENTIAL,
                    confidence=0.95,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 3. Numeric PINs
        for name, pat in cls.PIN_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.PIN,
                    confidence=0.92,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 4. Aadhaar Detection
        has_aadhaar_kw = any(pat.search(clean) for _, pat in cls.AADHAAR_PATTERNS if "KEYWORD" in _)
        num_match = re.search(r'\b([2-9][0-9]{3})[\s\-]?([0-9]{4})[\s\-]?([0-9]{4})\b', clean)
        if num_match:
            raw_digits = "".join(num_match.groups())
            if _validate_verhoeff(raw_digits) or has_aadhaar_kw:
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.AADHAAR,
                    confidence=0.99 if _validate_verhoeff(raw_digits) else 0.90,
                    detected_pattern_name="AADHAAR_NUMBER",
                    redacted_preview=cls.mask_sensitive(clean)
                )
        elif has_aadhaar_kw:
            return SensitiveClassification(
                is_sensitive=True,
                category=SensitiveCategory.AADHAAR,
                confidence=0.88,
                detected_pattern_name="AADHAAR_KEYWORD",
                redacted_preview=cls.mask_sensitive(clean)
            )

        # 5. PAN Card Detection
        for name, pat in cls.PAN_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.PAN,
                    confidence=0.95,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 6. Credit & Debit Cards
        for name, pat in cls.CARD_PATTERNS:
            match = pat.search(clean)
            if match:
                raw_num = re.sub(r'[\s\-]', '', match.group(0))
                if raw_num.isdigit() and len(raw_num) >= 13:
                    if _validate_luhn(raw_num):
                        return SensitiveClassification(
                            is_sensitive=True,
                            category=SensitiveCategory.CARD_NUMBER,
                            confidence=0.99,
                            detected_pattern_name="VALIDATED_CARD_NUMBER",
                            redacted_preview=cls.mask_sensitive(clean)
                        )
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.CARD_NUMBER,
                    confidence=0.90,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 7. Bank & Financial Accounts
        for name, pat in cls.BANK_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.BANK_ACCOUNT,
                    confidence=0.92,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # 8. User-Marked Confidential / International IDs
        for name, pat in cls.CONFIDENTIAL_PATTERNS:
            if pat.search(clean):
                return SensitiveClassification(
                    is_sensitive=True,
                    category=SensitiveCategory.CONFIDENTIAL,
                    confidence=0.85,
                    detected_pattern_name=name,
                    redacted_preview=cls.mask_sensitive(clean)
                )

        # Non-Sensitive
        return SensitiveClassification(
            is_sensitive=False,
            category=SensitiveCategory.GENERAL,
            confidence=1.0,
            detected_pattern_name="NONE",
            redacted_preview=clean
        )

    @classmethod
    def is_sensitive(cls, text: str) -> bool:
        """ Returns True if the text contains sensitive personal, financial, or credential data """
        return cls.detect(text).is_sensitive

    @classmethod
    def mask_sensitive(cls, text: str) -> str:
        """
        Masks out potential secrets, numbers, card numbers, and credentials
        from a string to create a safe loggable representation.
        """
        if not text:
            return ""
        out = text
        # Mask 16-digit cards
        out = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_CARD]', out)
        # Mask 12-digit Aadhaar
        out = re.sub(r'\b[2-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_AADHAAR]', out)
        # Mask PAN
        out = re.sub(r'\b[A-Za-z]{5}\d{4}[A-Za-z]\b', '[REDACTED_PAN]', out)
        # Mask API Keys
        out = re.sub(r'\bAIza[0-9A-Za-z\-_]{35}\b', '[REDACTED_API_KEY]', out)
        # Mask Recovery Codes
        out = re.sub(r'RC-[A-Z0-9]{4}-[A-Z0-9]{4}', '[REDACTED_RECOVERY_CODE]', out, flags=re.IGNORECASE)
        # Mask PINs following keywords
        out = re.sub(r'(?i)\b(pin\s+(?:is\s+|:\s*)?)([0-9]{4,8})\b', r'\1[REDACTED_PIN]', out)
        # Mask Passwords following keywords
        out = re.sub(r'(?i)\b((?:password|passphrase|passcode)\s+(?:is\s+|:\s*)?)([^\s,.]+)', r'\1[REDACTED_PASSWORD]', out)
        return out
