"""
TTS Text Normalizer for SG CUBE

Converts technical text, markdown, URLs, Windows file paths, IP addresses,
currencies, units, and symbols to natural spoken language for TTS.
Adapted from InterGenJLU JARVIS architecture for Windows NT / SG CUBE.
"""

from __future__ import annotations

import re
from typing import Dict, Callable


class TTSNormalizer:
    """Converts technical text and symbols to natural spoken English."""

    def __init__(self):
        self.digit_words = {
            "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
            "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        }

        self.ones = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        self.teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
                      "sixteen", "seventeen", "eighteen", "nineteen"]
        self.tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

        self._ext_pronunciations = {
            'py': 'P Y', 'sh': 'S H', 'js': 'J S', 'ts': 'T S', 'md': 'M D',
            'csv': 'C S V', 'json': 'JSON', 'txt': 'text', 'pdf': 'PDF',
            'exe': 'executable', 'bat': 'batch', 'html': 'HTML', 'css': 'CSS',
            'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'wav': 'wave', 'mp3': 'M P three'
        }

        # Pipeline order
        self.normalizations: list[tuple[str, Callable[[str], str]]] = [
            ("markdown", self.normalize_markdown),
            ("urls", self.normalize_urls),
            ("windows_paths", self.normalize_windows_paths),
            ("ips_and_ports", self.normalize_ips_and_ports),
            ("currency", self.normalize_currency),
            ("percentages", self.normalize_percentages),
            ("units", self.normalize_units),
            ("technical_acronyms", self.normalize_acronyms),
            ("cleanup", self.normalize_cleanup),
        ]

    def normalize(self, text: str) -> str:
        """Apply all registered normalizations in order."""
        if not text:
            return ""
        result = text
        for name, func in self.normalizations:
            try:
                result = func(result)
            except Exception:
                continue
        return result

    def normalize_markdown(self, text: str) -> str:
        """Strip markdown syntax (bold, italic, code blocks, links, headers)."""
        # Code blocks: ```python ... ``` -> "code block"
        s = re.sub(r'```[\w]*\n(.*?)```', r'code block', text, flags=re.DOTALL)
        # Inline code: `cmd` -> cmd
        s = re.sub(r'`([^`]+)`', r'\1', s)
        # Markdown links: [Title](URL) -> Title
        s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
        # Headers: ### Header -> Header
        s = re.sub(r'#{1,6}\s*([^\n]+)', r'\1', s)
        # Bold & Italic: **bold** or *italic* or _italic_
        s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
        s = re.sub(r'\*([^*]+)\*', r'\1', s)
        s = re.sub(r'__([^_]+)__', r'\1', s)
        s = re.sub(r'_([^_]+)_', r'\1', s)
        # Strikethrough: ~~strikethrough~~
        s = re.sub(r'~~([^~]+)~~', r'\1', s)
        # Bullet points: * or - at start of line
        s = re.sub(r'^\s*[-*+]\s+', '', s, flags=re.MULTILINE)
        return s

    def normalize_windows_paths(self, text: str) -> str:
        """Convert Windows drive paths (e.g. C:\\Users\\Name\\doc.txt) to spoken form."""
        def _replace_path(match):
            drive = match.group(1).upper()
            rest = match.group(2)
            parts = [p for p in re.split(r'[\\/]+', rest) if p]
            spoken_parts = []
            for part in parts:
                # check file extension
                if '.' in part:
                    base, ext = part.rsplit('.', 1)
                    ext_spoken = self._ext_pronunciations.get(ext.lower(), ext)
                    spoken_parts.append(f"{base} dot {ext_spoken}")
                else:
                    spoken_parts.append(part)
            return f"{drive} drive, " + ", ".join(spoken_parts)

        # Match Drive:\Path or Drive:/Path
        pattern = r'\b([A-Za-z]):[\\/]+([A-Za-z0-9_\-.\\/]+)\b'
        return re.sub(pattern, _replace_path, text)

    def normalize_urls(self, text: str) -> str:
        """Convert web URLs to spoken format (e.g. https://www.google.com -> google dot com)."""
        def _replace_url(match):
            domain = match.group(1) or ""
            domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
            domain = domain.replace('.', ' dot ')
            return domain

        pattern = r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?'
        return re.sub(pattern, _replace_url, text)

    def normalize_ips_and_ports(self, text: str) -> str:
        """Convert IP addresses and port numbers to spoken digits."""
        def _replace_ip_port(match):
            ip = match.group(1)
            port = match.group(2)
            ip_spoken = " dot ".join(ip.split('.'))
            if port:
                port_spoken = " ".join(self.digit_words.get(c, c) for c in port)
                return f"{ip_spoken}, port {port_spoken}"
            return ip_spoken

        pattern = r'\b(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?\b'
        return re.sub(pattern, _replace_ip_port, text)

    def normalize_currency(self, text: str) -> str:
        """Convert $100 or 100$ or ₹500 or €50 to spoken currency."""
        s = re.sub(r'\$(\d+(?:\.\d+)?)\s*(?:million|m)\b', r'\1 million dollars', text, flags=re.IGNORECASE)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*(?:million|m)\s*\$', r'\1 million dollars', s, flags=re.IGNORECASE)
        s = re.sub(r'\$(\d+(?:\.\d+)?)\s*(?:billion|b)\b', r'\1 billion dollars', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*(?:billion|b)\s*\$', r'\1 billion dollars', s, flags=re.IGNORECASE)
        s = re.sub(r'\$(\d+(?:\.\d+)?)', r'\1 dollars', s)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*\$', r'\1 dollars', s)
        s = re.sub(r'₹(\d+(?:\.\d+)?)', r'\1 rupees', s)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*₹', r'\1 rupees', s)
        s = re.sub(r'€(\d+(?:\.\d+)?)', r'\1 euros', s)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*€', r'\1 euros', s)
        s = re.sub(r'£(\d+(?:\.\d+)?)', r'\1 pounds', s)
        s = re.sub(r'(\d+(?:\.\d+)?)\s*£', r'\1 pounds', s)
        return s

    def normalize_percentages(self, text: str) -> str:
        """Convert 50% to 50 percent."""
        return re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)

    def normalize_units(self, text: str) -> str:
        """Convert technical units (GB, MB, ms, fps) to full spoken names."""
        s = re.sub(r'(\d+)\s*(?:gb|gbytes)\b', r'\1 gigabytes', text, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*(?:mb|mbytes)\b', r'\1 megabytes', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*(?:kb|kbytes)\b', r'\1 kilobytes', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*ms\b', r'\1 milliseconds', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*fps\b', r'\1 frames per second', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*hz\b', r'\1 hertz', s, flags=re.IGNORECASE)
        s = re.sub(r'(\d+)\s*ghz\b', r'\1 gigahertz', s, flags=re.IGNORECASE)
        return s

    def normalize_acronyms(self, text: str) -> str:
        """Expand common technical acronyms for clear pronunciation."""
        replacements = {
            r'\bUI\b': 'U I',
            r'\bGUI\b': 'G U I',
            r'\bURL\b': 'U R L',
            r'\bAPI\b': 'A P I',
            r'\bSDK\b': 'S D K',
            r'\bOS\b': 'O S',
            r'\bAI\b': 'A I',
            r'\bLLM\b': 'L L M',
            r'\bTTS\b': 'T T S',
            r'\bSTT\b': 'S T T',
            r'\bCPU\b': 'C P U',
            r'\bGPU\b': 'G P U',
            r'\bRAM\b': 'ram',
            r'\bVRAM\b': 'V ram',
            r'\bUIA\b': 'U I A',
            r'\bVS Code\b': 'V S Code',
            r'\bDPAPI\b': 'D P A P I',
        }
        res = text
        for pat, rep in replacements.items():
            res = re.sub(pat, rep, res)
        return res

    def normalize_cleanup(self, text: str) -> str:
        """Clean up multiple spaces, consecutive punctuation, and trailing slashes."""
        s = re.sub(r'[\\/|]+', ' ', text)
        s = re.sub(r'\s+', ' ', s).strip()
        return s


_DEFAULT_NORMALIZER = TTSNormalizer()


def normalize_for_tts(text: str) -> str:
    """Convenience helper to normalize text for natural TTS output."""
    return _DEFAULT_NORMALIZER.normalize(text)
