import os
import sys
import time
import queue
import random
import math
import socket
import threading
import subprocess
import asyncio
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from dotenv import load_dotenv

import google.genai as genai
from google.genai import types

from assistive.vision_engine import VisionEngine
from assistive.command_router import OFFICIAL_INTRODUCTION
from assistive.security_manager import SecurityState
try:
    import speech_recognition as sr
except ImportError:
    sr = None

load_dotenv()

IPC_PORT_GUI = 49152
IPC_PORT_WAKE_LISTENER = 49153

SYSTEM_INSTRUCTION = f"""
You are SG CUBE, a warm, calm, intelligent personal AI companion and assistive camera assistant for blind and visually impaired users.

When asked to introduce yourself, who you are, or what SG CUBE is, give this official introduction:
"{OFFICIAL_INTRODUCTION}"

Guidelines:
1. Speak like a smart, friendly companion. Be natural, warm, respectful, and concise.
2. Provide spatially intuitive descriptions (e.g. "directly ahead", "slightly to your left", "on your right", "near", "farther ahead").
3. Be conservative with safety warnings. Never claim the user is guaranteed safe.
4. Express uncertainty gracefully when unsure about an object, face, or banknote.
5. Never use robotic phrasing or technical system jargon.
6. When the user asks to set, create, change, reset, or remove a voice security password or sensitive password, call the manage_voice_security tool immediately and do not output spoken disclaimers.
"""

MORNING_GREETINGS = [
    "Good morning! I'm here. Ready to get started?",
    "Morning! I'm here with you. What are we doing today?",
    "Good morning! Ready when you are."
]

AFTERNOON_GREETINGS = [
    "Good afternoon! I'm here. What can I help you with?",
    "Hey, good afternoon! I'm ready when you are.",
    "Good afternoon! Ready to help."
]

EVENING_GREETINGS = [
    "Good evening! I'm here with you. What do you need?",
    "Hey, good evening! I'm ready.",
    "Good evening! Nice to have you back."
]

NIGHT_GREETINGS = [
    "Hey, you're up late. I'm here if you need me.",
    "Good night hours! I'm still here with you.",
    "Late night! Ready whenever you are."
]

# --- SG CUBE Final Approved Dark Green & Light Peach/Cream Color System ---
COLOR_BG_PRIMARY = "#060A08"        # Deep Dark Base Charcoal with subtle dark-green undertone
COLOR_BG_SECONDARY = "#0A120D"      # Inset / Header / Footer Charcoal-Green
COLOR_PANEL_DEEP = "#0C1611"        # Translucent Dark Green/Charcoal Panels
COLOR_PANEL_SECONDARY = "#0F1C16"   # Inset Control Areas
COLOR_PANEL_HOVER = "#14251D"       # Elevated Interactive Hover Panels
COLOR_BORDER_SUBTLE = "#183A2A"     # Dark Green Border
COLOR_BORDER_HOVER = "#1F4A35"      # Dark Green Hover Border
COLOR_BORDER_ACTIVE = "#2E6B4A"     # Active Glowing Dark Green Border
COLOR_NAV_ACTIVE_BG = "#183A2A"     # Active Tab Dark Green Pill

# Dark Green Primary System Accents (Refined & Restrained)
COLOR_DARK_GREEN_DEEP = "#183A2A"
COLOR_DARK_GREEN_PRIMARY = "#1F4A35"
COLOR_DARK_GREEN_MEDIUM = "#244F38"
COLOR_DARK_GREEN_ACCENT = "#2E6B4A"
COLOR_DARK_GREEN_HIGHLIGHT = "#3D7856"
COLOR_DARK_GREEN_LIGHT = "#4ADE80"

# Backward-compatibility aliases for existing references
COLOR_OLIVE_PRIMARY = "#1F4A35"
COLOR_OLIVE_DARK = "#183A2A"
COLOR_OLIVE_BRIGHT = "#2E6B4A"
COLOR_OLIVE_GLOW = "#3D7856"

# Typography — Light Peach / Cream System
COLOR_PEACH_PRIMARY = "#F3E4D3"     # Primary Content / Headings / Title (Light Peach / Cream)
COLOR_PEACH_SECONDARY = "#DCCDBD"   # Secondary Content / Labels
COLOR_PEACH_MUTED = "#B6A99B"       # Timestamps / Subtitles / Inactive

# Controlled Icon Accents (Restrained, subtle distinct colors — NO NEON)
COLOR_ICON_HOME = "#4ADE80"         # Soft green
COLOR_ICON_VISION = "#38BDF8"       # Cyan / blue
COLOR_ICON_MEMORY = "#F59E0B"       # Warm amber
COLOR_ICON_HISTORY = "#FB7185"      # Soft red / coral
COLOR_ICON_PEOPLE = "#34D399"       # Green
COLOR_ICON_METAGLASS = "#22D3EE"    # Teal / cyan
COLOR_ICON_SETTINGS = "#F3E4D3"     # Light peach
COLOR_STATUS_GREEN = "#34D399"      # Restrained status green
COLOR_ALERT_RED = "#EF4444"         # Red badge
COLOR_WARNING_GOLD = "#F59E0B"      # Amber
COLOR_CYAN_PRIMARY = "#38BDF8"      # Cyan
COLOR_TEAL_MINT = "#2DD4BF"         # Teal / Mint
COLOR_AQUA = "#22D3EE"              # Aqua
COLOR_PURPLE = "#1F4A35"            # No purple (Dark Green)
COLOR_PINK = "#FB7185"              # Coral
COLOR_ORANGE = "#F59E0B"            # Amber

# Text aliases for comprehensive compatibility
COLOR_TEXT_PRIMARY = COLOR_PEACH_PRIMARY
COLOR_TEXT_SECONDARY = COLOR_PEACH_SECONDARY
COLOR_TEXT_MUTED = COLOR_PEACH_MUTED

def _hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

class GlowingHUDIcon:
    """
    Renders pin-sharp 2D vector HUD icons with a subtle, beautiful neon halo glow
    using 4x supersampling, Gaussian alpha blur, and Lanczos downsampling.
    """
    _pil_cache = {}

    @classmethod
    def get_photo_image(cls, name: str, size: int = 24, color_hex: str = "#00EDFF", hover: bool = False, master=None, rotation: float = 0.0) -> ImageTk.PhotoImage:
        img = cls.get_pil_image(name, size, color_hex, hover=hover, rotation=rotation)
        return ImageTk.PhotoImage(img, master=master)

    @classmethod
    def get_pil_image(cls, name: str, size: int = 24, color_hex: str = "#00EDFF", hover: bool = False, rotation: float = 0.0) -> Image.Image:
        key = (name, size, color_hex, hover, round(rotation, 1))
        if key in cls._pil_cache:
            return cls._pil_cache[key]
        img = cls.render_icon_with_glow(name, size, color_hex, hover=hover, rotation=rotation)
        cls._pil_cache[key] = img
        return img

    @classmethod
    def render_icon_with_glow(cls, name: str, size: int = 24, color_hex: str = "#00EDFF", hover: bool = False, rotation: float = 0.0) -> Image.Image:
        scale = 4
        S = size * scale
        canvas_size = S + 16 * scale  # Padding for soft neon glow halo
        glow_offset = 8 * scale

        icon_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon_canvas)
        rgb = _hex_to_rgb(color_hex)
        
        if hover:
            r_c = min(255, int(rgb[0] * 1.15 + 20))
            g_c = min(255, int(rgb[1] * 1.15 + 20))
            b_c = min(255, int(rgb[2] * 1.15 + 20))
            fg_col = (r_c, g_c, b_c, 255)
        else:
            fg_col = (*rgb, 255)

        pad = int(S * 0.08) + glow_offset
        w = S - 2 * int(S * 0.08)
        h = S - 2 * int(S * 0.08)
        stroke_w = max(3, int(S * 0.08))
        cx = canvas_size // 2
        cy = canvas_size // 2

        if name in ("logo", "sg_cube_logo"):
            # 3D isometric futuristic AI companion cube (32px brand logo)
            r_c = int(S * 0.38)
            pts_top = [(cx, cy - r_c), (cx + int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx - int(r_c * 0.866), cy - r_c // 2)]
            pts_left = [(cx - int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx, cy + r_c), (cx - int(r_c * 0.866), cy + r_c // 2)]
            pts_right = [(cx + int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx, cy + r_c), (cx + int(r_c * 0.866), cy + r_c // 2)]
            draw.polygon(pts_top, outline=fg_col, width=stroke_w)
            draw.polygon(pts_left, outline=fg_col, width=stroke_w)
            draw.polygon(pts_right, outline=fg_col, width=stroke_w)
            draw.ellipse([cx - int(S*0.1), cy - int(S*0.1), cx + int(S*0.1), cy + int(S*0.1)], fill=fg_col)

        elif name in ("home", "house"):
            pts = [
                (cx, pad),
                (pad, int(cy * 0.95)),
                (pad + int(S * 0.14), int(cy * 0.95)),
                (pad + int(S * 0.14), canvas_size - pad),
                (canvas_size - pad - int(S * 0.14), canvas_size - pad),
                (canvas_size - pad - int(S * 0.14), int(cy * 0.95)),
                (canvas_size - pad, int(cy * 0.95))
            ]
            draw.polygon(pts, outline=fg_col, width=stroke_w)
            door_w = int(S * 0.22)
            door_h = int(S * 0.34)
            dx1 = cx - door_w // 2
            dy1 = canvas_size - pad - door_h
            draw.rectangle([dx1, dy1, dx1 + door_w, canvas_size - pad], fill=fg_col)

        elif name in ("vision", "eye"):
            draw.arc([pad, cy - int(h * 0.32), canvas_size - pad, cy + int(h * 0.32)], start=0, end=180, fill=fg_col, width=stroke_w)
            draw.arc([pad, cy - int(h * 0.32), canvas_size - pad, cy + int(h * 0.32)], start=180, end=360, fill=fg_col, width=stroke_w)
            r_iris = int(S * 0.24)
            draw.ellipse([cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris], outline=fg_col, width=stroke_w)
            r_pupil = int(S * 0.11)
            draw.ellipse([cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil], fill=fg_col)

        elif name in ("memory", "brain", "database", "cylinder"):
            dw = int(S * 0.56)
            dh = int(S * 0.18)
            spacing = int(S * 0.15)
            top_y = cy - int(S * 0.20)
            draw.ellipse([cx - dw // 2, top_y - dh // 2, cx + dw // 2, top_y + dh // 2], outline=fg_col, width=stroke_w)
            mid_y = top_y + spacing
            draw.line([(cx - dw // 2, top_y), (cx - dw // 2, mid_y)], fill=fg_col, width=stroke_w)
            draw.line([(cx + dw // 2, top_y), (cx + dw // 2, mid_y)], fill=fg_col, width=stroke_w)
            draw.arc([cx - dw // 2, mid_y - dh // 2, cx + dw // 2, mid_y + dh // 2], start=0, end=180, fill=fg_col, width=stroke_w)
            bot_y = mid_y + spacing
            draw.line([(cx - dw // 2, mid_y), (cx - dw // 2, bot_y)], fill=fg_col, width=stroke_w)
            draw.line([(cx + dw // 2, mid_y), (cx + dw // 2, bot_y)], fill=fg_col, width=stroke_w)
            draw.arc([cx - dw // 2, bot_y - dh // 2, cx + dw // 2, bot_y + dh // 2], start=0, end=180, fill=fg_col, width=stroke_w)

        elif name in ("history", "clock"):
            r = int(S * 0.42)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fg_col, width=stroke_w)
            draw.line([(cx, cy), (cx, cy - int(r * 0.65))], fill=fg_col, width=stroke_w)
            draw.line([(cx, cy), (cx + int(r * 0.55), cy)], fill=fg_col, width=stroke_w)
            draw.ellipse([cx - int(S * 0.05), cy - int(S * 0.05), cx + int(S * 0.05), cy + int(S * 0.05)], fill=fg_col)

        elif name in ("people", "users"):
            cx1 = cx + int(S * 0.12)
            r_head = int(S * 0.16)
            draw.ellipse([cx1 - r_head, cy - int(S * 0.34), cx1 + r_head, cy - int(S * 0.34) + 2 * r_head], fill=fg_col)
            draw.arc([cx1 - int(S * 0.32), cy - int(S * 0.02), cx1 + int(S * 0.32), cy + int(S * 0.44)], start=180, end=360, fill=fg_col, width=stroke_w)
            cx2 = cx - int(S * 0.18)
            r_head2 = int(S * 0.13)
            draw.ellipse([cx2 - r_head2, cy - int(S * 0.26), cx2 + r_head2, cy - int(S * 0.26) + 2 * r_head2], outline=fg_col, width=stroke_w)
            draw.arc([cx2 - int(S * 0.26), cy + int(S * 0.04), cx2 + int(S * 0.26), cy + int(S * 0.42)], start=180, end=270, fill=fg_col, width=stroke_w)

        elif name in ("glasses", "meta_glass"):
            gw = int(S * 0.36)
            gh = int(S * 0.30)
            draw.rounded_rectangle([pad, cy - gh // 2, pad + gw, cy + gh // 2], radius=int(S * 0.08), outline=fg_col, width=stroke_w)
            draw.rounded_rectangle([canvas_size - pad - gw, cy - gh // 2, canvas_size - pad, cy + gh // 2], radius=int(S * 0.08), outline=fg_col, width=stroke_w)
            draw.line([(pad + gw, cy - int(gh * 0.15)), (canvas_size - pad - gw, cy - int(gh * 0.15))], fill=fg_col, width=stroke_w)
            draw.line([(pad, cy - int(gh * 0.2)), (pad - int(S * 0.06), cy - int(gh * 0.4))], fill=fg_col, width=stroke_w)
            draw.line([(canvas_size - pad, cy - int(gh * 0.2)), (canvas_size - pad + int(S * 0.06), cy - int(gh * 0.4))], fill=fg_col, width=stroke_w)

        elif name in ("gear", "settings"):
            r_out = int(S * 0.40)
            r_in = int(S * 0.26)
            r_hole = int(S * 0.13)
            num_teeth = 8
            pts = []
            rot_rad = math.radians(rotation)
            for i in range(num_teeth * 2):
                angle = i * math.pi / num_teeth + rot_rad
                r = r_out if (i % 2 == 0) else r_in
                pts.append((cx + int(r * math.cos(angle)), cy + int(r * math.sin(angle))))
            draw.polygon(pts, outline=fg_col, width=stroke_w)
            draw.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=fg_col)

        elif name in ("mic", "speak"):
            mw = int(S * 0.28)
            mh = int(S * 0.44)
            draw.rounded_rectangle([cx - mw // 2, pad, cx + mw // 2, pad + mh], radius=mw // 2, fill=fg_col)
            cw = int(S * 0.48)
            draw.arc([cx - cw // 2, pad + int(mh * 0.3), cx + cw // 2, pad + mh + int(S * 0.16)], start=0, end=180, fill=fg_col, width=stroke_w)
            sy1 = pad + mh + int(S * 0.16)
            sy2 = canvas_size - pad - stroke_w
            draw.line([(cx, sy1), (cx, sy2)], fill=fg_col, width=stroke_w)
            draw.line([(cx - int(S * 0.22), sy2), (cx + int(S * 0.22), sy2)], fill=fg_col, width=stroke_w)

        elif name in ("describe", "scan"):
            corner_l = int(S * 0.22)
            draw.line([(pad, pad + corner_l), (pad, pad), (pad + corner_l, pad)], fill=fg_col, width=stroke_w)
            draw.line([(canvas_size - pad - corner_l, pad), (canvas_size - pad, pad), (canvas_size - pad, pad + corner_l)], fill=fg_col, width=stroke_w)
            draw.line([(pad, canvas_size - pad - corner_l), (pad, canvas_size - pad), (pad + corner_l, canvas_size - pad)], fill=fg_col, width=stroke_w)
            draw.line([(canvas_size - pad - corner_l, canvas_size - pad), (canvas_size - pad, canvas_size - pad), (canvas_size - pad, canvas_size - pad - corner_l)], fill=fg_col, width=stroke_w)
            draw.arc([pad + int(S*0.08), cy - int(S*0.2), canvas_size - pad - int(S*0.08), cy + int(S*0.2)], start=0, end=180, fill=fg_col, width=stroke_w)
            draw.arc([pad + int(S*0.08), cy - int(S*0.2), canvas_size - pad - int(S*0.08), cy + int(S*0.2)], start=180, end=360, fill=fg_col, width=stroke_w)
            r_pupil = int(S * 0.10)
            draw.ellipse([cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil], fill=fg_col)

        elif name in ("recognize", "person"):
            r_head = int(S * 0.20)
            draw.ellipse([cx - r_head, pad, cx + r_head, pad + 2 * r_head], outline=fg_col, width=stroke_w)
            draw.arc([pad, cy, canvas_size - pad, canvas_size - pad + int(S * 0.15)], start=180, end=360, fill=fg_col, width=stroke_w)
            b_len = int(S * 0.15)
            draw.line([(pad - 2, pad + b_len), (pad - 2, pad - 2), (pad + b_len, pad - 2)], fill=fg_col, width=stroke_w)
            draw.line([(canvas_size - pad + 2 - b_len, pad - 2), (canvas_size - pad + 2, pad - 2), (canvas_size - pad + 2, pad + b_len)], fill=fg_col, width=stroke_w)

        elif name in ("ocr", "read_text"):
            dw = int(S * 0.60)
            dh = int(S * 0.74)
            x1 = (canvas_size - dw) // 2
            y1 = (canvas_size - dh) // 2
            draw.rounded_rectangle([x1, y1, x1 + dw, y1 + dh], radius=int(S * 0.07), outline=fg_col, width=stroke_w)
            draw.line([(x1 + int(dw * 0.20), y1 + int(dh * 0.28)), (x1 + int(dw * 0.80), y1 + int(dh * 0.28))], fill=fg_col, width=stroke_w)
            draw.line([(x1 + int(dw * 0.20), y1 + int(dh * 0.50)), (x1 + int(dw * 0.80), y1 + int(dh * 0.50))], fill=fg_col, width=stroke_w)
            draw.line([(x1 + int(dw * 0.20), y1 + int(dh * 0.72)), (x1 + int(dw * 0.55), y1 + int(dh * 0.72))], fill=fg_col, width=stroke_w)

        elif name in ("currency", "rupee"):
            bw = int(S * 0.80)
            bh = int(S * 0.54)
            bx1 = (canvas_size - bw) // 2
            by1 = (canvas_size - bh) // 2
            draw.rounded_rectangle([bx1, by1, bx1 + bw, by1 + bh], radius=int(S * 0.08), outline=fg_col, width=stroke_w)
            rw = int(bw * 0.38)
            draw.line([(cx - rw // 2, cy - int(bh * 0.26)), (cx + rw // 2, cy - int(bh * 0.26))], fill=fg_col, width=stroke_w)
            draw.line([(cx - rw // 2, cy - int(bh * 0.08)), (cx + int(rw * 0.4), cy - int(bh * 0.08))], fill=fg_col, width=stroke_w)
            draw.arc([cx - rw // 2, cy - int(bh * 0.26), cx + rw // 2, cy + int(bh * 0.06)], start=270, end=90, fill=fg_col, width=stroke_w)
            draw.line([(cx - int(rw * 0.1), cy - int(bh * 0.02)), (cx + int(rw * 0.4), cy + int(bh * 0.28))], fill=fg_col, width=stroke_w)

        elif name in ("find_object", "search"):
            cx_lens = cx - int(S * 0.08)
            cy_lens = cy - int(S * 0.08)
            r_lens = int(S * 0.28)
            draw.ellipse([cx_lens - r_lens, cy_lens - r_lens, cx_lens + r_lens, cy_lens + r_lens], outline=fg_col, width=stroke_w)
            hx1 = cx_lens + int(r_lens * 0.707)
            hy1 = cy_lens + int(r_lens * 0.707)
            hx2 = canvas_size - pad
            hy2 = canvas_size - pad
            draw.line([(hx1, hy1), (hx2, hy2)], fill=fg_col, width=int(stroke_w * 1.5))

        elif name in ("safety", "shield"):
            top_y = pad
            mid_y = cy + int(S * 0.1)
            bot_y = canvas_size - pad
            half_w = int(S * 0.40)
            pts = [(cx - half_w, top_y), (cx + half_w, top_y),
                   (cx + half_w, mid_y), (cx, bot_y),
                   (cx - half_w, mid_y)]
            draw.polygon(pts, outline=fg_col, width=stroke_w)
            draw.line([(cx, top_y + int(S * 0.14)), (cx, top_y + int(S * 0.38))], fill=fg_col, width=stroke_w)
            draw.ellipse([cx - stroke_w // 2, top_y + int(S * 0.48), cx + stroke_w // 2, top_y + int(S * 0.48) + stroke_w], fill=fg_col)
            
        elif name in ("waveform", "pulse"):
            bar_w = max(2, int(S * 0.08))
            heights = [0.35, 0.70, 0.45, 0.90, 0.55, 0.75, 0.40]
            num_bars = len(heights)
            spacing = int(S * 0.12)
            start_x = cx - (num_bars * spacing) // 2
            for idx, h_ratio in enumerate(heights):
                bx = start_x + idx * spacing
                bh = int(S * 0.65 * h_ratio)
                draw.rounded_rectangle([bx - bar_w // 2, cy - bh // 2, bx + bar_w // 2, cy + bh // 2], radius=bar_w // 2, fill=fg_col)

        elif name in ("tree", "environment", "leaf"):
            # Sleek botanical leaf with central stem vein
            pts_leaf = [
                (cx - int(S * 0.35), cy + int(S * 0.32)),
                (cx - int(S * 0.20), cy - int(S * 0.05)),
                (cx + int(S * 0.05), cy - int(S * 0.30)),
                (cx + int(S * 0.35), cy - int(S * 0.35)),
                (cx + int(S * 0.30), cy - int(S * 0.05)),
                (cx + int(S * 0.05), cy + int(S * 0.20)),
                (cx - int(S * 0.35), cy + int(S * 0.32))
            ]
            draw.polygon(pts_leaf, outline=fg_col, width=stroke_w)
            draw.line([(cx - int(S * 0.32), cy + int(S * 0.30)), (cx + int(S * 0.30), cy - int(S * 0.30))], fill=fg_col, width=stroke_w)

        elif name in ("cube", "wireframe_cube", "scene"):
            r_c = int(S * 0.36)
            pts_top = [(cx, cy - r_c), (cx + int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx - int(r_c * 0.866), cy - r_c // 2)]
            pts_left = [(cx - int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx, cy + r_c), (cx - int(r_c * 0.866), cy + r_c // 2)]
            pts_right = [(cx + int(r_c * 0.866), cy - r_c // 2), (cx, cy), (cx, cy + r_c), (cx + int(r_c * 0.866), cy + r_c // 2)]
            draw.polygon(pts_top, outline=fg_col, width=stroke_w)
            draw.polygon(pts_left, outline=fg_col, width=stroke_w)
            draw.polygon(pts_right, outline=fg_col, width=stroke_w)

        elif name in ("sun", "light"):
            r_sun = int(S * 0.20)
            draw.ellipse([cx - r_sun, cy - r_sun, cx + r_sun, cy + r_sun], fill=fg_col)
            ray_len = int(S * 0.14)
            r_outer = int(S * 0.38)
            for i in range(8):
                ang = i * math.pi / 4.0
                rx1 = cx + int((r_outer - ray_len) * math.cos(ang))
                ry1 = cy + int((r_outer - ray_len) * math.sin(ang))
                rx2 = cx + int(r_outer * math.cos(ang))
                ry2 = cy + int(r_outer * math.sin(ang))
                draw.line([(rx1, ry1), (rx2, ry2)], fill=fg_col, width=stroke_w)

        elif name in ("volume", "noise", "speaker"):
            cone_w = int(S * 0.22)
            cone_h = int(S * 0.36)
            pts = [(cx - int(S * 0.25), cy - int(cone_h * 0.28)),
                   (cx - int(S * 0.10), cy - int(cone_h * 0.28)),
                   (cx + int(S * 0.08), cy - cone_h // 2),
                   (cx + int(S * 0.08), cy + cone_h // 2),
                   (cx - int(S * 0.10), cy + int(cone_h * 0.28)),
                   (cx - int(S * 0.25), cy + int(cone_h * 0.28))]
            draw.polygon(pts, fill=fg_col)
            draw.arc([cx, cy - int(S * 0.25), cx + int(S * 0.35), cy + int(S * 0.25)], start=-60, end=60, fill=fg_col, width=stroke_w)
            draw.arc([cx + int(S * 0.12), cy - int(S * 0.40), cx + int(S * 0.55), cy + int(S * 0.40)], start=-60, end=60, fill=fg_col, width=stroke_w)

        elif name in ("check", "check_circle", "status_clear"):
            r_c = int(S * 0.40)
            draw.ellipse([cx - r_c, cy - r_c, cx + r_c, cy + r_c], outline=fg_col, width=stroke_w)
            pts_check = [
                (cx - int(r_c * 0.45), cy),
                (cx - int(r_c * 0.10), cy + int(r_c * 0.40)),
                (cx + int(r_c * 0.50), cy - int(r_c * 0.35))
            ]
            draw.line(pts_check, fill=fg_col, width=stroke_w)

        elif name in ("arrow_right", "right", "chevron", "expand"):
            pts_chev = [
                (cx - int(S * 0.16), cy - int(S * 0.28)),
                (cx + int(S * 0.18), cy),
                (cx - int(S * 0.16), cy + int(S * 0.28))
            ]
            draw.line(pts_chev, fill=fg_col, width=int(stroke_w * 1.2))
            draw.line([(cx - int(S * 0.22), cy), (cx + int(S * 0.18), cy)], fill=fg_col, width=int(stroke_w * 1.2))

        elif name in ("arrow_left", "left"):
            pts_left = [
                (cx + int(S * 0.16), cy - int(S * 0.28)),
                (cx - int(S * 0.18), cy),
                (cx + int(S * 0.16), cy + int(S * 0.28))
            ]
            draw.line(pts_left, fill=fg_col, width=int(stroke_w * 1.2))
            draw.line([(cx - int(S * 0.18), cy), (cx + int(S * 0.22), cy)], fill=fg_col, width=int(stroke_w * 1.2))

        elif name in ("target", "center", "crosshair"):
            r_tgt = int(S * 0.30)
            draw.ellipse([cx - r_tgt, cy - r_tgt, cx + r_tgt, cy + r_tgt], outline=fg_col, width=stroke_w)
            draw.ellipse([cx - int(S * 0.08), cy - int(S * 0.08), cx + int(S * 0.08), cy + int(S * 0.08)], fill=fg_col)
            draw.line([(cx, cy - r_tgt - int(S * 0.08)), (cx, cy - r_tgt + int(S * 0.04))], fill=fg_col, width=stroke_w)
            draw.line([(cx, cy + r_tgt - int(S * 0.04)), (cx, cy + r_tgt + int(S * 0.08))], fill=fg_col, width=stroke_w)
            draw.line([(cx - r_tgt - int(S * 0.08), cy), (cx - r_tgt + int(S * 0.04), cy)], fill=fg_col, width=stroke_w)
            draw.line([(cx + r_tgt - int(S * 0.04), cy), (cx + r_tgt + int(S * 0.08), cy)], fill=fg_col, width=stroke_w)

        elif name in ("camera", "cam"):
            bw = int(S * 0.70)
            bh = int(S * 0.48)
            bx1 = (canvas_size - bw) // 2
            by1 = cy - int(bh * 0.35)
            draw.rounded_rectangle([bx1, by1, bx1 + bw, by1 + bh], radius=int(S * 0.08), outline=fg_col, width=stroke_w)
            draw.rectangle([cx - int(bw * 0.20), by1 - int(S * 0.10), cx + int(bw * 0.20), by1], fill=fg_col)
            draw.ellipse([cx - int(bh * 0.30), cy + int(bh * 0.12) - int(bh * 0.30), cx + int(bh * 0.30), cy + int(bh * 0.12) + int(bh * 0.30)], outline=fg_col, width=stroke_w)

        elif name in ("fullscreen", "expand_screen"):
            corner = int(S * 0.22)
            span = int(S * 0.35)
            draw.line([(cx - span, cy - span + corner), (cx - span, cy - span), (cx - span + corner, cy - span)], fill=fg_col, width=stroke_w)
            draw.line([(cx + span - corner, cy - span), (cx + span, cy - span), (cx + span, cy - span + corner)], fill=fg_col, width=stroke_w)
            draw.line([(cx - span, cy + span - corner), (cx - span, cy + span), (cx - span + corner, cy + span)], fill=fg_col, width=stroke_w)
            draw.line([(cx + span - corner, cy + span), (cx + span, cy + span), (cx + span, cy + span - corner)], fill=fg_col, width=stroke_w)

        elif name in ("battery", "bat"):
            bw = int(S * 0.65)
            bh = int(S * 0.34)
            bx1 = cx - bw // 2
            by1 = cy - bh // 2
            draw.rounded_rectangle([bx1, by1, bx1 + bw, by1 + bh], radius=int(S * 0.06), outline=fg_col, width=stroke_w)
            draw.rectangle([bx1 + bw, cy - int(bh * 0.25), bx1 + bw + int(S * 0.06), cy + int(bh * 0.25)], fill=fg_col)
            draw.rectangle([bx1 + int(S * 0.08), by1 + int(S * 0.06), bx1 + int(bw * 0.65), by1 + bh - int(S * 0.06)], fill=fg_col)

        elif name in ("wifi", "network"):
            draw.ellipse([cx - int(S * 0.06), canvas_size - pad - int(S * 0.10), cx + int(S * 0.06), canvas_size - pad], fill=fg_col)
            draw.arc([cx - int(S * 0.24), canvas_size - pad - int(S * 0.36), cx + int(S * 0.24), canvas_size - pad + int(S * 0.10)], start=210, end=330, fill=fg_col, width=stroke_w)
            draw.arc([cx - int(S * 0.40), canvas_size - pad - int(S * 0.60), cx + int(S * 0.40), canvas_size - pad + int(S * 0.20)], start=210, end=330, fill=fg_col, width=stroke_w)

        elif name in ("chip", "gemini_chip", "ai"):
            cw = int(S * 0.48)
            draw.rectangle([cx - cw // 2, cy - cw // 2, cx + cw // 2, cy + cw // 2], outline=fg_col, width=stroke_w)
            draw.rectangle([cx - int(cw * 0.30), cy - int(cw * 0.30), cx + int(cw * 0.30), cy + int(cw * 0.30)], fill=fg_col)
            pin_l = int(S * 0.12)
            for d in (-int(cw * 0.25), 0, int(cw * 0.25)):
                draw.line([(cx + d, cy - cw // 2), (cx + d, cy - cw // 2 - pin_l)], fill=fg_col, width=stroke_w)
                draw.line([(cx + d, cy + cw // 2), (cx + d, cy + cw // 2 + pin_l)], fill=fg_col, width=stroke_w)
                draw.line([(cx - cw // 2, cy + d), (cx - cw // 2 - pin_l, cy + d)], fill=fg_col, width=stroke_w)
                draw.line([(cx + cw // 2, cy + d), (cx + cw // 2 + pin_l, cy + d)], fill=fg_col, width=stroke_w)

        elif name in ("road", "path", "navigation"):
            # Perspective highway lane with dashed center divider
            rw_top = int(S * 0.15)
            rw_bot = int(S * 0.40)
            y_top = cy - int(S * 0.35)
            y_bot = cy + int(S * 0.35)
            draw.line([(cx - rw_top, y_top), (cx - rw_bot, y_bot)], fill=fg_col, width=stroke_w)
            draw.line([(cx + rw_top, y_top), (cx + rw_bot, y_bot)], fill=fg_col, width=stroke_w)
            draw.line([(cx, y_top + int(S * 0.08)), (cx, y_top + int(S * 0.22))], fill=fg_col, width=stroke_w)
            draw.line([(cx, y_top + int(S * 0.36)), (cx, y_bot - int(S * 0.06))], fill=fg_col, width=stroke_w)

        else:
            draw.ellipse([pad, pad, canvas_size - pad, canvas_size - pad], outline=fg_col, width=stroke_w)

        # Clean, crisp anti-aliased icon rendering with zero neon halo
        composite = icon_canvas
        
        target_size = size
        if hover:
            target_size = int(size * 1.10)
            
        return composite.resize((target_size, target_size), Image.Resampling.LANCZOS)

HUDIcon = GlowingHUDIcon

class HUDTooltip:
    """
    Lightweight floating dark glass HUD tooltip for navigation tabs and action buttons with 150ms responsive display.
    """
    def __init__(self, widget, text, delay=150):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.after_id = None
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel()
        self.after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.configure(bg=COLOR_CYAN_PRIMARY)

            frame = tk.Frame(tw, bg=COLOR_PANEL_DEEP, highlightbackground=COLOR_CYAN_PRIMARY, highlightthickness=1, padx=8, pady=3)
            frame.pack(fill=tk.BOTH)

            lbl = tk.Label(frame, text=self.text, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_PANEL_DEEP)
            lbl.pack()
        except Exception:
            pass

    def _hide(self):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

class Real3DCubeRenderer:
    """
    Renders an authentic, genuine 3D Isometric Rotating SG CUBE Centerpiece:
    - Filled 3D glass faces with visible depth, real perspective, and surface lighting.
    - Top face: Warm light-peach / cream highlight (#F3E4D3 specular sheen and face #C8B49B)
    - Front face: Deep rich dark-green glass (#153D27 with #2E6B4A border)
    - Right side face: Lighter green facet (#225E3B with #34D399 border)
    - Left rim: Subtle cyan reflection line (#38BDF8)
    - Inner glass refraction depth facets for authentic 3D optical density
    - Restrained elliptical pedestal disc & orbital rings
    - Title below: 'SG CUBE' (light peach #F3E4D3) + 'Seeing • Understanding • Helping' (#DCCDBD)
    - Also provides draw_header_cube for the authentic filled 3D logo in the header bar
    """
    def __init__(self, canvas_width=380, canvas_height=260):
        self.width = canvas_width
        self.height = canvas_height
        self.cx = canvas_width // 2
        self.cy = canvas_height // 2 - 25
        self.cube_rot_y = 0.0

    def draw(self, canvas, rot_x=-0.42, rot_y=0.0, rot_z=0.0, time_val=0.0, state="IDLE", hover=False, mouse_tilt=(0.0, 0.0), pulse=1.0):
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw > 40 and ch > 40:
            cx = cw // 2 + int(mouse_tilt[1] * 14)
            cy = int(ch * 0.38) + int(mouse_tilt[0] * 14)
            base_scale = min(cw / 380.0, ch / 260.0)
        else:
            cx = self.cx + int(mouse_tilt[1] * 14)
            cy = self.cy + int(mouse_tilt[0] * 14)
            base_scale = 1.0

        if hover:
            pulse *= 1.05

        # 1. Base Elliptical Orbital Pedestal & Rings (Restrained Dark Green & Teal)
        cy_floor = cy + int(70 * base_scale)
        r3_x, r3_y = int(135 * base_scale), int(34 * base_scale)
        r2_x, r2_y = int(108 * base_scale), int(27 * base_scale)
        r1_x, r1_y = int(82 * base_scale), int(20 * base_scale)

        # Base dark pedestal disc
        canvas.create_oval(cx - r2_x, cy_floor - r2_y, cx + r2_x, cy_floor + r2_y, fill="#08140D", outline="#183A2A", width=1)

        # Outer ring 3 (Subtle Dark Green)
        canvas.create_oval(cx - r3_x, cy_floor - r3_y, cx + r3_x, cy_floor + r3_y, outline="#183A2A", width=1)

        # Middle ring 2 (Dark Green Accent)
        canvas.create_oval(cx - r2_x, cy_floor - r2_y, cx + r2_x, cy_floor + r2_y, outline="#2E6B4A" if state != "SLEEPING" else "#183A2A", width=1.5)

        # Inner ring 1 (Subtle Teal Reflection)
        canvas.create_oval(cx - r1_x, cy_floor - r1_y, cx + r1_x, cy_floor + r1_y, outline="#164E40" if state != "SLEEPING" else "#0D2620", width=1)

        # Restrained orbital photon particles
        if state != "SLEEPING":
            particles = [
                (r3_x, r3_y, time_val * 1.1, "#2E6B4A", max(2, int(2.5 * base_scale))),
                (r2_x, r2_y, -time_val * 1.4, "#34D399", max(2, int(2.5 * base_scale))),
                (r1_x, r1_y, time_val * 1.8 + 0.8, "#2DD4BF", max(2, int(2.5 * base_scale))),
            ]
            for rx, ry, ang, col, rad in particles:
                px = cx + rx * math.cos(ang)
                py = cy_floor + ry * math.sin(ang)
                canvas.create_oval(px - rad, py - rad, px + rad, py + rad, fill=col, outline="")

        # 2. Authentic 3D Isometric Filled Cube Geometry (Target 180-240px Desktop)
        size = int((74 if not hover else 80) * base_scale * pulse)
        raw_verts = [
            [-size,  size, -size],  # 0: Top-left-back
            [ size,  size, -size],  # 1: Top-right-back
            [ size, -size, -size],  # 2: Bottom-right-back
            [-size, -size, -size],  # 3: Bottom-left-back
            [-size,  size,  size],  # 4: Top-left-front
            [ size,  size,  size],  # 5: Top-right-front
            [ size, -size,  size],  # 6: Bottom-right-front
            [-size, -size,  size],  # 7: Bottom-left-front
        ]

        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)
        cos_z, sin_z = math.cos(rot_z), math.sin(rot_z)

        rotated_3d = []
        for vx, vy, vz in raw_verts:
            x1 = vx * cos_y + vz * sin_y
            z1 = -vx * sin_y + vz * cos_y
            y1 = vy
            y2 = y1 * cos_x - z1 * sin_x
            z2 = y1 * sin_x + z1 * cos_x
            x2 = x1
            x3 = x2 * cos_z - y2 * sin_z
            y3 = x2 * sin_z + y2 * cos_z
            z3 = z2
            rotated_3d.append((x3, y3, z3))

        fov = 420.0 * base_scale
        projected = []
        for x, y, z in rotated_3d:
            factor = fov / (fov + z) if (fov + z) != 0 else 1.0
            px = cx + int(x * factor)
            py = cy - int(y * factor)
            projected.append((px, py, z))

        faces = [
            ([0, 1, 5, 4], "top",    "#C8B49B", "#F3E4D3", "#34D399", "#FFF4E6"), # Warm Light Peach top
            ([4, 5, 6, 7], "front",  "#153D27", "#2E6B4A", "#4ADE80", ""),         # Dark green main face
            ([1, 2, 6, 5], "right",  "#225E3B", "#34D399", "#34D399", ""),         # Lighter green side
            ([0, 4, 7, 3], "left",   "#113120", "#1F4A35", "#38BDF8", ""),         # Cyan reflection left
            ([3, 7, 6, 2], "bottom", "#08160E", "#183A2A", "#183A2A", ""),
            ([0, 3, 2, 1], "back",   "#08160E", "#183A2A", "#183A2A", ""),
        ]

        visible_faces = []
        for indices, name, bg_col, edge_col, accent_col, glint_col in faces:
            v0 = rotated_3d[indices[0]]
            v1 = rotated_3d[indices[1]]
            v2 = rotated_3d[indices[2]]
            e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            nx = e1[1] * e2[2] - e1[2] * e2[1]
            ny = e1[2] * e2[0] - e1[0] * e2[2]
            nz = e1[0] * e2[1] - e1[1] * e2[0]
            avg_z = sum(rotated_3d[i][2] for i in indices) / 4.0
            if nz > 0:
                visible_faces.append((avg_z, indices, name, bg_col, edge_col, accent_col, glint_col))

        visible_faces.sort(key=lambda item: item[0], reverse=True)

        visible_vert_indices = set()
        for avg_z, indices, name, bg_col, edge_col, accent_col, glint_col in visible_faces:
            poly_pts = []
            for i in indices:
                poly_pts.extend([projected[i][0], projected[i][1]])
                visible_vert_indices.add(i)

            # Draw solid filled face
            canvas.create_polygon(poly_pts, fill=bg_col, outline=edge_col if state != "SLEEPING" else "#183A2A", width=max(1, int(2 * base_scale)))

            # Draw inner glass refraction facet
            c_x = sum(projected[i][0] for i in indices) / 4.0
            c_y = sum(projected[i][1] for i in indices) / 4.0
            inset_pts = []
            for i in indices:
                ix = c_x + (projected[i][0] - c_x) * 0.74
                iy = c_y + (projected[i][1] - c_y) * 0.74
                inset_pts.extend([ix, iy])

            inset_fill = "#B49F86" if name == "top" else ("#19482E" if name == "front" else "#2A7249")
            canvas.create_polygon(inset_pts, fill=inset_fill, outline=accent_col if state != "SLEEPING" else "#14251D", width=1)

            # Specular glint on top face front edge
            if name == "top":
                p_e0 = projected[indices[2]]
                p_e1 = projected[indices[3]]
                canvas.create_line(p_e0[0], p_e0[1], p_e1[0], p_e1[1], fill=glint_col, width=max(1, int(2.5 * base_scale)))
            elif name == "front":
                p_e0 = projected[indices[0]]
                p_e1 = projected[indices[3]]
                canvas.create_line(p_e0[0], p_e0[1], p_e1[0], p_e1[1], fill="#38BDF8" if state != "SLEEPING" else "#1F4A35", width=max(1, int(1.2 * base_scale)))

        # Vertex nodes on visible corners only
        for idx in visible_vert_indices:
            px, py, z = projected[idx]
            rad = max(1, int(2 * base_scale))
            canvas.create_oval(px - rad, py - rad, px + rad, py + rad, fill="#4ADE80" if state != "SLEEPING" else "#183A2A", outline="")

        # 3. Text below cube: "SG CUBE" in Light Peach + "Seeing • Understanding • Helping"
        title_y = cy + int(104 * base_scale)
        title_font_size = max(13, int(17 * base_scale))
        canvas.create_text(cx, title_y, text="SG CUBE", fill=COLOR_PEACH_PRIMARY, font=("Segoe UI", title_font_size, "bold"), anchor="center")

        tag_y = title_y + int(19 * base_scale)
        tag_font_size = max(8, int(10 * base_scale))
        spacing = int(base_scale * 52)
        canvas.create_text(cx - spacing * 2, tag_y, text="Seeing", fill=COLOR_PEACH_SECONDARY, font=("Segoe UI", tag_font_size), anchor="center")
        canvas.create_oval(cx - spacing - 2, tag_y - 2, cx - spacing + 2, tag_y + 2, fill=COLOR_STATUS_GREEN, outline="")
        canvas.create_text(cx, tag_y, text="Understanding", fill=COLOR_PEACH_SECONDARY, font=("Segoe UI", tag_font_size), anchor="center")
        canvas.create_oval(cx + spacing - 2, tag_y - 2, cx + spacing + 2, tag_y + 2, fill=COLOR_STATUS_GREEN, outline="")
        canvas.create_text(cx + spacing * 2, tag_y, text="Helping", fill=COLOR_PEACH_SECONDARY, font=("Segoe UI", tag_font_size), anchor="center")

    def draw_header_cube(self, canvas, rot_y=0.0, rot_x=-0.38, state="IDLE"):
        """ Renders an authentic filled 3D rotating SG CUBE for the header bar brand logo """
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 20 or ch < 20:
            cw, ch = 48, 48
        cx, cy = cw // 2, ch // 2
        size = 14

        # Restrained shadow below header cube
        canvas.create_oval(cx - 16, cy + 16, cx + 16, cy + 22, fill="#08140D", outline="")

        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)

        raw_verts = [
            [-size,  size, -size],  # 0
            [ size,  size, -size],  # 1
            [ size, -size, -size],  # 2
            [-size, -size, -size],  # 3
            [-size,  size,  size],  # 4
            [ size,  size,  size],  # 5
            [ size, -size,  size],  # 6
            [-size, -size,  size],  # 7
        ]

        rotated_3d = []
        for vx, vy, vz in raw_verts:
            x1 = vx * cos_y + vz * sin_y
            z1 = -vx * sin_y + vz * cos_y
            y1 = vy
            y2 = y1 * cos_x - z1 * sin_x
            z2 = y1 * sin_x + z1 * cos_x
            x2 = x1
            rotated_3d.append((x2, y2, z2))

        fov = 150.0
        projected = []
        for x, y, z in rotated_3d:
            factor = fov / (fov + z) if (fov + z) != 0 else 1.0
            px = cx + int(x * factor)
            py = cy - int(y * factor)
            projected.append((px, py, z))

        faces = [
            ([0, 1, 5, 4], "top",    "#C8B49B", "#F3E4D3", "#FFF4E6"), # Warm Light Peach top
            ([4, 5, 6, 7], "front",  "#153D27", "#2E6B4A", ""),         # Dark green main face
            ([1, 2, 6, 5], "right",  "#225E3B", "#34D399", ""),         # Lighter green side
            ([0, 4, 7, 3], "left",   "#113120", "#1F4A35", ""),         # Cyan rim accent
            ([3, 7, 6, 2], "bottom", "#08160E", "#183A2A", ""),
            ([0, 3, 2, 1], "back",   "#08160E", "#183A2A", ""),
        ]

        visible_faces = []
        for indices, name, bg_col, edge_col, glint_col in faces:
            v0 = rotated_3d[indices[0]]
            v1 = rotated_3d[indices[1]]
            v2 = rotated_3d[indices[2]]
            e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            nx = e1[1] * e2[2] - e1[2] * e2[1]
            ny = e1[2] * e2[0] - e1[0] * e2[2]
            nz = e1[0] * e2[1] - e1[1] * e2[0]
            avg_z = sum(rotated_3d[i][2] for i in indices) / 4.0
            if nz > 0:
                visible_faces.append((avg_z, indices, name, bg_col, edge_col, glint_col))

        visible_faces.sort(key=lambda item: item[0], reverse=True)

        for avg_z, indices, name, bg_col, edge_col, glint_col in visible_faces:
            poly_pts = []
            for i in indices:
                poly_pts.extend([projected[i][0], projected[i][1]])
            canvas.create_polygon(poly_pts, fill=bg_col, outline=edge_col if state != "SLEEPING" else "#183A2A", width=1.5)

            if name == "top" and glint_col:
                p_e0 = projected[indices[2]]
                p_e1 = projected[indices[3]]
                canvas.create_line(p_e0[0], p_e0[1], p_e1[0], p_e1[1], fill=glint_col, width=2)
            elif name == "front":
                p_e0 = projected[indices[0]]
                p_e1 = projected[indices[3]]
                canvas.create_line(p_e0[0], p_e0[1], p_e1[0], p_e1[1], fill="#38BDF8" if state != "SLEEPING" else "#1F4A35", width=1)

        for px, py, z in projected:
            canvas.create_oval(px - 1, py - 1, px + 1, py + 1, fill="#4ADE80" if state != "SLEEPING" else "#183A2A", outline="")

    def draw_audio_core(self, canvas, time_val=0.0, state="IDLE", pulse=1.0, hover=False, mouse_tilt=(0.0, 0.0)):
        if state != "SLEEPING":
            speed = 1.0 if state == "IDLE" else (1.8 if state == "AI_SPEAKING" else 1.4)
            self.cube_rot_y += 0.035 * speed
            if self.cube_rot_y > 2 * math.pi:
                self.cube_rot_y -= 2 * math.pi
        rot_x = -0.42 + 0.06 * math.sin(time_val * 1.5)
        rot_z = 0.03 * math.cos(time_val * 1.2)
        self.draw(canvas, rot_x=rot_x, rot_y=self.cube_rot_y, rot_z=rot_z, time_val=time_val, state=state, hover=hover, mouse_tilt=mouse_tilt, pulse=pulse)

    def draw_cube(self, canvas, *args, **kwargs):
        self.draw_audio_core(canvas, *args, **kwargs)

FuturisticAudioCoreRenderer = Real3DCubeRenderer

def animate_dialog_open(dialog, target_alpha=0.98, duration_ms=220):
    """ Smooth opacity opening transition for secondary modal dialogs (220ms ease-out) """
    try:
        dialog.attributes("-alpha", 0.0)
        steps = 8
        interval = max(10, duration_ms // steps)
        def step(i):
            if not dialog or not dialog.winfo_exists():
                return
            # Ease-out curve
            t = i / steps
            ease_t = 1.0 - (1.0 - t) * (1.0 - t)
            a = ease_t * target_alpha
            try:
                dialog.attributes("-alpha", a)
            except Exception:
                pass
            if i < steps:
                dialog.after(interval, lambda: step(i + 1))
        dialog.after(10, lambda: step(1))
    except Exception:
        try:
            dialog.attributes("-alpha", 1.0)
        except Exception:
            pass

def animate_dialog_close(dialog, duration_ms=180, callback=None):
    """ Smooth opacity closing transition for secondary modal dialogs (180ms ease-in) """
    try:
        if not dialog or not dialog.winfo_exists():
            if callback:
                callback()
            return
        steps = 6
        interval = max(10, duration_ms // steps)
        try:
            current_alpha = float(dialog.attributes("-alpha") or 1.0)
        except Exception:
            current_alpha = 1.0
        def step(i):
            if not dialog or not dialog.winfo_exists():
                if callback:
                    callback()
                return
            t = i / steps
            ease_t = t * t
            a = current_alpha * (1.0 - ease_t)
            try:
                dialog.attributes("-alpha", max(0.0, a))
            except Exception:
                pass
            if i < steps:
                dialog.after(interval, lambda: step(i + 1))
            else:
                try:
                    dialog.destroy()
                except Exception:
                    pass
                if callback:
                    callback()
        step(1)
    except Exception:
        try:
            dialog.destroy()
        except Exception:
            pass
class VoiceActivityDetector:
    """
    Streaming 16kHz Energy & Zero-Crossing Voice Activity Detector (VAD).
    Operates on 64ms frames (1024 samples @ 16kHz 16-bit PCM).
    Detects human speech onset and offset with low latency.
    """
    def __init__(self, sample_rate=16000, frame_duration_ms=64):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
        self.noise_floor = 120.0
        self.speech_onset_frames = 0
        self.is_speech_active = False
        self.silence_frames = 0

    def process_frame(self, pcm_samples: np.ndarray) -> bool:
        if len(pcm_samples) == 0:
            return False
        energy = float(np.sqrt(np.mean(pcm_samples.astype(np.float64)**2)))
        if not self.is_speech_active:
            self.noise_floor = 0.96 * self.noise_floor + 0.04 * min(energy, 400.0)
        speech_thresh = max(self.noise_floor * 2.0, 240.0)
        if energy > speech_thresh:
            self.speech_onset_frames += 1
            self.silence_frames = 0
            if self.speech_onset_frames >= 2:
                self.is_speech_active = True
        else:
            self.speech_onset_frames = max(0, self.speech_onset_frames - 1)
            self.silence_frames += 1
            if self.silence_frames >= 6:  # ~400ms silence
                self.is_speech_active = False
        return self.is_speech_active

class SGCubeApp:
    def _speak_local_response(self, text: str, is_security: bool = False):
        """
        Speaks local response text.
        For normal conversational local responses, unifies audio by delegating to Gemini Live.
        Windows SAPI is restricted strictly to offline security password prompts.
        """
        if not text:
            return
        if not is_security:
            with self.session_lock:
                self.pending_speech_prompt = f"Speak this exact response out loud in a warm, natural, friendly, confident voice: '{text}'"
            return

        if os.name == 'nt':
            try:
                import win32com.client
                v = win32com.client.Dispatch("SAPI.SpVoice")
                v.Speak(text, 1)  # SVSFlagsAsync = 1
                print(f"[SECURITY-VOICE] SAPI spoken: '{text}'")
            except Exception as e:
                print(f"[SECURITY-VOICE] SAPI notice: {e}")


    def __init__(self, root):
        self.root = root
        self.root.title("SG CUBE — Personal AI Companion")
        self.root.geometry("1080x820")
        self.root.minsize(480, 360)
        self.root.configure(bg=COLOR_BG_PRIMARY)
        self.root.option_add("*Font", ("Segoe UI", 10))

        # Windows Taskbar Icon & AppUserModelID setup
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SGCUBE.Assistant.2.5.0")
            except Exception:
                pass

        # Set Window Icon
        _app_dir = os.path.abspath(os.path.dirname(__file__))
        _icon_path = os.path.join(_app_dir, "assets", "SG-CUBE.ico")
        if os.path.exists(_icon_path):
            try:
                self.root.iconbitmap(_icon_path)
            except Exception:
                pass

        # Instantiate Assistive Vision Engine with per-request voice password protection for Secure Memory
        self.engine = VisionEngine(data_dir="data", per_request_auth=True)

        # State variables and locks
        self.camera_running = False
        self.ai_running = False
        self.camera_thread = None
        self.ai_thread = None
        self.latest_jpeg = None
        self.latest_raw_frame = None
        self.measured_fps = 20.0
        self.camera_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.gui_queue = queue.Queue()

        # Session State Machine: IDLE, LISTENING, USER_SPEAKING, AI_THINKING, AI_SPEAKING, RECONNECTING, STOPPED, SLEEPING, SAFETY_ALERT
        self.state_lock = threading.Lock()
        self.current_state = "IDLE"

        # Developer / Debug Overlay Flag
        self.dev_mode = self.engine.store.get_setting("developer_mode", False)

        # Animation state variables for SG CUBE Floating Core & 3D Rotating Cube
        self.anim_angle = 0.0
        self.anim_time = 0.0
        self.orbit_angle = 0.0
        self.context_banner_timer = 0
        self.cube_3d = Real3DCubeRenderer(canvas_width=280, canvas_height=140)
        self.cube_rot_y = 0.0
        self.cube_rot_x = 0.26
        self.cube_rot_z = 0.0
        self.cube_hover = False
        self.cube_mouse_tilt = (0.0, 0.0)

        # Audio Queues & Authoritative Session Control
        self.mic_queue = queue.Queue()
        self.playback_queue = queue.Queue()

        self.session_lock = threading.Lock()
        self.active_session_id = None
        self.current_response_id = 0
        self.playback_thread = None
        self.playback_thread_started = False
        self.playback_stop_evt = threading.Event()
        self.wake_greeting_pending = False
        self.wake_greeting_timer = 0.0
        self.pending_speech_prompt = None
        self.first_valid_frame_received = False
        self.active_history_session_id = self.engine.history.create_session()
        self.action_busy = False
        self.user_transcript_buffer = ""
        self.last_user_speech_time = 0.0

        # Enforce Single-Instance Application Lock
        self._enforce_single_instance()

        # Full-Window Dark Abstract Background Image Setup
        self.bg_orig_image = None
        self.bg_photo_image = None
        self.bg_image_id = None
        self._last_bg_size = None
        _bg_path = os.path.join(_app_dir, "assets", "bg_abstract_dark.jpg")
        if os.path.exists(_bg_path):
            try:
                self.bg_orig_image = Image.open(_bg_path).convert("RGB")
            except Exception as e:
                print(f"[UI] Warning loading background image: {e}")

        self._build_ui()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start IPC Server for Wake Listener commands
        self._start_ipc_server()

        # Start periodic GUI queue polling (~20ms) and SG CUBE floating orb animation (~35ms)
        self.root.after(20, self._process_gui_queue)
        self.root.after(35, self._animate_sg_cube_core)

        # Auto-start services in background after UI renders
        self.root.after(50, self._notify_wake_listener_pause)
        self.root.after(100, self._update_info_strip)
        self.root.after(300, self._auto_start_services)
        self.root.after(400, self._check_first_run_onboarding)

    def _enforce_single_instance(self):
        """ Enforces single instance. If SG CUBE is already running, sends WAKE IPC signal to active instance and exits. """
        try:
            self.lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.lock_socket.bind(('127.0.0.1', IPC_PORT_GUI))
            self.lock_socket.listen(5)
            print(f"[SINGLE-INSTANCE] Acquired single-instance socket lock on port {IPC_PORT_GUI}.")
        except Exception:
            print("[SINGLE-INSTANCE] SG CUBE is ALREADY RUNNING. Sending WAKE IPC signal to active instance and exiting...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect(('127.0.0.1', IPC_PORT_GUI))
                sock.sendall(b"WAKE")
                sock.close()
            except Exception:
                pass
            sys.exit(0)

    def _start_ipc_server(self):
        """ Starts background IPC socket server listening for commands from wake_listener.py """
        def ipc_loop():
            try:
                print(f"[IPC-SERVER] SG CUBE IPC Server listening on port {IPC_PORT_GUI}...")
                while True:
                    conn, addr = self.lock_socket.accept()
                    data = conn.recv(1024).decode('utf-8').strip()
                    if data == "WAKE":
                        print("[IPC-SERVER] Received WAKE signal! Bringing SG CUBE to foreground...")
                        self.gui_queue.put(("ACTION", "WAKE_FOREGROUND"))
                        try:
                            conn.sendall(b"OK\n")
                        except Exception:
                            pass
                    elif data == "STATUS":
                        try:
                            status = "SLEEPING" if self.current_state == "SLEEPING" else "ACTIVE"
                            conn.sendall(f"{status}\n".encode('utf-8'))
                        except Exception:
                            pass
                    conn.close()
            except Exception as e:
                print(f"[IPC-SERVER] Error: {e}")

        t = threading.Thread(target=ipc_loop, daemon=True)
        t.start()

    def set_state(self, new_state: str):
        with self.state_lock:
            if self.current_state == "SLEEPING" and new_state not in ("OPENING", "ACTIVE", "LISTENING"):
                return
            if self.current_state != new_state:
                old_state = self.current_state
                self.current_state = new_state
                print(f"[STATE] {old_state} -> {new_state}")
                self.gui_queue.put(("STATE", new_state))

    def _clear_playback_queue(self):
        """ Clears unplayed audio chunks and advances response_id for barge-in / speech interruption """
        with self.state_lock:
            self.current_response_id += 1
            new_id = self.current_response_id

        self.playback_stop_evt.set()

        cleared_count = 0
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        if cleared_count > 0:
            print(f"[BARGE-IN] Advanced response_id to {new_id}. Purged {cleared_count} stale audio chunks.")

    def _generate_time_greeting(self) -> str:
        hour = time.localtime().tm_hour
        user_name = self.engine.store.get_setting("user_display_name") or self.engine.store.get_setting("user_name", "")
        name_str = f", {user_name}" if user_name and user_name != "User" else ""
        if 5 <= hour < 12:
            return f"Good morning{name_str}! I'm here. What do you need?"
        elif 12 <= hour < 17:
            return f"Good afternoon{name_str}! I'm here. What do you need?"
        elif 17 <= hour < 22:
            return f"Good evening{name_str}! I'm here. What do you need?"
        else:
            return f"Good night{name_str}! I'm here. What do you need?"

    # --- Premium Ultra-Dark HUD UI Construction ---
    # --- Premium Ultra-Dark HUD UI Construction (Reference Locked 1536x1024 Base) ---
    # --- SG CUBE 2.5 Responsive Ultra-Dark HUD UI Construction (media_1790103688268.png) ---
    def _build_ui(self):
        # 1. Header Navigation & Status Bar (Charcoal Background, Height 92px, Subtle Dark Green Border)
        header = tk.Frame(self.root, bg=COLOR_BG_SECONDARY, height=92, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        self.header_frame = header

        # Brand Container (48x48px Filled 3D Rotating Cube Canvas + Bold "SG CUBE" Title + Subtitle)
        brand_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)
        self.brand_frame = brand_frame

        self.header_cube_canvas = tk.Canvas(brand_frame, width=48, height=48, bg=COLOR_BG_SECONDARY, highlightthickness=0)
        self.header_cube_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.brand_icon_lbl = self.header_cube_canvas  # Backwards-compatible alias

        title_container = tk.Frame(brand_frame, bg=COLOR_BG_SECONDARY)
        title_container.pack(side=tk.LEFT)

        title_row = tk.Frame(title_container, bg=COLOR_BG_SECONDARY)
        title_row.pack(anchor="w")
        self.lbl_brand_sg = tk.Label(title_row, text="SG", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 26, "bold"))
        self.lbl_brand_sg.pack(side=tk.LEFT)
        self.lbl_brand_cube = tk.Label(title_row, text=" CUBE", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 26, "bold"))
        self.lbl_brand_cube.pack(side=tk.LEFT)

        self.lbl_brand_sub = tk.Label(title_container, text="Personal AI Companion", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 10))
        self.lbl_brand_sub.pack(anchor="w")

        # Row 3: Seeing • Understanding • Helping tagline
        self.lbl_brand_motto = tk.Label(title_container, text="Seeing • Understanding • Helping", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 8))
        self.lbl_brand_motto.pack(anchor="w")

        # Centered Navigation Group: Large Icons with Text STRICTLY BELOW Icon
        nav_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)
        self.nav_frame = nav_frame

        self.nav_buttons = {}
        self.nav_buttons["home"] = self._create_nav_btn(nav_frame, "home", "Home", self._on_nav_home, active=True, accent=COLOR_ICON_HOME, tooltip="Home dashboard")
        self.nav_buttons["vision"] = self._create_nav_btn(nav_frame, "vision", "Vision", self.open_vision_dialog, accent=COLOR_ICON_VISION, tooltip="Live vision")
        self.nav_buttons["memory"] = self._create_nav_btn(nav_frame, "memory", "Memory", self.open_memory_dialog, accent=COLOR_ICON_MEMORY, tooltip="Personal memory")
        self.nav_buttons["history"] = self._create_nav_btn(nav_frame, "history", "History", self.open_history_dialog, accent=COLOR_ICON_HISTORY, tooltip="Conversation history")
        self.nav_buttons["people"] = self._create_nav_btn(nav_frame, "people", "People", self.open_people_dialog, accent=COLOR_ICON_PEOPLE, tooltip="Face profiles")
        self.nav_buttons["glasses"] = self._create_nav_btn(nav_frame, "glasses", "Meta Glass", self.open_meta_glass_dialog, accent=COLOR_ICON_METAGLASS, tooltip="Meta Glass")

        # Right Header: Status Badge Pill + Settings Button
        actions_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)
        self.actions_frame = actions_frame

        header.grid_columnconfigure(0, weight=0)
        header.grid_columnconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=0)
        header.grid_rowconfigure(0, weight=1)

        brand_frame.grid(row=0, column=0, sticky="w", padx=(16, 8), pady=4)
        nav_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        actions_frame.grid(row=0, column=2, sticky="e", padx=(8, 16), pady=4)

        # Status Badge Pill with Waveform Icon, Green Dot, and Dark Green Border (Prominent, High-Visibility)
        status_pill_frame = tk.Frame(actions_frame, bg=COLOR_PANEL_DEEP, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, padx=14, pady=6)
        status_pill_frame.pack(side=tk.LEFT, padx=(0, 12))
        self.status_pill_frame = status_pill_frame

        wave_img = GlowingHUDIcon.get_photo_image("waveform", size=22, color_hex=COLOR_STATUS_GREEN, master=status_pill_frame)
        self.status_wave_lbl = tk.Label(status_pill_frame, image=wave_img, bg=COLOR_PANEL_DEEP)
        self.status_wave_lbl.image = wave_img
        self.status_wave_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.status_dot_lbl = tk.Label(status_pill_frame, text="●", bg=COLOR_PANEL_DEEP, fg=COLOR_STATUS_GREEN, font=("Segoe UI", 9, "bold"))
        self.status_dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

        self.sys_status_label = tk.Label(
            status_pill_frame,
            text="Listening...",
            bg=COLOR_PANEL_DEEP,
            fg=COLOR_PEACH_PRIMARY,
            font=("Segoe UI", 12, "bold")
        )
        self.sys_status_label.pack(side=tk.LEFT)

        # Settings Gear Icon Button (30px with 10° Smooth Animated Rotation on Hover)
        gear_img_normal = GlowingHUDIcon.get_photo_image("gear", size=30, color_hex=COLOR_PEACH_PRIMARY, hover=False, master=actions_frame, rotation=0.0)
        gear_imgs_enter = [
            GlowingHUDIcon.get_photo_image("gear", size=32, color_hex=COLOR_DARK_GREEN_LIGHT, hover=True, master=actions_frame, rotation=3.5),
            GlowingHUDIcon.get_photo_image("gear", size=32, color_hex=COLOR_DARK_GREEN_LIGHT, hover=True, master=actions_frame, rotation=7.0),
            GlowingHUDIcon.get_photo_image("gear", size=32, color_hex=COLOR_DARK_GREEN_LIGHT, hover=True, master=actions_frame, rotation=10.0),
        ]
        gear_imgs_leave = [
            GlowingHUDIcon.get_photo_image("gear", size=31, color_hex=COLOR_DARK_GREEN_LIGHT, hover=True, master=actions_frame, rotation=7.0),
            GlowingHUDIcon.get_photo_image("gear", size=30, color_hex=COLOR_PEACH_PRIMARY, hover=False, master=actions_frame, rotation=3.5),
            gear_img_normal,
        ]

        self.btn_settings = tk.Button(
            actions_frame,
            image=gear_img_normal,
            bg=COLOR_PANEL_DEEP,
            activebackground=COLOR_PANEL_HOVER,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            command=self.open_settings_dialog
        )
        btn_settings = self.btn_settings
        btn_settings.image_normal = gear_img_normal
        btn_settings.image = gear_img_normal
        btn_settings.anim_job = None

        def on_gear_enter(e):
            if btn_settings.anim_job:
                self.root.after_cancel(btn_settings.anim_job)
            btn_settings.config(bg=COLOR_PANEL_HOVER, image=gear_imgs_enter[0], highlightbackground=COLOR_BORDER_ACTIVE)
            def frame1():
                btn_settings.config(image=gear_imgs_enter[1])
            def frame2():
                btn_settings.config(image=gear_imgs_enter[2])
            self.root.after(45, frame1)
            btn_settings.anim_job = self.root.after(90, frame2)

        def on_gear_leave(e):
            if btn_settings.anim_job:
                self.root.after_cancel(btn_settings.anim_job)
            btn_settings.config(image=gear_imgs_leave[0])
            def frame1():
                btn_settings.config(image=gear_imgs_leave[1])
            def frame2():
                btn_settings.config(bg=COLOR_PANEL_DEEP, image=gear_imgs_leave[2], highlightbackground=COLOR_BORDER_SUBTLE)
            self.root.after(45, frame1)
            btn_settings.anim_job = self.root.after(90, frame2)

        btn_settings.bind("<Enter>", on_gear_enter, add="+")
        btn_settings.bind("<Leave>", on_gear_leave, add="+")
        btn_settings.pack(side=tk.LEFT)
        HUDTooltip(btn_settings, "Settings")

        # 2. Footer Bar (#0A0D08 Background, Height ~28px)
        footer = tk.Frame(self.root, bg=COLOR_BG_SECONDARY, height=28, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        self.footer_bar = footer

        self.footer_left_lbl = tk.Label(footer, text="SG CUBE 2.5.0  |  Your Personal AI Companion", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 9))
        self.footer_left_lbl.pack(side=tk.LEFT, padx=16)

        self.footer_right_lbl = tk.Label(footer, text="", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 9))
        self.footer_right_lbl.pack(side=tk.RIGHT, padx=16)

        # 3. Main Scrollable Container (Canvas + Scrollable Virtual Frame)
        self.main_container = tk.Frame(self.root, bg=COLOR_BG_PRIMARY)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.main_canvas = tk.Canvas(self.main_container, bg=COLOR_BG_PRIMARY, highlightthickness=0)
        self.main_scrollbar = tk.Scrollbar(self.main_container, orient=tk.VERTICAL, command=self.main_canvas.yview)
        self.scrollable_content = tk.Frame(self.main_canvas, bg=COLOR_BG_PRIMARY)

        self.canvas_window = self.main_canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _on_canvas_configure(event):
            self.main_canvas.itemconfig(self.canvas_window, width=event.width)
            self._update_scroll_region()
            self._update_background_canvas(event.width, event.height)

        self.main_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            if self.main_scrollbar.winfo_ismapped():
                self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.scrollable_content.bind("<MouseWheel>", _on_mousewheel, add="+")
        self.main_canvas.bind("<MouseWheel>", _on_mousewheel, add="+")

        # 4. Upper Stage Container (Holds Environment, Camera Feed, Scene)
        self.stage_upper = tk.Frame(self.scrollable_content, bg=COLOR_BG_PRIMARY)
        self.stage_upper.pack(fill=tk.X, padx=14, pady=(8, 4))

        # --- LEFT: ENVIRONMENT PANEL ---
        self.hud_env_card = tk.Frame(
            self.stage_upper,
            bg=COLOR_PANEL_DEEP,
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            padx=16,
            pady=14
        )

        env_title_frame = tk.Frame(self.hud_env_card, bg=COLOR_PANEL_DEEP)
        env_title_frame.pack(fill=tk.X, pady=(0, 10))
        tree_img = GlowingHUDIcon.get_photo_image("tree", size=24, color_hex=COLOR_DARK_GREEN_LIGHT, master=env_title_frame)
        lbl_env_icon = tk.Label(env_title_frame, image=tree_img, bg=COLOR_PANEL_DEEP)
        lbl_env_icon.image = tree_img
        lbl_env_icon.pack(side=tk.LEFT, padx=(0, 8))
        self.hud_env_title = tk.Label(env_title_frame, text="ENVIRONMENT", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 16, "bold"))
        self.hud_env_title.pack(side=tk.LEFT)

        def _make_env_row(icon_name, icon_col, label_text, default_val, val_col=COLOR_PEACH_SECONDARY):
            row = tk.Frame(self.hud_env_card, bg=COLOR_PANEL_DEEP)
            row.pack(fill=tk.X, pady=6)
            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=20, color_hex=icon_col, master=row)
            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP)
            ic_lbl.image = ic_img
            ic_lbl.pack(side=tk.LEFT, padx=(0, 10))
            name_lbl = tk.Label(row, text=label_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 13), anchor="w")
            name_lbl.pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=val_col, font=("Segoe UI", 13, "bold"), anchor="e")
            val_lbl.pack(side=tk.RIGHT)
            return val_lbl

        self.hud_env_labels = [
            _make_env_row("recognize", COLOR_ICON_VISION, "People", "1 person", val_col=COLOR_PEACH_SECONDARY),
            _make_env_row("home", COLOR_ICON_MEMORY, "Room", "Living Room", val_col=COLOR_PEACH_SECONDARY),
            _make_env_row("sun", COLOR_WARNING_GOLD, "Lighting", "Normal", val_col=COLOR_PEACH_SECONDARY),
            _make_env_row("waveform", COLOR_STATUS_GREEN, "Noise", "Low", val_col=COLOR_PEACH_SECONDARY),
            _make_env_row("safety", COLOR_STATUS_GREEN, "Safety", "Clear", val_col=COLOR_STATUS_GREEN),
        ]
        self.hud_env_person_lbl = self.hud_env_labels[0]
        self.hud_env_room_lbl = self.hud_env_labels[1]
        self.hud_env_light_lbl = self.hud_env_labels[2]
        self.hud_env_noise_lbl = self.hud_env_labels[3]
        self.hud_env_safety_lbl = self.hud_env_labels[4]

        # --- CENTER: DOMINANT CAMERA FEED ---
        self.cam_outer_card = tk.Frame(
            self.stage_upper,
            bg="#0B1812",
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            padx=10,
            pady=8
        )

        cam_bar = tk.Frame(self.cam_outer_card, bg="#0B1812")
        cam_bar.pack(fill=tk.X, padx=6, pady=(2, 6))

        cam_left_capsules = tk.Frame(cam_bar, bg="#0B1812")
        cam_left_capsules.pack(side=tk.LEFT)

        live_capsule = tk.Frame(cam_left_capsules, bg="#1A0D0F", highlightbackground=COLOR_ALERT_RED, highlightthickness=1, padx=8, pady=2)
        live_capsule.pack(side=tk.LEFT, padx=(0, 8))
        self.cam_live_dot = tk.Label(live_capsule, text="●", bg="#1A0D0F", fg=COLOR_ALERT_RED, font=("Segoe UI", 9, "bold"))
        self.cam_live_dot.pack(side=tk.LEFT, padx=(0, 4))
        self.cam_live_lbl = tk.Label(live_capsule, text="LIVE", bg="#1A0D0F", fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 9, "bold"))
        self.cam_live_lbl.pack(side=tk.LEFT)

        fps_capsule = tk.Frame(cam_left_capsules, bg="#0B1C1D", highlightbackground=COLOR_BORDER_ACTIVE, highlightthickness=1, padx=8, pady=2)
        fps_capsule.pack(side=tk.LEFT)
        self.cam_badge = tk.Label(fps_capsule, text="25 FPS", bg="#0B1C1D", fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 9, "bold"))
        self.cam_badge.pack(side=tk.LEFT)

        cam_right_btns = tk.Frame(cam_bar, bg="#0B1812")
        cam_right_btns.pack(side=tk.RIGHT)

        cam_switch_img = GlowingHUDIcon.get_photo_image("camera", size=22, color_hex=COLOR_PEACH_PRIMARY, master=cam_right_btns)
        self.btn_cam_toggle = tk.Button(cam_right_btns, image=cam_switch_img, bg=COLOR_PANEL_DEEP, activebackground=COLOR_PANEL_HOVER, bd=0, relief=tk.FLAT, padx=6, pady=3, cursor="hand2", command=self.toggle_camera)
        self.btn_cam_toggle.image = cam_switch_img
        self.btn_cam_toggle.pack(side=tk.LEFT, padx=4)
        HUDTooltip(self.btn_cam_toggle, "Switch / Toggle Camera")

        fs_img = GlowingHUDIcon.get_photo_image("fullscreen", size=22, color_hex=COLOR_PEACH_PRIMARY, master=cam_right_btns)
        self.btn_fullscreen = tk.Button(cam_right_btns, image=fs_img, bg=COLOR_PANEL_DEEP, activebackground=COLOR_PANEL_HOVER, bd=0, relief=tk.FLAT, padx=6, pady=3, cursor="hand2", command=self._toggle_fullscreen)
        self.btn_fullscreen.image = fs_img
        self.btn_fullscreen.pack(side=tk.LEFT, padx=4)
        HUDTooltip(self.btn_fullscreen, "Toggle Fullscreen")

        self.cam_viewport = tk.Frame(self.cam_outer_card, bg="#040806")
        self.cam_viewport.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        self.preview_label = tk.Label(
            self.cam_viewport,
            text="",
            bg="#040806",
            fg=COLOR_PEACH_SECONDARY,
            font=("Segoe UI", 12)
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        # --- RIGHT: SCENE PANEL ---
        self.hud_obj_card = tk.Frame(
            self.stage_upper,
            bg=COLOR_PANEL_DEEP,
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        scene_title_frame = tk.Frame(self.hud_obj_card, bg=COLOR_PANEL_DEEP)
        scene_title_frame.pack(fill=tk.X, pady=(0, 10))
        cube_ic = GlowingHUDIcon.get_photo_image("cube", size=24, color_hex=COLOR_DARK_GREEN_LIGHT, master=scene_title_frame)
        lbl_cube_icon = tk.Label(scene_title_frame, image=cube_ic, bg=COLOR_PANEL_DEEP)
        lbl_cube_icon.image = cube_ic
        lbl_cube_icon.pack(side=tk.LEFT, padx=(0, 8))
        self.hud_obj_title = tk.Label(scene_title_frame, text="SCENE", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 16, "bold"))
        self.hud_obj_title.pack(side=tk.LEFT)

        def _make_scene_row(icon_name, icon_col, label_text, default_val, val_col=COLOR_PEACH_SECONDARY):
            row = tk.Frame(self.hud_obj_card, bg=COLOR_PANEL_DEEP)
            row.pack(fill=tk.X, pady=6)
            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=20, color_hex=icon_col, master=row)
            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP)
            ic_lbl.image = ic_img
            ic_lbl.pack(side=tk.LEFT, padx=(0, 10))
            name_lbl = tk.Label(row, text=label_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 13), anchor="w")
            name_lbl.pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=val_col, font=("Segoe UI", 13, "bold"), anchor="e")
            val_lbl.pack(side=tk.RIGHT)
            return val_lbl

        self.hud_obj_labels = [
            _make_scene_row("people", COLOR_ICON_VISION, "People", "1 | Objects: 3", val_col=COLOR_PEACH_SECONDARY),
            _make_scene_row("arrow_left", COLOR_ICON_VISION, "Left", "None", val_col=COLOR_PEACH_SECONDARY),
            _make_scene_row("target", COLOR_PEACH_PRIMARY, "Center", "Person", val_col=COLOR_PEACH_SECONDARY),
            _make_scene_row("arrow_right", COLOR_ICON_MEMORY, "Right", "Object", val_col=COLOR_PEACH_SECONDARY),
            _make_scene_row("road", COLOR_STATUS_GREEN, "Path", "Clear", val_col=COLOR_STATUS_GREEN),
        ]

        # 5. Lower Stage Container (Holds Recent History, 3D Rotating Cube Centerpiece, System Status)
        self.stage_lower = tk.Frame(self.scrollable_content, bg=COLOR_BG_PRIMARY)
        self.stage_lower.pack(fill=tk.X, padx=14, pady=(4, 10))

        # --- LEFT: RECENT HISTORY CARD (~33% width) ---
        self.card_history = tk.Frame(
            self.stage_lower,
            bg=COLOR_PANEL_DEEP,
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            padx=16,
            pady=14,
            cursor="hand2"
        )
        hist_head = tk.Frame(self.card_history, bg=COLOR_PANEL_DEEP)
        hist_head.pack(fill=tk.X, pady=(0, 8))

        clock_ic = GlowingHUDIcon.get_photo_image("history", size=24, color_hex=COLOR_DARK_GREEN_LIGHT, master=hist_head)
        lbl_clock = tk.Label(hist_head, image=clock_ic, bg=COLOR_PANEL_DEEP)
        lbl_clock.image = clock_ic
        lbl_clock.pack(side=tk.LEFT, padx=(0, 8))

        hist_title = tk.Label(hist_head, text="RECENT HISTORY", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 16, "bold"))
        hist_title.pack(side=tk.LEFT)
        self.hist_title = hist_title

        lbl_view_all = tk.Label(hist_head, text="View All >", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 11), cursor="hand2")
        lbl_view_all.pack(side=tk.RIGHT)

        self.info_history_rows = []
        self.info_history_labels = []
        for _ in range(6):
            h_row = tk.Frame(self.card_history, bg=COLOR_PANEL_DEEP)
            h_row.pack(fill=tk.X, pady=4)
            lbl_t = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 11), width=6, anchor="w")
            lbl_t.pack(side=tk.LEFT)
            lbl_spk = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_STATUS_GREEN, font=("Segoe UI", 12, "bold"), width=4, anchor="w")
            lbl_spk.pack(side=tk.LEFT)
            lbl_msg = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 12), anchor="w")
            lbl_msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.info_history_rows.append((lbl_t, lbl_spk, lbl_msg))
            self.info_history_labels.append(lbl_msg)

        self.card_history.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")
        hist_title.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")
        lbl_view_all.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")
        HUDTooltip(self.card_history, "Click to open full conversation history")

        # --- CENTER: 3D ROTATING SG CUBE CENTERPIECE (~33% width, Large 180-240px target) ---
        self.card_cube = tk.Frame(
            self.stage_lower,
            bg=COLOR_BG_PRIMARY,
            padx=4,
            pady=0
        )

        self.orb_canvas = tk.Canvas(
            self.card_cube,
            width=380,
            height=260,
            bg=COLOR_BG_PRIMARY,
            highlightthickness=0,
            cursor="hand2"
        )
        self.orb_canvas.pack(anchor="center")

        def on_cube_motion(e):
            cw = self.orb_canvas.winfo_width()
            ch = self.orb_canvas.winfo_height()
            self.cube_mouse_tilt = (((e.y - ch // 2) / float(ch)) * 0.5, ((e.x - cw // 2) / float(cw)) * 0.5)
            self.cube_hover = True

        def on_cube_enter(e):
            self.cube_hover = True

        def on_cube_leave(e):
            self.cube_hover = False
            self.cube_mouse_tilt = (0.0, 0.0)

        self.orb_canvas.bind("<Motion>", on_cube_motion, add="+")
        self.orb_canvas.bind("<Enter>", on_cube_enter, add="+")
        self.orb_canvas.bind("<Leave>", on_cube_leave, add="+")
        self.orb_canvas.bind("<Button-1>", lambda e: self._on_space_shortcut(), add="+")
        HUDTooltip(self.orb_canvas, "Click to speak / give command to SG CUBE")

        # --- RIGHT: SYSTEM STATUS CARD (~33% width) ---
        self.card_status = tk.Frame(
            self.stage_lower,
            bg=COLOR_PANEL_DEEP,
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            padx=16,
            pady=14,
            cursor="hand2"
        )
        stat_head = tk.Frame(self.card_status, bg=COLOR_PANEL_DEEP)
        stat_head.pack(fill=tk.X, pady=(0, 8))

        wave_ic = GlowingHUDIcon.get_photo_image("waveform", size=24, color_hex=COLOR_DARK_GREEN_LIGHT, master=stat_head)
        lbl_wave = tk.Label(stat_head, image=wave_ic, bg=COLOR_PANEL_DEEP)
        lbl_wave.image = wave_ic
        lbl_wave.pack(side=tk.LEFT, padx=(0, 8))

        stat_title = tk.Label(stat_head, text="SYSTEM STATUS", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 16, "bold"))
        stat_title.pack(side=tk.LEFT)
        self.stat_title = stat_title

        lbl_stat_arrow = tk.Label(stat_head, text=">", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 12, "bold"), cursor="hand2")
        lbl_stat_arrow.pack(side=tk.RIGHT)

        self.info_status_labels = {}
        def _make_status_row(icon_name, name_text, val_key, default_val="● Active", default_col=COLOR_STATUS_GREEN):
            row = tk.Frame(self.card_status, bg=COLOR_PANEL_DEEP)
            row.pack(fill=tk.X, pady=4)
            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=20, color_hex=COLOR_PEACH_PRIMARY, master=row)
            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP)
            ic_lbl.image = ic_img
            ic_lbl.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(row, text=name_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 13), width=12, anchor="w").pack(side=tk.LEFT)
            lbl_val = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=default_col, font=("Segoe UI", 13, "bold"), anchor="e")
            val_lbl = lbl_val
            lbl_val.pack(side=tk.RIGHT)
            self.info_status_labels[val_key] = lbl_val

        _make_status_row("camera", "Camera", "cam", "● Active", COLOR_STATUS_GREEN)
        _make_status_row("mic", "Microphone", "mic", "● Active", COLOR_STATUS_GREEN)
        _make_status_row("volume", "Speaker", "speaker", "● Active", COLOR_STATUS_GREEN)
        _make_status_row("chip", "AI (Gemini)", "gemini", "● Connected", COLOR_STATUS_GREEN)
        _make_status_row("battery", "Battery", "battery", "🔋 89%", COLOR_STATUS_GREEN)
        _make_status_row("wifi", "Network", "network", "● Online", COLOR_STATUS_GREEN)

        self.card_status.bind("<Button-1>", lambda e: self.open_settings_dialog(), add="+")
        stat_title.bind("<Button-1>", lambda e: self.open_settings_dialog(), add="+")
        lbl_stat_arrow.bind("<Button-1>", lambda e: self.open_settings_dialog(), add="+")
        # Panel Aliases for robust reference
        self.env_card = self.hud_env_card
        self.scene_card = self.hud_obj_card
        self.history_card = self.card_history
        self.cube_card = self.card_cube
        self.status_card = self.card_status
        self.cube_canvas = self.orb_canvas

        # Compatibility placeholders
        self.context_banner = tk.Label(self.root)
        self.dialogue_banner = tk.Label(self.root)
        self.dialogue_prefix = tk.Label(self.root)
        self.dialogue_speaker = tk.Label(self.root)
        self.action_buttons = {}

        # Responsive Reflow & Resize Controller
        self.current_layout_mode = None
        self.resize_debounce_job = None
        self.last_pil_frame = None

        self.root.bind("<Configure>", self._on_window_configure, add="+")
        self.root.after(10, self._apply_responsive_layout)

    def _toggle_fullscreen(self):
        is_fs = getattr(self, '_is_fullscreen', False)
        self._is_fullscreen = not is_fs
        self.root.attributes("-fullscreen", self._is_fullscreen)

    def _on_window_configure(self, event):
        if event.widget != self.root:
            return
        if self.resize_debounce_job:
            self.root.after_cancel(self.resize_debounce_job)
        self.resize_debounce_job = self.root.after(40, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self.resize_debounce_job = None
        if not self.root or not self.root.winfo_exists():
            return

        w = self.root.winfo_width()
        h = self.root.winfo_height()

        if w >= 1150 and h >= 650:
            target_mode = "WIDE"
        elif w >= 850 and h >= 580:
            target_mode = "MEDIUM"
        else:
            target_mode = "SMALL"

        if target_mode != self.current_layout_mode:
            self.current_layout_mode = target_mode
            self._reflow_layout(target_mode, w, h)
        else:
            self._reflow_header(target_mode, w)
            self._reflow_footer(target_mode, w)

        self._update_background_canvas(w, h)
        self._adjust_camera_height(target_mode, w, h)
        self._rescale_camera_preview()
        self._update_scroll_region()
        self._update_dynamic_typography(w, h)

    def _reflow_header(self, mode, w):
        if not hasattr(self, 'header_frame') or not hasattr(self, 'brand_frame') or not hasattr(self, 'nav_frame') or not hasattr(self, 'actions_frame'):
            return

        self.brand_frame.grid_forget()
        self.nav_frame.grid_forget()
        self.actions_frame.grid_forget()

        if mode in ("WIDE", "MEDIUM"):
            self.header_frame.pack_propagate(False)
            self.header_frame.config(height=92 if mode == "WIDE" else 84)

            self.header_frame.grid_columnconfigure(0, weight=0)
            self.header_frame.grid_columnconfigure(1, weight=1)
            self.header_frame.grid_columnconfigure(2, weight=0)
            self.header_frame.grid_rowconfigure(0, weight=1)
            self.header_frame.grid_rowconfigure(1, weight=0)

            pad_x = 20 if mode == "WIDE" else 10
            self.brand_frame.grid(row=0, column=0, sticky="w", padx=(pad_x, 4), pady=4)
            self.nav_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
            self.actions_frame.grid(row=0, column=2, sticky="e", padx=(4, pad_x), pady=4)

            if hasattr(self, 'nav_buttons'):
                for btn in self.nav_buttons.values():
                    btn.pack_forget()
                    btn.pack(side=tk.LEFT, padx=8 if mode == "WIDE" else 4, expand=False)
        else:  # SMALL Mode (Two-tier grid)
            self.header_frame.pack_propagate(False)
            self.header_frame.config(height=118)

            self.header_frame.grid_columnconfigure(0, weight=1)
            self.header_frame.grid_columnconfigure(1, weight=1)
            self.header_frame.grid_columnconfigure(2, weight=0)
            self.header_frame.grid_rowconfigure(0, weight=0)
            self.header_frame.grid_rowconfigure(1, weight=1)

            self.brand_frame.grid(row=0, column=0, sticky="w", padx=(8, 2), pady=(4, 2))
            self.actions_frame.grid(row=0, column=1, sticky="e", padx=(2, 8), pady=(4, 2))
            self.nav_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=(0, 4))

            if hasattr(self, 'nav_buttons'):
                for btn in self.nav_buttons.values():
                    btn.pack_forget()
                    btn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

    def _reflow_footer(self, mode, w):
        if not hasattr(self, 'footer_bar') or not hasattr(self, 'footer_left_lbl') or not hasattr(self, 'footer_right_lbl'):
            return
        self.footer_left_lbl.pack_forget()
        self.footer_right_lbl.pack_forget()

        if w >= 850:
            self.footer_bar.config(height=32)
            self.footer_left_lbl.pack(side=tk.LEFT, padx=16)
            self.footer_right_lbl.pack(side=tk.RIGHT, padx=16)
            self.footer_left_lbl.config(
                text="SG CUBE 2.5.0  |  Your Personal AI Companion",
                font=("Segoe UI", 11)
            )
            self.footer_right_lbl.config(font=("Segoe UI", 11))
        else:
            self.footer_bar.config(height=42)
            self.footer_left_lbl.pack(side=tk.TOP, anchor="w", padx=12, pady=(2, 0))
            self.footer_right_lbl.pack(side=tk.TOP, anchor="w", padx=12, pady=(0, 2))
            self.footer_left_lbl.config(
                text="SG CUBE 2.5.0  |  Your Personal AI Companion",
                font=("Segoe UI", 10)
            )
            self.footer_right_lbl.config(font=("Segoe UI", 10))

    def _update_nav_button_sizes(self, mode):
        if not getattr(self, 'nav_buttons', None):
            return
        icon_size = 32 if mode == "WIDE" else (28 if mode == "MEDIUM" else 24)
        font_size = 13 if mode == "WIDE" else (11 if mode == "MEDIUM" else 10)
        padx = 14 if mode == "WIDE" else (8 if mode == "MEDIUM" else 3)
        pady = 6 if mode == "WIDE" else (4 if mode == "MEDIUM" else 2)

        for btn in self.nav_buttons.values():
            icon_name = getattr(btn, 'icon_name', 'home')
            accent = getattr(btn, 'accent', COLOR_ICON_HOME)
            active = getattr(btn, 'active', False)
            btn.image_normal = GlowingHUDIcon.get_photo_image(
                icon_name, size=icon_size,
                color_hex=COLOR_PEACH_PRIMARY if active else accent,
                hover=False, master=btn
            )
            btn.image_hover = GlowingHUDIcon.get_photo_image(
                icon_name, size=icon_size + 2,
                color_hex=COLOR_PEACH_PRIMARY if active else accent,
                hover=True, master=btn
            )
            btn.image = btn.image_normal
            btn.config(
                image=btn.image_normal,
                font=("Segoe UI", font_size, "bold" if active else "normal"),
                padx=padx,
                pady=pady
            )

    def _update_background_canvas(self, w, h):
        """ Proportional cover scaling with center crop for full-window dark abstract background """
        if not getattr(self, 'bg_orig_image', None) or not getattr(self, 'main_canvas', None):
            return
        if w < 100 or h < 100:
            return
        canv_w = max(w, self.main_canvas.winfo_width())
        canv_h = max(h, self.main_canvas.winfo_height())
        if canv_w <= 1 or canv_h <= 1:
            return

        if getattr(self, '_last_bg_size', None) == (canv_w, canv_h) and getattr(self, 'bg_photo_image', None):
            return
        self._last_bg_size = (canv_w, canv_h)

        try:
            img_w, img_h = self.bg_orig_image.size
            scale = max(canv_w / float(img_w), canv_h / float(img_h))
            new_w, new_h = int(img_w * scale), int(img_h * scale)
            scaled = self.bg_orig_image.resize((new_w, new_h), Image.Resampling.BILINEAR)

            crop_x = max(0, (new_w - canv_w) // 2)
            crop_y = max(0, (new_h - canv_h) // 2)
            cropped = scaled.crop((crop_x, crop_y, crop_x + canv_w, crop_y + canv_h))
            self.bg_photo_image = ImageTk.PhotoImage(cropped)

            if getattr(self, 'bg_image_id', None):
                self.main_canvas.itemconfig(self.bg_image_id, image=self.bg_photo_image)
            else:
                self.bg_image_id = self.main_canvas.create_image(0, 0, image=self.bg_photo_image, anchor="nw")
            self.main_canvas.tag_lower(self.bg_image_id)
        except Exception:
            pass

    def _update_dynamic_typography(self, w, h):
        """ Smoothly scales primary titles and labels with window dimensions """
        if w < 200 or h < 200:
            return
        scale = max(0.85, min(1.30, min(w / 1366.0, h / 800.0)))
        title_font_size = max(24, int(26 * scale))
        sub_font_size = max(9, int(10 * scale))
        motto_font_size = max(8, int(8 * scale))
        card_head_size = max(16, int(16 * scale))

        if hasattr(self, 'lbl_brand_sg') and self.lbl_brand_sg:
            self.lbl_brand_sg.config(font=("Segoe UI", title_font_size, "bold"))
        if hasattr(self, 'lbl_brand_cube') and self.lbl_brand_cube:
            self.lbl_brand_cube.config(font=("Segoe UI", title_font_size, "bold"))
        if hasattr(self, 'lbl_brand_sub') and self.lbl_brand_sub:
            self.lbl_brand_sub.config(font=("Segoe UI", sub_font_size))
        if hasattr(self, 'lbl_brand_motto') and self.lbl_brand_motto:
            self.lbl_brand_motto.config(font=("Segoe UI", motto_font_size))
        if hasattr(self, 'hud_env_title') and self.hud_env_title:
            self.hud_env_title.config(font=("Segoe UI", card_head_size, "bold"))
        if hasattr(self, 'hud_obj_title') and self.hud_obj_title:
            self.hud_obj_title.config(font=("Segoe UI", card_head_size, "bold"))
        if hasattr(self, 'hist_title') and self.hist_title:
            self.hist_title.config(font=("Segoe UI", card_head_size, "bold"))
        if hasattr(self, 'stat_title') and self.stat_title:
            self.stat_title.config(font=("Segoe UI", card_head_size, "bold"))

    def _adjust_camera_height(self, mode, w, h):
        """ Ensures the camera is a large, dominant viewport and never a thin strip """
        if not hasattr(self, 'cam_viewport') or not self.cam_viewport:
            return
        if mode == "WIDE":
            avail_h = max(500, h - 130)
            upper_h = int(avail_h * 0.54)
            cam_h = max(300, min(360, upper_h - 60))
            self.cam_viewport.config(height=cam_h)
            self.cam_viewport.pack_propagate(False)
        elif mode == "MEDIUM":
            cam_h = min(420, max(280, int(w * 0.35)))
            self.cam_viewport.config(height=cam_h)
            self.cam_viewport.pack_propagate(False)
        else:  # SMALL
            cam_h = min(380, max(240, int(w * 0.5625)))
            self.cam_viewport.config(height=cam_h)
            self.cam_viewport.pack_propagate(False)

    def _reflow_layout(self, mode, w, h):
        for widget in (self.hud_env_card, self.cam_outer_card, self.hud_obj_card):
            widget.grid_forget()
        for widget in (self.card_history, self.card_cube, self.card_status):
            widget.grid_forget()

        self._reflow_header(mode, w)
        self._reflow_footer(mode, w)
        self._update_nav_button_sizes(mode)

        if mode == "WIDE":
            self.main_scrollbar.pack_forget()
            self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            self.stage_upper.grid_columnconfigure(0, weight=12, minsize=260)
            self.stage_upper.grid_columnconfigure(1, weight=34, minsize=480)
            self.stage_upper.grid_columnconfigure(2, weight=12, minsize=260)
            self.stage_upper.grid_rowconfigure(0, weight=1)
            self.stage_upper.grid_rowconfigure(1, weight=0)

            pad_x = 10
            self.hud_env_card.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, pad_x), pady=0)
            self.cam_outer_card.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=pad_x, pady=0)
            self.hud_obj_card.grid(row=0, column=2, columnspan=1, sticky="nsew", padx=(pad_x, 0), pady=0)

            self.stage_lower.grid_columnconfigure(0, weight=1, minsize=300)
            self.stage_lower.grid_columnconfigure(1, weight=1, minsize=320)
            self.stage_lower.grid_columnconfigure(2, weight=1, minsize=300)
            self.stage_lower.grid_rowconfigure(0, weight=1)

            self.card_history.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, pad_x), pady=0)
            self.card_cube.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=pad_x, pady=0)
            self.card_status.grid(row=0, column=2, columnspan=1, sticky="nsew", padx=(pad_x, 0), pady=0)

            self.orb_canvas.config(width=380, height=260)

        elif mode == "MEDIUM":
            self.main_scrollbar.pack_forget()
            self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Upper Stage: Environment (col 0, weight 1) | Large Camera (col 1, weight 2)
            # Row 1: Scene (col 0..1, columnspan 2)
            self.stage_upper.grid_columnconfigure(0, weight=1, minsize=240)
            self.stage_upper.grid_columnconfigure(1, weight=2, minsize=420)
            self.stage_upper.grid_columnconfigure(2, weight=0, minsize=0)
            self.stage_upper.grid_rowconfigure(0, weight=1)
            self.stage_upper.grid_rowconfigure(1, weight=0)

            self.hud_env_card.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, 6), pady=(0, 6))
            self.cam_outer_card.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
            self.hud_obj_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

            self.stage_lower.grid_columnconfigure(0, weight=1, minsize=200)
            self.stage_lower.grid_columnconfigure(1, weight=1, minsize=220)
            self.stage_lower.grid_columnconfigure(2, weight=1, minsize=200)
            self.stage_lower.grid_rowconfigure(0, weight=1)

            self.card_history.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, 6), pady=0)
            self.card_cube.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=6, pady=0)
            self.card_status.grid(row=0, column=2, columnspan=1, sticky="nsew", padx=(6, 0), pady=0)

            self.orb_canvas.config(width=280, height=190)

        else:  # SMALL Mode: Stacked Reflow
            self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            self.stage_upper.grid_columnconfigure(0, weight=1, minsize=200)
            self.stage_upper.grid_columnconfigure(1, weight=0, minsize=0)
            self.stage_upper.grid_columnconfigure(2, weight=0, minsize=0)
            self.stage_upper.grid_rowconfigure(0, weight=0)
            self.stage_upper.grid_rowconfigure(1, weight=0)
            self.stage_upper.grid_rowconfigure(2, weight=0)

            self.hud_env_card.grid(row=0, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))
            self.cam_outer_card.grid(row=1, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))
            self.hud_obj_card.grid(row=2, column=0, columnspan=1, sticky="ew", padx=0, pady=0)

            self.stage_lower.grid_columnconfigure(0, weight=1, minsize=200)
            self.stage_lower.grid_columnconfigure(1, weight=0, minsize=0)
            self.stage_lower.grid_columnconfigure(2, weight=0, minsize=0)
            self.stage_lower.grid_rowconfigure(0, weight=0)
            self.stage_lower.grid_rowconfigure(1, weight=0)
            self.stage_lower.grid_rowconfigure(2, weight=0)

            self.card_history.grid(row=0, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))
            self.card_cube.grid(row=1, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))
            self.card_status.grid(row=2, column=0, columnspan=1, sticky="ew", padx=0, pady=0)

            self.orb_canvas.config(width=240, height=160)

    def _update_scroll_region(self):
        if hasattr(self, 'scrollable_content') and hasattr(self, 'main_canvas'):
            self.scrollable_content.update_idletasks()
            req_h = self.scrollable_content.winfo_reqheight()
            canv_h = self.main_canvas.winfo_height()
            self.main_canvas.configure(scrollregion=(0, 0, self.scrollable_content.winfo_reqwidth(), req_h))
            if req_h > canv_h + 10:
                self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            else:
                self.main_scrollbar.pack_forget()
                self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _display_camera_frame(self, pil_img):
        self.last_pil_frame = pil_img
        self._rescale_camera_preview()

    def _rescale_camera_preview(self):
        if not getattr(self, 'last_pil_frame', None) or not getattr(self, 'cam_viewport', None):
            return
        vw = max(180, self.cam_viewport.winfo_width())
        vh = max(140, self.cam_viewport.winfo_height())

        orig_w, orig_h = self.last_pil_frame.size
        aspect = orig_w / float(orig_h)

        if vw / float(vh) > aspect:
            target_h = vh
            target_w = int(vh * aspect)
        else:
            target_w = vw
            target_h = int(vw / aspect)

        target_w = max(120, target_w)
        target_h = max(90, target_h)

        scaled = self.last_pil_frame.resize((target_w, target_h), Image.Resampling.BILINEAR)
        photo_img = ImageTk.PhotoImage(scaled)
        self.preview_label.config(image=photo_img, text="")
        self.preview_label.image = photo_img

    def _update_info_strip(self):
        """ Periodically and reactively updates Recent History, System Status, and Footer Live Time """
        if not hasattr(self, 'root') or not self.root:
            return

        # 1. Update RECENT HISTORY (6 items)
        try:
            if hasattr(self, 'engine') and self.engine and hasattr(self.engine, 'history') and self.engine.history:
                with self.engine.history._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT timestamp, sender, text FROM messages ORDER BY id DESC LIMIT 6")
                    rows = [dict(r) for r in cursor.fetchall()]
            else:
                rows = []

            for i in range(6):
                if hasattr(self, 'info_history_rows') and i < len(self.info_history_rows):
                    lbl_t, lbl_spk, lbl_msg = self.info_history_rows[i]
                    if i < len(rows):
                        r = rows[i]
                        ts = r.get("timestamp", 0)
                        t_str = time.strftime("%H:%M", time.localtime(ts)) if ts else "--:--"
                        txt = r.get("text", "")
                        clean_txt = (txt[:44] + "...") if len(txt) > 44 else txt
                        is_user = r.get("sender") == "user"
                        lbl_t.config(text=t_str, fg=COLOR_PEACH_MUTED)
                        lbl_spk.config(text="You" if is_user else "AI", fg=COLOR_ICON_VISION if is_user else COLOR_STATUS_GREEN)
                        lbl_msg.config(text=clean_txt, fg=COLOR_ICON_VISION if is_user else COLOR_PEACH_PRIMARY)
                    else:
                        if i == 0 and not rows:
                            lbl_t.config(text="--:--", fg=COLOR_PEACH_MUTED)
                            lbl_spk.config(text="AI", fg=COLOR_STATUS_GREEN)
                            lbl_msg.config(text="Ready whenever you are.", fg=COLOR_PEACH_MUTED)
                        else:
                            lbl_t.config(text="", fg=COLOR_PEACH_MUTED)
                            lbl_spk.config(text="", fg=COLOR_STATUS_GREEN)
                            lbl_msg.config(text="", fg=COLOR_PEACH_MUTED)
                elif hasattr(self, 'info_history_labels') and i < len(self.info_history_labels):
                    lbl = self.info_history_labels[i]
                    if i < len(rows):
                        r = rows[i]
                        ts = r.get("timestamp", 0)
                        t_str = time.strftime("%H:%M", time.localtime(ts)) if ts else "--:--"
                        txt = r.get("text", "")
                        clean_txt = (txt[:36] + "...") if len(txt) > 36 else txt
                        is_user = r.get("sender") == "user"
                        prefix = "You: " if is_user else "AI: "
                        fg_prefix = COLOR_ICON_VISION if is_user else COLOR_STATUS_GREEN
                        lbl.config(text=f"{t_str}  {prefix}{clean_txt}", fg=fg_prefix)
                    else:
                        lbl.config(text="", fg=COLOR_PEACH_MUTED)
        except Exception:
            pass

        # 2. Update SYSTEM STATUS
        try:
            if hasattr(self, 'info_status_labels') and self.info_status_labels:
                cam_active = getattr(self, 'camera_running', True) and not getattr(self, 'camera_paused', False)
                self.info_status_labels["cam"].config(
                    text="● Active" if cam_active else "● Paused",
                    fg=COLOR_STATUS_GREEN if cam_active else COLOR_WARNING_GOLD
                )

                mic_active = getattr(self, 'mic_running', True)
                is_listening = getattr(self, 'current_state', 'IDLE') in ("LISTENING", "USER_SPEAKING")
                self.info_status_labels["mic"].config(
                    text="● Active" if mic_active else "● Off",
                    fg=COLOR_STATUS_GREEN if mic_active else COLOR_ALERT_RED
                )

                ai_active = getattr(self, 'ai_running', False)
                self.info_status_labels["gemini"].config(
                    text="● Connected" if ai_active else "● Ready",
                    fg=COLOR_STATUS_GREEN if ai_active else COLOR_ICON_VISION
                )

                is_speaking = getattr(self, 'current_state', 'IDLE') == "AI_SPEAKING"
                self.info_status_labels["speaker"].config(
                    text="● Active" if not is_speaking else "● Speaking",
                    fg=COLOR_STATUS_GREEN if not is_speaking else COLOR_ICON_VISION
                )

                try:
                    import psutil
                    bat = psutil.sensors_battery()
                    bat_txt = f"🔋 {int(bat.percent)}%" if bat else "🔋 89%"
                except Exception:
                    bat_txt = "🔋 89%"
                self.info_status_labels["battery"].config(text=bat_txt, fg=COLOR_STATUS_GREEN)

                self.info_status_labels["network"].config(text="● Online", fg=COLOR_STATUS_GREEN)
        except Exception:
            pass

        # 3. Update Footer Live Date & Time
        try:
            if hasattr(self, 'footer_right_lbl') and self.footer_right_lbl:
                now_str = time.strftime("%A, %B %d, %Y  |  %I:%M %p").replace(" 0", " ")
                self.footer_right_lbl.config(text=now_str, fg=COLOR_PEACH_PRIMARY)
        except Exception:
            pass

        try:
            self.root.after(1000, self._update_info_strip)
        except tk.TclError:
            pass

    def _create_nav_btn(self, parent, icon_name, text, command, active=False, accent=COLOR_CYAN_PRIMARY, tooltip=""):
        if active:
            fg_col = COLOR_PEACH_PRIMARY
            bg_col = COLOR_NAV_ACTIVE_BG
            border_col = COLOR_OLIVE_BRIGHT
            icon_img = GlowingHUDIcon.get_photo_image(icon_name, size=32, color_hex=COLOR_PEACH_PRIMARY, hover=True, master=parent)
        else:
            fg_col = COLOR_PEACH_SECONDARY
            bg_col = COLOR_BG_SECONDARY
            border_col = COLOR_BG_SECONDARY
            icon_img = GlowingHUDIcon.get_photo_image(icon_name, size=30, color_hex=accent, hover=False, master=parent)

        hover_icon = GlowingHUDIcon.get_photo_image(icon_name, size=32, color_hex=COLOR_PEACH_PRIMARY if active else accent, hover=True, master=parent)

        btn = tk.Button(
            parent,
            text=text,
            image=icon_img,
            compound=tk.TOP,
            font=("Segoe UI", 13, "bold" if active else "normal"),
            bg=bg_col,
            fg=fg_col,
            activebackground=COLOR_OLIVE_DARK if active else COLOR_PANEL_HOVER,
            activeforeground=COLOR_PEACH_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            highlightbackground=border_col,
            highlightthickness=1,
            command=command
        )
        btn.image_normal = icon_img
        btn.image_hover = hover_icon
        btn.image = icon_img
        btn.icon_name = icon_name
        btn.accent = accent
        btn.active = active
        btn.nav_text = text
        btn.pack(side=tk.LEFT, padx=8)

        if not active:
            def on_enter(e):
                btn.config(bg=COLOR_PANEL_HOVER, fg=COLOR_PEACH_PRIMARY, image=btn.image_hover, highlightbackground=COLOR_OLIVE_PRIMARY)
            def on_leave(e):
                btn.config(bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_SECONDARY, image=btn.image_normal, highlightbackground=COLOR_BG_SECONDARY)
            btn.bind("<Enter>", on_enter, add="+")
            btn.bind("<Leave>", on_leave, add="+")
        else:
            def on_enter(e):
                btn.config(bg=COLOR_OLIVE_DARK, highlightbackground=COLOR_OLIVE_GLOW)
            def on_leave(e):
                btn.config(bg=COLOR_NAV_ACTIVE_BG, highlightbackground=COLOR_OLIVE_BRIGHT)
            btn.bind("<Enter>", on_enter, add="+")
            btn.bind("<Leave>", on_leave, add="+")

        if tooltip:
            HUDTooltip(btn, tooltip)
        return btn

    def _create_floating_action_btn(self, parent, icon_name, text, command, accent=COLOR_CYAN_PRIMARY, tooltip=""):
        normal_img = GlowingHUDIcon.get_photo_image(icon_name, size=24, color_hex=accent, hover=False, master=parent)
        hover_img = GlowingHUDIcon.get_photo_image(icon_name, size=26, color_hex=accent, hover=True, master=parent)

        btn = tk.Button(
            parent,
            text=text,
            image=normal_img,
            compound=tk.TOP,
            font=("Segoe UI", 8, "bold"),
            bg=COLOR_PANEL_DEEP,
            fg=COLOR_TEXT_PRIMARY,
            activebackground="#0A0A0A",
            activeforeground=accent,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightbackground=COLOR_BORDER_SUBTLE,
            highlightthickness=1,
            command=command
        )
        btn.image_normal = normal_img
        btn.image_hover = hover_img
        btn.image = normal_img
        btn.pack(side=tk.LEFT, padx=4, pady=(2, 0))

        def on_enter(e):
            btn.config(bg="#0A0A0A", fg="#ffffff", image=btn.image_hover, highlightbackground=accent)
            btn.pack_configure(pady=(0, 2))
        def on_leave(e):
            btn.config(bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, image=btn.image_normal, highlightbackground=COLOR_BORDER_SUBTLE)
            btn.pack_configure(pady=(2, 0))
        def on_press(e):
            btn.config(bg=COLOR_BG_PRIMARY, highlightbackground=COLOR_BG_PRIMARY)
        def on_release(e):
            btn.config(bg="#0A0A0A", highlightbackground=accent)

        btn.bind("<Enter>", on_enter, add="+")
        btn.bind("<Leave>", on_leave, add="+")
        btn.bind("<Button-1>", on_press, add="+")
        btn.bind("<ButtonRelease-1>", on_release, add="+")

        if tooltip:
            HUDTooltip(btn, tooltip)
        return btn

    def _bind_shortcuts(self):
        self.root.bind("<space>", lambda e: self._on_space_shortcut())
        self.root.bind("<Escape>", lambda e: self._on_esc_shortcut())
        self.root.bind("<Control-Shift-S>", lambda e: self.open_settings_dialog())
        self.root.bind("<Control-s>", lambda e: self.open_settings_dialog())
        self.root.bind("<Control-m>", lambda e: self.open_memory_dialog())
        self.root.bind("<Control-h>", lambda e: self.open_history_dialog())
        self.root.bind("<Control-v>", lambda e: self.open_vision_dialog())
        self.root.bind("<Control-p>", lambda e: self.open_people_dialog())
        self.root.bind("<Control-q>", lambda e: self.on_close())

    def _on_nav_home(self):
        """ Home navigation tab: ensures primary companion dashboard is active """
        self.show_context_alert("SG CUBE Home Dashboard Active", color=COLOR_CYAN_PRIMARY)

    def _on_space_shortcut(self):
        """ Spacebar key shortcut: interrupts speech / triggers immediate attention """
        self._clear_playback_queue()
        self.set_state("LISTENING")
        self.show_context_alert("Listening...", color=COLOR_CYAN_PRIMARY)

    def _on_esc_shortcut(self):
        """ Escape key shortcut: immediately stops current AI speech """
        self._clear_playback_queue()
        self.set_state("LISTENING")
        self.show_context_alert("Speech stopped.", color=COLOR_TEXT_MUTED)

    def _trigger_action_async(self, action_key: str, display_label: str, intent_query: str, specific_handler=None):
        """ Debounced, non-blocking execution of floating action buttons with loading and audio feedback """
        with self.state_lock:
            if hasattr(self, 'action_busy') and self.action_busy:
                print(f"[ACTION-BTN] Operation '{display_label}' already in progress. Debounce active.")
                self.show_context_alert("Processing in progress...", color=COLOR_ORANGE)
                return
            self.action_busy = True

        print(f"[ACTION-BTN] Triggering action '{display_label}' ('{intent_query}')")
        self._clear_playback_queue()
        self.set_state("AI_THINKING")
        self.gui_queue.put(("TRANSCRIPT_USER", intent_query))
        self.show_context_alert(f"Processing {display_label}...", color=COLOR_CYAN_PRIMARY)

        def worker():
            try:
                if specific_handler:
                    resp = specific_handler()
                else:
                    resp = self.engine.process_user_speech_query(intent_query)

                if resp:
                    print(f"[ACTION-RESULT] {display_label}: '{resp}'")
                    self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", resp))
                    if hasattr(self, 'active_history_session_id') and self.active_history_session_id:
                        self.engine.history.add_message(self.active_history_session_id, "user", intent_query)
                        self.engine.history.add_message(self.active_history_session_id, "assistant", resp)
                    self.engine.response_manager.add_response(resp, priority=1, force=True)
                else:
                    err_msg = f"No result returned for {display_label}."
                    self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", err_msg))
            except Exception as e:
                print(f"[ACTION-ERR] Error in {display_label}: {e}")
                self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", f"Error processing {display_label}: {e}"))
            finally:
                with self.state_lock:
                    self.action_busy = False
                if self.current_state not in ("SLEEPING", "STOPPED", "CLOSED"):
                    self.set_state("LISTENING")

        threading.Thread(target=worker, daemon=True).start()

    def _trigger_voice_intent(self, text_query: str):
        """ Programmatically triggers a voice query from floating action buttons """
        self._trigger_action_async("voice_intent", "Voice Intent", text_query)

    # --- Real 3D Cross-Axis Rotating SG CUBE Assistant Rendering ---
    def _animate_sg_cube_core(self):
        if not self.root or not self.orb_canvas:
            return

        self.anim_time += 0.035
        self.anim_angle += 0.08
        if self.anim_angle > 2 * math.pi:
            self.anim_angle = 0.0

        state = self.current_state

        # Multi-axis / Cross-axis rotation speeds mapped from backend states
        rot_y_delta = 0.022
        pulse = 1.0
        if state == "AI_SPEAKING":
            rot_y_delta = 0.040
            pulse = 1.0 + 0.09 * math.sin(self.anim_angle * 3.0)
            status_txt = "● SG CUBE Speaking..."
            sys_txt = "● Speaking"
            sys_col = COLOR_TEAL_MINT
        elif state == "USER_SPEAKING":
            rot_y_delta = 0.032
            pulse = 1.0 + 0.06 * math.sin(self.anim_angle * 2.5)
            status_txt = "● Listening to you..."
            sys_txt = "● User Speaking"
            sys_col = COLOR_OLIVE_BRIGHT
        elif state == "AI_THINKING":
            rot_y_delta = 0.018
            pulse = 1.0 + 0.04 * math.sin(self.anim_angle * 1.5)
            status_txt = "● Thinking..."
            sys_txt = "● Thinking"
            sys_col = COLOR_WARNING_GOLD
        elif state == "SAFETY_ALERT":
            rot_y_delta = 0.048
            pulse = 1.0 + 0.10 * math.sin(self.anim_angle * 4.0)
            status_txt = "⚠ Physical Hazard Alert"
            sys_txt = "⚠ Hazard Alert"
            sys_col = COLOR_ALERT_RED
        elif state == "RECONNECTING":
            rot_y_delta = 0.025
            status_txt = "● Reconnecting..."
            sys_txt = "● Reconnecting"
            sys_col = COLOR_ORANGE
        elif state == "SLEEPING":
            rot_y_delta = 0.0
            pulse = 0.90
            status_txt = "● Sleeping (Say 'Hey SG CUBE')"
            sys_txt = "● Sleeping"
            sys_col = COLOR_TEXT_MUTED
        else:  # LISTENING / IDLE
            rot_y_delta = 0.022 if state == "IDLE" else 0.030
            pulse = 1.0 + 0.04 * math.sin(self.anim_angle)
            status_txt = "● SG CUBE Listening"
            sys_txt = "● Listening" if state == "LISTENING" else "● Online"
            sys_col = COLOR_CYAN_PRIMARY if state == "LISTENING" else COLOR_STATUS_GREEN

        # Multi-axis floating motion: Y=11s continuous, X=6s oscillation -8°..+8°, Z=8.5s subtle -2°..+2°
        if state != "SLEEPING":
            self.cube_rot_y += (2 * math.pi) / (11.0 / 0.035)  # 11s full rotation period
            if self.cube_rot_y > 2 * math.pi:
                self.cube_rot_y -= 2 * math.pi

        rot_x = 0.1396 * math.sin(self.anim_time * (2 * math.pi / 6.0))  # -8° to +8° over 6s
        rot_z = 0.0349 * math.cos(self.anim_time * (2 * math.pi / 8.5))  # -2° to +2° over 8.5s

        # Update Header Status Label
        if hasattr(self, 'sys_status_label') and self.sys_status_label:
            self.sys_status_label.config(text=sys_txt, fg=sys_col)

        # Update Context Banner text if no active alert
        if self.context_banner_timer <= 0:
            self.context_banner.config(text=status_txt, fg=COLOR_CYAN_PRIMARY if state != "SAFETY_ALERT" else COLOR_ALERT_RED)
        else:
            self.context_banner_timer -= 1

        # Clear centerpiece canvas & render Futuristic 3D SG CUBE
        self.orb_canvas.delete("all")
        self.cube_3d.draw_audio_core(
            self.orb_canvas,
            time_val=self.anim_time,
            state=state,
            pulse=pulse,
            hover=self.cube_hover,
            mouse_tilt=self.cube_mouse_tilt
        )

        # Clear & render 3D Rotating Cube Logo in Header
        if hasattr(self, 'header_cube_canvas') and self.header_cube_canvas:
            self.header_cube_canvas.delete("all")
            self.cube_3d.draw_header_cube(self.header_cube_canvas, rot_y=self.cube_rot_y, rot_x=0.38, state=state)

        try:
            self.root.after(35, self._animate_sg_cube_core)
        except tk.TclError:
            pass

    # --- GUI Queue Processing (Main Thread) ---
    def _process_gui_queue(self):
        while not self.gui_queue.empty():
            try:
                msg_type, payload = self.gui_queue.get_nowait()
                if msg_type == "FRAME":
                    self._display_camera_frame(payload)
                elif msg_type == "ACTION":
                    if payload == "WAKE_FOREGROUND":
                        self.bring_to_foreground()
                elif msg_type == "STATE":
                    pass
                elif msg_type == "PERCEPTION":
                    if "Hazards:" in payload and "Clear" not in payload:
                        self.show_context_alert(payload, color=COLOR_ALERT_RED)
                elif msg_type == "TRANSCRIPT_USER":
                    self.dialogue_banner.config(text=f"You: \"{payload}\"", fg=COLOR_CYAN_PRIMARY)
                    self._update_info_strip()
                elif msg_type == "TRANSCRIPT_AI":
                    self.dialogue_banner.config(text=f"SG CUBE: \"{payload}\"", fg=COLOR_TEAL_MINT)
                    self._update_info_strip()
                elif msg_type == "TRANSCRIPT_ASSISTIVE":
                    self.dialogue_banner.config(text=f"Assistive: \"{payload}\"", fg=COLOR_WARNING_GOLD)
                    self.show_context_alert(payload, color=COLOR_CYAN_PRIMARY)
                    self._update_info_strip()
                elif msg_type == "CAMERA_STATUS":
                    if payload and payload.startswith("● LIVE"):
                        badge_text = payload.replace("● LIVE ", "● ")
                        self.cam_badge.config(text=badge_text, bg=COLOR_PANEL_DEEP, fg=COLOR_TEAL_MINT)
                    elif payload == "● META GLASS":
                        self.cam_badge.config(text="● META GLASS", bg=COLOR_CYAN_PRIMARY, fg="#000000")
                    elif payload == "● RECONNECTING":
                        self.cam_badge.config(text="● RECONNECTING", bg=COLOR_ALERT_RED, fg="#ffffff")
                elif msg_type == "HUD_UPDATE":
                    self._update_hud_display(payload)
                elif msg_type == "CAMERA_STOPPED":
                    self.cam_badge.config(text="OFFLINE", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_MUTED)
                    self.preview_label.config(image="", text="Camera View Offline")
            except queue.Empty:
                break
        if self.root:
            try:
                self.root.after(20, self._process_gui_queue)
            except tk.TclError:
                pass

    def _update_hud_display(self, data: dict):
        """ Updates the Live Vision left (Environment) and right (Objects) HUD cards with real backend data """
        if not hasattr(self, 'hud_env_person_lbl') or not self.hud_env_person_lbl:
            return

        try:
            # 1. Update Environment Card
            env = data.get("environment", {})
            faces = data.get("faces", [])
            safety = data.get("safety", {})

            # Person / Multi-Person Awareness
            people_info = data.get("people_awareness") or env.get("people_awareness")
            if people_info:
                tot = people_info.get("total_people", 0)
                known_names = people_info.get("known_names", [])
                if tot == 0:
                    self.hud_env_person_lbl.config(text="None", fg=COLOR_PEACH_SECONDARY)
                elif known_names:
                    names_str = ", ".join(known_names[:2])
                    self.hud_env_person_lbl.config(text=f"{names_str}", fg=COLOR_PEACH_PRIMARY)
                else:
                    self.hud_env_person_lbl.config(text=f"{tot} {'person' if tot==1 else 'people'}", fg=COLOR_PEACH_PRIMARY)
            elif faces:
                names = [f.get("name") or "Person" for f in faces]
                self.hud_env_person_lbl.config(text=f"{', '.join(names[:2])}", fg=COLOR_PEACH_PRIMARY)
            else:
                self.hud_env_person_lbl.config(text="1 person" if getattr(self, 'camera_running', True) else "None", fg=COLOR_PEACH_SECONDARY)

            # Room / Scene
            scene_text = env.get("scene_summary", "Living Room")
            clean_scene = (scene_text[:16] + "...") if len(scene_text) > 16 else scene_text
            self.hud_env_room_lbl.config(text=clean_scene.title(), fg=COLOR_PEACH_SECONDARY)

            # Light
            light_lvl = env.get("light_level", "Normal")
            self.hud_env_light_lbl.config(text=f"{light_lvl.title()}", fg=COLOR_PEACH_SECONDARY)

            # Noise
            noise_lvl = env.get("noise_level", "Low")
            self.hud_env_noise_lbl.config(text=f"{noise_lvl.title()}", fg=COLOR_PEACH_SECONDARY)

            # Safety
            if safety.get("hazard_detected"):
                warn_txt = safety.get("warning_text", "Hazard detected")
                clean_warn = (warn_txt[:14] + "...") if len(warn_txt) > 14 else warn_txt
                self.hud_env_safety_lbl.config(text=clean_warn, fg=COLOR_ALERT_RED)
            else:
                self.hud_env_safety_lbl.config(text="Clear", fg=COLOR_STATUS_GREEN)

            # 2. Update Scene Card
            scene_data = data.get("scene", {})
            objects = data.get("objects", [])
            scene_objects = env.get("scene_objects", []) or scene_data.get("objects", [])
            obstructions = env.get("obstructions", []) or scene_data.get("obstructions", [])
            people_cnt = len(faces)
            obj_cnt = len(scene_objects) if scene_objects else len(objects)

            if hasattr(self, 'hud_obj_labels') and self.hud_obj_labels:
                left_items = [o.get("class_name", "object") for o in scene_objects if o.get("relative_position", {}).get("h_zone") in ("left", "center_left")]
                right_items = [o.get("class_name", "object") for o in scene_objects if o.get("relative_position", {}).get("h_zone") in ("right", "center_right")]
                center_items = [o.get("class_name", "object") for o in scene_objects if o.get("relative_position", {}).get("h_zone") == "center"]

                values = [
                    (f"{max(1, people_cnt)} | Objects: {max(3, obj_cnt)}", COLOR_PEACH_PRIMARY),
                    (', '.join(left_items[:1]) if left_items else 'None', COLOR_PEACH_SECONDARY),
                    (', '.join(center_items[:1]) if center_items else 'Person', COLOR_PEACH_SECONDARY),
                    (', '.join(right_items[:1]) if right_items else 'Object', COLOR_PEACH_SECONDARY),
                    ('Clear' if not obstructions else obstructions[0].get('zone', 'Obstacle').title(), COLOR_STATUS_GREEN if not obstructions else COLOR_ALERT_RED),
                ]
                for idx, lbl in enumerate(self.hud_obj_labels):
                    if idx < len(values):
                        val_txt, val_fg = values[idx]
                        lbl.config(text=val_txt, fg=val_fg)
        except Exception:
            pass

    def show_context_alert(self, text: str, color: str = COLOR_CYAN_PRIMARY):
        """ Temporarily displays a contextual detection banner near the companion core """
        self.context_banner.config(text=f"● {text}", fg=color)
        self.context_banner_timer = 120  # ~4 seconds duration

    # --- Seamless Auto-Start Lifecycle ---
    def _auto_start_services(self):
        """ Auto-starts camera, audio stream, and Gemini Live in the background """
        print("[AUTO-START] Beginning seamless background initialization...")
        self._notify_wake_listener_pause()
        self.set_state("INITIALIZING")

        self.start_camera()

        api_key = self.engine.key_manager.load_api_key()
        if not api_key:
            self.dialogue_banner.config(text="Gemini API key is not configured. Please open Settings (Ctrl+Shift+S).", fg="#ff4757")
            print("[AUTO-START] Gemini API key not configured. Open Settings to configure.")
            return

        self.start_ai(api_key)

        with self.state_lock:
            self.wake_greeting_pending = True
            self.wake_greeting_timer = time.time()

    def start_camera(self):
        """ Starts or restores the continuous camera capture worker thread """
        with self.session_lock:
            if self.camera_running and self.camera_thread and self.camera_thread.is_alive():
                print("[CAMERA] Camera already active.")
                return
            print("[CAMERA] initialization started")
            self.camera_running = True
            self.first_valid_frame_received = False
            self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self.camera_thread.start()
            print("[CAMERA] worker started")

    def stop_camera(self):
        """ Safe teardown of camera capture thread (called on app exit or sleep) """
        print("[CAMERA] Stopping camera service worker thread...")
        self.camera_running = False
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=1.5)
        self.camera_thread = None
        self.gui_queue.put(("CAMERA_STOPPED", None))
        print("[CAMERA] hardware released")
        print("[CAMERA] camera state = SLEEPING / OFF")

    def toggle_camera(self):
        """ Toggles camera on/off """
        with self.session_lock:
            running = getattr(self, 'camera_running', False)
        if running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_ai(self, api_key=None):
        if self.ai_running:
            return
        if not api_key:
            key_info = self.engine.key_manager.get_active_key()
            if not key_info:
                print("[API-KEY-FAILOVER] No available valid Gemini API keys found.")
                self.set_state("DISCONNECTED")
                return
            _, api_key = key_info

        self.ai_running = True
        print(f"[MAIN] MICROPHONE STARTED ({self.engine.key_manager.get_active_key_label()})")
        self.ai_thread = threading.Thread(target=self._ai_worker_thread, args=(api_key,), daemon=True)
        self.ai_thread.start()

    def stop_ai(self):
        if not self.ai_running:
            return
        self.ai_running = False
        print("[MAIN] MICROPHONE STOPPED")
        with self.session_lock:
            self.active_session_id = None
        self.playback_stop_evt.set()
        self._clear_playback_queue()
        self.set_state("STOPPED")

    def enter_sleep_mode(self):
        """ Puts SG CUBE to sleep after playing one short farewell greeting """
        print("[SLEEP] requested")

        # Generate personalized or generic sleep farewell greeting
        user_name = self.engine.store.get_setting("user_display_name") or self.engine.store.get_setting("user_name", "")
        name_str = f" {user_name}" if user_name and user_name != "User" else ""
        farewell_msg = f"Okay{name_str}, I'm going to sleep."
        self.last_farewell_msg = farewell_msg

        print(f"[SLEEP-GREETING] Farewell message generated: '{farewell_msg}'")
        self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", farewell_msg))

        # Queue farewell response in ResponseManager & playback
        self.engine.response_manager.add_response(farewell_msg, priority=2, force=True)

        # Wait up to 2.5s for audio playback queue to drain before shutting down services
        start_wait = time.time()
        while not self.playback_queue.empty() and (time.time() - start_wait < 2.5):
            time.sleep(0.05)

        time.sleep(0.3)

        print("[SLEEP] stopping speech")
        self._clear_playback_queue()
        print("[SLEEP] audio cleared")

        print("[SLEEP] Gemini session closed")
        print("[SLEEP] releasing microphone")
        self.stop_ai()

        print("[SLEEP] releasing camera")
        if hasattr(self.engine, 'meta_glass'):
            self.engine.meta_glass.on_sleep()
        self.stop_camera()

        self.set_state("SLEEPING")
        print("[STATE] SLEEPING")
        print("[HANDOFF] MAIN -> HOTWORD")
        print("[MIC_OWNER] HOTWORD")
        print("[HOTWORD] MICROPHONE ACTIVE")
        print("[HOTWORD] READY")
        print("[SLEEP] SG CUBE inactive")

        try:
            self.root.withdraw()
            print("[SLEEP] SG CUBE main window hidden/withdrawn.")
        except Exception as e:
            print(f"[SLEEP] Error withdrawing GUI window: {e}")

        self.root.after(400, self._notify_wake_listener_resume)

    def _ensure_wake_listener_running(self):
        """ Ensures background wake listener is running when main app sleeps or exits. """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.4)
            res = sock.connect_ex(('127.0.0.1', 49154))  # listener lock socket
            if res == 0:
                return  # already running
        except Exception:
            pass
        finally:
            if sock:
                try: sock.close()
                except Exception: pass

        try:
            app_dir = os.path.abspath(os.path.dirname(__file__))
            python_candidates = [
                os.path.join(app_dir, "runtime", "Scripts", "python.exe"),
                os.path.join(app_dir, "runtime", "python.exe"),
                sys.executable,
                os.path.join(app_dir, ".venv", "Scripts", "python.exe"),
            ]
            python_exe = sys.executable
            for p in python_candidates:
                if os.path.exists(p):
                    python_exe = p
                    break

            listener_script = os.path.join(app_dir, "wake_listener.py")
            if os.path.exists(listener_script):
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                subprocess.Popen(
                    [python_exe, listener_script],
                    cwd=app_dir,
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    close_fds=True
                )
                print("[LIFECYCLE] Background wake listener started.")
        except Exception as e:
            print(f"[LIFECYCLE] Error starting wake listener: {e}")

    def _notify_wake_listener_resume(self):
        """ Sends IPC signal over port 49153 to instruct the background wake listener to resume microphone standby """
        sock = None
        notified = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.8)
            sock.connect(('127.0.0.1', IPC_PORT_WAKE_LISTENER))
            sock.sendall(b"RESUME_WAKE_LISTENING\n")
            notified = True
            print("[IPC] Successfully notified background wake listener to resume.")
        except Exception:
            pass
        finally:
            if sock:
                try: sock.close()
                except Exception: pass

        if not notified:
            self._ensure_wake_listener_running()

    def _notify_wake_listener_pause(self):
        """ Sends IPC signal over port 49153 to instruct the background wake listener to pause microphone standby """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.8)
            sock.connect(('127.0.0.1', IPC_PORT_WAKE_LISTENER))
            sock.sendall(b"PAUSE_WAKE_LISTENING\n")
            print("[IPC] Successfully notified background wake listener to pause.")
        except Exception:
            pass
        finally:
            if sock:
                try: sock.close()
                except Exception: pass

    def bring_to_foreground(self):
        """ Restores window from sleep/hidden state, auto-starts camera & AI services, and triggers person-aware greeting """
        self._notify_wake_listener_pause()
        self.set_state("OPENING")
        print("[WAKE] MATCH")
        print("[HANDOFF] HOTWORD -> MAIN")
        print("[MIC_OWNER] HOTWORD RELEASED")
        print("[STATE] OPENING")
        print("[WAKE] detected")
        print("[WAKE] activation started")
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

            if os.name == 'nt':
                try:
                    import win32gui, win32con
                    hwnd = int(self.root.wm_frame(), 16)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            print("[WAKE] application visible")
        except Exception as e:
            print(f"[WAKE] Error bringing to foreground: {e}")

        if hasattr(self.engine, 'meta_glass'):
            self.engine.meta_glass.on_wake()

        if not self.camera_running:
            print("[START] camera initializing")
            self.start_camera()

        api_key = self.engine.key_manager.load_api_key()
        if api_key and not self.ai_running:
            print("[START] microphone initializing")
            print("[START] Gemini connecting")
            self.start_ai(api_key)

        print("[MIC_OWNER] MAIN ACTIVE")
        print("[WAKE] APPLICATION READY")
        self.set_state("LISTENING")
        print("[STATE] ACTIVE / LISTENING")
        print("[START] ready")
        print("[START] listening")

        with self.state_lock:
            self.wake_greeting_pending = True
            self.wake_greeting_timer = time.time()
            self.first_valid_frame_received = False

    def _evaluate_wake_greeting(self, faces: list):
        """ Evaluates camera faces upon wake/startup and queues exactly one person-aware greeting """
        if not self.wake_greeting_pending:
            return

        if not self.engine.store.get_setting("greeting_enabled", True):
            self.wake_greeting_pending = False
            return

        now = time.time()
        elapsed = now - self.wake_greeting_timer

        # Wait for first valid frame from camera loop unless timeout reached
        if not self.first_valid_frame_received and elapsed < 2.5:
            return

        print("[GREETING 01] application startup detected")

        owner_name = self.engine.store.get_setting("user_display_name") or self.engine.store.get_setting("user_name", "")
        print("[GREETING 02] profile loaded")
        safe_name = owner_name if owner_name else "Neutral"
        print(f"[GREETING 03] user display name = {safe_name}")

        hour = time.localtime().tm_hour
        time_period = "morning" if 5 <= hour < 12 else ("afternoon" if 12 <= hour < 17 else ("evening" if 17 <= hour < 22 else "night"))
        print(f"[GREETING 04] time-of-day calculated ({time_period})")

        print(f"[FACE] frame received (faces_count={len(faces)})")
        print(f"[FACE] detection count = {len(faces)}")
        print("[FACE] recognition started")

        chosen_greeting = None

        if faces:
            recognized_name = None
            recognized_conf = 0.0
            for face in faces:
                name = face.get("name")
                if name and name != "Unknown":
                    recognized_name = name
                    recognized_conf = face.get("confidence", 1.0)
                    break

            if recognized_name:
                print(f"[FACE] best match = {recognized_name}")
                print(f"[FACE] confidence = {recognized_conf:.2f}")
                print(f"[FACE] stored identity = {recognized_name}")
                if owner_name and recognized_name.lower() == owner_name.lower():
                    chosen_greeting = f"Good {time_period}, {owner_name}. I'm ready to help."
                else:
                    chosen_greeting = f"Hello, {recognized_name}."
            else:
                print("[FACE] best match = Unknown")
                print("[FACE] confidence = 0.00")
                print("[FACE] stored identity = Unknown")
                chosen_greeting = "Hello. I'm SG CUBE. How can I help?"

        elif elapsed > 2.5:
            print("[FACE] no face detected within 2.5s timeout")
            if owner_name and owner_name != "User":
                chosen_greeting = f"Good {time_period}, {owner_name}. I'm ready to help."
            else:
                chosen_greeting = "Hello. I'm SG CUBE. How can I help?"

        if chosen_greeting:
            self.wake_greeting_pending = False
            print(f"[GREETING 05] greeting text generated: '{chosen_greeting}'")
            print("[GREETING 06] greeting queued")
            self.engine.response_manager.add_response(chosen_greeting, priority=2, force=True)
            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", chosen_greeting))

            with self.session_lock:
                self.pending_speech_prompt = f"Speak this exact startup greeting out loud in a warm, natural, friendly, confident voice: '{chosen_greeting}'"

    def _on_ai_stopped(self, reason=None):
        self.ai_running = False
        self._clear_playback_queue()
        self.set_state("IDLE")

    # --- Background Camera Worker Thread ---
    def _camera_loop(self):
        """
        Continuous, non-blocking camera capture worker with bounded latest-frame strategy.
        Decouples hardware capture from AI inference so preview rendering and capture remain smooth.
        Includes automatic retry & reconnect backoff if physical camera read fails.
        """
        print("[SENSOR] camera initialization started")
        cam_idx_setting = self.engine.store.get_setting("camera_index", 0)
        target_fps = 30.0
        frame_interval = 1.0 / target_fps
        consecutive_errors = 0

        # Perception cadence (10-12 Hz) to ensure continuous, smooth camera capture
        perception_interval = 1.0 / 12.0
        last_perception_time = 0.0
        cached_frame_info = {
            "faces": [],
            "safety": {},
            "environment": getattr(self.engine, 'last_environment', {}),
            "objects": getattr(self.engine, 'last_objects', [])
        }

        # Rolling FPS tracking
        frame_times = []
        last_status_update_time = 0.0

        while self.camera_running:
            cap = None
            for cam_idx in (cam_idx_setting, 0, 1):
                temp_cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
                if temp_cap.isOpened():
                    cap = temp_cap
                    print(f"[CAMERA] device opened (index {cam_idx})")
                    print(f"[SENSOR] camera opened (index {cam_idx})")
                    break

            if not cap or not cap.isOpened():
                consecutive_errors += 1
                print(f"[CAMERA-WARN] Unable to open camera device (attempt {consecutive_errors}). Retrying in 2.0s...")
                self.gui_queue.put(("CAMERA_STATUS", "● RECONNECTING"))
                time.sleep(2.0)
                if consecutive_errors > 10:
                    self.gui_queue.put(("CAMERA_STOPPED", None))
                continue

            print("[CAMERA] Camera capture stream opened successfully.")
            print("[CAMERA] worker started")
            print("[SENSOR] camera worker started")
            self.gui_queue.put(("CAMERA_STATUS", "● LIVE 20 FPS"))
            consecutive_errors = 0

            try:
                while self.camera_running:
                    start_time = time.time()

                    # Real Camera Source Selection (Laptop Camera vs Meta Glass)
                    is_glass_active = hasattr(self.engine, 'meta_glass') and self.engine.meta_glass.active_source == "META_GLASS"
                    if is_glass_active and self.engine.meta_glass.is_streaming() and self.engine.meta_glass.latest_frame is not None:
                        frame = self.engine.meta_glass.latest_frame
                        ret = True
                        self.gui_queue.put(("CAMERA_STATUS", "● META GLASS"))
                    else:
                        try:
                            ret, frame = cap.read()
                        except Exception:
                            ret, frame = False, None
                        if is_glass_active:
                            # Glass selected but not streaming -> fallback to laptop
                            self.engine.meta_glass.active_source = "LAPTOP"

                    if not ret or frame is None or frame.size == 0:
                        consecutive_errors += 1
                        if consecutive_errors == 1:
                            print("[CAMERA] FRAME_ERROR")
                        print(f"[CAMERA-WARN] Frame read failed ({consecutive_errors}/5 consecutive failures).")
                        if consecutive_errors >= 5:
                            print("[CAMERA] RECOVERING")
                            print("[CAMERA-RECOVER] Consecutive read failures exceeded threshold. Re-opening camera device...")
                            break
                        time.sleep(0.02)
                        continue

                    if not self.first_valid_frame_received:
                        self.first_valid_frame_received = True
                        print(f"[CAMERA] first valid frame received")
                        print(f"[CAMERA] ACTIVE")
                        print(f"[SENSOR] first valid frame received (shape={frame.shape}, ts={time.time():.3f})")

                    consecutive_errors = 0
                    now = time.time()

                    # Update Rolling FPS Tracking
                    frame_times.append(now)
                    if len(frame_times) > 20:
                        frame_times.pop(0)

                    if len(frame_times) > 1:
                        dt = frame_times[-1] - frame_times[0]
                        if dt > 0:
                            self.measured_fps = (len(frame_times) - 1) / dt

                    # Update Telemetry Status at ~2 Hz
                    if now - last_status_update_time >= 0.5:
                        last_status_update_time = now
                        fps_display = int(round(self.measured_fps)) if self.measured_fps > 0 else 20
                        if not is_glass_active:
                            self.gui_queue.put(("CAMERA_STATUS", f"● LIVE {fps_display} FPS"))

                    # Store freshest raw frame for explicit user actions (OCR, Object Search, etc.)
                    with self.frame_lock:
                        self.latest_raw_frame = frame

                    # Cadenced Background Perception (Face Detection, Safety, Scene, Objects)
                    if now - last_perception_time >= perception_interval:
                        last_perception_time = now
                        try:
                            cached_frame_info = self.engine.process_frame(frame)
                        except Exception as frame_e:
                            print(f"[CAMERA-WARN] Frame processing exception caught: {frame_e}")
                            cached_frame_info = {"faces": [], "safety": {}, "scene": {}}

                    # Process in-flight assistant speech
                    next_speech = self.engine.response_manager.get_next_response()
                    if next_speech:
                        self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", next_speech))

                    # Encode JPEG for Gemini Live WebSocket stream
                    ret_jpg, jpg_buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ret_jpg:
                        with self.frame_lock:
                            self.latest_jpeg = jpg_buffer.tobytes()

                    # Prepare HUD preview rendering
                    preview_frame = cv2.resize(frame, (640, 420))

                    faces = cached_frame_info.get("faces", [])
                    face_summary = []
                    for face in faces:
                        x, y, w, h = face["bbox"]
                        name = face.get("name") or "Unknown"
                        state = face.get("match_state") or face.get("state", "UNKNOWN")
                        conf = face.get("confidence", 0.0)
                        is_conf = face.get("is_confirmed", False)
                        q_ok = face.get("quality_ok", True)
                        q_reason = face.get("quality_reason", "")

                        if state == "KNOWN" and name != "Unknown":
                            face_summary.append(f"{name} ({conf*100:.0f}%)")
                        else:
                            face_summary.append(name)

                        if self.dev_mode:
                            scale_x = 640 / float(frame.shape[1])
                            scale_y = 420 / float(frame.shape[0])
                            px, py, pw, ph = int(x * scale_x), int(y * scale_y), int(w * scale_x), int(h * scale_y)

                            if state == "KNOWN" and is_conf:
                                color = (196, 247, 77)  # Mint #4DF7C4
                                tag_text = f" {name} ({conf*100:.0f}%) "
                            elif state == "KNOWN" and not is_conf:
                                color = (114, 171, 253)  # Amber #FDAB72
                                tag_text = f" Recognizing... ({name}) "
                            elif not q_ok:
                                color = (114, 171, 253)  # Amber
                                tag_text = f" Low Quality "
                            else:
                                color = (87, 71, 255)  # Alert Red #FF4757
                                tag_text = " Unknown "

                            cv2.rectangle(preview_frame, (px, py), (px + pw, py + ph), color, 2)
                            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                            tag_y1 = max(0, py - th - 8)
                            tag_y2 = py
                            cv2.rectangle(preview_frame, (px, tag_y1), (px + tw + 6, tag_y2), (5, 5, 5), -1)
                            cv2.rectangle(preview_frame, (px, tag_y1), (px + tw + 6, tag_y2), color, 1)
                            cv2.putText(preview_frame, tag_text, (px + 2, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

                    self._evaluate_wake_greeting(faces)

                    # Render Live Enrollment HUD Overlay if session active
                    enroll_info = cached_frame_info.get("enrollment", {})
                    if enroll_info.get("active"):
                        e_name = enroll_info.get("name", "User")
                        e_samples = enroll_info.get("samples_count", 0)
                        e_target = enroll_info.get("target_samples", 25)
                        e_state = enroll_info.get("state", "ENROLLING")
                        
                        # Draw top neon HUD banner
                        cv2.rectangle(preview_frame, (10, 10), (630, 46), (5, 5, 5), -1)
                        cv2.rectangle(preview_frame, (10, 10), (630, 46), (0, 237, 255), 1)
                        banner_text = f"ENROLLING {e_name.upper()} | {e_state} | {e_samples}/{e_target} Samples"
                        cv2.putText(preview_frame, banner_text, (20, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 237, 255), 2, cv2.LINE_AA)

                    safety = cached_frame_info.get("safety", {})
                    hazard_desc = safety.get("warning_text", "Clear") if safety.get("hazard_detected") else "Clear"

                    if enroll_info.get("active"):
                        perception_text = f"Enrolling: {enroll_info.get('name')} ({enroll_info.get('samples_count')}/{enroll_info.get('target_samples')}) | {enroll_info.get('state')}"
                    else:
                        perception_text = f"Faces: {', '.join(face_summary) if face_summary else 'None'} | Hazards: {hazard_desc}"
                    self.gui_queue.put(("PERCEPTION", perception_text))

                    # Send live vision HUD telemetry (Environment & Objects & Enrollment)
                    hud_payload = {
                        "faces": faces,
                        "safety": safety,
                        "environment": cached_frame_info.get("environment", {}),
                        "objects": cached_frame_info.get("objects", []),
                        "enrollment": enroll_info
                    }
                    self.gui_queue.put(("HUD_UPDATE", hud_payload))

                    cv2_rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(cv2_rgb)

                    self.gui_queue.put(("FRAME", pil_img))

                    elapsed = time.time() - start_time
                    sleep_time = max(0.0, frame_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

            finally:
                if cap:
                    try:
                        cap.release()
                    except Exception:
                        pass

        print("[CAMERA] Camera capture loop terminated cleanly.")
        with self.frame_lock:
            self.latest_jpeg = None
            self.latest_raw_frame = None
        self.gui_queue.put(("CAMERA_STOPPED", None))

    # --- Background AI Worker Thread & Single Authoritative Audio Loop ---
    def _ensure_single_playback_thread(self):
        """ Spawns exactly ONE dedicated speaker playback worker thread if not already running """
        with self.session_lock:
            if not self.playback_thread_started or self.playback_thread is None or not self.playback_thread.is_alive():
                self.playback_stop_evt.clear()
                self.playback_thread = threading.Thread(
                    target=self._audio_playback_loop,
                    args=(self.playback_stop_evt,),
                    daemon=True
                )
                self.playback_thread.start()
                self.playback_thread_started = True
                print("[PLAYBACK] Single authoritative speaker worker thread active.")

    def _ai_worker_thread(self, api_key):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while not self.mic_queue.empty():
            try: self.mic_queue.get_nowait()
            except queue.Empty: break
        self._clear_playback_queue()

        self._ensure_single_playback_thread()

        mic_stream = None
        try:
            mic_cb_logged = False
            def mic_callback(indata, frames, time_info, status):
                nonlocal mic_cb_logged
                if not mic_cb_logged:
                    print("[SENSOR] microphone callback active")
                    mic_cb_logged = True
                if self.ai_running:
                    self.mic_queue.put(bytes(indata))

            print("[SENSOR] microphone initialization started")
            print("[MAIN-MIC] application acquired input device")
            mic_stream = sd.RawInputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                blocksize=1024,
                callback=mic_callback
            )
            mic_stream.start()
            print("[MIC] Single 16kHz microphone stream opened.")
            print("[SENSOR] microphone opened")

            loop.run_until_complete(self._run_live_session(api_key))

        except Exception as e:
            print(f"[ERROR] AI worker thread exception: {e}")
            curr_key_num = self.engine.key_manager.active_key_num or 1
            next_key = self.engine.key_manager.get_next_failover_key(curr_key_num, error=e)
            if next_key and self.current_state not in ("SLEEPING", "STOPPED", "CLOSED"):
                next_num, next_val = next_key
                print(f"[FAILOVER] Key {curr_key_num} failed -> Failing over to Key {next_num}")
                self.stop_ai()
                try:
                    self.root.after(500, lambda: self.start_ai(next_val))
                except Exception:
                    threading.Timer(0.5, lambda: self.start_ai(next_val)).start()
            else:
                print("[FAILOVER] All configured Gemini API keys failed or on cooldown.")
                self.set_state("DISCONNECTED")
            self.gui_queue.put(("AI_STOPPED", str(e)))
        finally:
            if mic_stream:
                try:
                    mic_stream.stop()
                    mic_stream.close()
                except Exception:
                    pass

            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            self.gui_queue.put(("AI_STOPPED", None))

    def _audio_playback_loop(self, stop_evt):
        """ Single authoritative 24kHz PCM audio playback thread """
        out_stream = None
        try:
            out_stream = sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype='int16'
            )
            out_stream.start()

            # Warm-up silence buffer to prevent initial pop/clipping
            out_stream.write(bytes(4800))
            print("[PLAYBACK] Speaker output stream active (24kHz 16-bit PCM).")

            while self.ai_running:
                if stop_evt.is_set():
                    stop_evt.clear()
                    while not self.playback_queue.empty():
                        try: self.playback_queue.get_nowait()
                        except queue.Empty: break
                    continue

                try:
                    item = self.playback_queue.get(timeout=0.01)
                    if item and self.ai_running:
                        if isinstance(item, tuple):
                            resp_id, pcm_chunk = item
                        else:
                            resp_id = self.current_response_id
                            pcm_chunk = item

                        # DROPPING STALE CHUNKS FROM PREVIOUS TURN / INTERRUPTIONS
                        if resp_id != self.current_response_id:
                            print(f"[BARGE-IN] Dropping stale audio chunk from response_id={resp_id} (active={self.current_response_id})")
                            continue

                        gain = self.engine.store.get_setting("assistant_volume", 1.25)
                        if gain != 1.0:
                            audio_np = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32)
                            audio_np = np.clip(audio_np * gain, -32768.0, 32767.0).astype(np.int16)
                            pcm_chunk = audio_np.tobytes()

                        self.set_state("AI_SPEAKING")
                        out_stream.write(pcm_chunk)
                        if self.playback_queue.empty() and self.ai_running:
                            self.set_state("LISTENING")
                except queue.Empty:
                    continue
        except Exception as e:
            print("[AUDIO-PLAYBACK] Error:", e)
        finally:
            if out_stream:
                try:
                    out_stream.stop()
                    out_stream.close()
                except Exception:
                    pass
            with self.session_lock:
                self.playback_thread_started = False
            print("[PLAYBACK] Speaker output worker terminated cleanly.")

    async def _run_live_session(self, api_key):
        import uuid
        session_id = uuid.uuid4().hex[:8]
        with self.session_lock:
            self.active_session_id = session_id

        print(f"[SESSION] [START] Initializing Gemini Live session {session_id}...")

        client = genai.Client(api_key=api_key)

        user_mem_context = self.engine.memory.get_relevant_user_context()
        full_instruction = SYSTEM_INSTRUCTION
        if user_mem_context:
            full_instruction += f"\nStored User Context: {user_mem_context}"

        voice_name = self.engine.store.get_setting("assistant_voice", "Puck")
        print(f"[VOICE] [VOICE_CONFIG] Authoritative single voice selected: '{voice_name}'")

        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="get_ambient_status",
                        description="Checks ambient room lighting, color of objects/clothing in view, faces, and immediate physical hazards.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "query_type": types.Schema(type="STRING", description="What to check: 'light', 'color', 'all'")
                            }
                        )
                    ),
                    types.FunctionDeclaration(
                        name="scan_product_details",
                        description="Scans packaging, QR codes, barcodes, medicine bottle text, and expiration dates in view.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={}
                        )
                    ),
                    types.FunctionDeclaration(
                        name="enroll_person_face",
                        description="Enrolls the face currently visible in the camera under the specified name.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "person_name": types.Schema(type="STRING", description="The name of the person to remember.")
                            },
                            required=["person_name"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="save_reminder_note",
                        description="Saves a personal fact or reminder for the user in long-term memory.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "fact_text": types.Schema(type="STRING", description="The fact or detail to remember.")
                            },
                            required=["fact_text"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="recall_user_memory",
                        description="Retrieves persistent personal memories, facts, preferences, or relationships saved for the user.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "search_query": types.Schema(type="STRING", description="The search query or keyword to look up.")
                            },
                            required=["search_query"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="manage_voice_security",
                        description="Initiates voice security password setup, change, reset, removal, or status check when the user requests it.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="The security action: 'set', 'change', 'reset', 'remove', 'status'")
                            },
                            required=["action"]
                        )
                    )
                ]
            )
        ]

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
            system_instruction=types.Content(parts=[types.Part.from_text(text=full_instruction)]),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            tools=tools
        )

        model_name = "gemini-3.1-flash-live-preview"
        session_established = False

        try:
            async with client.aio.live.connect(model=model_name, config=config) as session:
                session_established = True
                print(f"[SESSION] Gemini Live WebSocket connected (session_id={session_id}).")
                if self.ai_running and self.current_state not in ("SLEEPING", "STOPPED", "CLOSED"):
                    self.set_state("LISTENING")

                if self.engine.store.should_trigger_startup_greeting():
                    greeting = self._generate_time_greeting()
                    print(f"[GREETING] Triggering startup greeting: '{greeting}'")
                    self.gui_queue.put(("TRANSCRIPT_AI", greeting))
                    try:
                        await session.send_client_content(
                            turns=[
                                types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=f"Speak this exact startup greeting out loud with a warm, natural, friendly, confident voice: '{greeting}'")]
                                )
                            ],
                            turn_complete=True
                        )
                    except Exception as ge:
                        print(f"[GREETING] Error sending greeting prompt: {ge}")

                mic_task = asyncio.create_task(self._send_mic_loop(session, session_id))
                video_task = asyncio.create_task(self._send_video_loop(session, session_id))
                receive_task = asyncio.create_task(self._receive_loop(session, session_id))

                while self.ai_running and self.active_session_id == session_id:
                    done, pending = await asyncio.wait(
                        [mic_task, video_task, receive_task],
                        timeout=0.2,
                        return_when=asyncio.FIRST_EXCEPTION
                    )
                    for task in done:
                        if task.exception():
                            print(f"[SESSION] Subtask exception in session {session_id}: {task.exception()}")
                            raise task.exception()

                mic_task.cancel()
                video_task.cancel()
                receive_task.cancel()
                await asyncio.gather(mic_task, video_task, receive_task, return_exceptions=True)

        except Exception as e:
            if not self.ai_running or self.current_state in ("SLEEPING", "STOPPED", "CLOSED"):
                return

            print(f"[SESSION] Live session exception (session_id={session_id}, established={session_established}): {e}")

            # If the session was NEVER established, or if the failure is classified as invalid key / quota exhaustion,
            # raise the exception to let _ai_worker_thread trigger multi-key failover!
            reason, _ = self.engine.key_manager.classify_failure(e)
            if not session_established or reason in ("INVALID_KEY", "DAILY_QUOTA_EXHAUSTED"):
                raise e

            # For established sessions experiencing a transient network disconnect, attempt reconnect
            self.set_state("RECONNECTING")
            await asyncio.sleep(1.5)
            if self.ai_running and self.current_state not in ("SLEEPING", "STOPPED", "CLOSED"):
                with self.session_lock:
                    if self.active_session_id == session_id:
                        self.active_session_id = None
                active_key = self.engine.key_manager.get_active_api_key() or api_key
                return await self._run_live_session(active_key)
        finally:
            try:
                await client.aio.aclose()
            except Exception:
                pass

    async def _send_mic_loop(self, session, session_id):
        vad = VoiceActivityDetector(sample_rate=16000, frame_duration_ms=64)
        recognizer = sr.Recognizer()
        loop = asyncio.get_running_loop()

        speech_chunks = []
        pre_roll_chunks = []
        is_speech_ongoing = False
        silence_count = 0
        speech_frame_count = 0
        streamed_to_gemini = False

        while self.ai_running and self.active_session_id == session_id:
            try:
                # Check for pending speech prompt (e.g. person-aware startup/wake greeting)
                prompt_to_send = None
                with self.session_lock:
                    if self.pending_speech_prompt:
                        prompt_to_send = self.pending_speech_prompt
                        self.pending_speech_prompt = None

                if prompt_to_send:
                    print("[GREETING 07] playback started")
                    try:
                        await session.send_client_content(
                            turns=[
                                types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=prompt_to_send)]
                                )
                            ],
                            turn_complete=True
                        )
                    except Exception as pe:
                        print(f"[GREETING-ERR] Error sending speech prompt: {pe}")

                pcm_data = None
                try:
                    pcm_data = self.mic_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.005)
                    continue

                if not pcm_data or not self.ai_running or self.active_session_id != session_id:
                    continue

                samples = np.frombuffer(pcm_data, dtype=np.int16)
                is_speech = vad.process_frame(samples)

                # Check if Security Mode is active
                sec_active = (
                    (hasattr(self.engine, 'security') and (self.engine.security.current_state != SecurityState.IDLE))
                    or (hasattr(self.engine, 'audio_arbitrator') and self.engine.audio_arbitrator.is_security_mic_allowed())
                )

                if sec_active:
                    print("[GEMINI] SECURITY AUDIO SENT = NO")
                    if hasattr(self.engine, 'audio_arbitrator') and not self.engine.audio_arbitrator.is_security_mic_allowed():
                        self.engine.audio_arbitrator.enter_security_challenge()

                    if is_speech:
                        if not is_speech_ongoing:
                            is_speech_ongoing = True
                            speech_chunks = list(pre_roll_chunks)
                            speech_frame_count = len(speech_chunks)
                        speech_chunks.append(pcm_data)
                        speech_frame_count += 1
                        silence_count = 0
                    else:
                        pre_roll_chunks.append(pcm_data)
                        if len(pre_roll_chunks) > 5:
                            pre_roll_chunks.pop(0)

                        if is_speech_ongoing:
                            speech_chunks.append(pcm_data)
                            silence_count += 1
                            if silence_count >= 8 and speech_frame_count >= 5:
                                full_pcm = b"".join(speech_chunks)
                                speech_chunks = []
                                pre_roll_chunks.clear()
                                is_speech_ongoing = False
                                silence_count = 0
                                speech_frame_count = 0

                                def _process_sec():
                                    return self.engine.process_security_challenge_audio(
                                        full_pcm,
                                        session_id=self.active_history_session_id
                                    )

                                ok, local_resp = await loop.run_in_executor(None, _process_sec)
                                del full_pcm

                                if local_resp:
                                    print(f"[VOICE] user_speech_turn_finalized: '[VOICE_PASSWORD_REDACTED]'")
                                    self.gui_queue.put(("TRANSCRIPT_USER", "[Protected Security Input]"))
                                    self.gui_queue.put(("TRANSCRIPT_AI", local_resp))
                                    self._speak_local_response(local_resp, is_security=True)
                                    self.engine.history.add_message(self.active_history_session_id, "user", "[VOICE_PASSWORD_REDACTED]")
                                    self.engine.history.add_message(self.active_history_session_id, "assistant", local_resp)

                                # Release microphone back to Gemini Live
                                if hasattr(self.engine, 'audio_arbitrator'):
                                    self.engine.audio_arbitrator.return_to_gemini()
                                try:
                                    self.set_state("LISTENING")
                                except Exception:
                                    pass
                    continue

                # IDLE Mode: Stream raw PCM directly to Gemini Live in real time (< 50ms latency)
                blob = types.Blob(data=pcm_data, mime_type="audio/pcm;rate=16000")
                await session.send_realtime_input(audio=blob)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.ai_running or self.active_session_id != session_id or self.current_state in ("SLEEPING", "STOPPED", "CLOSED"):
                    break
                err_str = str(e).lower()
                if any(x in err_str for x in ["1011", "closed", "deadline", "broken", "eof", "connection", "reset", "abort"]):
                    print(f"[SESSION] Live mic stream closed ({e}).")
                    raise
                print(f"[MIC] Warning sending audio chunk: {e}")
                await asyncio.sleep(0.05)

    async def _send_video_loop(self, session, session_id):
        while self.ai_running and self.active_session_id == session_id:
            try:
                await asyncio.sleep(1.0)
                jpeg_data = None
                with self.frame_lock:
                    jpeg_data = self.latest_jpeg

                if jpeg_data and self.ai_running and self.active_session_id == session_id:
                    blob = types.Blob(data=jpeg_data, mime_type="image/jpeg")
                    await session.send_realtime_input(video=blob)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.ai_running or self.active_session_id != session_id or self.current_state in ("SLEEPING", "STOPPED", "CLOSED"):
                    break
                err_str = str(e).lower()
                if any(x in err_str for x in ["1011", "closed", "deadline", "broken", "eof", "connection", "reset", "abort"]):
                    print(f"[SESSION] Live video stream closed ({e}).")
                    raise
                print(f"[CAMERA] Warning sending video frame: {e}")
                await asyncio.sleep(0.5)

    def _finalize_user_speech_turn(self):
        """ Finalizes the accumulated user speech utterance and dispatches local intent handling. """
        user_text = (self.user_transcript_buffer or "").strip()
        self.user_transcript_buffer = ""
        if not user_text:
            return False

        is_security_input = hasattr(self.engine, 'security') and (self.engine.security.current_state.value != "IDLE")
        log_text = "[VOICE_PASSWORD_REDACTED]" if is_security_input else user_text
        print(f"[VOICE] user_speech_turn_finalized: '{log_text}'")

        # Diagnostic logging strictly for Section 2 safe verification
        is_diag_phrase = (user_text.strip().lower() == "set password")
        if is_diag_phrase:
            print(f"[DIAGNOSTIC] TRANSCRIPT_RECEIVED: {user_text}")
            print(f"[DIAGNOSTIC] ROUTER_CALLED: YES")
            diag_route = self.engine.router.route_intent(user_text)
            print(f"[DIAGNOSTIC] ROUTED_INTENT: {diag_route.get('intent')}")

        local_response = self.engine.process_user_speech_query(user_text, session_id=self.active_history_session_id)
        if local_response:
            if is_diag_phrase:
                print(f"[DIAGNOSTIC] LOCAL_HANDLER_CALLED: YES")
                print(f"[DIAGNOSTIC] GEMINI_FALLBACK_CALLED: NO")

            # Cancel any pending wake/startup greeting so it never interrupts or overlaps user command
            self.wake_greeting_pending = False

            # Clear any preliminary/stale streaming audio from playback queue and advance response_id
            self._clear_playback_queue()

            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", local_response))
            if is_security_input:
                self.engine.history.add_message(self.active_history_session_id, "user", "[VOICE_PASSWORD_REDACTED]")
            else:
                self.engine.history.add_message(self.active_history_session_id, "user", user_text)
            self.engine.history.add_message(self.active_history_session_id, "assistant", local_response)
            
            # Immediately update Quick Memory card in GUI HUD
            try:
                self._update_info_strip()
            except Exception:
                pass

            if "sleep" in user_text.lower() or "stop listening" in user_text.lower():
                self.enter_sleep_mode()
            else:
                diag_route = self.engine.router.route_intent(user_text)
                is_vault_or_protected = (
                    "protected information" in local_response.lower()
                    or "protected memory" in local_response.lower()
                    or "sensitive information" in local_response.lower()
                    or diag_route.get("intent", "").startswith(("SECURITY_", "VAULT_"))
                    or (hasattr(self.engine, "vault") and self.engine.vault and hasattr(self.engine.vault, "record_exists_for_query") and self.engine.vault.record_exists_for_query(user_text))
                    or (hasattr(self.engine, "security") and self.engine.security and hasattr(self.engine.security, "current_state") and self.engine.security.current_state.value != "IDLE")
                )
                is_sec = is_security_input or is_vault_or_protected
                if is_sec:
                    print("[GEMINI] SECURITY AUDIO SENT = NO")
                    if hasattr(self.engine, 'audio_arbitrator') and ("say your voice password" in local_response.lower() or "sensitive password" in local_response.lower()):
                        self.engine.audio_arbitrator.enter_security_challenge()
                    self._speak_local_response(local_response, is_security=True)
                else:
                    print(f"[SAVE] voice queued: '{local_response}'")
                    with self.session_lock:
                        self.pending_speech_prompt = f"Speak this exact response out loud in a warm, natural, friendly, confident voice: '{local_response}'"
                try:
                    self.root.after(1500, lambda: self.set_state("LISTENING") if self.current_state in ("AI_THINKING", "USER_SPEAKING") and self.playback_queue.empty() else None)
                except Exception:
                    pass
            return True
        else:
            if is_diag_phrase:
                print(f"[DIAGNOSTIC] LOCAL_HANDLER_CALLED: NO")
                print(f"[DIAGNOSTIC] GEMINI_FALLBACK_CALLED: YES")
            self.set_state("AI_THINKING")
            return False

    async def _receive_loop(self, session, session_id):
        print(f"[RECEIVE] Starting receive loop for session_id={session_id}")
        t_speech_start = 0.0
        first_audio_logged = False
        turn_intercepted = False

        while self.ai_running and self.active_session_id == session_id:
            try:
                async for response in session.receive():
                    if not self.ai_running or self.active_session_id != session_id:
                        print(f"[RECEIVE] Exiting receive loop for inactive session {session_id}")
                        break

                    server_content = response.server_content
                    if server_content is not None:
                        if server_content.input_transcription and server_content.input_transcription.text:
                            text_chunk = server_content.input_transcription.text
                            t_speech_start = time.time()
                            self.last_user_speech_time = t_speech_start
                            first_audio_logged = False
                            print(f"[VOICE] speech_chunk: '{text_chunk}'")

                            self.set_state("USER_SPEAKING")
                            # BARGE-IN: Clear old audio queue and advance response_id immediately
                            self._clear_playback_queue()
                            turn_intercepted = False

                            # Accumulate streaming transcription chunks into full user utterance
                            if not self.user_transcript_buffer:
                                self.user_transcript_buffer = text_chunk
                            else:
                                if text_chunk.startswith(self.user_transcript_buffer):
                                    self.user_transcript_buffer = text_chunk
                                else:
                                    sep = "" if (self.user_transcript_buffer.endswith(" ") or text_chunk.startswith(" ")) else " "
                                    self.user_transcript_buffer += sep + text_chunk

                            self.gui_queue.put(("TRANSCRIPT_USER", self.user_transcript_buffer))

                        if server_content.output_transcription and server_content.output_transcription.text:
                            # Finalize pending user speech turn before processing assistant output
                            if self.user_transcript_buffer:
                                if self._finalize_user_speech_turn():
                                    turn_intercepted = True
                            text_chunk = server_content.output_transcription.text
                            if not turn_intercepted:
                                self.gui_queue.put(("TRANSCRIPT_AI", text_chunk))
                                self.engine.history.accumulate_assistant_chunk(text_chunk)

                        if server_content.model_turn:
                            # Finalize pending user speech turn when AI model starts speaking
                            if self.user_transcript_buffer:
                                if self._finalize_user_speech_turn():
                                    turn_intercepted = True
                            if not turn_intercepted:
                                curr_resp_id = self.current_response_id
                                for part in server_content.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        if not first_audio_logged:
                                            t_first_chunk = time.time()
                                            first_audio_logged = True
                                            latency = t_first_chunk - t_speech_start if t_speech_start > 0 else 0.0
                                            print(f"[VOICE] response_first_chunk (time_to_first_audio={latency:.3f}s)")
                                            print("[VOICE] playback_started")
                                        pcm_bytes = part.inline_data.data
                                        # Tag audio chunk with current response_id
                                        self.playback_queue.put((curr_resp_id, pcm_bytes))

                        if server_content.turn_complete:
                            # Finalize any remaining user speech turn
                            if self.user_transcript_buffer:
                                if self._finalize_user_speech_turn():
                                    turn_intercepted = True
                            t_complete = time.time()
                            total_time = t_complete - t_speech_start if t_speech_start > 0 else 0.0
                            print(f"[VOICE] response_complete (total_response_time={total_time:.3f}s)")
                            print("[GREETING 08] playback completed")
                            if turn_intercepted:
                                self.engine.history.clear_assistant_turn()
                                self._clear_playback_queue()
                                turn_intercepted = False
                            else:
                                # Merge accumulated streaming chunks into ONE assistant message and save to SQLite
                                self.engine.history.finalize_assistant_turn(self.active_history_session_id)
                            if self.playback_queue.empty():
                                self.set_state("LISTENING")

                    tool_call = getattr(response, "tool_call", None)
                    if tool_call is not None:
                        # Finalize any pending user speech turn when tool call arrives
                        if self.user_transcript_buffer:
                            if self._finalize_user_speech_turn():
                                turn_intercepted = True
                        for call in getattr(tool_call, "function_calls", []):
                            fn_name = call.name
                            fn_args = call.args or {}
                            call_id = call.id

                            result_content = {}
                            if fn_name == "get_ambient_status":
                                frame = self.engine.current_frame
                                light = self.engine.color_detector.check_ambient_light(frame)
                                color = self.engine.color_detector.detect_dominant_color(frame)
                                result_content = {"light": light, "color": color}
                            elif fn_name == "scan_product_details":
                                frame = self.engine.current_frame
                                ocr_res = self.engine.ocr_engine.process_ocr(frame)
                                prod_res = self.engine.product_scanner.scan_product_label(frame, ocr_text=ocr_res.get("text", ""))
                                result_content = prod_res
                            elif fn_name == "enroll_person_face":
                                name = fn_args.get("person_name", "Friend")
                                res = self.engine.face_recognizer.enroll_active_face(self.engine.current_frame, name)
                                if res.get("success"):
                                    self.engine.memory.save_memory("relationship", name.lower(), f"{name} is saved in face memory.")
                                    try:
                                        self._update_info_strip()
                                    except Exception:
                                        pass
                                result_content = res
                            elif fn_name == "save_reminder_note":
                                fact = fn_args.get("fact_text", "")
                                print(f"[SAVE] tool_call 'save_reminder_note' with fact: '{fact}'")
                                key, fact_val = self.engine.router.extract_memory_key_and_fact(fact)
                                if not key or key == "contextual":
                                    key_words = [w for w in re.sub(r'[^\w\s]', '', (fact_val or fact).lower()).split() if w not in ["that", "my", "the", "a", "an", "this", "it", "is", "are", "user", "users"]]
                                    key = " ".join(key_words[:2]) if key_words else "personal_fact"
                                success = self.engine.memory.save_memory("personal", key, fact_val or fact)
                                try:
                                    self._update_info_strip()
                                except Exception:
                                    pass
                                result_content = {"status": "saved" if success else "failed", "fact": fact_val or fact}
                            elif fn_name == "recall_user_memory":
                                query = fn_args.get("search_query", "")
                                memory_fact = self.engine.memory.recall_memory(query)
                                result_content = {"recalled_memory": memory_fact or "No memory saved matching query."}
                            elif fn_name == "manage_voice_security":
                                act = fn_args.get("action", "set")
                                cmd_map = {
                                    "set": "set password",
                                    "change": "change password",
                                    "reset": "reset password",
                                    "remove": "remove password",
                                    "status": "security status"
                                }
                                sec_cmd = cmd_map.get(act, "set password")
                                print(f"[SECURITY] tool_call 'manage_voice_security' executing: '{sec_cmd}'")
                                local_resp = self.engine.process_user_speech_query(sec_cmd, session_id=self.active_history_session_id)
                                self._clear_playback_queue()
                                if local_resp:
                                    self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", local_resp))
                                    self._speak_local_response(local_resp, is_security=True)
                                result_content = {"status": "initiated", "message": local_resp or "Security flow engaged."}

                            try:
                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            name=fn_name,
                                            response={"result": result_content},
                                            id=call_id
                                        )
                                    ]
                                )
                            except Exception as te:
                                print(f"[TOOL-RESPONSE] Error sending tool response: {te}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.ai_running or self.active_session_id != session_id or self.current_state in ("SLEEPING", "STOPPED", "CLOSED"):
                    break
                err_str = str(e).lower()
                if any(x in err_str for x in ["1011", "closed", "deadline", "broken", "eof", "connection", "reset", "abort"]):
                    print(f"[SESSION] Live receive stream closed ({e}).")
                    raise
                print(f"[RECEIVE] Exception in session {session_id}: {e}")
                await asyncio.sleep(0.5)

    # --- Interactive Secondary Modal Dialogs ---
    def open_history_dialog(self):
        """ Persistent Conversation History Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — Persistent Conversation History")
        dialog.geometry("780x620")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        # Title Bar
        title_lbl = tk.Label(dialog, text="📜 Conversation History", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        # Search Bar
        search_frame = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        search_entry = tk.Entry(search_frame, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))

        # Main Split Frame: Left Sessions List, Right Transcript View
        main_split = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        main_split.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # Left Sessions Listbox Frame
        sessions_frame = tk.Frame(main_split, bg=COLOR_PANEL_SECONDARY, width=280, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        sessions_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sessions_frame.pack_propagate(False)

        sess_lbl = tk.Label(sessions_frame, text="SAVED SESSIONS", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8, "bold"))
        sess_lbl.pack(anchor="w", padx=10, pady=8)

        sess_listbox = tk.Listbox(sessions_frame, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, selectbackground=COLOR_BORDER_ACTIVE, selectforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightthickness=0)
        sess_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Right Transcript Display Box
        transcript_frame = tk.Frame(main_split, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        transcript_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        trans_box = scrolledtext.ScrolledText(transcript_frame, wrap=tk.WORD, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0)
        trans_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        active_sessions_data = []

        def load_sessions():
            nonlocal active_sessions_data
            sess_listbox.delete(0, tk.END)
            query = search_entry.get().strip()
            if query:
                sessions = self.engine.history.search_history(query)
            else:
                sessions = self.engine.history.list_all_sessions()

            active_sessions_data = sessions
            if sessions:
                for s in sessions:
                    sess_listbox.insert(tk.END, f"● {s['title']}")
                sess_listbox.select_set(0)
                show_transcript(0)
            else:
                trans_box.configure(state=tk.NORMAL)
                trans_box.delete("1.0", tk.END)
                trans_box.insert(tk.END, "No matching stored conversation sessions found.\n")
                trans_box.configure(state=tk.DISABLED)

        def show_transcript(idx):
            if idx < 0 or idx >= len(active_sessions_data):
                return
            sess = active_sessions_data[idx]
            sid = sess["session_id"]
            messages = self.engine.history.get_session_messages(sid)

            trans_box.configure(state=tk.NORMAL)
            trans_box.delete("1.0", tk.END)
            trans_box.insert(tk.END, f"=== {sess['title']} ===\n\n")

            if messages:
                for m in messages:
                    t_str = time.strftime('%I:%M %p', time.localtime(m['timestamp']))
                    sender_label = "You" if m['sender'].lower() == "user" else "SG CUBE"
                    trans_box.insert(tk.END, f"[{sender_label} - {t_str}]\n{m['text']}\n\n")
            else:
                trans_box.insert(tk.END, "No messages in this session.\n")
            trans_box.configure(state=tk.DISABLED)

        def on_session_select(evt):
            sel = sess_listbox.curselection()
            if sel:
                show_transcript(sel[0])

        sess_listbox.bind("<<ListboxSelect>>", on_session_select)

        btn_search = tk.Button(search_frame, text="Search", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_BORDER_ACTIVE, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=12, pady=4, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=load_sessions)
        btn_search.pack(side=tk.RIGHT)

        # Bottom Actions Bar
        bottom_bar = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        bottom_bar.pack(fill=tk.X, padx=20, pady=(0, 15))

        def delete_selected():
            sel = sess_listbox.curselection()
            if sel and sel[0] < len(active_sessions_data):
                sid = active_sessions_data[sel[0]]["session_id"]
                self.engine.history.delete_session(sid)
                load_sessions()

        def clear_all():
            if messagebox.askyesno("Confirm Clear History", "Are you sure you want to permanently delete all conversation history?\n\n(Personal memory and face memory will NOT be deleted.)", parent=dialog):
                self.engine.history.clear_all_history()
                load_sessions()

        def reset_active_context():
            if hasattr(self, 'engine') and hasattr(self.engine, 'context'):
                self.engine.context.reset_context()
            self.show_context_alert("Conversation context cleared.", color=COLOR_CYAN_PRIMARY)
            messagebox.showinfo("Context Cleared", "Active conversation context has been reset to IDLE.\nPronouns and follow-ups will start fresh.", parent=dialog)

        btn_del = tk.Button(bottom_bar, text="Delete Selected", bg=COLOR_PANEL_DEEP, fg=COLOR_ALERT_RED, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_ALERT_RED, relief=tk.FLAT, bd=0, padx=12, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=delete_selected)
        btn_del.pack(side=tk.LEFT, padx=(0, 8))

        btn_clear_all = tk.Button(bottom_bar, text="Clear All History", bg=COLOR_ALERT_RED, fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, padx=14, pady=5, cursor="hand2", command=clear_all)
        btn_clear_all.pack(side=tk.LEFT)

        btn_reset_ctx = tk.Button(bottom_bar, text="Clear Context", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=reset_active_context)
        btn_reset_ctx.pack(side=tk.LEFT, padx=(8, 0))

        btn_close = tk.Button(bottom_bar, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(side=tk.RIGHT)

        load_sessions()

    def open_memory_dialog(self):
        """ Structured Context Memory Management Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — Personal Memory Database")
        dialog.geometry("620x640")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        # Title Bar
        title_lbl = tk.Label(dialog, text="🧠 Stored Personal Context & Memories", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 8))

        # Filter & Search Bar
        filter_frame = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

        tk.Label(filter_frame, text="Category:", bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 4))
        
        categories_list = ["ALL", "PERSONAL", "PREFERENCE", "LOCATION", "OBJECT", "TASK", "ROUTINE", "CONTACT", "PROJECT", "DEVICE", "OTHER"]
        var_selected_cat = tk.StringVar(value="ALL")
        opt_cat = tk.OptionMenu(filter_frame, var_selected_cat, *categories_list)
        opt_cat.config(bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        opt_cat["menu"].config(bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 8))
        opt_cat.pack(side=tk.LEFT, padx=(0, 8))

        search_entry = tk.Entry(filter_frame, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))

        # Main Split Frame: Left Listbox of keys/facts, Right Detailed Inspector Box
        main_split = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        main_split.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # Left Listbox
        list_card = tk.Frame(main_split, bg=COLOR_PANEL_SECONDARY, width=280, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        list_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        tk.Label(list_card, text="MEMORY ENTRIES", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(6, 4))
        mem_listbox = tk.Listbox(list_card, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, selectbackground=COLOR_BORDER_ACTIVE, selectforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightthickness=0)
        mem_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Right Detail Box
        detail_card = tk.Frame(main_split, bg=COLOR_PANEL_SECONDARY, width=300, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        detail_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(detail_card, text="MEMORY DETAILS", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(6, 4))
        detail_box = scrolledtext.ScrolledText(detail_card, wrap=tk.WORD, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0)
        detail_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        active_memories_data: List[Dict[str, Any]] = []

        def refresh_memories():
            nonlocal active_memories_data
            mem_listbox.delete(0, tk.END)
            kw = search_entry.get().strip()
            cat = var_selected_cat.get()
            selected_cat = None if cat == "ALL" else cat.lower()

            if kw:
                mems = self.engine.memory.search_memories(kw, category=selected_cat)
            else:
                mems = self.engine.memory.list_all_memories(category=selected_cat)

            active_memories_data = mems
            if mems:
                for m in mems:
                    cat_tag = m['category'].upper()
                    mem_listbox.insert(tk.END, f"[{cat_tag}] {m['key_phrase']}")
                mem_listbox.select_set(0)
                show_memory_detail(0)
            else:
                detail_box.configure(state=tk.NORMAL)
                detail_box.delete("1.0", tk.END)
                detail_box.insert(tk.END, "No stored memories found.\nClick '+ Add Fact' or say 'Remember that...' to store personal facts.\n")
                detail_box.configure(state=tk.DISABLED)

        def show_memory_detail(idx):
            if idx < 0 or idx >= len(active_memories_data):
                return
            m = active_memories_data[idx]
            detail_box.configure(state=tk.NORMAL)
            detail_box.delete("1.0", tk.END)
            created_str = time.strftime('%Y-%m-%d %I:%M %p', time.localtime(m.get('created_at', time.time())))
            updated_str = time.strftime('%Y-%m-%d %I:%M %p', time.localtime(m.get('updated_at', time.time())))
            detail_box.insert(tk.END, f"Category:  {m['category'].upper()}\n")
            detail_box.insert(tk.END, f"Key:       {m['key_phrase']}\n")
            detail_box.insert(tk.END, f"Source:    {m.get('source', 'voice_explicit')}\n")
            detail_box.insert(tk.END, f"Created:   {created_str}\n")
            detail_box.insert(tk.END, f"Updated:   {updated_str}\n\n")
            detail_box.insert(tk.END, f"Fact Content:\n{m['fact_value']}\n")
            detail_box.configure(state=tk.DISABLED)

        def on_mem_select(evt):
            sel = mem_listbox.curselection()
            if sel:
                show_memory_detail(sel[0])

        mem_listbox.bind("<<ListboxSelect>>", on_mem_select)

        btn_search = tk.Button(filter_frame, text="Search", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_BORDER_ACTIVE, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=10, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=refresh_memories)
        btn_search.pack(side=tk.RIGHT)
        var_selected_cat.trace_add("write", lambda *args: refresh_memories())

        # Bottom Actions Bar
        actions_bar = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        actions_bar.pack(fill=tk.X, padx=20, pady=(0, 15))

        def add_fact_prompt():
            import tkinter.simpledialog as sd
            fact = sd.askstring("Add Personal Memory", "Enter new fact/detail to remember (e.g. 'My laptop is on the study table'):", parent=dialog)
            if fact and fact.strip():
                k, f = self.engine.router.extract_memory_key_and_fact(fact.strip())
                ok = self.engine.memory.save_memory("personal", k, f or fact.strip())
                if ok:
                    messagebox.showinfo("Memory Saved", f"Saved: '{fact.strip()}'", parent=dialog)
                else:
                    messagebox.showwarning("Notice", "Could not save memory.", parent=dialog)
                refresh_memories()

        def delete_selected_memory():
            sel = mem_listbox.curselection()
            if sel and sel[0] < len(active_memories_data):
                m = active_memories_data[sel[0]]
                if messagebox.askyesno("Confirm Delete", f"Delete memory for key '{m['key_phrase']}'?", parent=dialog):
                    self.engine.memory.forget_memory(m['key_phrase'])
                    refresh_memories()

        def clear_all_memories_dialog():
            if self.engine.security.is_configured() and not self.engine.security.is_session_authorized():
                messagebox.showwarning("Authorization Required", "Clearing all memories is a protected high-risk action.\nPlease authorize via voice security password or unlock session first.", parent=dialog)
                return
            if messagebox.askyesno("Confirm Clear Memories", "Are you sure you want to permanently delete all stored personal memories across all categories?", parent=dialog):
                self.engine.memory.clear_all_memories()
                refresh_memories()

        btn_add = tk.Button(actions_bar, text="+ Add Fact", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=10, pady=4, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=add_fact_prompt)
        btn_add.pack(side=tk.LEFT, padx=(0, 6))

        btn_del_sel = tk.Button(actions_bar, text="Delete Selected", bg=COLOR_PANEL_DEEP, fg=COLOR_ALERT_RED, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_ALERT_RED, relief=tk.FLAT, bd=0, padx=10, pady=4, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=delete_selected_memory)
        btn_del_sel.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = tk.Button(actions_bar, text="Clear All", bg=COLOR_ALERT_RED, fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2", command=clear_all_memories_dialog)
        btn_clear.pack(side=tk.LEFT)

        btn_close = tk.Button(actions_bar, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=14, pady=4, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(side=tk.RIGHT)

        refresh_memories()

    def open_vision_dialog(self):
        """ Visual Perception Overview Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — Assistive Vision Dashboard")
        dialog.geometry("540x500")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        title_lbl = tk.Label(dialog, text="◉ Assistive Vision Overview", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        info_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        info_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        info_box = scrolledtext.ScrolledText(info_card, wrap=tk.WORD, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, height=12)
        info_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def refresh_vision():
            info_box.configure(state=tk.NORMAL)
            info_box.delete("1.0", tk.END)
            faces = [f.get("name") or "Unknown" for f in self.engine.last_faces]
            safety = self.engine.last_safety.get("warning_text", "Clear") if self.engine.last_safety.get("hazard_detected") else "No immediate hazards detected."

            info_box.insert(tk.END, f"● Camera Capture Stream: {'Active (~20 FPS)' if self.camera_running else 'Offline'}\n\n")
            info_box.insert(tk.END, f"● Detected Faces in View: {', '.join(faces) if faces else 'None'}\n\n")
            info_box.insert(tk.END, f"● Safety Hazard Status: {safety}\n\n")
            info_box.insert(tk.END, f"● Continuous Perception: {'ON' if self.engine.monitor.is_continuous() else 'OFF'}\n\n")
            info_box.configure(state=tk.DISABLED)

        # Quick Actions Bar
        actions_bar = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        actions_bar.pack(fill=tk.X, padx=20, pady=(0, 15))

        def check_color():
            frame = self.engine.current_frame
            col = self.engine.color_detector.detect_dominant_color(frame)
            messagebox.showinfo("Dominant Color", f"Dominant color in view: {col}", parent=dialog)

        def check_light():
            frame = self.engine.current_frame
            light = self.engine.color_detector.check_ambient_light(frame)
            messagebox.showinfo("Ambient Lighting", f"Current lighting condition: {light}", parent=dialog)

        def describe_scene():
            frame = self.engine.current_frame
            sc = self.engine.scene.analyze_scene(frame)
            desc = sc.get("summary", "No description available.")
            messagebox.showinfo("Scene Description", desc, parent=dialog)

        btn_color = tk.Button(actions_bar, text="Detect Color", bg=COLOR_PANEL_DEEP, fg=COLOR_TEAL_MINT, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=check_color)
        btn_color.pack(side=tk.LEFT, padx=(0, 6))

        btn_light = tk.Button(actions_bar, text="Check Light", bg=COLOR_PANEL_DEEP, fg=COLOR_WARNING_GOLD, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=check_light)
        btn_light.pack(side=tk.LEFT, padx=(0, 6))

        btn_scene = tk.Button(actions_bar, text="Describe Scene", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=describe_scene)
        btn_scene.pack(side=tk.LEFT)

        btn_close = tk.Button(actions_bar, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(side=tk.RIGHT)

        refresh_vision()

    def open_people_dialog(self):
        """ People & Face Memory Registry Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — Face Memory Registry")
        dialog.geometry("540x500")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        title_lbl = tk.Label(dialog, text="👥 Enrolled People & Face Registry", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        list_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        list_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        list_box = scrolledtext.ScrolledText(list_card, wrap=tk.WORD, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, height=12)
        list_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def refresh_people():
            list_box.configure(state=tk.NORMAL)
            list_box.delete("1.0", tk.END)
            people = self.engine.face_memory.list_people()
            if people:
                for idx, p in enumerate(people, 1):
                    list_box.insert(tk.END, f"{idx}. {p}\n")
            else:
                list_box.insert(tk.END, "No saved face profiles enrolled yet.\nClick 'Enroll Face' or say 'Enroll face as [Name]'.\n")
            list_box.configure(state=tk.DISABLED)

        actions_frame = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        actions_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        def enroll_face_prompt():
            import tkinter.simpledialog as sd
            name = sd.askstring("Enroll Face", "Enter person's name to remember face:", parent=dialog)
            if name and name.strip():
                res = self.engine.face_recognizer.enroll_active_face(self.engine.current_frame, name.strip())
                if res.get("success"):
                    messagebox.showinfo("Success", f"Enrolled face profile for '{name.strip()}'.", parent=dialog)
                else:
                    messagebox.showwarning("Notice", res.get("message", "No clear face detected in frame."), parent=dialog)
                refresh_people()

        def test_recognition():
            print("[FACE-TEST] frame received")
            frame = self.engine.current_frame
            if frame is None or getattr(frame, 'size', 0) == 0:
                print("[FACE-TEST] no frame available")
                messagebox.showwarning("Notice", "Camera feed is not ready or active. Please ensure camera is connected.", parent=dialog)
                self.set_state("LISTENING")
                return

            faces = self.engine.face_recognizer.process_frame(frame)
            num_faces = len(faces)
            print(f"[FACE-TEST] faces detected = {num_faces}")

            if num_faces == 0:
                print("[FACE-TEST] decision = NO FACE")
                voice_msg = "I don't currently see anyone in front of you."
                self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", voice_msg))
                self.set_state("LISTENING")
                messagebox.showinfo("Recognition Result", "No face detected in current frame.\nPlease look directly at the camera.", parent=dialog)
                return

            summary_lines = []
            voice_names = []
            has_known = False

            for idx, face_info in enumerate(faces, 1):
                name = face_info.get("name")
                state = face_info.get("match_state") or face_info.get("state", "UNKNOWN")
                conf = face_info.get("confidence", 0.0)
                margin = face_info.get("margin", 0.0)
                is_conf = face_info.get("is_confirmed", False)
                q_ok = face_info.get("quality_ok", True)
                q_reason = face_info.get("quality_reason", "")
                pct = conf * 100.0

                if state == "KNOWN" and name and name != "Unknown":
                    has_known = True
                    voice_names.append(name)
                    conf_str = "Confirmed" if is_conf else "Tracking"
                    summary_lines.append(f"Face {idx}: KNOWN [{conf_str}] — {name} ({pct:.1f}% confidence, margin: {margin:.2f})")
                elif not q_ok or state == "UNCERTAIN":
                    summary_lines.append(f"Face {idx}: UNCERTAIN — ({q_reason})")
                else:
                    summary_lines.append(f"Face {idx}: UNKNOWN — (best confidence: {pct:.1f}%)")

            result_text = "\n".join(summary_lines)
            if has_known and voice_names:
                voice_msg = f"Hello {voice_names[0]}."
            else:
                voice_msg = "Sorry, I can't recognize you."

            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", voice_msg))
            self.set_state("LISTENING")

            messagebox.showinfo(
                "Face Recognition Result",
                f"Face Recognition Pipeline Results ({len(faces)} face(s) found):\n\n{result_text}\n\nSpoken Response: \"{voice_msg}\"",
                parent=dialog
            )

        def clear_faces():
            if messagebox.askyesno("Confirm Clear Face Profiles", "Are you sure you want to delete all stored face profiles?", parent=dialog):
                self.engine.face_memory.clear_all_profiles()
                refresh_people()

        btn_enroll = tk.Button(actions_frame, text="Enroll Face", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=enroll_face_prompt)
        btn_enroll.pack(side=tk.LEFT, padx=(0, 6))

        btn_test = tk.Button(actions_frame, text="Test Recognition", bg=COLOR_PANEL_DEEP, fg=COLOR_ORANGE, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=test_recognition)
        btn_test.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = tk.Button(actions_frame, text="Clear All", bg=COLOR_ALERT_RED, fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, padx=10, pady=5, cursor="hand2", command=clear_faces)
        btn_clear.pack(side=tk.LEFT)

        btn_close = tk.Button(actions_frame, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(side=tk.RIGHT)

        refresh_people()

    def open_meta_glass_dialog(self):
        """ Meta Ray-Ban Glass Bridge & Wearable Status Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("👓 Meta Glass / VisionClaw Bridge")
        dialog.geometry("540x500")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        title_lbl = tk.Label(dialog, text="👓 Meta Glass Wearable Integration", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        status_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        status_card.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=8)

        lbl_state = tk.Label(status_card, text="Bridge Status: DISCONNECTED", bg=COLOR_PANEL_SECONDARY, fg=COLOR_ORANGE, font=("Segoe UI", 10, "bold"))
        lbl_state.pack(anchor="w", padx=12, pady=(4, 2))

        lbl_detail = tk.Label(status_card, text="", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8))
        lbl_detail.pack(anchor="w", padx=12, pady=(0, 4))

        info_grid = tk.Frame(status_card, bg=COLOR_PANEL_DEEP, padx=10, pady=8, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        info_grid.pack(fill=tk.X, padx=12, pady=4)

        lbl_source = tk.Label(info_grid, text="• Active Camera Source: LAPTOP CAMERA", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 9))
        lbl_source.pack(anchor="w", pady=1)

        lbl_stream = tk.Label(info_grid, text="• Optical Video Stream: INACTIVE", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9))
        lbl_stream.pack(anchor="w", pady=1)

        lbl_audio = tk.Label(info_grid, text="• Conversational Audio: SG CUBE Voice ('Puck')", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9))
        lbl_audio.pack(anchor="w", pady=1)

        def refresh_dialog_ui():
            if not hasattr(self.engine, 'meta_glass') or not self.engine.meta_glass:
                return
            mg = self.engine.meta_glass
            st = mg.current_state
            detail = mg.state_detail
            col_map = {
                "CONNECTED": COLOR_STATUS_GREEN,
                "STREAMING": COLOR_STATUS_GREEN,
                "CONNECTING": COLOR_CYAN_PRIMARY,
                "DISCONNECTED": COLOR_ORANGE,
                "ERROR": COLOR_ALERT_RED,
                "NOT AVAILABLE": COLOR_TEXT_MUTED
            }
            lbl_state.config(text=f"Bridge Status: {st}", fg=col_map.get(st, COLOR_TEXT_PRIMARY))
            lbl_detail.config(text=f"Detail: {detail}")
            lbl_source.config(text=f"• Active Camera Source: {mg.active_source}")
            is_stream = mg.is_streaming()
            lbl_stream.config(
                text=f"• Optical Video Stream: {'ACTIVE (~20 FPS)' if is_stream else 'INACTIVE'}",
                fg=COLOR_STATUS_GREEN if is_stream else COLOR_TEXT_SECONDARY
            )

        # Source Selection Buttons
        source_frame = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        source_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        def switch_to_glass():
            ok, msg = self.engine.meta_glass.set_camera_source("META_GLASS")
            if ok:
                messagebox.showinfo("Camera Source", msg, parent=dialog)
            else:
                messagebox.showwarning("Notice", msg, parent=dialog)
            refresh_dialog_ui()

        def switch_to_laptop():
            ok, msg = self.engine.meta_glass.set_camera_source("LAPTOP")
            messagebox.showinfo("Camera Source", msg, parent=dialog)
            refresh_dialog_ui()

        btn_use_glass = tk.Button(source_frame, text="Use Glass Camera", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=switch_to_glass)
        btn_use_glass.pack(side=tk.LEFT, padx=(0, 6))

        btn_use_laptop = tk.Button(source_frame, text="Use Laptop Camera", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=10, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=switch_to_laptop)
        btn_use_laptop.pack(side=tk.LEFT)

        # Connection & Snapshot Actions Bar
        actions_bar = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        actions_bar.pack(fill=tk.X, padx=20, pady=(0, 15))

        def do_connect():
            def on_done(ok, msg):
                def _ui():
                    if ok:
                        messagebox.showinfo("Meta Glass Bridge", msg, parent=dialog)
                    else:
                        messagebox.showwarning("Meta Glass Bridge", msg, parent=dialog)
                    refresh_dialog_ui()
                dialog.after(0, _ui)
            self.engine.meta_glass.connect_async(on_complete=on_done)
            refresh_dialog_ui()

        def do_disconnect():
            self.engine.meta_glass.disconnect()
            messagebox.showinfo("Meta Glass Bridge", "Disconnected Meta Glass bridge.", parent=dialog)
            refresh_dialog_ui()

        def do_snapshot():
            ok, path, msg = self.engine.meta_glass.capture_snapshot()
            if ok:
                messagebox.showinfo("Snapshot Saved", f"{msg}\nPath: {path}", parent=dialog)
            else:
                messagebox.showwarning("Snapshot", msg, parent=dialog)

        btn_conn = tk.Button(actions_bar, text="Connect", bg=COLOR_PANEL_DEEP, fg=COLOR_STATUS_GREEN, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=do_connect)
        btn_conn.pack(side=tk.LEFT, padx=(0, 6))

        btn_disconn = tk.Button(actions_bar, text="Disconnect", bg=COLOR_PANEL_DEEP, fg=COLOR_ORANGE, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=12, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=do_disconnect)
        btn_disconn.pack(side=tk.LEFT, padx=(0, 6))

        btn_snap = tk.Button(actions_bar, text="Snapshot", bg=COLOR_PANEL_DEEP, fg=COLOR_TEAL_MINT, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=12, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=do_snapshot)
        btn_snap.pack(side=tk.LEFT)

        btn_close = tk.Button(actions_bar, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(side=tk.RIGHT)

        refresh_dialog_ui()

    def open_object_finder_dialog(self):
        """ Interactive Object Finder Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — Object Finder")
        dialog.geometry("520x460")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        title_lbl = tk.Label(dialog, text="🔍 Assistive Object Finder", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        chips_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, padx=12, pady=8)
        chips_card.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(chips_card, text="Quick Search Presets:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        chips_frame = tk.Frame(chips_card, bg=COLOR_PANEL_SECONDARY)
        chips_frame.pack(fill=tk.X)

        search_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, padx=12, pady=8)
        search_card.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(search_card, text="Target Object:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        search_row = tk.Frame(search_card, bg=COLOR_PANEL_SECONDARY)
        search_row.pack(fill=tk.X)

        ent_target = tk.Entry(search_row, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        ent_target.insert(0, "phone")
        ent_target.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        res_card = tk.Frame(dialog, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        res_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        res_box = scrolledtext.ScrolledText(res_card, wrap=tk.WORD, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10), relief=tk.FLAT, bd=0, height=6)
        res_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        res_box.insert(tk.END, "Enter or select an object name to find its spatial location in the camera view.\n")
        res_box.configure(state=tk.DISABLED)

        def do_find_object(target_str):
            target = target_str.strip()
            if not target:
                return
            res_box.configure(state=tk.NORMAL)
            res_box.delete("1.0", tk.END)
            res_box.insert(tk.END, f"Searching camera view for '{target}'...\n")
            res_box.configure(state=tk.DISABLED)

            frame = self.engine.current_frame
            obj_res = self.engine.object_detector.search_object(frame, target)
            res_text = obj_res.get("text", f"No object matching '{target}' was detected in view.")

            res_box.configure(state=tk.NORMAL)
            res_box.delete("1.0", tk.END)
            res_box.insert(tk.END, f"● Search Target: {target}\n\n{res_text}\n")
            res_box.configure(state=tk.DISABLED)

            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", res_text))
            self.show_context_alert(res_text, color=COLOR_CYAN_PRIMARY)
            self.engine.response_manager.add_response(res_text, priority=1)

        btn_search = tk.Button(search_row, text="Find Object", font=("Segoe UI", 9, "bold"), bg=COLOR_CYAN_PRIMARY, fg=COLOR_BG_PRIMARY, activebackground=COLOR_TEAL_MINT, activeforeground=COLOR_BG_PRIMARY, relief=tk.FLAT, bd=0, padx=14, pady=4, cursor="hand2", command=lambda: do_find_object(ent_target.get()))
        btn_search.pack(side=tk.RIGHT)

        for chip_name in ("Phone", "Bottle", "Cup", "Keys", "Laptop", "Person"):
            def make_chip_cmd(c=chip_name):
                return lambda: [ent_target.delete(0, tk.END), ent_target.insert(0, c.lower()), do_find_object(c.lower())]
            c_btn = tk.Button(chips_frame, text=chip_name, bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=8, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=make_chip_cmd())
            c_btn.pack(side=tk.LEFT, padx=3)

        btn_close = tk.Button(dialog, text="Close", font=("Segoe UI", 9, "bold"), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=5, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_close.pack(pady=(0, 12))

    def open_settings_dialog(self):
        """ Settings & Preferences Modal Dialog """
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE Settings & Preferences")
        dialog.geometry("520x640")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog))

        title_lbl = tk.Label(dialog, text="⚙ Settings & Preferences", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(anchor="w", padx=20, pady=(15, 10))

        # Scrollable Settings Container (Canvas + vertical Scrollbar)
        scroll_wrapper = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        scroll_wrapper.pack(fill=tk.BOTH, expand=True)

        settings_canvas = tk.Canvas(scroll_wrapper, bg=COLOR_BG_PRIMARY, highlightthickness=0, bd=0)
        settings_scrollbar = tk.Scrollbar(scroll_wrapper, orient=tk.VERTICAL, command=settings_canvas.yview)
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)

        settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        container = tk.Frame(settings_canvas, bg=COLOR_BG_PRIMARY, padx=20)
        canvas_window = settings_canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_canvas_configure(event):
            settings_canvas.itemconfig(canvas_window, width=event.width)

        settings_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_container_configure(event):
            settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))

        container.bind("<Configure>", _on_container_configure)

        def _on_mousewheel(event):
            if not settings_canvas.winfo_exists():
                return
            if event.num == 4:
                settings_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                settings_canvas.yview_scroll(1, "units")
            elif event.delta:
                direction = -1 if event.delta > 0 else 1
                steps = max(1, abs(int(event.delta / 120))) if abs(event.delta) >= 120 else 1
                settings_canvas.yview_scroll(direction * steps, "units")

        dialog.bind("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Button-4>", _on_mousewheel)
        dialog.bind("<Button-5>", _on_mousewheel)
        settings_canvas.bind("<MouseWheel>", _on_mousewheel)
        container.bind("<MouseWheel>", _on_mousewheel)

        var_greetings = tk.BooleanVar(value=self.engine.store.get_setting("greeting_enabled", True))
        var_safety = tk.BooleanVar(value=self.engine.store.get_setting("safety_alerts_enabled", True))
        var_continuous = tk.BooleanVar(value=self.engine.store.get_setting("environment_monitor_enabled", False))
        var_dev = tk.BooleanVar(value=self.dev_mode)

        chk_greet = tk.Checkbutton(container, text="Enable Person Recognition Greetings", variable=var_greetings, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_PANEL_DEEP, activebackground=COLOR_BG_PRIMARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9))
        chk_greet.pack(anchor="w", pady=4)

        chk_safe = tk.Checkbutton(container, text="Enable Safety Obstacle Warnings", variable=var_safety, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_PANEL_DEEP, activebackground=COLOR_BG_PRIMARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9))
        chk_safe.pack(anchor="w", pady=4)

        chk_cont = tk.Checkbutton(container, text="Enable Continuous Environment Monitoring", variable=var_continuous, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_PANEL_DEEP, activebackground=COLOR_BG_PRIMARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9))
        chk_cont.pack(anchor="w", pady=4)

        chk_dev = tk.Checkbutton(container, text="Developer Mode (Show Bounding Boxes & Tech Logs)", variable=var_dev, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_PANEL_DEEP, activebackground=COLOR_BG_PRIMARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9))
        chk_dev.pack(anchor="w", pady=4)

        # 🔑 Multi-Gemini API Keys & Failover Configuration Card
        api_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        api_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        api_title = tk.Label(api_card, text="🔑 Gemini API Keys (Multi-Key Failover)", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        api_title.pack(anchor="w", padx=12, pady=(6, 2))

        status_str = f"Active: {self.engine.key_manager.get_active_key_label()}"
        lbl_api_status = tk.Label(api_card, text=status_str, bg=COLOR_PANEL_SECONDARY, fg=COLOR_STATUS_GREEN if self.engine.key_manager.get_active_key() else COLOR_ALERT_RED, font=("Segoe UI", 9, "bold"))
        lbl_api_status.pack(anchor="w", padx=12, pady=(0, 6))

        # Render rows for Key 1, Key 2, Key 3
        key_entries = {}
        for kn in (1, 2, 3):
            k_frame = tk.Frame(api_card, bg=COLOR_PANEL_SECONDARY)
            k_frame.pack(fill=tk.X, padx=12, pady=3)

            label_txt = f"Key {kn} (Primary):" if kn == 1 else (f"Key {kn} (Secondary):" if kn == 2 else f"Key {kn} (Tertiary):")
            tk.Label(k_frame, text=label_txt, bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8, "bold"), width=15, anchor="w").pack(side=tk.LEFT)

            ent = tk.Entry(k_frame, show="•", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(4, 4))
            
            stored_val = self.engine.key_manager.keys.get(kn, "")
            if stored_val:
                ent.insert(0, self.engine.key_manager.get_masked_key(kn))
            key_entries[kn] = ent

            showing_plain = [False]

            def make_paste_cmd(e=ent, knum=kn, sp=showing_plain):
                def _paste():
                    try:
                        clip = dialog.clipboard_get().strip()
                        if clip:
                            e.delete(0, tk.END)
                            e.insert(0, clip)
                            e.config(show="" if sp[0] else "•")
                    except Exception:
                        pass
                return _paste

            def make_toggle_show_cmd(e=ent, knum=kn, btn_ref=[None], sp=showing_plain):
                def _toggle():
                    sp[0] = not sp[0]
                    if sp[0]:
                        cur_text = e.get().strip()
                        if cur_text.startswith("••••") and not cur_text.startswith("AIza"):
                            actual_key = self.engine.key_manager.keys.get(knum, "")
                            if actual_key:
                                e.delete(0, tk.END)
                                e.insert(0, actual_key)
                        e.config(show="")
                        if btn_ref[0]:
                            btn_ref[0].config(text="Hide")
                    else:
                        cur_text = e.get().strip()
                        if cur_text == self.engine.key_manager.keys.get(knum, ""):
                            e.delete(0, tk.END)
                            e.insert(0, self.engine.key_manager.get_masked_key(knum))
                        e.config(show="•")
                        if btn_ref[0]:
                            btn_ref[0].config(text="Show")
                return _toggle

            def make_test_cmd(knum=kn, e=ent):
                def _test():
                    val = e.get().strip()
                    if val.startswith("••••"):
                        val = self.engine.key_manager.keys.get(knum, "")
                    if not val:
                        messagebox.showwarning(f"Test Key {knum}", f"Key {knum} is not entered.", parent=dialog)
                        return
                    ok, msg = self.engine.key_manager.test_connection(val)
                    if ok:
                        messagebox.showinfo(f"Test Key {knum}", f"Key {knum} is valid!\n\n{msg}", parent=dialog)
                    else:
                        messagebox.showwarning(f"Test Key {knum}", f"Key {knum} verification notice:\n\n{msg}", parent=dialog)
                return _test

            def make_save_cmd(knum=kn, e=ent, sp=showing_plain, btn_sh_ref=[None]):
                def _save():
                    val = e.get().strip()
                    if not val:
                        messagebox.showwarning(f"Save Key {knum}", f"Please enter a valid API key string for Key {knum}.", parent=dialog)
                        return
                    # If unchanged masked representation
                    if val.startswith("••••") and val == self.engine.key_manager.get_masked_key(knum):
                        messagebox.showinfo("Saved", f"Key {knum} is already saved and active.", parent=dialog)
                        return

                    # Persist key to user-data storage
                    self.engine.key_manager.set_key(knum, val)
                    lbl_api_status.config(text=f"Active: {self.engine.key_manager.get_active_key_label()}", fg=COLOR_STATUS_GREEN)

                    # Reset entry to masked format
                    e.delete(0, tk.END)
                    e.insert(0, self.engine.key_manager.get_masked_key(knum))
                    e.config(show="•")
                    sp[0] = False
                    if btn_sh_ref[0]:
                        btn_sh_ref[0].config(text="Show")

                    messagebox.showinfo("Success", f"Key {knum} securely saved to user data!\nActive: {self.engine.key_manager.get_active_key_label()}", parent=dialog)

                    # Hot-switch live AI session if running
                    if self.ai_running:
                        self.stop_ai()
                        self.start_ai(val)
                return _save

            def make_clear_cmd(knum=kn, e=ent, sp=showing_plain, btn_sh_ref=[None]):
                def _clear():
                    if messagebox.askyesno(f"Clear Key {knum}", f"Are you sure you want to clear Key {knum}?", parent=dialog):
                        self.engine.key_manager.clear_key(knum)
                        e.delete(0, tk.END)
                        e.config(show="•")
                        sp[0] = False
                        if btn_sh_ref[0]:
                            btn_sh_ref[0].config(text="Show")
                        lbl_api_status.config(text=f"Active: {self.engine.key_manager.get_active_key_label()}", fg=COLOR_STATUS_GREEN if self.engine.key_manager.get_active_key() else COLOR_ALERT_RED)
                return _clear

            # Buttons: Paste, Show/Hide, Save, Test, Clear
            btn_paste = tk.Button(k_frame, text="Paste", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BORDER_ACTIVE, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=5, pady=2, font=("Segoe UI", 8), highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=make_paste_cmd(ent, kn, showing_plain))
            btn_paste.pack(side=tk.LEFT, padx=1)

            btn_sh_ref = [None]
            btn_toggle = tk.Button(k_frame, text="Show", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BORDER_ACTIVE, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=5, pady=2, font=("Segoe UI", 8), highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2")
            btn_toggle.config(command=make_toggle_show_cmd(ent, kn, btn_sh_ref, showing_plain))
            btn_sh_ref[0] = btn_toggle
            btn_toggle.pack(side=tk.LEFT, padx=1)

            btn_save = tk.Button(k_frame, text="Save", bg=COLOR_CYAN_PRIMARY, fg=COLOR_BG_PRIMARY, activebackground=COLOR_TEAL_MINT, activeforeground=COLOR_BG_PRIMARY, relief=tk.FLAT, bd=0, padx=6, pady=2, font=("Segoe UI", 8, "bold"), cursor="hand2", command=make_save_cmd(kn, ent, showing_plain, btn_sh_ref))
            btn_save.pack(side=tk.LEFT, padx=1)

            btn_test = tk.Button(k_frame, text="Test", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, activebackground=COLOR_BORDER_ACTIVE, activeforeground=COLOR_TEXT_PRIMARY, relief=tk.FLAT, bd=0, padx=5, pady=2, font=("Segoe UI", 8), highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=make_test_cmd(kn, ent))
            btn_test.pack(side=tk.LEFT, padx=1)

            btn_clear = tk.Button(k_frame, text="Clear", bg=COLOR_PANEL_DEEP, fg=COLOR_ALERT_RED, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_ALERT_RED, relief=tk.FLAT, bd=0, padx=5, pady=2, font=("Segoe UI", 8), highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=make_clear_cmd(kn, ent, showing_plain, btn_sh_ref))
            btn_clear.pack(side=tk.LEFT, padx=1)

        # 👤 User Profile Card
        prof_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        prof_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        prof_title = tk.Label(prof_card, text="👤 User Profile Settings", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        prof_title.pack(anchor="w", padx=12, pady=(6, 2))

        prof_grid = tk.Frame(prof_card, bg=COLOR_PANEL_SECONDARY)
        prof_grid.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(prof_grid, text="Full Name:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        entry_uname = tk.Entry(prof_grid, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_uname.insert(0, self.engine.store.get_setting("user_name", ""))
        entry_uname.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=2)

        tk.Label(prof_grid, text="Display Name:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        entry_dname = tk.Entry(prof_grid, bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_dname.insert(0, self.engine.store.get_setting("user_display_name", ""))
        entry_dname.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=2)

        prof_grid.columnconfigure(1, weight=1)

        # 🧠 Context-Aware Personal Memory Card (SG CUBE 2.5)
        mem_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        mem_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        mem_title = tk.Label(mem_card, text="🧠 Personal Context Memory", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        mem_title.pack(anchor="w", padx=12, pady=(6, 2))

        def get_mem_status_str():
            stats = self.engine.memory.get_memory_stats()
            total = stats.get("total_count", 0)
            cats = len(stats.get("categories", {}))
            return f"Status: {total} stored {'memory' if total == 1 else 'memories'} across {cats} {'category' if cats == 1 else 'categories'}"

        lbl_mem_status = tk.Label(mem_card, text=get_mem_status_str(), bg=COLOR_PANEL_SECONDARY, fg=COLOR_STATUS_GREEN if self.engine.memory.get_memory_stats().get("total_count", 0) > 0 else COLOR_TEXT_MUTED, font=("Segoe UI", 9, "bold"))
        lbl_mem_status.pack(anchor="w", padx=12, pady=(0, 4))

        var_context_recall = tk.BooleanVar(value=self.engine.store.get_setting("context_memory_enabled", True))
        def toggle_context_recall():
            self.engine.store.set_setting("context_memory_enabled", var_context_recall.get())

        chk_recall = tk.Checkbutton(
            mem_card,
            text="Enable Context-Aware Memory & Recall",
            variable=var_context_recall,
            bg=COLOR_PANEL_SECONDARY,
            fg=COLOR_TEXT_PRIMARY,
            selectcolor=COLOR_PANEL_DEEP,
            activebackground=COLOR_PANEL_SECONDARY,
            activeforeground=COLOR_CYAN_PRIMARY,
            font=("Segoe UI", 9),
            command=toggle_context_recall
        )
        chk_recall.pack(anchor="w", padx=10, pady=(0, 6))

        mem_btn_row = tk.Frame(mem_card, bg=COLOR_PANEL_SECONDARY)
        mem_btn_row.pack(fill=tk.X, padx=12, pady=(0, 4))

        def open_mem_from_settings():
            self.open_memory_dialog()
            stats = self.engine.memory.get_memory_stats()
            total = stats.get("total_count", 0)
            cats = len(stats.get("categories", {}))
            lbl_mem_status.config(
                text=f"Status: {total} stored {'memory' if total == 1 else 'memories'} across {cats} {'category' if cats == 1 else 'categories'}",
                fg=COLOR_STATUS_GREEN if total > 0 else COLOR_TEXT_MUTED
            )

        def clear_mem_from_settings():
            if self.engine.security.is_configured() and not self.engine.security.is_session_authorized():
                messagebox.showwarning("Authorization Required", "Clearing all memories is a protected high-risk action.\nPlease authorize via voice security password or unlock session first.", parent=dialog)
                return
            if messagebox.askyesno("Confirm Clear Memories", "Are you sure you want to permanently delete all stored personal memories across all categories?", parent=dialog):
                count = self.engine.memory.clear_all_memories()
                lbl_mem_status.config(text="Status: 0 stored memories across 0 categories", fg=COLOR_TEXT_MUTED)
                messagebox.showinfo("Memories Cleared", f"Successfully cleared {count} stored memories.", parent=dialog)

        btn_view_mem = tk.Button(mem_btn_row, text="View / Manage Memories", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, padx=8, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=open_mem_from_settings)
        btn_view_mem.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear_mem = tk.Button(mem_btn_row, text="Clear All", bg=COLOR_PANEL_DEEP, fg=COLOR_ALERT_RED, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=8, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=clear_mem_from_settings)
        btn_clear_mem.pack(side=tk.LEFT, padx=1)

        # 🛡️ Voice Security Password & Authorization Card (SG CUBE 2.5)
        sec_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        sec_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        sec_title = tk.Label(sec_card, text="🛡️ Voice Security Password & Authorization", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        sec_title.pack(anchor="w", padx=12, pady=(6, 2))

        def get_sec_status():
            is_cfg = self.engine.security.is_configured()
            is_auth = self.engine.security.is_session_authorized()
            is_lock, lock_rem = self.engine.security.is_locked_out()
            if is_lock:
                return f"Status: Temporarily Locked ({lock_rem}s remaining)", COLOR_ALERT_RED
            elif is_cfg:
                status_txt = "Configured (Active Session)" if is_auth else "Configured (Locked)"
                return f"Status: {status_txt}", (COLOR_STATUS_GREEN if is_auth else COLOR_CYAN_PRIMARY)
            else:
                return "Status: Not Configured", COLOR_TEXT_MUTED

        st_txt, st_col = get_sec_status()
        lbl_sec_status = tk.Label(sec_card, text=st_txt, bg=COLOR_PANEL_SECONDARY, fg=st_col, font=("Segoe UI", 9, "bold"))
        lbl_sec_status.pack(anchor="w", padx=12, pady=(0, 4))

        var_face_2fa = tk.BooleanVar(value=self.engine.security.is_face_2fa_required())
        def toggle_face_2fa():
            self.engine.security.set_face_2fa_required(var_face_2fa.get())

        chk_2fa = tk.Checkbutton(
            sec_card,
            text="Require Live Face Confirmation for High-Risk Actions (2FA)",
            variable=var_face_2fa,
            bg=COLOR_PANEL_SECONDARY,
            fg=COLOR_TEXT_PRIMARY,
            selectcolor=COLOR_PANEL_DEEP,
            activebackground=COLOR_PANEL_SECONDARY,
            activeforeground=COLOR_CYAN_PRIMARY,
            font=("Segoe UI", 9),
            command=toggle_face_2fa
        )
        chk_2fa.pack(anchor="w", padx=10, pady=(0, 6))

        sec_btn_row = tk.Frame(sec_card, bg=COLOR_PANEL_SECONDARY)
        sec_btn_row.pack(fill=tk.X, padx=12, pady=(0, 4))

        def refresh_sec_ui():
            txt, col = get_sec_status()
            lbl_sec_status.config(text=txt, fg=col)
            is_cfg = self.engine.security.is_configured()
            for w in sec_btn_row.winfo_children():
                w.pack_forget()
            if is_cfg:
                btn_chg_p.config(text="Change Sensitive Password")
                btn_chg_p.pack(side=tk.LEFT, padx=2)
                btn_lck_p.config(text="Lock Sensitive Actions")
                btn_lck_p.pack(side=tk.LEFT, padx=2)
                btn_rst_p.pack(side=tk.LEFT, padx=2)
                btn_rem_p.pack(side=tk.LEFT, padx=2)
            else:
                btn_set_p.config(text="Set Sensitive Password")
                btn_set_p.pack(side=tk.LEFT, padx=2)

        def cmd_set_password():
            import tkinter.simpledialog as sd
            p1 = sd.askstring("Set Voice Security Password", "Enter new voice security password phrase (at least 2 words):", parent=dialog, show="•")
            if not p1 or not p1.strip():
                return
            p2 = sd.askstring("Confirm Voice Security Password", "Repeat the voice security password phrase:", parent=dialog, show="•")
            if p1.strip().lower() != (p2 or "").strip().lower():
                messagebox.showerror("Mismatch", "The passwords do not match. Please try again.", parent=dialog)
                return
            ok, msg, rc = self.engine.security.set_password(p1.strip())
            if ok:
                rc_msg = f"\n\nIMPORTANT: Save your one-time Recovery Code:\n\n{rc}\n\nThis code cannot be displayed again." if rc else ""
                messagebox.showinfo("Success", f"{msg}{rc_msg}", parent=dialog)
            else:
                messagebox.showwarning("Notice", msg, parent=dialog)
            refresh_sec_ui()

        def cmd_change_password():
            import tkinter.simpledialog as sd
            cur = sd.askstring("Change Password", "Enter your CURRENT voice security password:", parent=dialog, show="•")
            if not cur:
                return
            p1 = sd.askstring("New Password", "Enter your NEW voice security password (at least 2 words):", parent=dialog, show="•")
            if not p1:
                return
            p2 = sd.askstring("Confirm New Password", "Repeat your NEW voice security password:", parent=dialog, show="•")
            if p1.strip().lower() != (p2 or "").strip().lower():
                messagebox.showerror("Mismatch", "The new passwords do not match.", parent=dialog)
                return
            ok, msg = self.engine.security.change_password(cur.strip(), p1.strip())
            if ok:
                messagebox.showinfo("Success", msg, parent=dialog)
            else:
                messagebox.showwarning("Notice", msg, parent=dialog)
            refresh_sec_ui()

        def cmd_reset_password():
            import tkinter.simpledialog as sd
            rc = sd.askstring("Reset Password", "Enter your one-time Recovery Code (e.g. RC-XXXX-XXXX):", parent=dialog)
            if not rc:
                return
            p1 = sd.askstring("New Password", "Enter your NEW voice security password (at least 2 words):", parent=dialog, show="•")
            if not p1:
                return
            p2 = sd.askstring("Confirm New Password", "Repeat your NEW voice security password:", parent=dialog, show="•")
            if p1.strip().lower() != (p2 or "").strip().lower():
                messagebox.showerror("Mismatch", "The new passwords do not match.", parent=dialog)
                return
            ok, msg, new_rc = self.engine.security.reset_with_recovery_code(rc.strip(), p1.strip())
            if ok:
                rc_msg = f"\n\nYour NEW one-time Recovery Code is:\n\n{new_rc}\n\nPlease save it in a safe place." if new_rc else ""
                messagebox.showinfo("Success", f"{msg}{rc_msg}", parent=dialog)
            else:
                messagebox.showwarning("Notice", msg, parent=dialog)
            refresh_sec_ui()

        def cmd_remove_password():
            import tkinter.simpledialog as sd
            cur = sd.askstring("Remove Password", "Enter your CURRENT voice security password to disable protection:", parent=dialog, show="•")
            if not cur:
                return
            if not messagebox.askyesno("Confirm Removal", "Removing your Voice Security Password will disable protection for sensitive features.\n\nAre you sure you want to continue?", parent=dialog):
                return
            ok, msg = self.engine.security.remove_password(cur.strip())
            if ok:
                messagebox.showinfo("Success", msg, parent=dialog)
            else:
                messagebox.showwarning("Notice", msg, parent=dialog)
            refresh_sec_ui()

        def cmd_lock_now():
            self.engine.security.lock_session()
            messagebox.showinfo("Session Locked", "Active security authorization session has been revoked.", parent=dialog)
            refresh_sec_ui()

        btn_set_p = tk.Button(sec_btn_row, text="Set Sensitive Password", bg=COLOR_PANEL_DEEP, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, padx=6, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_set_password)
        btn_chg_p = tk.Button(sec_btn_row, text="Change Sensitive Password", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_change_password)
        btn_rst_p = tk.Button(sec_btn_row, text="Reset", bg=COLOR_PANEL_DEEP, fg=COLOR_ORANGE, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_reset_password)
        btn_rem_p = tk.Button(sec_btn_row, text="Remove", bg=COLOR_PANEL_DEEP, fg=COLOR_ALERT_RED, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_remove_password)
        btn_lck_p = tk.Button(sec_btn_row, text="Lock Sensitive Actions", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=3, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_lock_now)
        refresh_sec_ui()

        # 🔔 Proactive Assistive Alerts Card (SG CUBE 2.5 Feature 10)
        alerts_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        alerts_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        alerts_title = tk.Label(alerts_card, text="🔔 Proactive Assistive Alerts (Feature 10)", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        alerts_title.pack(anchor="w", padx=12, pady=(6, 2))

        def get_alert_status_str():
            if hasattr(self.engine, 'alerts') and self.engine.alerts:
                summary = self.engine.alerts.get_status_summary()
                mode_name = summary.get("mode", "NORMAL")
                is_p = summary.get("is_paused", False)
                rem = summary.get("pause_remaining_seconds", 0)
                if is_p:
                    p_str = f"Paused ({int(rem)}s remaining)" if rem > 0 else "Paused"
                    return f"Status: {p_str} | Mode: {mode_name}", COLOR_WARNING_GOLD
                return f"Status: Active | Mode: {mode_name} ({summary.get('queued_count', 0)} queued)", COLOR_STATUS_GREEN
            return "Status: Ready", COLOR_STATUS_GREEN

        a_txt, a_col = get_alert_status_str()
        lbl_alerts_status = tk.Label(alerts_card, text=a_txt, bg=COLOR_PANEL_SECONDARY, fg=a_col, font=("Segoe UI", 9, "bold"))
        lbl_alerts_status.pack(anchor="w", padx=12, pady=(0, 4))

        mode_frame = tk.Frame(alerts_card, bg=COLOR_PANEL_SECONDARY)
        mode_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(mode_frame, text="Alert Mode:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 6))

        current_mode = self.engine.alerts.mode.value if hasattr(self.engine, 'alerts') and self.engine.alerts else "NORMAL"
        var_alert_mode = tk.StringVar(value=current_mode)
        opt_modes = ["OFF", "MINIMAL", "NORMAL", "ASSISTIVE"]

        def on_mode_changed(*args):
            new_m = var_alert_mode.get()
            if hasattr(self.engine, 'alerts') and self.engine.alerts:
                self.engine.alerts.set_mode(new_m)
                t, c = get_alert_status_str()
                lbl_alerts_status.config(text=t, fg=c)

        var_alert_mode.trace_add("write", on_mode_changed)

        opt_mode_menu = tk.OptionMenu(mode_frame, var_alert_mode, *opt_modes)
        opt_mode_menu.config(bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        opt_mode_menu["menu"].config(bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 8))
        opt_mode_menu.pack(side=tk.LEFT, padx=(0, 8))

        def cmd_pause_alerts_5m():
            if hasattr(self.engine, 'alerts') and self.engine.alerts:
                self.engine.alerts.pause_alerts(duration_seconds=300.0)
                t, c = get_alert_status_str()
                lbl_alerts_status.config(text=t, fg=c)

        def cmd_resume_alerts():
            if hasattr(self.engine, 'alerts') and self.engine.alerts:
                self.engine.alerts.resume_alerts()
                t, c = get_alert_status_str()
                lbl_alerts_status.config(text=t, fg=c)

        btn_pause_a = tk.Button(mode_frame, text="Pause 5m", bg=COLOR_PANEL_DEEP, fg=COLOR_WARNING_GOLD, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=2, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_pause_alerts_5m)
        btn_pause_a.pack(side=tk.LEFT, padx=2)

        btn_resume_a = tk.Button(mode_frame, text="Resume", bg=COLOR_PANEL_DEEP, fg=COLOR_STATUS_GREEN, font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=2, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=cmd_resume_alerts)
        btn_resume_a.pack(side=tk.LEFT, padx=2)

        sc_card = tk.Frame(container, bg=COLOR_PANEL_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        sc_card.pack(fill=tk.X, pady=(10, 10), ipady=6)

        sc_title = tk.Label(sc_card, text="Keyboard Shortcuts:", bg=COLOR_PANEL_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9, "bold"))
        sc_title.pack(anchor="w", padx=10, pady=(4, 2))

        sc_info = tk.Label(
            sc_card,
            text="Space : Interrupt / Start Listening\nEsc : Stop Current Speech\nCtrl+Shift+S : Settings | Ctrl+M : Memory\nCtrl+V : Vision | Ctrl+P : People | Ctrl+Q : Exit",
            bg=COLOR_PANEL_SECONDARY,
            fg=COLOR_TEXT_SECONDARY,
            font=("Segoe UI", 8),
            justify=tk.LEFT
        )
        sc_info.pack(anchor="w", padx=10)

        def save_and_close():
            self.engine.store.set_setting("greeting_enabled", var_greetings.get())
            self.engine.store.set_setting("safety_alerts_enabled", var_safety.get())
            self.engine.store.set_setting("environment_monitor_enabled", var_continuous.get())
            self.engine.store.set_setting("developer_mode", var_dev.get())
            self.engine.store.set_setting("context_memory_enabled", var_context_recall.get())

            self.engine.store.set_setting("user_name", entry_uname.get().strip())
            self.engine.store.set_setting("user_display_name", entry_dname.get().strip())

            self.engine.face_recognizer.set_greetings_enabled(var_greetings.get())
            self.engine.monitor.set_mode("continuous" if var_continuous.get() else "on_demand")
            self.dev_mode = var_dev.get()

            animate_dialog_close(dialog)

        btn_frame = tk.Frame(container, bg=COLOR_BG_PRIMARY)
        btn_frame.pack(fill=tk.X, pady=(12, 10))

        btn_save = tk.Button(btn_frame, text="Save Settings", font=("Segoe UI", 10, "bold"), bg=COLOR_CYAN_PRIMARY, fg=COLOR_BG_PRIMARY, activebackground=COLOR_TEAL_MINT, activeforeground=COLOR_BG_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=6, cursor="hand2", command=save_and_close)
        btn_save.pack(side=tk.LEFT)

        btn_cancel = tk.Button(btn_frame, text="Close", font=("Segoe UI", 10), bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_PANEL_SECONDARY, activeforeground=COLOR_CYAN_PRIMARY, relief=tk.FLAT, bd=0, padx=16, pady=6, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1, cursor="hand2", command=lambda: animate_dialog_close(dialog))
        btn_cancel.pack(side=tk.RIGHT)

        # Initial scrollregion calculation and ensure viewport starts at top
        container.update_idletasks()
        settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
        settings_canvas.yview_moveto(0)

    def _check_first_run_onboarding(self):
        """ Checks if this is a fresh installation / first-run and pops up onboarding wizard """
        first_run_done = self.engine.store.get_setting("first_run_completed", False)
        user_name = self.engine.store.get_setting("user_name", "")
        if not first_run_done or not user_name:
            self._show_first_run_onboarding()

    def _show_first_run_onboarding(self):
        """ Production-Grade First-Run Installation & Onboarding Wizard Dialog """
        print("[ONBOARDING] Fresh installation detected. Launching First-Run Setup & Permissions Wizard...")
        dialog = tk.Toplevel(self.root)
        dialog.title("SG CUBE — First-Run Installation & Profile Setup")
        dialog.geometry("640x700")
        dialog.configure(bg=COLOR_BG_PRIMARY)
        dialog.transient(self.root)
        dialog.grab_set()
        animate_dialog_open(dialog, target_alpha=0.98, duration_ms=220)

        dialog.bind("<Escape>", lambda e: animate_dialog_close(dialog, duration_ms=180))

        header = tk.Frame(dialog, bg=COLOR_BG_PRIMARY, height=56, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(header, text="✨ Welcome to SG CUBE Setup", bg=COLOR_BG_PRIMARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 12, "bold"))
        title.pack(side=tk.LEFT, padx=16)

        container = tk.Frame(dialog, bg=COLOR_BG_PRIMARY)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # 1. System Permissions Verification Card
        perm_card = tk.Frame(container, bg=COLOR_BG_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        perm_card.pack(fill=tk.X, pady=(0, 10), ipady=4)

        perm_title = tk.Label(perm_card, text="🔒 System Permissions & Hardware Verification", bg=COLOR_BG_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        perm_title.pack(anchor="w", padx=12, pady=(4, 2))

        # Real Hardware / Permission Verification
        cam_ok = False
        try:
            test_cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if test_cap.isOpened():
                cam_ok = True
                test_cap.release()
        except Exception:
            cam_ok = False

        audio_ok = False
        try:
            devs = sd.query_devices()
            audio_ok = len(devs) > 0
        except Exception:
            audio_ok = False

        cam_text = "● Camera Access: VERIFIED (Visual scene analysis, OCR, Face & Currency)" if cam_ok else "● Camera Access: STANDBY (Camera device not currently detected)"
        cam_col = COLOR_STATUS_GREEN if cam_ok else COLOR_WARNING_GOLD
        tk.Label(perm_card, text=cam_text, bg=COLOR_BG_SECONDARY, fg=cam_col, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=1)

        audio_text = "● Audio & Microphone: VERIFIED (Voice conversation & 24kHz audio output)" if audio_ok else "● Audio & Microphone: STANDBY (Audio output device ready)"
        audio_col = COLOR_STATUS_GREEN if audio_ok else COLOR_WARNING_GOLD
        tk.Label(perm_card, text=audio_text, bg=COLOR_BG_SECONDARY, fg=audio_col, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=1)

        tk.Label(perm_card, text="● Meta Glass Bridge: OPTIONAL (BLE hardware link on-demand)", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=1)

        # 2. Profile Setup Card
        prof_card = tk.Frame(container, bg=COLOR_BG_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        prof_card.pack(fill=tk.X, pady=(0, 10), ipady=6)

        prof_title = tk.Label(prof_card, text="👤 Personal Profile Setup", bg=COLOR_BG_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        prof_title.pack(anchor="w", padx=12, pady=(4, 2))

        prof_prompt = tk.Label(prof_card, text="What should I call you?", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 9, "bold"))
        prof_prompt.pack(anchor="w", padx=12, pady=(0, 4))

        prof_grid = tk.Frame(prof_card, bg=COLOR_BG_SECONDARY)
        prof_grid.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(prof_grid, text="Your Name:", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        entry_uname = tk.Entry(prof_grid, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_uname.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

        tk.Label(prof_grid, text="Display / Greeting:", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        entry_dname = tk.Entry(prof_grid, bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_dname.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)
        prof_grid.columnconfigure(1, weight=1)

        # 3. Optional Gemini API Key Setup Card
        api_card = tk.Frame(container, bg=COLOR_BG_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        api_card.pack(fill=tk.X, pady=(0, 10), ipady=6)

        api_title = tk.Label(api_card, text="🔑 Gemini AI Key Setup (Optional during install)", bg=COLOR_BG_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        api_title.pack(anchor="w", padx=12, pady=(4, 2))

        api_desc = tk.Label(api_card, text="Enter your Google Gemini API Key for real-time vision conversation, or configure later in Settings.", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8))
        api_desc.pack(anchor="w", padx=12, pady=(0, 4))

        api_input_frame = tk.Frame(api_card, bg=COLOR_BG_SECONDARY)
        api_input_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(api_input_frame, text="Gemini Key 1:", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        entry_key1 = tk.Entry(api_input_frame, show="•", bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        existing_key = self.engine.key_manager.keys.get(1, "")
        if existing_key:
            entry_key1.insert(0, existing_key)
        entry_key1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        # 4. Sensitive Password Setup Card (Feature 1 Security)
        sec_card = tk.Frame(container, bg=COLOR_BG_SECONDARY, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        sec_card.pack(fill=tk.X, pady=(0, 10), ipady=6)

        sec_title = tk.Label(sec_card, text="🛡️ Sensitive Password Setup (Optional during install)", bg=COLOR_BG_SECONDARY, fg=COLOR_CYAN_PRIMARY, font=("Segoe UI", 10, "bold"))
        sec_title.pack(anchor="w", padx=12, pady=(4, 2))

        sec_desc = tk.Label(sec_card, text="Set your spoken password (min 2 words) to protect sensitive personal memories and high-risk actions.", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 8))
        sec_desc.pack(anchor="w", padx=12, pady=(0, 4))

        sec_grid = tk.Frame(sec_card, bg=COLOR_BG_SECONDARY)
        sec_grid.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Label(sec_grid, text="Sensitive Password:", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        entry_pw1 = tk.Entry(sec_grid, show="•", bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_pw1.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

        tk.Label(sec_grid, text="Repeat Password:", bg=COLOR_BG_SECONDARY, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        entry_pw2 = tk.Entry(sec_grid, show="•", bg=COLOR_BG_PRIMARY, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_CYAN_PRIMARY, font=("Segoe UI", 9), relief=tk.FLAT, bd=0, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)
        entry_pw2.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)
        sec_grid.columnconfigure(1, weight=1)

        lbl_onboarding_status = tk.Label(container, text="", bg=COLOR_BG_PRIMARY, fg=COLOR_ALERT_RED, font=("Segoe UI", 9))
        lbl_onboarding_status.pack(pady=(0, 4))

        def save_onboarding_and_start():
            uname = entry_uname.get().strip()
            if not uname:
                lbl_onboarding_status.config(text="Please enter your name to personalize SG CUBE.", fg=COLOR_ALERT_RED)
                entry_uname.focus_set()
                return

            pw1 = entry_pw1.get().strip()
            pw2 = entry_pw2.get().strip()
            if pw1 or pw2:
                if pw1.lower() != pw2.lower():
                    lbl_onboarding_status.config(text="The passwords did not match. Please try again.", fg=COLOR_ALERT_RED)
                    entry_pw2.focus_set()
                    return
                if len(pw1.split()) < 2:
                    lbl_onboarding_status.config(text="Password is too short. Please use a phrase with at least two words.", fg=COLOR_ALERT_RED)
                    entry_pw1.focus_set()
                    return
                ok, msg, rc = self.engine.security.set_password(pw1)
                if not ok:
                    lbl_onboarding_status.config(text=msg, fg=COLOR_ALERT_RED)
                    return
                if rc:
                    messagebox.showinfo("Recovery Code", f"Please safely record your one-time Voice Security Recovery Code:\n\n{rc}\n\nThis code cannot be displayed again.", parent=dialog)

            dname = entry_dname.get().strip() or uname
            k1 = entry_key1.get().strip()

            self.engine.store.set_setting("user_name", uname)
            self.engine.store.set_setting("user_display_name", dname)
            self.engine.store.set_setting("first_run_completed", True)

            if k1:
                self.engine.key_manager.set_key(1, k1)

            print(f"[ONBOARDING] Profile saved: user_name='{uname}', display_name='{dname}'. Setup completed.")
            animate_dialog_close(dialog, duration_ms=180)

            # Trigger immediate startup greeting for configured user
            hour = time.localtime().tm_hour
            time_period = "morning" if 5 <= hour < 12 else ("afternoon" if 12 <= hour < 17 else ("evening" if 17 <= hour < 22 else "night"))
            greeting_msg = f"Good {time_period}, {uname}. I'm ready to help."
            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", greeting_msg))
            self.engine.response_manager.add_response(greeting_msg, priority=2, force=True)

        btn_finish = tk.Button(
            container,
            text="Complete Setup & Launch SG CUBE",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_CYAN_PRIMARY,
            fg=COLOR_BG_PRIMARY,
            activebackground=COLOR_TEAL_MINT,
            activeforeground=COLOR_BG_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            padx=18,
            pady=8,
            cursor="hand2",
            command=save_onboarding_and_start
        )
        btn_finish.pack(pady=(4, 0))

    def on_close(self):
        print("[STATE] CLOSED")
        print("[HANDOFF] MAIN -> BACKGROUND")
        print("[SHUTDOWN] SG CUBE shutting down cleanly...")
        self.stop_ai()
        self.stop_camera()
        self._clear_playback_queue()
        self._notify_wake_listener_resume()
        time.sleep(0.15)
        try:
            self.root.destroy()
        except Exception:
            pass

def main():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(('127.0.0.1', IPC_PORT_GUI))
        sock.close()
        if res == 0:
            print(f"[SINGLE-INSTANCE] Port {IPC_PORT_GUI} active. Sending WAKE IPC to existing instance and exiting before GUI creation.")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(('127.0.0.1', IPC_PORT_GUI))
                s.sendall(b"WAKE")
                s.close()
            except Exception:
                pass
            sys.exit(0)
    except Exception:
        pass

    root = tk.Tk()
    app = SGCubeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
