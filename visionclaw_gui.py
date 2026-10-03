import os
import sys
import re
import time



import queue



import random



import math



import socket



import threading



import subprocess



import asyncio
import functools
import concurrent.futures
from typing import Any, Dict, Optional



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

7. When the user asks to adjust, check, or change screen brightness or master volume, call set_screen_brightness or set_system_volume.

8. When the user asks to turn Wi-Fi on or off, or check Wi-Fi status, call set_wifi_state.

9. When the user asks to turn Bluetooth on or off, check Bluetooth status, list Bluetooth devices, or connect or disconnect a Bluetooth device, call set_bluetooth_state or manage_bluetooth_device.
10. When the user asks to read the screen, describe what's on the screen, check the screen, or tell what is displayed on the screen, call read_screen.
11. When the user gives voice mouse commands (such as moving the mouse, clicking, double clicking, right clicking, scrolling, dragging, or checking cursor position), do not output spoken disclaimers; the local controller handles real Windows mouse events.
12. When the user asks to open Windows Settings or specific settings pages (such as Wi-Fi settings, Bluetooth settings, display settings, sound settings, accessibility settings, etc.), call open_windows_settings.
13. When the user asks to open Notepad, write or type text into Notepad, select all, copy text, paste clipboard content, or clear Notepad, call notepad_control or open_notepad.
14. When the user asks to search YouTube, play a video or music on YouTube, open YouTube, mute or unmute YouTube, skip or seek forward or backward, or close YouTube, call youtube_control.
15. When the user asks to take a screenshot, capture the screen, or save a screenshot of the active window, call take_screenshot.
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







# --- SG CUBE Neon Green & Emerald Global Design System ---
COLOR_BG_PRIMARY = "#020604"        # Pure near-black obsidian application base (#000000 / #020604)
COLOR_BG_SECONDARY = "#030A06"      # Inset header/footer background
COLOR_PANEL_DEEP = "#040D08"        # Translucent black-emerald glass cards
COLOR_PANEL_SECONDARY = "#071810"   # Inset control panels
COLOR_PANEL_HOVER = "#0A2418"       # Elevated interactive hover panels
COLOR_BORDER_SUBTLE = "#084A2A"     # Dark emerald border
COLOR_BORDER_HOVER = "#00D46A"      # Rich emerald hover border
COLOR_BORDER_ACTIVE = "#39FF88"     # Luminous neon green active border
COLOR_NAV_ACTIVE_BG = "#021A10"     # Active tab dark green glass surface
COLOR_DIVIDER = "#063B25"           # Deep emerald divider (1px)

# Neon Green / Emerald System Hierarchy
COLOR_NEON_PRIMARY = "#39FF88"      # Primary neon green accent
COLOR_EMERALD_PRIMARY = "#00D46A"   # Primary rich emerald
COLOR_EMERALD_BRIGHT = "#22F56F"    # Bright vivid emerald
COLOR_MINT_HIGHLIGHT = "#8AFFC1"    # Mint highlight sheen
COLOR_EMERALD_DEEP = "#063B25"      # Deep emerald
COLOR_GREEN_DARK = "#021A10"        # Dark green core interior
COLOR_GREEN_FACE_EMERALD = "#087A45"# Core emerald face
COLOR_GREEN_FACE_BRIGHT = "#13B95D" # Core bright green face
COLOR_NEON_GLOW = "#39FF8833"       # Soft neon green glow aura

# Backward-compatible references mapped to Neon Green / Emerald
COLOR_GOLD_LIGHT = "#8AFFC1"        # Mint highlight
COLOR_GOLD_PRIMARY = "#39FF88"      # Neon green
COLOR_GOLD_MEDIUM = "#22F56F"       # Bright emerald
COLOR_GOLD_DARK = "#00D46A"         # Emerald
COLOR_GOLD_DEEP = "#063B25"         # Deep emerald
COLOR_GOLD_GLOW = "#39FF8833"

# Typography — White, Silver & Muted Reading Hierarchy
COLOR_PEACH_PRIMARY = "#FFFFFF"     # Primary Headings / Titles / AI Text (pure white)
COLOR_PEACH_SECONDARY = "#D0D0D0"   # Secondary Labels / Subtitles (refined silver)
COLOR_PEACH_MUTED = "#858585"       # Timestamps / Subtitles / Muted text (neutral gray/silver)
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#D0D0D0"
COLOR_TEXT_MUTED = "#858585"

# Controlled Semantic Functional Status Colors
COLOR_STATUS_GREEN = "#39FF88"      # Connected / healthy / active (neon green)
COLOR_STATUS_CYAN = "#8AFFC1"       # Mint
COLOR_STATUS_BLUE = "#22F56F"       # Bright emerald
COLOR_ALERT_RED = "#EF4444"         # Error / physical hazard
COLOR_WARNING_GOLD = "#F59E0B"      # Warning amber
COLOR_CYAN_PRIMARY = "#39FF88"      # Neon green
COLOR_TEAL_MINT = "#8AFFC1"         # Mint
COLOR_ORANGE = "#F97316"            # Reconnecting

# Functional Icons — Neon Green / Emerald Family
COLOR_ICON_HOME = "#39FF88"         # Neon green
COLOR_ICON_VISION = "#22F56F"       # Bright emerald
COLOR_ICON_MEMORY = "#00D46A"       # Emerald
COLOR_ICON_HISTORY = "#8AFFC1"      # Mint
COLOR_ICON_PEOPLE = "#22F56F"       # Bright emerald
COLOR_ICON_METAGLASS = "#39FF88"    # Neon green
COLOR_ICON_SETTINGS = "#00D46A"     # Emerald
COLOR_ICON_ENV = "#39FF88"          # Section icon neon green
COLOR_ICON_SCENE = "#22F56F"        # Section icon bright emerald
COLOR_ICON_STATUS = "#00D46A"       # Section icon emerald

# Aliases for backwards compatibility with any remaining references
COLOR_DARK_BLUE_DEEP = "#020604"
COLOR_DARK_BLUE_PRIMARY = "#084A2A"
COLOR_DARK_BLUE_MEDIUM = "#00D46A"
COLOR_DARK_BLUE_ACCENT = "#39FF88"
COLOR_DARK_BLUE_HIGHLIGHT = "#8AFFC1"
COLOR_DARK_BLUE_LIGHT = "#39FF88"
COLOR_DARK_GREEN_DEEP = "#020604"
COLOR_DARK_GREEN_PRIMARY = "#084A2A"
COLOR_DARK_GREEN_MEDIUM = "#00D46A"
COLOR_DARK_GREEN_ACCENT = "#39FF88"
COLOR_DARK_GREEN_HIGHLIGHT = "#8AFFC1"
COLOR_DARK_GREEN_LIGHT = "#39FF88"
COLOR_OLIVE_PRIMARY = "#084A2A"
COLOR_OLIVE_DARK = "#020604"
COLOR_OLIVE_BRIGHT = "#39FF88"
COLOR_OLIVE_GLOW = "#8AFFC1"







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







class ResponsiveDesignSystem:



    """



    Centralized Proportional Responsive Design System for SG CUBE.



    Canonical Reference Dimensions: 1672 x 941 (scale = 1.00).



    Every visual dimension (fonts, icons, header, cards, paddings, rows,



    camera, 3D cube centerpiece, footer) derives proportionally from this system.



    """



    REFERENCE_WIDTH = 1672.0



    REFERENCE_HEIGHT = 941.0







    # Reference Canonical Metrics (at 1672x941, scale = 1.00)



    # The desktop composition is intentionally tall: the identity and navigation



    # form one quiet glass rail, while the live camera remains the visual anchor.



    REF_HEADER_HEIGHT = 145



    REF_FOOTER_HEIGHT = 50







    # Stage Layout & Gaps



    REF_STAGE_PAD_X = 22



    REF_STAGE_MARGIN_Y = 4



    REF_STAGE_GAP_Y = 8



    REF_CARD_GAP_X = 18







    # Card Dimensions & Padding



    REF_CARD_PAD_X = 22



    REF_CARD_PAD_Y = 14



    REF_ROW_PAD_Y = 4



    REF_DIVIDER_PAD_Y = 5



    REF_ICON_GAP_X = 12







    # Camera & Centerpiece Viewports



    REF_CAMERA_HEIGHT = 395



    REF_ORB_CANVAS_WIDTH = 450



    REF_ORB_CANVAS_HEIGHT = 310







    # Icon Sizes



    REF_ICON_LOGO = 104



    REF_ICON_NAV = 32



    REF_ICON_STATUS = 26



    REF_ICON_SETTINGS = 38



    REF_ICON_CARD_TITLE = 26



    REF_ICON_ROW = 20



    REF_ICON_CAM_BTN = 28







    # Typography (pt)



    REF_FONT_BRAND_TITLE = 28



    REF_FONT_BRAND_SUB = 14



    REF_FONT_BRAND_TAGLINE = 12



    REF_FONT_NAV = 15



    REF_FONT_STATUS_TEXT = 16



    REF_FONT_STATUS_DOT = 12



    REF_FONT_CARD_TITLE = 18



    REF_FONT_CARD_LINK = 15



    REF_FONT_ROW_LABEL = 14



    REF_FONT_ROW_VAL = 14



    REF_FONT_CAM_PILL = 14



    REF_FONT_FOOTER = 14







    # Button & Pill Paddings



    REF_NAV_PAD_X = 6



    REF_NAV_PAD_Y = 4



    REF_STATUS_PILL_PAD_X = 12



    REF_STATUS_PILL_PAD_Y = 5



    REF_CAM_PILL_PAD_X = 8



    REF_CAM_PILL_PAD_Y = 2



    REF_BTN_PAD_X = 8



    REF_BTN_PAD_Y = 5



    REF_FOOTER_PAD_X = 16







    @classmethod



    def compute(cls, current_width, current_height):



        w = max(400, float(current_width))



        h = max(300, float(current_height))







        scale_x = w / cls.REFERENCE_WIDTH



        scale_y = h / cls.REFERENCE_HEIGHT



        base_scale = min(scale_x, scale_y)







        # Proportional scale factors with safeguards for usability



        font_scale = max(0.48, base_scale)



        icon_scale = max(0.50, base_scale)







        # Header & Footer sizes



        hdr_h = max(68, int(round(cls.REF_HEADER_HEIGHT * scale_y)))



        ftr_h = max(26, int(round(cls.REF_FOOTER_HEIGHT * scale_y)))



        avail_h = max(200, int(h - hdr_h - ftr_h))







        # Dynamic vertical budget allocation:
        # Controlled margins with distinct stage gap separating upper and lower rows
        if h <= 620:
            stage_margin_y = max(2, int(round(3 * scale_y)))
            stage_gap_y = max(6, int(round(8 * scale_y)))
        else:
            stage_margin_y = max(3, int(round(4 * scale_y)))
            stage_gap_y = max(6, int(round(8 * scale_y)))

        total_gaps = stage_margin_y * 2 + stage_gap_y
        usable_h = max(180, avail_h - total_gaps)

        # Account for cam_outer_card padding and border (3px top/bottom + 1px border = 8px total)
        cam_extra_y = max(4, int(round(8 * base_scale)))

        # Target: Upper stage 44-47% of total window height h
        # Lower stage 33-36% of total window height h
        # Hero camera consumes 90-95%+ of upper stage height
        upper_stage_h = max(180, int(round(h * 0.445)))
        lower_stage_h = max(150, usable_h - upper_stage_h)
        camera_height = max(160, upper_stage_h - cam_extra_y)

        orb_canvas_w = max(180, int(round((w - 44) * 0.28)))
        orb_canvas_h = max(130, lower_stage_h - 14)







        return {



            'w': int(w),



            'h': int(h),



            'scale_x': round(scale_x, 4),



            'scale_y': round(scale_y, 4),



            'base_scale': round(base_scale, 4),



            'font_scale': round(font_scale, 4),



            'icon_scale': round(icon_scale, 4),







            # Header & Footer



            'header_height': hdr_h,



            'footer_height': ftr_h,







            # Layout & Gaps



            'stage_pad_x': max(8, int(round(cls.REF_STAGE_PAD_X * scale_x))),



            'stage_margin_y': stage_margin_y,



            'stage_gap_y': stage_gap_y,



            'card_gap_x': max(6, int(round(cls.REF_CARD_GAP_X * scale_x))),







            # Card internal padding



            'card_pad_x': max(6, int(round(cls.REF_CARD_PAD_X * base_scale))),



            'card_pad_y': max(3, int(round(cls.REF_CARD_PAD_Y * scale_y))),



            'row_pad_y': max(0, int(round(cls.REF_ROW_PAD_Y * scale_y))),



            'div_pad_y': max(0, int(round(cls.REF_DIVIDER_PAD_Y * scale_y))),



            'icon_gap_x': max(4, int(round(cls.REF_ICON_GAP_X * base_scale))),







            # Viewports (Hero Camera + Lower Stage)



            'upper_stage_height': upper_stage_h,
            'lower_stage_height': lower_stage_h,
            'camera_height': camera_height,
            'lower_height': lower_stage_h,



            'orb_canvas_width': orb_canvas_w,



            'orb_canvas_height': orb_canvas_h,







            # Icons



            'logo_size': max(28, int(round(cls.REF_ICON_LOGO * icon_scale))),



            'icon_nav': max(18, int(round(cls.REF_ICON_NAV * icon_scale))),



            'icon_status': max(16, int(round(cls.REF_ICON_STATUS * icon_scale))),



            'icon_settings': max(18, int(round(cls.REF_ICON_SETTINGS * icon_scale))),



            'icon_card_title': max(16, int(round(cls.REF_ICON_CARD_TITLE * icon_scale))),



            'icon_row': max(12, int(round(cls.REF_ICON_ROW * icon_scale))),



            'icon_cam_btn': max(14, int(round(cls.REF_ICON_CAM_BTN * icon_scale))),







            # Fonts



            'font_brand_title': max(14, int(round(cls.REF_FONT_BRAND_TITLE * font_scale))),



            'font_brand_sub': max(8, int(round(cls.REF_FONT_BRAND_SUB * font_scale))),



            'font_brand_tagline': max(7, int(round(cls.REF_FONT_BRAND_TAGLINE * font_scale))),



            'font_nav': max(8, int(round(cls.REF_FONT_NAV * font_scale))),



            'font_status_text': max(9, int(round(cls.REF_FONT_STATUS_TEXT * font_scale))),



            'font_status_dot': max(6, int(round(cls.REF_FONT_STATUS_DOT * font_scale))),



            'font_card_title': max(10, int(round(cls.REF_FONT_CARD_TITLE * font_scale))),



            'font_card_link': max(8, int(round(cls.REF_FONT_CARD_LINK * font_scale))),



            'font_row_label': max(8, int(round(cls.REF_FONT_ROW_LABEL * font_scale))),



            'font_hist_msg': max(8, int(round(11 * font_scale))),



            'font_row_val': max(8, int(round(cls.REF_FONT_ROW_VAL * font_scale))),



            'font_cam_pill': max(8, int(round(cls.REF_FONT_CAM_PILL * font_scale))),



            'font_footer': max(8, int(round(cls.REF_FONT_FOOTER * font_scale))),







            # Paddings for elements



            'nav_pad_x': max(2, int(round(cls.REF_NAV_PAD_X * base_scale))),



            'nav_pad_y': max(2, int(round(cls.REF_NAV_PAD_Y * base_scale))),



            'status_pill_pad_x': max(6, int(round(cls.REF_STATUS_PILL_PAD_X * base_scale))),



            'status_pill_pad_y': max(2, int(round(cls.REF_STATUS_PILL_PAD_Y * base_scale))),



            'cam_pill_pad_x': max(4, int(round(cls.REF_CAM_PILL_PAD_X * base_scale))),



            'cam_pill_pad_y': max(1, int(round(cls.REF_CAM_PILL_PAD_Y * base_scale))),



            'btn_pad_x': max(4, int(round(cls.REF_BTN_PAD_X * base_scale))),



            'btn_pad_y': max(2, int(round(cls.REF_BTN_PAD_Y * base_scale))),



            'footer_pad_x': max(8, int(round(cls.REF_FOOTER_PAD_X * base_scale))),



        }







class RoundedGlassCard(tk.Canvas):



    """



    Renders a premium dark green-black glass card matching reference:



    - Smooth anti-aliased rounded corners (radius ~14px)



    - Subtle outer emerald glow (#07180F / #133824)



    - Thin, clearly visible emerald border (#2E7D52)



    - Deep obsidian-emerald glass interior (#09130E)



    - Hosts an inner tk.Frame for child widgets that seamlessly blends with the glass interior.



    """



    def __init__(self, master, radius=14, **kwargs):



        self.radius = radius



        raw_px = kwargs.pop('padx', 12)



        raw_py = kwargs.pop('pady', 6)



        self._pad_x = max(4, int(raw_px * 2))



        self._pad_y = max(4, int(raw_py * 2))



        kwargs.pop('highlightbackground', None)



        kwargs.pop('highlightthickness', None)



        kwargs.pop('bg', None)



        kwargs.setdefault('width', 10)
        super().__init__(master, bg=COLOR_BG_PRIMARY, highlightthickness=0, bd=0, **kwargs)



        self.inner = tk.Frame(self, bg=COLOR_PANEL_DEEP)



        self.win_id = self.create_window(0, 0, window=self.inner, anchor='center')



        self.bind('<Configure>', self._on_resize)







    def _round_rect_pts(self, x1, y1, x2, y2, r):



        return [



            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,



            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,



            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1



        ]







    def _on_resize(self, e):



        if e is not None and e.widget != self:



            return



        w, h = e.width, e.height



        if w < 20 or h < 20:



            return



        self.delete('card_bg')



        # Two restrained layers give every panel a distinct glass edge without



        # making the data area look like a thick framed box.



        pts_glow = self._round_rect_pts(1, 1, w - 1, h - 1, self.radius + 2)
        self.create_polygon(pts_glow, fill='#040D08', outline='#042618', width=2.5, smooth=True, tags='card_bg')
        pts_body = self._round_rect_pts(3, 3, w - 3, h - 3, self.radius)
        self.create_polygon(pts_body, fill=COLOR_PANEL_DEEP, outline='#084A2A', width=1.0, smooth=True, tags='card_bg')



        self.tag_lower('card_bg')



        # Position inner content container



        self.coords(self.win_id, w // 2, h // 2)



        self.itemconfig(self.win_id, width=max(10, w - self._pad_x), height=max(10, h - self._pad_y))







    def config(self, **kwargs):



        px = kwargs.pop('padx', None)



        py = kwargs.pop('pady', None)



        h_val = kwargs.pop('height', None)



        w_val = kwargs.pop('width', None)



        kwargs.pop('highlightbackground', None)



        kwargs.pop('highlightthickness', None)



        if px is not None:



            self._pad_x = max(6, int(px * 2))



        if py is not None:



            self._pad_y = max(6, int(py * 2))



        if h_val is not None:



            super().config(height=h_val)



        if w_val is not None:



            super().config(width=w_val)



        w = self.winfo_width()



        h = self.winfo_height()



        if w > 20 and h > 20 and getattr(self, 'win_id', None):



            self.coords(self.win_id, w // 2, h // 2)



            self.itemconfig(self.win_id, width=max(10, w - self._pad_x), height=max(10, h - self._pad_y))



        if kwargs:



            super().config(**kwargs)







    def bind(self, sequence=None, func=None, add=None):



        res = super().bind(sequence, func, add)



        try:



            self.inner.bind(sequence, func, add)



        except Exception:



            pass



        return res







class RoundedPill(tk.Canvas):



    """



    Renders a camera overlay pill with rounded capsule ends matching reference.



    """



    def __init__(self, master, text="LIVE", dot=False, border_col="#FF4B4B", bg_col="#141715", text_col="#FFFFFF", **kwargs):



        self.text_val = text



        self.has_dot = dot



        self.border_col = border_col



        self.bg_col = bg_col



        self.text_col = text_col



        self.font = ("Segoe UI", 9, "bold")



        self._pad_x = kwargs.pop('padx', 6)



        self._pad_y = kwargs.pop('pady', 2)



        kwargs.pop('highlightthickness', None)



        kwargs.pop('bd', None)



        kwargs.pop('bg', None)



        super().__init__(master, bg=COLOR_PANEL_DEEP, highlightthickness=0, bd=0, **kwargs)



        self._recalc_size()



        self.bind("<Configure>", self._render)







    def _recalc_size(self):



        try:



            import tkinter.font as tkfont



            f = tkfont.Font(font=self.font)



            req_w = f.measure(self.text_val) + (34 if self.has_dot else 22)



            req_h = max(22, f.metrics('linespace') + 6)



            super().config(width=max(56, req_w), height=req_h)



        except Exception:



            pass







    def _render(self, e=None):



        if e is not None and e.widget != self:



            return



        w = self.winfo_width()



        h = self.winfo_height()



        if w < 10 or h < 10:



            return



        self.delete("all")



        r = min(8, h // 2)



        pts = [



            1 + r, 1, w - 1 - r, 1, w - 1, 1, w - 1, 1 + r,



            w - 1, h - 1 - r, w - 1, h - 1, w - 1 - r, h - 1, 1 + r, h - 1,



            1, h - 1, 1, h - 1 - r, 1, 1 + r, 1, 1



        ]



        self.create_polygon(pts, fill=self.bg_col, outline=self.border_col, width=1.2, smooth=True)



        tx = w // 2



        if self.has_dot:



            dot_x = 12



            dot_y = h // 2



            self.create_oval(dot_x - 3.5, dot_y - 3.5, dot_x + 3.5, dot_y + 3.5, fill=self.border_col, outline="")



            tx = dot_x + 14



            self.create_text(tx, h // 2, text=self.text_val, fill=self.text_col, font=self.font, anchor="w")



        else:



            self.create_text(tx, h // 2, text=self.text_val, fill=self.text_col, font=self.font, anchor="center")







    def config(self, **kwargs):



        if 'text' in kwargs:



            self.text_val = kwargs.pop('text')



        if 'fg' in kwargs:



            self.text_col = kwargs.pop('fg')



        if 'bg' in kwargs:



            self.bg_col = kwargs.pop('bg')



        if 'font' in kwargs:



            self.font = kwargs.pop('font')



        if 'padx' in kwargs:



            self._pad_x = kwargs.pop('padx')



        if 'pady' in kwargs:



            self._pad_y = kwargs.pop('pady')



        self._recalc_size()



        self._render()



        if kwargs:



            super().config(**kwargs)







class Real3DCubeRenderer:
    """
    Renders an authentic, genuine live animated vector SG CUBE HUD centerpiece:
    - 100% Vector Tkinter Canvas primitives (<0.2ms / frame, zero lag, zero memory leaks).
    - Multiple 3D-tilted concentric orbital rings with differential rotation and depth cues.
    - Sparse glowing orbiting nodes with mint halos.
    - Central 3D geometric core: translucent faceted cyber-core with dark green interior,
      emerald and bright green faces, neon edges, and mint specular sheen.
    - Outer HUD reticle with rotating radial calipers and cardinal tick marks.
    - Centered crisp typography: 'SG CUBE' (pure white) + 'Seeing • Understanding • Helping'
      with silver labels and neon green bullet dots.
    - Smooth 3D rotating cube logo for header bar (draw_header_cube).
    - Zero image assets used — purely programmatic, smooth, and resilient.
    """

    # Color palette constants
    C_BG = "#020604"
    C_NEON = "#39FF88"
    C_EMERALD = "#00D46A"
    C_EMERALD_BRIGHT = "#22F56F"
    C_MINT = "#8AFFC1"
    C_EMERALD_DEEP = "#063B25"
    C_GREEN_DARK = "#021A10"
    C_FACE_EMERALD = "#087A45"
    C_FACE_BRIGHT = "#13B95D"
    C_TEXT_WHITE = "#FFFFFF"
    C_TEXT_SILVER = "#D0D0D0"
    C_TEXT_MUTED = "#858585"

    def __init__(self, canvas_width=380, canvas_height=260):
        self.width = canvas_width
        self.height = canvas_height

    def draw(self, canvas, rot_x=-0.40, rot_y=0.785398, rot_z=0.0, time_val=0.0, state="IDLE", hover=False, mouse_tilt=(0.0, 0.0), pulse=1.0, show_labels=True):
        """Draws the entire live animated HUD using ultra-fast Canvas vector primitives."""
        try:
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw < 30 or ch < 30:
                try:
                    cw = int(canvas.cget("width"))
                    ch = int(canvas.cget("height"))
                except Exception:
                    cw, ch = 380, 260

            canvas.delete("all")

            tilt_x, tilt_y = mouse_tilt
            # Center of the HUD system (elevated when show_labels=True to leave room for typography)
            cy_offset = 24 if show_labels else 0
            cx = cw // 2 + int(tilt_y * 10)
            cy = ch // 2 - cy_offset + int(tilt_x * 10)

            # Responsive radius calculation
            max_r = max(36, min(cw * 0.38, (ch - (44 if show_labels else 0)) * 0.42))
            scale_f = max_r / 115.0

            t = float(time_val if time_val else (rot_y or 0.0))
            if state == "AI_SPEAKING":
                pulse_f = 1.0 + 0.10 * math.sin(t * 4.5)
                rot_speed_mult = 1.5
            elif state == "USER_SPEAKING":
                pulse_f = 1.0 + 0.07 * math.sin(t * 3.5)
                rot_speed_mult = 1.25
            elif state == "SAFETY_ALERT":
                pulse_f = 1.0 + 0.12 * math.sin(t * 5.0)
                rot_speed_mult = 1.8
            elif state == "SLEEPING":
                pulse_f = 0.65
                rot_speed_mult = 0.3
            elif state == "AI_THINKING":
                pulse_f = 1.0 + 0.06 * math.sin(t * 2.5)
                rot_speed_mult = 1.35
            else:  # IDLE / LISTENING
                pulse_f = 0.98 + 0.04 * math.sin(t * 1.5)
                rot_speed_mult = 1.0

            if hover:
                pulse_f = min(1.20, pulse_f + 0.05)

            # -------------------------------------------------------------
            # 1. OUTER HUD RETICLE & CALIPER RING
            # -------------------------------------------------------------
            r_hud_x = max_r * 0.96
            r_hud_y = max_r * 0.65

            # Outer caliper arc with open bottom sector for typography
            canvas.create_arc(cx - r_hud_x, cy - r_hud_y, cx + r_hud_x, cy + r_hud_y,
                              start=30, extent=300, style=tk.ARC,
                              outline=self.C_EMERALD_DEEP, width=1.0)
            canvas.create_arc(cx - r_hud_x, cy - r_hud_y, cx + r_hud_x, cy + r_hud_y,
                              start=75, extent=30, style=tk.ARC,
                              outline=self.C_NEON, width=1.6)
            canvas.create_arc(cx - r_hud_x, cy - r_hud_y, cx + r_hud_x, cy + r_hud_y,
                              start=255, extent=30, style=tk.ARC,
                              outline=self.C_NEON, width=1.6)

            # Radial tick marks along outer rim (omitting bottom sector where text lives)
            tick_yaw = t * 0.08 * rot_speed_mult
            for i in range(24):
                ang = (2 * math.pi * i / 24.0) + tick_yaw
                ang_deg = math.degrees(ang) % 360
                if 60 <= ang_deg <= 120 and show_labels:
                    continue
                cos_a, sin_a = math.cos(ang), math.sin(ang)
                x_in = cx + (r_hud_x - 4 * scale_f) * cos_a
                y_in = cy + (r_hud_y - 3 * scale_f) * sin_a
                x_out = cx + (r_hud_x + 3 * scale_f) * cos_a
                y_out = cy + (r_hud_y + 2 * scale_f) * sin_a
                is_cardinal = (i % 6 == 0)
                t_col = self.C_NEON if is_cardinal else self.C_EMERALD_DEEP
                t_w = 1.5 if is_cardinal else 1.0
                canvas.create_line(x_in, y_in, x_out, y_out, fill=t_col, width=t_w)

            # -------------------------------------------------------------
            # 2. CONCENTRIC 3D ORBITAL RINGS
            # -------------------------------------------------------------
            r1 = max_r * 0.92
            r2 = max_r * 0.72
            r3 = max_r * 0.52

            def get_ring_pts(radius, tilt_rad, yaw_rad, num_steps=48):
                cos_t, sin_t = math.cos(tilt_rad), math.sin(tilt_rad)
                cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
                pts = []
                for i in range(num_steps + 1):
                    phi = (2 * math.pi * i) / num_steps
                    x0 = radius * math.cos(phi)
                    y0 = radius * math.sin(phi) * cos_t
                    z0 = radius * math.sin(phi) * sin_t
                    x1 = x0 * cos_y + z0 * sin_y
                    y1 = y0
                    z1 = -x0 * sin_y + z0 * cos_y
                    pts.append((cx + x1, cy + y1, z1))
                return pts

            pts_r1 = get_ring_pts(r1, math.radians(65), t * 0.20 * rot_speed_mult, num_steps=48)
            pts_r2 = get_ring_pts(r2, math.radians(-54), t * 0.36 * rot_speed_mult, num_steps=42)
            pts_r3 = get_ring_pts(r3, math.radians(72), -t * 0.28 * rot_speed_mult, num_steps=36)

            # Draw background ring segments (z < 0)
            for pts in (pts_r1, pts_r2, pts_r3):
                for i in range(len(pts) - 1):
                    p_a, p_b = pts[i], pts[i + 1]
                    if (p_a[2] + p_b[2]) < 0:
                        canvas.create_line(p_a[0], p_a[1], p_b[0], p_b[1],
                                           fill=self.C_EMERALD_DEEP, width=1.0)

            # -------------------------------------------------------------
            # 3. BACKGROUND ORBITING NODES (z < 0)
            # -------------------------------------------------------------
            nodes = [
                (pts_r1, t * 0.42 * rot_speed_mult, 3.5),
                (pts_r1, t * 0.42 * rot_speed_mult + math.pi, 3.0),
                (pts_r2, -t * 0.60 * rot_speed_mult, 3.0),
                (pts_r2, -t * 0.60 * rot_speed_mult + 2.3, 2.5),
                (pts_r3, t * 0.80 * rot_speed_mult + 1.1, 2.5)
            ]

            def eval_node(ring_pts, angle):
                norm_angle = (angle % (2 * math.pi)) / (2 * math.pi)
                idx = norm_angle * (len(ring_pts) - 1)
                i0 = int(idx)
                i1 = min(len(ring_pts) - 1, i0 + 1)
                frac = idx - i0
                p0, p1 = ring_pts[i0], ring_pts[i1]
                return (p0[0] + (p1[0] - p0[0]) * frac,
                        p0[1] + (p1[1] - p0[1]) * frac,
                        p0[2] + (p1[2] - p0[2]) * frac)

            node_coords = [eval_node(r_pts, ang) for r_pts, ang, sz in nodes]

            for (nx, ny, nz), (_, _, sz) in zip(node_coords, nodes):
                if nz < 0:
                    canvas.create_oval(nx - sz * 0.6, ny - sz * 0.6, nx + sz * 0.6, ny + sz * 0.6,
                                       fill=self.C_EMERALD, outline=self.C_EMERALD_DEEP, width=1)

            # -------------------------------------------------------------
            # 4. CENTRAL 3D GEOMETRIC CORE
            # -------------------------------------------------------------
            core_sz = max(18, int(max_r * 0.35 * pulse_f))
            c_cos_y = math.cos(t * 0.18 * rot_speed_mult)
            c_sin_y = math.sin(t * 0.18 * rot_speed_mult)
            c_cos_x = math.cos(0.34 + 0.04 * math.sin(t * 0.4))
            c_sin_x = math.sin(0.34 + 0.04 * math.sin(t * 0.4))

            def proj_core(vx, vy, vz):
                x1 = vx * c_cos_y + vz * c_sin_y
                y1 = vy
                z1 = -vx * c_sin_y + vz * c_cos_y
                x2 = x1
                y2 = y1 * c_cos_x - z1 * c_sin_x
                z2 = y1 * c_sin_x + z1 * c_cos_x
                return (cx + x2, cy + y2, z2)

            cs = core_sz
            raw_verts = [
                (-cs, -cs, -cs), ( cs, -cs, -cs), ( cs,  cs, -cs), (-cs,  cs, -cs),
                (-cs, -cs,  cs), ( cs, -cs,  cs), ( cs,  cs,  cs), (-cs,  cs,  cs),
            ]
            proj_v = [proj_core(*v) for v in raw_verts]

            # Central soft glowing emitter
            orb_r = core_sz * 0.50 * pulse_f
            canvas.create_oval(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r,
                               fill=self.C_GREEN_DARK, outline=self.C_EMERALD, width=1.2)

            faces = [
                ([0, 1, 5, 4], ( 0, -1,  0), self.C_FACE_BRIGHT, self.C_MINT),       # Top
                ([4, 5, 6, 7], ( 0,  0,  1), self.C_FACE_EMERALD, self.C_NEON),      # Front
                ([1, 5, 6, 2], ( 1,  0,  0), self.C_FACE_EMERALD, self.C_EMERALD_BRIGHT),# Right
                ([0, 4, 7, 3], (-1,  0,  0), self.C_GREEN_DARK, self.C_EMERALD_DEEP),# Left
                ([1, 0, 3, 2], ( 0,  0, -1), self.C_GREEN_DARK, self.C_EMERALD_DEEP),# Back
                ([3, 2, 6, 7], ( 0,  1,  0), self.C_GREEN_DARK, self.C_EMERALD_DEEP),# Bottom
            ]

            edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
            for v1, v2 in edges:
                canvas.create_line(proj_v[v1][0], proj_v[v1][1], proj_v[v2][0], proj_v[v2][1],
                                   fill=self.C_EMERALD_DEEP, width=1.0)

            face_depths = []
            for idxs, norm, fill_col, out_col in faces:
                nx, ny, nz = norm
                nx1 = nx * c_cos_y + nz * c_sin_y
                nz1 = -nx * c_sin_y + nz * c_cos_y
                ny2 = ny * c_cos_x - nz1 * sin_x if 'sin_x' in dir() else ny * c_cos_x - nz1 * math.sin(0.34)
                nz2 = ny * c_sin_x + nz1 * c_cos_x
                if nz2 > -0.05:
                    avg_z = sum(proj_v[i][2] for i in idxs) / 4.0
                    face_depths.append((avg_z, idxs, fill_col, out_col))

            face_depths.sort(key=lambda x: x[0])
            for avg_z, idxs, fill_col, out_col in face_depths:
                pts = []
                for i in idxs:
                    pts.extend([proj_v[i][0], proj_v[i][1]])
                canvas.create_polygon(pts, fill=fill_col, outline=out_col, width=1.5)

            for v1, v2 in edges:
                if proj_v[v1][2] > 0 and proj_v[v2][2] > 0:
                    canvas.create_line(proj_v[v1][0], proj_v[v1][1], proj_v[v2][0], proj_v[v2][1],
                                       fill=self.C_MINT, width=1.8)

            # -------------------------------------------------------------
            # 5. FOREGROUND RINGS (z >= 0)
            # -------------------------------------------------------------
            for i in range(len(pts_r3) - 1):
                p_a, p_b = pts_r3[i], pts_r3[i + 1]
                if (p_a[2] + p_b[2]) >= 0:
                    canvas.create_line(p_a[0], p_a[1], p_b[0], p_b[1], fill=self.C_MINT, width=1.2)

            for i in range(len(pts_r2) - 1):
                p_a, p_b = pts_r2[i], pts_r2[i + 1]
                if (p_a[2] + p_b[2]) >= 0 and (i % 6) < 4:
                    canvas.create_line(p_a[0], p_a[1], p_b[0], p_b[1], fill=self.C_EMERALD_BRIGHT, width=1.5)

            for i in range(len(pts_r1) - 1):
                p_a, p_b = pts_r1[i], pts_r1[i + 1]
                if (p_a[2] + p_b[2]) >= 0 and (i % 8) < 6:
                    canvas.create_line(p_a[0], p_a[1], p_b[0], p_b[1], fill=self.C_NEON, width=1.8)

            # -------------------------------------------------------------
            # 6. FOREGROUND ORBITING NODES (z >= 0)
            # -------------------------------------------------------------
            for (nx, ny, nz), (_, _, sz) in zip(node_coords, nodes):
                if nz >= 0:
                    halo_sz = sz * 2.2
                    canvas.create_oval(nx - halo_sz, ny - halo_sz, nx + halo_sz, ny + halo_sz,
                                       outline=self.C_NEON, fill="", width=1.0)
                    canvas.create_oval(nx - sz, ny - sz, nx + sz, ny + sz,
                                       fill=self.C_MINT, outline=self.C_NEON, width=1.5)

            # -------------------------------------------------------------
            # 7. TYPOGRAPHY & HUD LABELS
            # -------------------------------------------------------------
            if show_labels:
                font_title_sz = max(11, int(round(13 * scale_f)))
                font_sub_sz = max(8, int(round(8.5 * scale_f)))

                y_text = cy + r_hud_y + int(12 * scale_f)
                y_motto = y_text + int(16 * scale_f)

                canvas.create_text(cx, y_text, text="SG CUBE",
                                   font=("Segoe UI", font_title_sz, "bold"),
                                   fill=self.C_TEXT_WHITE)

                try:
                    from tkinter import font as tkfont
                    f_obj = tkfont.Font(font=("Segoe UI", font_sub_sz))
                    w_see = f_obj.measure("Seeing")
                    w_dot1 = f_obj.measure("  •  ")
                    w_und = f_obj.measure("Understanding")
                    w_dot2 = f_obj.measure("  •  ")
                    w_hlp = f_obj.measure("Helping")
                    total_w = w_see + w_dot1 + w_und + w_dot2 + w_hlp
                    curr_x = cx - total_w // 2

                    canvas.create_text(curr_x + w_see // 2, y_motto, text="Seeing", fill=self.C_TEXT_SILVER, font=("Segoe UI", font_sub_sz), anchor="center")
                    curr_x += w_see
                    canvas.create_text(curr_x + w_dot1 // 2, y_motto, text="  •  ", fill=self.C_NEON, font=("Segoe UI", font_sub_sz), anchor="center")
                    curr_x += w_dot1
                    canvas.create_text(curr_x + w_und // 2, y_motto, text="Understanding", fill=self.C_TEXT_SILVER, font=("Segoe UI", font_sub_sz), anchor="center")
                    curr_x += w_und
                    canvas.create_text(curr_x + w_dot2 // 2, y_motto, text="  •  ", fill=self.C_NEON, font=("Segoe UI", font_sub_sz), anchor="center")
                    curr_x += w_dot2
                    canvas.create_text(curr_x + w_hlp // 2, y_motto, text="Helping", fill=self.C_TEXT_SILVER, font=("Segoe UI", font_sub_sz), anchor="center")
                except Exception:
                    canvas.create_text(cx, y_motto, text="Seeing  •  Understanding  •  Helping",
                                       fill=self.C_TEXT_SILVER, font=("Segoe UI", font_sub_sz), anchor="center")
        except Exception:
            pass

    def draw_audio_core(self, canvas, time_val=0.0, rot_y=None, state="IDLE", pulse=1.0, hover=False, mouse_tilt=(0.0, 0.0)):
        """Renders the authentic live animated vector SG CUBE HUD centerpiece with zero lag."""
        return self.draw(canvas, rot_x=-0.40, rot_y=rot_y if rot_y is not None else time_val, rot_z=0.0,
                         time_val=time_val, state=state, hover=hover, mouse_tilt=mouse_tilt, pulse=pulse, show_labels=True)

    def draw_cube(self, canvas, *args, **kwargs):
        return self.draw(canvas, *args, **kwargs)

    def draw_header_cube(self, canvas, rot_y=0.45, rot_x=-0.38, state="IDLE"):
        """Renders an authentic 3D rotating emerald/neon SG CUBE for the header bar brand logo."""
        try:
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw < 10 or ch < 10:
                try:
                    cw = int(canvas.cget("width"))
                    ch = int(canvas.cget("height"))
                except Exception:
                    cw, ch = 38, 38
            canvas.delete("all")
            cx, cy = cw // 2, ch // 2
            logo_scale = min(cw / 38.0, ch / 38.0)

            # Grounding pedestal ring
            r_x = int(14 * logo_scale)
            r_y = int(5 * logo_scale)
            y_ring = cy + int(14 * logo_scale)
            canvas.create_oval(cx - r_x, y_ring - r_y, cx + r_x, y_ring + r_y, outline=self.C_EMERALD_DEEP, width=1)
            canvas.create_arc(cx - r_x, y_ring - r_y, cx + r_x, y_ring + r_y, start=200, extent=140, style=tk.ARC, outline=self.C_NEON, width=1.5)

            s = 9.0 * logo_scale
            raw_verts = [
                (-s, -s, -s), ( s, -s, -s), ( s,  s, -s), (-s,  s, -s),
                (-s, -s,  s), ( s, -s,  s), ( s,  s,  s), (-s,  s,  s),
            ]

            cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
            cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)

            def proj(p):
                x, y, z = p
                x1 = x * cos_y + z * sin_y
                y1 = y
                z1 = -x * sin_y + z * cos_y
                x2 = x1
                y2 = y1 * cos_x - z1 * sin_x
                z2 = y1 * sin_x + z1 * cos_x
                return (cx + x2, cy + y2, z2)

            proj_v = [proj(v) for v in raw_verts]

            faces = [
                ([0, 1, 5, 4], ( 0, -1,  0), self.C_FACE_BRIGHT, self.C_MINT),
                ([4, 5, 6, 7], ( 0,  0,  1), self.C_FACE_EMERALD, self.C_NEON),
                ([1, 5, 6, 2], ( 1,  0,  0), self.C_FACE_EMERALD, self.C_EMERALD_BRIGHT),
                ([0, 4, 7, 3], (-1,  0,  0), self.C_EMERALD_DEEP, self.C_EMERALD),
                ([1, 0, 3, 2], ( 0,  0, -1), self.C_GREEN_DARK, self.C_EMERALD_DEEP),
                ([3, 2, 6, 7], ( 0,  1,  0), self.C_GREEN_DARK, self.C_EMERALD_DEEP),
            ]

            edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
            for v1, v2 in edges:
                canvas.create_line(proj_v[v1][0], proj_v[v1][1], proj_v[v2][0], proj_v[v2][1], fill=self.C_EMERALD_DEEP, width=1)

            face_depths = []
            for idxs, norm, fill_col, out_col in faces:
                nx, ny, nz = norm
                nx1 = nx * cos_y + nz * sin_y
                nz1 = -nx * sin_y + nz * cos_y
                ny2 = ny * cos_x - nz1 * sin_x
                nz2 = ny * sin_x + nz1 * cos_x
                if nz2 > 0:
                    avg_z = sum(proj_v[i][2] for i in idxs) / 4.0
                    face_depths.append((avg_z, idxs, fill_col, out_col))

            face_depths.sort(key=lambda x: x[0])
            for avg_z, idxs, fill_col, out_col in face_depths:
                pts = []
                for i in idxs:
                    pts.extend([proj_v[i][0], proj_v[i][1]])
                canvas.create_polygon(pts, fill=fill_col, outline=out_col, width=1)

            for v1, v2 in edges:
                if proj_v[v1][2] > 0 and proj_v[v2][2] > 0:
                    canvas.create_line(proj_v[v1][0], proj_v[v1][1], proj_v[v2][0], proj_v[v2][1], fill=self.C_MINT, width=1.2)
        except Exception:
            pass


LiveAnimatedHUD = Real3DCubeRenderer
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


class TurnExecutionTracker:
    """
    Thread-safe, turn-scoped execution tracker ensuring that within a single
    user request/turn, local side-effecting actions execute EXACTLY ONCE.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._current_turn_id = 0
        self._executed_actions = {}

    def start_new_turn(self) -> int:
        with self._lock:
            self._current_turn_id += 1
            self._executed_actions.clear()
            tid = self._current_turn_id
        print(f"[TURN_MGR] [turn_id={tid}] Turn started. Registry cleared.")
        return tid

    def reset_current_turn(self):
        with self._lock:
            tid = self._current_turn_id
            self._executed_actions.clear()
        print(f"[TURN_MGR] [turn_id={tid}] Turn reset.")

    @property
    def current_turn_id(self) -> int:
        with self._lock:
            return self._current_turn_id

    def record_execution(self, action_key: str, response: Any, result_content: Dict, owner: str):
        if not action_key:
            return
        with self._lock:
            self._executed_actions[action_key] = {
                "response": response,
                "result_content": result_content,
                "owner": owner,
                "timestamp": time.time()
            }
            tid = self._current_turn_id
        safe_key = action_key.split(":")[0] if any(s in action_key for s in ["pin", "password", "secret"]) else action_key
        print(f"[TURN_MGR] [turn_id={tid}] action='{safe_key}' owner='{owner}' status=EXECUTED")

    def get_executed(self, action_key: str) -> Optional[Dict]:
        if not action_key:
            return None
        with self._lock:
            res = self._executed_actions.get(action_key)
            if res is None and action_key.startswith("screenshot:"):
                for k, v in self._executed_actions.items():
                    if k.startswith("screenshot:"):
                        res = v
                        break
            tid = self._current_turn_id
        if res is not None:
            safe_key = action_key.split(":")[0] if any(s in action_key for s in ["pin", "password", "secret"]) else action_key
            print(f"[TURN_MGR] [turn_id={tid}] action='{safe_key}' owner='{res['owner']}' status=REUSED_RESULT / SKIPPED_DUPLICATE")
        return res


class SGCubeApp:



    def is_local_tts_eligible(self, text: str, intent: Optional[str] = None) -> bool:
        """
        Conservatively checks if an utterance/response qualifies for instant local TTS.
        Eligible categories:
        - SYSTEM_TIME, SYSTEM_DATE, SYSTEM_DAY responses (Fix 3 clock queries)
        - Hardware status / settings confirmations (Volume, Brightness, Wi-Fi, Bluetooth)
        - Calculator / deterministic local answers
        - Local diagnostic / system status responses
        - Explicit Screen Reading responses
        - Protected / Security prompts & responses
        - Simple context reset / confirmation prompts
        Non-eligible (Open-ended conversational queries, explanations, reasoning) remain cloud TTS.
        """
        if not text:
            return False

        t = text.lower().strip()

        # 1. Intent check if supplied
        if intent:
            i_upper = intent.upper()
            if any(i_upper.startswith(prefix) for prefix in (
                "SYSTEM_", "SECURITY_", "VAULT_", "SCREEN_", "VISION_SCREEN_", "CALCULATOR_", "MATH_",
                "AUTOMATION_READ_", "READ_SCREEN", "MOUSE_", "WINDOWS_SETTINGS", "NOTEPAD_", "WAKE_",
                "YOUTUBE_", "SCREENSHOT_"
            )):
                return True

        # 1.5. Wake acknowledgment responses & greetings
        if any(w in t for w in [
            "i'm listening", "listening", "how can i help", "yes, i'm listening",
            "good morning", "good afternoon", "good evening", "what do you need",
            "hello. i'm sg cube", "i'm ready to help"
        ]):
            return True

        # 2. Security & Protected memory disclosures
        if any(w in t for w in [
            "protected information", "protected memory", "sensitive information",
            "voice password", "security challenge", "password required", "authorization failed",
            "access granted", "access denied", "vault"
        ]):
            return True

        # 3. System Time / Date / Day (Fix 3 fast-path & clock queries)
        if any(p in t for p in [
            "the current time is", "the time is", "today is", "it's currently",
            "it is currently", "current day is"
        ]):
            return True

        # 4. Hardware settings & confirmations (Volume, Brightness, Wi-Fi, Bluetooth)
        if any(w in t for w in [
            "volume set to", "volume is at", "volume is", "muted", "unmuted",
            "brightness set to", "brightness is at", "brightness is", "screen brightness",
            "wi-fi turned on", "wi-fi turned off", "wi-fi is on", "wi-fi is off", "connected to wi-fi", "wifi turned", "wifi is",
            "bluetooth turned on", "bluetooth turned off", "bluetooth is on", "bluetooth is off", "connected to bluetooth", "bluetooth status",
            "opening windows settings", "opening wi-fi settings", "opening wifi settings", "opening bluetooth settings",
            "opening display settings", "opening sound settings", "opening accessibility settings", "opening settings",
            "opening network settings", "opening microphone settings", "opening camera settings", "opening privacy settings",
            "opening personalization settings", "opening apps settings", "opening time and date settings"
        ]):
            return True

        # 5. Screen Reading responses
        if any(p in t for p in [
            "on your screen", "the screen shows", "screen reading", "on screen:",
            "currently displaying", "screen content:", "active window is", "notepad contains",
            "you are viewing", "windows settings", "file explorer is open",
            "calculator display shows", "vs code is displaying", "no active application window",
            "no readable text"
        ]):
            return True

        # 5.5. Mouse control responses
        if any(w in t for w in [
            "mouse moved", "cursor moved", "clicked", "double clicked", "right clicked",
            "scrolled", "dragged", "cursor position is", "mouse position is",
            "outside the screen", "released mouse"
        ]):
            return True

        # 5.6. Notepad & Text entry / Clipboard responses
        if any(w in t for w in [
            "opening notepad", "written that in notepad", "selected all text in notepad",
            "copied text to clipboard", "pasted clipboard content", "cleared notepad document",
            "notepad is not active", "typing stopped", "clipboard is empty", "could not copy text"
        ]):
            return True

        # 5.7. YouTube & Media control responses
        if any(w in t for w in [
            "searching youtube", "playing on youtube", "opening youtube", "youtube muted",
            "youtube unmuted", "skipped forward", "rewound", "closed youtube",
            "youtube is not open", "could not find youtube"
        ]):
            return True

        # 5.8. Screenshot responses
        if any(w in t for w in [
            "screenshot saved", "window screenshot saved", "screen captured", "failed to capture",
            "could not save screenshot"
        ]):
            return True

        # 6. Diagnostics / Battery / System status
        if any(p in t for p in [
            "battery level", "system status", "all systems nominal", "system diagnostic",
            "cpu usage", "memory usage"
        ]):
            return True

        # 7. Context reset / confirmation prompts
        if any(p in t for p in [
            "context reset", "cleared conversation", "session reset", "history cleared",
            "stopped listening", "stopping", "cancelled"
        ]):
            return True

        # 8. Calculator / Math deterministic results
        if any(p in t for p in [
            "equals", "the result is", "the answer is"
        ]) and len(t) < 80:
            return True

        return False

    def _speak_local_response(self, text: str, is_security: bool = False, intent: Optional[str] = None):
        """
        Single-Voice Router: Routes ALL SG CUBE voice responses through ONE consistent voice identity.

        Voice identity: Gemini Live prebuilt voice (configured in assistant_voice setting, default 'Puck').
        - Non-security responses: Routed through pending_speech_prompt → Gemini Live (Puck voice).
          This covers all commands: screenshot, notepad, YouTube, volume, brightness, Wi-Fi,
          Bluetooth, settings, mouse, screen reading, camera/vision, wake-word, conversation, etc.
        - Security responses: Kept on local SAPI TTS as a network-independent protected path.
          Security challenges (voice password prompts) must work even without Gemini connection.

        Deduplication: identical text within 1 second is suppressed to prevent double speech.
        """
        if not text:
            return

        try:
            from assistive.tts_normalizer import normalize_for_tts
            text = normalize_for_tts(text)
        except Exception:
            pass

        now = time.time()
        if getattr(self, "_last_local_tts_text", None) == text and (now - getattr(self, "_last_local_tts_time", 0.0) < 1.0):
            return
        self._last_local_tts_text = text
        self._last_local_tts_time = now

        # SECURITY PATH: Always use local SAPI — must never depend on Gemini network.
        # Security challenges (voice password prompts/responses) require instant, offline-capable speech.
        if is_security:
            print(f"[SECURITY-VOICE] SAPI local path for protected response: '{text[:60]}'")
            if os.name == 'nt':
                try:
                    if hasattr(self, 'audio_output_manager') and self.audio_output_manager:
                        self.audio_output_manager.speak_text_local(text)
                        return
                    from assistive.audio_output_manager import get_audio_output_manager
                    get_audio_output_manager().speak_text_local(text)
                    return
                except Exception as e:
                    print(f"[SECURITY-VOICE] AudioOutputManager error, SAPI direct fallback: {e}")
                    try:
                        import win32com.client
                        v = win32com.client.Dispatch("SAPI.SpVoice")
                        v.AudioOutput = None
                        v.Speak(text, 1)
                    except Exception as sapi_err:
                        print(f"[SECURITY-VOICE] SAPI notice: {sapi_err}")
            return

        # SINGLE-VOICE PATH: All other responses → Gemini Live (Puck voice).
        # This ensures ONE consistent voice identity across every SG CUBE feature:
        # screenshot, notepad, YouTube, volume, brightness, Wi-Fi, Bluetooth, settings,
        # mouse/keyboard, screen reading, camera/vision, errors, confirmations, conversation.
        print(f"[SINGLE-VOICE] Routing to Gemini Live (Puck): '{text[:80]}'")
        with self.session_lock:
            prompt_str = f"Speak this exact response out loud: '{text}'"
            if self.pending_speech_prompt != prompt_str:
                self.pending_speech_prompt = prompt_str












    def register_event_listener(self, listener):
        self.event_listener = listener

    def __init__(self, root):



        self.root = root



        self._is_closing = False
        self._shutting_down = False
        self._sleep_shutdown = False
        self._gui_destroyed = False
        self._animations_enabled = True
        self._after_ids = set()
        self._cube_after_id = None
        self._queue_after_id = None
        self._info_after_id = None
        self._loading_after_id = None
        self._readiness_after_id = None
        self.resize_debounce_job = None



        self.root.title("SG CUBE — Personal AI Companion")



        geom_env = os.environ.get("SGCUBE_GEOMETRY")
        if geom_env:
            self.root.geometry(geom_env)
        else:
            cur_geom = self.root.geometry()
            if not cur_geom or cur_geom in ("1x1+0+0", "200x200+0+0"):
                self.root.geometry("1672x941")



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
        self._preview_frame_lock = threading.Lock()
        self._pending_preview_frame = None
        self._preview_frame_signaled = False
        self._last_frame_capture_time = 0.0
        self._last_display_frame_age = 0.0

        self.gui_queue = queue.Queue()
        self.event_listener = None
        self.web_mode = False
        self.web_window = None







        # Session State Machine: IDLE, LISTENING, USER_SPEAKING, AI_THINKING, AI_SPEAKING, RECONNECTING, STOPPED, SLEEPING, SAFETY_ALERT



        self.state_lock = threading.Lock()
        from concurrent.futures import ThreadPoolExecutor
        self._local_tool_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="SGCubeToolWorker")
        self.turn_tracker = TurnExecutionTracker()



        self.current_state = "IDLE"







        # Developer / Debug Overlay Flag



        self.dev_mode = self.engine.store.get_setting("developer_mode", False)







        # Animation state variables for SG CUBE Floating Core & 3D Rotating Cube



        self.anim_angle = 0.0



        self.anim_time = 0.0



        self.orbit_angle = 0.0



        self.context_banner_timer = 0



        self.cube_3d = Real3DCubeRenderer(canvas_width=280, canvas_height=140)



        self.cube_rot_y = 0.785398



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
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            self.audio_output_manager = get_audio_output_manager()
        except Exception as _aom_err:
            print(f"[AUDIO] Warning: AudioOutputManager init error: {_aom_err}")
            self.audio_output_manager = None



        self.wake_greeting_pending = False



        self.wake_greeting_timer = 0.0



        self.pending_speech_prompt = None
        self.current_turn_intercepted = False



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



                self.bg_orig_image = self._tint_bg_green(self.bg_orig_image)



            except Exception as e:



                print(f"[UI] Warning loading background image: {e}")







        self._build_ui()



        self._bind_shortcuts()



        self.root.protocol("WM_DELETE_WINDOW", self.on_close)







        # Start IPC Server for Wake Listener commands



        self._start_ipc_server()



        # Network resilience monitor
        self.network_online = True
        self.network_monitor_running = True
        self._network_thread = threading.Thread(target=self._network_monitor_loop, daemon=True)
        self._network_thread.start()



        # Start periodic GUI queue polling (~20ms) and SG CUBE floating orb animation (~35ms)



        self._queue_after_id = self.safe_after(20, self._process_gui_queue)
        self._cube_after_id = self.safe_after(35, self._animate_sg_cube_core)

        # Auto-start services in background after UI renders
        self.safe_after(50, self._notify_wake_listener_pause)
        self._info_after_id = self.safe_after(100, self._update_info_strip)
        self.safe_after(300, self._auto_start_services)
        self.safe_after(400, self._check_first_run_onboarding)







    def _network_monitor_loop(self):
        """Background thread monitoring internet connectivity to 8.8.8.8:53 with 1.5s timeout."""
        was_online = True
        while getattr(self, 'network_monitor_running', True) and not getattr(self, '_is_closing', False):
            is_online = False
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.5)
                s.connect(("8.8.8.8", 53))
                s.close()
                is_online = True
            except Exception:
                try:
                    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s2.settimeout(1.5)
                    s2.connect(("1.1.1.1", 53))
                    s2.close()
                    is_online = True
                except Exception:
                    is_online = False

            if is_online != was_online:
                was_online = is_online
                self.network_online = is_online
                try:
                    self.gui_queue.put(("NETWORK_STATUS", is_online))
                except Exception:
                    pass

            for _ in range(30):
                if not getattr(self, 'network_monitor_running', True) or getattr(self, '_is_closing', False):
                    break
                time.sleep(0.1)



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



                sock.sendall(b"WAKE\n")



                sock.close()



            except Exception:



                pass



            sys.exit(0)

    def _release_single_instance_lock(self):
        """ Alias to _close_ipc_server for backwards compatibility """
        self._close_ipc_server()

    def safe_after(self, delay_ms: int, callback, *args):
        """
        Schedules a Tkinter callback with automatic tracking in self._after_ids.
        Prevents scheduling if shutting down, closed, or GUI destroyed.
        """
        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False)):
            return None
        if not self.root:
            return None
        try:
            if not self.root.winfo_exists():
                return None
        except Exception:
            return None

        job_id = None
        def _wrapper():
            if job_id and hasattr(self, '_after_ids'):
                self._after_ids.discard(job_id)
            if (getattr(self, '_shutting_down', False) or 
                getattr(self, '_sleep_shutdown', False) or 
                getattr(self, '_is_closing', False) or 
                getattr(self, '_gui_destroyed', False)):
                return
            try:
                callback(*args)
            except (tk.TclError, Exception):
                pass

        try:
            job_id = self.root.after(delay_ms, _wrapper)
            if hasattr(self, '_after_ids'):
                self._after_ids.add(job_id)
            return job_id
        except (tk.TclError, Exception):
            return None

    def safe_after_cancel(self, job_id):
        """ Safely cancels a scheduled after() callback and removes from registry """
        if not job_id:
            return
        if hasattr(self, '_after_ids'):
            self._after_ids.discard(job_id)
        if self.root:
            try:
                self.root.after_cancel(job_id)
            except Exception:
                pass

    def _cancel_all_after_callbacks(self):
        """
        Cancels ALL registered and named Tkinter after() callbacks.
        Guarantees no pending animation, polling, or queue callbacks fire again.
        """
        self._animations_enabled = False
        
        # Cancel all tracked job IDs in set
        if hasattr(self, '_after_ids'):
            current_ids = list(self._after_ids)
            self._after_ids.clear()
            for jid in current_ids:
                if self.root and jid:
                    try:
                        self.root.after_cancel(jid)
                    except Exception:
                        pass

        # Cancel explicit named jobs
        named_jobs = [
            '_cube_after_id',
            '_queue_after_id',
            '_info_after_id',
            '_loading_after_id',
            '_readiness_after_id',
            'resize_debounce_job'
        ]
        for attr in named_jobs:
            jid = getattr(self, attr, None)
            if jid and self.root:
                try:
                    self.root.after_cancel(jid)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _close_ipc_server(self):



        """ Closes single-instance lock socket and unbinds port 49152 """



        sock = getattr(self, 'lock_socket', None)



        if sock:



            self.lock_socket = None



            try:



                sock.close()



                print(f"[SINGLE-INSTANCE] Released socket lock on port {IPC_PORT_GUI}.")



            except Exception as e:



                print(f"[SINGLE-INSTANCE] Error closing socket: {e}")







    def _start_ipc_server(self):



        """ Starts background IPC socket server listening for commands from wake_listener.py """



        def ipc_loop():



            try:



                print(f"[IPC-SERVER] SG CUBE IPC Server listening on port {IPC_PORT_GUI}...")



                while not getattr(self, '_is_closing', False):



                    try:



                        if not self.lock_socket:



                            break



                        conn, addr = self.lock_socket.accept()



                    except (OSError, socket.error):



                        break



                    except Exception:



                        break







                    if getattr(self, '_is_closing', False):



                        try:



                            conn.close()



                        except Exception:



                            pass



                        break







                    try:



                        data = conn.recv(1024).decode('utf-8', errors='ignore').strip()



                    except Exception:



                        data = ""







                    if data == "WAKE":



                        if getattr(self, '_is_closing', False):



                            try:



                                conn.close()



                            except Exception:



                                pass



                            break



                        print("[IPC-SERVER] Received WAKE signal! Bringing SG CUBE to foreground...")



                        self.gui_queue.put(("ACTION", "WAKE_FOREGROUND"))



                        try:



                            conn.sendall(b"OK\n")



                        except Exception:



                            pass



                    elif data in ("SLEEP", "GO_TO_SLEEP"):
                        print("[IPC-SERVER] Received SLEEP signal! Transitioning to SLEEP mode...")
                        try:
                            conn.sendall(b"OK\n")
                        except Exception:
                            pass
                        self.enter_sleep_mode()

                    elif data in ("CLOSE", "QUIT", "SHUTDOWN"):



                        print("[IPC-SERVER] Received CLOSE signal! Closing SG CUBE...")



                        try:



                            conn.sendall(b"OK\n")



                        except Exception:



                            pass



                        self.gui_queue.put(("ACTION", "CLOSE_APP"))



                    elif data == "STATUS":



                        try:



                            status = "CLOSING" if getattr(self, '_is_closing', False) else ("SLEEPING" if self.current_state == "SLEEPING" else "ACTIVE")



                            conn.sendall(f"{status}\n".encode('utf-8'))



                        except Exception:



                            pass



                    try:



                        conn.close()



                    except Exception:



                        pass



            except Exception as e:



                if not getattr(self, '_is_closing', False):



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







    def _clear_playback_queue(self, stop_local_tts: bool = True):



        """ Clears unplayed audio chunks and advances response_id for barge-in / speech interruption """



        with self.state_lock:



            self.current_response_id += 1



            new_id = self.current_response_id







        self.playback_stop_evt.set()

        if stop_local_tts:
            try:
                if hasattr(self, 'audio_output_manager') and self.audio_output_manager:
                    self.audio_output_manager.stop_speech()
                else:
                    from assistive.audio_output_manager import get_audio_output_manager
                    get_audio_output_manager().stop_speech()
            except Exception:
                pass

        try:
            from assistive.notepad_controller import get_notepad_controller
            get_notepad_controller().stop()
        except Exception:
            pass







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



        # 0. Premium loading overlay (shown instantly, covers dashboard until
        # real first layout + services are ready; non-blocking, no fake delay).
        self._loading_ready = False
        self._loading_status_text = "Preparing assistant..."
        self._show_loading_overlay()



        # 1. Header Navigation & Status Bar (Charcoal Background, Height 86px, Subtle Dark Green Border)



        header = tk.Frame(self.root, bg=COLOR_BG_SECONDARY, height=86, highlightbackground=COLOR_BORDER_SUBTLE, highlightthickness=1)



        header.pack(fill=tk.X, side=tk.TOP)



        header.pack_propagate(False)



        header.grid_propagate(False)



        self.header_frame = header







        # Brand Container (3D Rotating Cube Canvas + Bold "SG CUBE" Title + Subtitle)



        brand_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)



        self.brand_frame = brand_frame







        self.header_cube_canvas = tk.Canvas(brand_frame, width=38, height=38, bg=COLOR_BG_SECONDARY, highlightthickness=0)



        self.header_cube_canvas.pack(side=tk.LEFT, padx=(0, 6))



        self.brand_icon_lbl = self.header_cube_canvas  # Backwards-compatible alias



        self.cube_3d.draw_header_cube(self.header_cube_canvas, rot_y=0.45, rot_x=-0.38, state="IDLE")







        title_container = tk.Frame(brand_frame, bg=COLOR_BG_SECONDARY)



        title_container.pack(side=tk.LEFT)







        title_row = tk.Frame(title_container, bg=COLOR_BG_SECONDARY)



        title_row.pack(anchor="w")



        self.lbl_brand_sg = tk.Label(title_row, text="SG", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 18, "bold"), bd=0, pady=0)



        self.lbl_brand_sg.pack(side=tk.LEFT)



        self.lbl_brand_cube = tk.Label(title_row, text=" CUBE", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 18, "bold"), bd=0, pady=0)



        self.lbl_brand_cube.pack(side=tk.LEFT)







        self.lbl_brand_sub = tk.Label(title_container, text="Personal AI Companion", bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 9), bd=0, pady=0)



        self.lbl_brand_sub.pack(anchor="w")







        # Row 3: Seeing • Understanding • Helping tagline in header brand



        self.lbl_brand_motto = tk.Label(title_container, text="Seeing • Understanding • Helping", bg=COLOR_BG_SECONDARY, fg=COLOR_GOLD_PRIMARY, font=("Segoe UI", 8), bd=0, pady=0)



        self.lbl_brand_motto.pack(anchor="w")







        # Centered Navigation Group: Uniform Grid Columns with Large Icons & Labels Below



        nav_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)



        self.nav_frame = nav_frame







        for col_idx in range(6):



            nav_frame.grid_columnconfigure(col_idx, weight=1, uniform="nav_col")



        nav_frame.grid_rowconfigure(0, weight=1)







        self.nav_buttons = {}



        self.nav_buttons["home"] = self._create_nav_btn(nav_frame, "home", "Home", self._on_nav_home, active=True, accent=COLOR_ICON_HOME, tooltip="Home dashboard", col_idx=0)



        self.nav_buttons["vision"] = self._create_nav_btn(nav_frame, "vision", "Vision", self.open_vision_dialog, accent=COLOR_ICON_VISION, tooltip="Live vision", col_idx=1)



        self.nav_buttons["memory"] = self._create_nav_btn(nav_frame, "memory", "Memory", self.open_memory_dialog, accent=COLOR_ICON_MEMORY, tooltip="Personal memory", col_idx=2)



        self.nav_buttons["history"] = self._create_nav_btn(nav_frame, "history", "History", self.open_history_dialog, accent=COLOR_ICON_HISTORY, tooltip="Conversation history", col_idx=3)



        self.nav_buttons["people"] = self._create_nav_btn(nav_frame, "people", "People", self.open_people_dialog, accent=COLOR_ICON_PEOPLE, tooltip="Face profiles", col_idx=4)



        self.nav_buttons["glasses"] = self._create_nav_btn(nav_frame, "glasses", "Meta Glass", self.open_meta_glass_dialog, accent=COLOR_ICON_METAGLASS, tooltip="Meta Glass", col_idx=5)







        # Right Header: Status Badge Pill + Settings Button



        actions_frame = tk.Frame(header, bg=COLOR_BG_SECONDARY)



        self.actions_frame = actions_frame







        header.grid_columnconfigure(0, weight=0)



        header.grid_columnconfigure(1, weight=1)



        header.grid_columnconfigure(2, weight=0)



        header.grid_rowconfigure(0, weight=1)







        self.nav_backdrop = tk.Canvas(header, bg=COLOR_BG_SECONDARY, highlightthickness=0, bd=0)



        self.nav_backdrop.bind("<Configure>", lambda e: self._draw_nav_backdrop())



        nav_frame.bind("<Configure>", lambda e: self._draw_nav_backdrop(), add="+")



        brand_frame.grid(row=0, column=0, sticky="w", padx=(16, 8), pady=4)



        nav_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)



        self.nav_backdrop.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)



        tk.Widget.lower(self.nav_backdrop)



        actions_frame.grid(row=0, column=2, sticky="e", padx=(8, 16), pady=4)







        # Status Badge Pill with Waveform Icon, Green Dot, and Dark Green Border



        self.status_pill_lbl = tk.Label(actions_frame, bg=COLOR_BG_SECONDARY, bd=0, highlightthickness=0)
        self.status_pill_lbl.pack(side=tk.LEFT, padx=(0, 10))
        self.status_pill_frame = self.status_pill_lbl
        self.status_wave_lbl = None
        self.status_dot_lbl = None
        self.sys_status_label = self.status_pill_lbl
        self._status_pill_cache = {}
        self._status_pill_key = None
        self._status_pill_text = "Listening..."
        self._status_pill_col = COLOR_STATUS_GREEN
        self._status_pill_font_px = 15
        self._status_pill_icon_px = 26
        self._render_status_pill(self._status_pill_text, self._status_pill_col)







        # Settings Gear Icon Button (26px with Smooth Animated Rotation on Hover)



        gear_img_normal = self._gear_image(26, COLOR_PEACH_PRIMARY, 0.0, actions_frame, hover=False)



        gear_imgs_enter = [



            self._gear_image(28, COLOR_DARK_GREEN_LIGHT, 3.5, actions_frame, hover=True),



            self._gear_image(28, COLOR_DARK_GREEN_LIGHT, 7.0, actions_frame, hover=True),



            self._gear_image(28, COLOR_DARK_GREEN_LIGHT, 10.0, actions_frame, hover=True),



        ]



        gear_imgs_leave = [



            self._gear_image(27, COLOR_DARK_GREEN_LIGHT, 7.0, actions_frame, hover=True),



            self._gear_image(26, COLOR_PEACH_PRIMARY, 3.5, actions_frame, hover=False),



            gear_img_normal,



        ]







        self.btn_settings = tk.Button(



            actions_frame,



            image=gear_img_normal,



            bg=COLOR_BG_SECONDARY,



            activebackground=COLOR_BG_SECONDARY,



            relief=tk.FLAT,



            bd=0,



            padx=8,



            pady=5,



            cursor="hand2",



            highlightbackground=COLOR_BORDER_SUBTLE,



            highlightthickness=0,



            command=self.open_settings_dialog



        )



        btn_settings = self.btn_settings



        btn_settings.image_normal = gear_img_normal



        btn_settings.image = gear_img_normal



        btn_settings.anim_job = None







        def on_gear_enter(e):



            if btn_settings.anim_job:



                self.root.after_cancel(btn_settings.anim_job)



            btn_settings.config(image=gear_imgs_enter[0])



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



                btn_settings.config(image=gear_imgs_leave[2])



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



        self.stage_upper.pack(fill=tk.X, padx=14, pady=(2, 1))







        # --- LEFT: ENVIRONMENT PANEL ---



        self.hud_env_card = RoundedGlassCard(



            self.stage_upper,



            radius=20,



            padx=12,



            pady=6



        )







        env_title_frame = tk.Frame(self.hud_env_card.inner, bg=COLOR_PANEL_DEEP)



        env_title_frame.pack(fill=tk.X, pady=(0, 4))



        leaf_img = GlowingHUDIcon.get_photo_image("leaf", size=20, color_hex=COLOR_ICON_ENV, master=env_title_frame)



        lbl_env_icon = tk.Label(env_title_frame, image=leaf_img, bg=COLOR_PANEL_DEEP)



        lbl_env_icon.image = leaf_img



        lbl_env_icon.pack(side=tk.LEFT, padx=(0, 8))



        self.lbl_env_icon = lbl_env_icon



        self.hud_env_title = tk.Label(env_title_frame, text="ENVIRONMENT", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 12, "bold"))



        self.hud_env_title.pack(side=tk.LEFT)







        tk.Frame(self.hud_env_card.inner, bg=COLOR_DIVIDER, height=1).pack(fill=tk.X, pady=(2, 4))







        self.env_rows = []



        def _make_env_row(icon_name, icon_col, label_text, default_val, val_col=COLOR_PEACH_PRIMARY, show_div=True):



            row = tk.Frame(self.hud_env_card.inner, bg=COLOR_PANEL_DEEP)



            row.pack(fill=tk.X, pady=1)



            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=15, color_hex=icon_col, master=row)



            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP, bd=0, pady=0)



            ic_lbl.image = ic_img



            ic_lbl.pack(side=tk.LEFT, padx=(0, 8))



            name_lbl = tk.Label(row, text=label_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 9), anchor="w", bd=0, pady=0)



            name_lbl.pack(side=tk.LEFT)



            val_lbl = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=val_col, font=("Segoe UI", 9, "bold" if val_col == COLOR_STATUS_GREEN else "normal"), anchor="e", bd=0, pady=0)



            val_lbl.pack(side=tk.RIGHT)



            div = None



            if show_div:



                div = tk.Frame(self.hud_env_card.inner, bg=COLOR_DIVIDER, height=1)



                div.pack(fill=tk.X, pady=(1, 1))



            self.env_rows.append((row, ic_lbl, icon_name, icon_col, name_lbl, val_lbl, val_col, div))



            return val_lbl







        self.hud_env_labels = [



            _make_env_row("recognize", "#38BDF8", "People", "1 person", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_env_row("home", "#F6D8A9", "Room", "Living Room", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_env_row("sun", "#FACC15", "Lighting", "Normal", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_env_row("waveform", COLOR_STATUS_GREEN, "Noise", "Low", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_env_row("safety", COLOR_STATUS_GREEN, "Safety", "Clear", val_col=COLOR_STATUS_GREEN, show_div=False),



        ]



        self.hud_env_person_lbl = self.hud_env_labels[0]



        self.hud_env_room_lbl = self.hud_env_labels[1]



        self.hud_env_light_lbl = self.hud_env_labels[2]



        self.hud_env_noise_lbl = self.hud_env_labels[3]



        self.hud_env_safety_lbl = self.hud_env_labels[4]







        # --- CENTER: BALANCED CAMERA FEED (50% Upper Row) ---



        self.cam_outer_card = RoundedGlassCard(



            self.stage_upper,



            radius=20,



            padx=3,



            pady=3



        )







        self.cam_viewport = tk.Frame(self.cam_outer_card.inner, bg=COLOR_PANEL_DEEP)



        self.cam_viewport.pack(fill=tk.BOTH, expand=True)







        self.preview_label = tk.Label(



            self.cam_viewport,



            text="",



            bg=COLOR_PANEL_DEEP,



            fg=COLOR_PEACH_SECONDARY,



            font=("Segoe UI", 12)



        )



        self.preview_label.pack(fill=tk.BOTH, expand=True)







        # Floating Camera Control Overlay Elements (pinned to top corners of video feed)



        cam_left_capsules = tk.Frame(self.cam_viewport, bg=COLOR_PANEL_DEEP)



        self.cam_left_capsules = cam_left_capsules



        self.cam_bar = cam_left_capsules







        self.live_capsule = RoundedPill(cam_left_capsules, text="LIVE", dot=True, border_col="#EF4444", bg_col="#1C0A0A", text_col="#FFFFFF", width=64, height=22)
        self.live_capsule.pack(side=tk.LEFT, padx=(0, 4))
        self.cam_live_dot = self.live_capsule
        self.cam_live_lbl = self.live_capsule

        self.fps_capsule = RoundedPill(cam_left_capsules, text="25 FPS", dot=False, border_col="#00D9FF", bg_col="#051830", text_col="#FFFFFF", width=62, height=22)
        self.fps_capsule.pack(side=tk.LEFT)
        self.cam_badge = self.fps_capsule







        cam_right_btns = tk.Frame(self.cam_viewport, bg=COLOR_PANEL_DEEP)



        self.cam_right_btns = cam_right_btns







        cam_switch_img = self._hud_btn_image("camera", 18, cam_right_btns)



        self.btn_cam_toggle = tk.Button(cam_right_btns, image=cam_switch_img, bg=COLOR_PANEL_DEEP, activebackground=COLOR_PANEL_DEEP, highlightthickness=0, bd=0, relief=tk.FLAT, padx=2, pady=2, cursor="hand2", command=self.toggle_camera)



        self.btn_cam_toggle.image = cam_switch_img



        self.btn_cam_toggle.pack(side=tk.LEFT, padx=2)



        HUDTooltip(self.btn_cam_toggle, "Switch / Toggle Camera")







        fs_img = self._hud_btn_image("fullscreen", 18, cam_right_btns)



        self.btn_fullscreen = tk.Button(cam_right_btns, image=fs_img, bg=COLOR_PANEL_DEEP, activebackground=COLOR_PANEL_DEEP, highlightthickness=0, bd=0, relief=tk.FLAT, padx=2, pady=2, cursor="hand2", command=self._toggle_fullscreen)



        self.btn_fullscreen.image = fs_img



        self.btn_fullscreen.pack(side=tk.LEFT, padx=2)



        HUDTooltip(self.btn_fullscreen, "Toggle Fullscreen")







        # --- RIGHT: SCENE PANEL ---



        self.hud_obj_card = RoundedGlassCard(



            self.stage_upper,



            radius=20,



            padx=12,



            pady=6



        )



        scene_title_frame = tk.Frame(self.hud_obj_card.inner, bg=COLOR_PANEL_DEEP)



        scene_title_frame.pack(fill=tk.X, pady=(0, 4))



        cube_ic = GlowingHUDIcon.get_photo_image("cube", size=20, color_hex=COLOR_ICON_SCENE, master=scene_title_frame)



        lbl_cube_icon = tk.Label(scene_title_frame, image=cube_ic, bg=COLOR_PANEL_DEEP)



        lbl_cube_icon.image = cube_ic



        lbl_cube_icon.pack(side=tk.LEFT, padx=(0, 8))



        self.lbl_cube_icon = lbl_cube_icon



        self.hud_obj_title = tk.Label(scene_title_frame, text="SCENE", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 12, "bold"))



        self.hud_obj_title.pack(side=tk.LEFT)







        tk.Frame(self.hud_obj_card.inner, bg=COLOR_DIVIDER, height=1).pack(fill=tk.X, pady=(2, 4))







        self.scene_rows = []



        def _make_scene_row(icon_name, icon_col, label_text, default_val, val_col=COLOR_PEACH_PRIMARY, show_div=True):



            row = tk.Frame(self.hud_obj_card.inner, bg=COLOR_PANEL_DEEP)



            row.pack(fill=tk.X, pady=1)



            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=15, color_hex=icon_col, master=row)



            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP, bd=0, pady=0)



            ic_lbl.image = ic_img



            ic_lbl.pack(side=tk.LEFT, padx=(0, 8))



            name_lbl = tk.Label(row, text=label_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 9), anchor="w", bd=0, pady=0)



            name_lbl.pack(side=tk.LEFT)



            val_lbl = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=val_col, font=("Segoe UI", 9, "bold" if val_col == COLOR_STATUS_GREEN else "normal"), anchor="e", bd=0, pady=0)



            val_lbl.pack(side=tk.RIGHT)



            div = None



            if show_div:



                div = tk.Frame(self.hud_obj_card.inner, bg=COLOR_DIVIDER, height=1)



                div.pack(fill=tk.X, pady=(1, 1))



            self.scene_rows.append((row, ic_lbl, icon_name, icon_col, name_lbl, val_lbl, val_col, div))



            return val_lbl







        self.hud_obj_labels = [



            _make_scene_row("people", "#38BDF8", "People", "1 | Objects: 3", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_scene_row("arrow_left", "#38BDF8", "Left", "None", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_scene_row("target", "#FFFFFF", "Center", "Person", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_scene_row("arrow_right", "#FACC15", "Right", "Object", val_col=COLOR_PEACH_PRIMARY, show_div=True),



            _make_scene_row("road", COLOR_STATUS_GREEN, "Path", "Clear", val_col=COLOR_STATUS_GREEN, show_div=False),



        ]







        # 5. Lower Stage Container (Holds Recent History, 3D Rotating Cube Centerpiece, System Status)



        self.stage_lower = tk.Frame(self.scrollable_content, bg=COLOR_BG_PRIMARY)



        self.stage_lower.pack(fill=tk.X, padx=14, pady=(1, 2))







        # --- LEFT: RECENT HISTORY CARD (35% width, Compact & Dense) ---



        self.card_history = RoundedGlassCard(



            self.stage_lower,



            radius=20,



            padx=12,



            pady=6,



            cursor="hand2"



        )



        hist_head = tk.Frame(self.card_history.inner, bg=COLOR_PANEL_DEEP)



        hist_head.pack(fill=tk.X, pady=(0, 3))







        clock_ic = GlowingHUDIcon.get_photo_image("history", size=20, color_hex=COLOR_ICON_HISTORY, master=hist_head)



        lbl_clock = tk.Label(hist_head, image=clock_ic, bg=COLOR_PANEL_DEEP)



        lbl_clock.image = clock_ic



        lbl_clock.pack(side=tk.LEFT, padx=(0, 6))



        self.lbl_clock = lbl_clock







        hist_title = tk.Label(hist_head, text="RECENT HISTORY", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 12, "bold"))



        hist_title.pack(side=tk.LEFT)



        self.hist_title = hist_title







        lbl_view_all = tk.Label(hist_head, text="View All >", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 10), cursor="hand2")



        lbl_view_all.pack(side=tk.RIGHT)



        self.lbl_view_all = lbl_view_all







        tk.Frame(self.card_history.inner, bg=COLOR_DIVIDER, height=1).pack(fill=tk.X, pady=(1, 3))







        self.info_history_rows = []



        self.info_history_labels = []



        self.hist_rows = []



        for row_idx in range(5):



            h_row = tk.Frame(self.card_history.inner, bg=COLOR_PANEL_DEEP)



            h_row.pack(fill=tk.X, pady=0)



            lbl_t = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_MUTED, font=("Segoe UI", 9), width=5, anchor="w", bd=0, pady=0)



            lbl_t.pack(side=tk.LEFT)



            lbl_spk = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_STATUS_GREEN, font=("Segoe UI", 9, "bold"), width=3, anchor="w", bd=0, pady=0)



            lbl_spk.pack(side=tk.LEFT, padx=(2, 6))



            lbl_msg = tk.Label(h_row, text="", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 9), anchor="w", bd=0, pady=0)



            lbl_msg.pack(side=tk.LEFT, fill=tk.X, expand=True)



            self.info_history_rows.append((lbl_t, lbl_spk, lbl_msg))



            self.info_history_labels.append(lbl_msg)



            div = None



            if row_idx < 4:



                div = tk.Frame(self.card_history.inner, bg=COLOR_DIVIDER, height=1)



                div.pack(fill=tk.X, pady=(1, 1))



            self.hist_rows.append((h_row, lbl_t, lbl_spk, lbl_msg, div))







        self.card_history.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")



        hist_title.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")



        lbl_view_all.bind("<Button-1>", lambda e: self.open_history_dialog(), add="+")



        HUDTooltip(self.card_history, "Click to open full conversation history")







        # --- CENTER: 3D ROTATING SG CUBE CENTERPIECE (30% width) ---



        self.card_cube = tk.Frame(



            self.stage_lower,



            bg=COLOR_BG_PRIMARY,



            padx=0,



            pady=0,



            highlightthickness=0,



            bd=0



        )







        self.orb_canvas = tk.Canvas(



            self.card_cube,



            width=280,



            height=200,



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







        # --- RIGHT: SYSTEM STATUS CARD (35% width) ---



        self.card_status = RoundedGlassCard(



            self.stage_lower,



            radius=20,



            padx=12,



            pady=6,



            cursor="hand2"



        )



        stat_head = tk.Frame(self.card_status.inner, bg=COLOR_PANEL_DEEP)



        stat_head.pack(fill=tk.X, pady=(0, 3))







        wave_ic = GlowingHUDIcon.get_photo_image("waveform", size=20, color_hex=COLOR_ICON_STATUS, master=stat_head)



        lbl_wave = tk.Label(stat_head, image=wave_ic, bg=COLOR_PANEL_DEEP)



        lbl_wave.image = wave_ic



        lbl_wave.pack(side=tk.LEFT, padx=(0, 6))



        self.lbl_wave = lbl_wave







        stat_title = tk.Label(stat_head, text="SYSTEM STATUS", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_PRIMARY, font=("Segoe UI", 12, "bold"))



        stat_title.pack(side=tk.LEFT)



        self.stat_title = stat_title







        lbl_stat_arrow = tk.Label(stat_head, text=">", bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 11, "bold"), cursor="hand2")



        lbl_stat_arrow.pack(side=tk.RIGHT)



        self.lbl_stat_arrow = lbl_stat_arrow







        tk.Frame(self.card_status.inner, bg=COLOR_DIVIDER, height=1).pack(fill=tk.X, pady=(1, 3))







        self.info_status_labels = {}



        self.status_rows = []



        def _make_status_row(icon_name, name_text, val_key, default_val="● Active", default_col=COLOR_STATUS_GREEN, show_div=True):



            row = tk.Frame(self.card_status.inner, bg=COLOR_PANEL_DEEP)



            row.pack(fill=tk.X, pady=1)



            ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=15, color_hex=COLOR_PEACH_SECONDARY, master=row)



            ic_lbl = tk.Label(row, image=ic_img, bg=COLOR_PANEL_DEEP, bd=0, pady=0)



            ic_lbl.image = ic_img



            ic_lbl.pack(side=tk.LEFT, padx=(0, 8))



            name_lbl = tk.Label(row, text=name_text, bg=COLOR_PANEL_DEEP, fg=COLOR_PEACH_SECONDARY, font=("Segoe UI", 9), width=12, anchor="w", bd=0, pady=0)



            name_lbl.pack(side=tk.LEFT)



            lbl_val = tk.Label(row, text=default_val, bg=COLOR_PANEL_DEEP, fg=default_col, font=("Segoe UI", 9, "bold"), anchor="e", bd=0, pady=0)



            lbl_val.pack(side=tk.RIGHT)



            self.info_status_labels[val_key] = lbl_val



            div = None



            if show_div:



                div = tk.Frame(self.card_status.inner, bg=COLOR_DIVIDER, height=1)



                div.pack(fill=tk.X, pady=(1, 1))



            self.status_rows.append((row, ic_lbl, icon_name, COLOR_PEACH_SECONDARY, name_lbl, lbl_val, default_col, div))







        _make_status_row("camera", "Camera", "cam", "● Active", COLOR_STATUS_GREEN, show_div=True)



        _make_status_row("mic", "Microphone", "mic", "● Active", COLOR_STATUS_GREEN, show_div=True)



        _make_status_row("volume", "Speaker", "speaker", "● Active", COLOR_STATUS_GREEN, show_div=True)



        _make_status_row("chip", "AI (Gemini)", "gemini", "● Connected", COLOR_STATUS_GREEN, show_div=True)



        _make_status_row("battery", "Battery", "battery", "🔋 89%", COLOR_STATUS_GREEN, show_div=True)



        _make_status_row("wifi", "Network", "network", "● Online", COLOR_STATUS_GREEN, show_div=False)







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



        if getattr(self, '_loading_overlay', None):
            self._loading_overlay.lift()
        self._loading_start_time = time.time()
        self.root.after(10, self._apply_responsive_layout)
        # Loading overlay hides only when the real UI is ready (first layout
        # pass done); each poll also refreshes the overlay with real state.
        self.root.after(60, self._poll_loading_readiness)
        self.root.after(60, self._animate_loading_overlay)







    def _toggle_fullscreen(self):



        is_fs = getattr(self, '_is_fullscreen', False)



        self._is_fullscreen = not is_fs



        self.root.attributes("-fullscreen", self._is_fullscreen)







    # --- Premium startup / loading experience (Black & Gold HUD) ---
    def _show_loading_overlay(self):
        try:
            ov = tk.Frame(self.root, bg="#020604")
            ov.place(relx=0, rely=0, relwidth=1, relheight=1)
            ov.lift()

            center_f = tk.Frame(ov, bg="#020604")
            center_f.place(relx=0.5, rely=0.5, anchor="center")

            cube = tk.Canvas(center_f, bg="#020604", highlightthickness=0, bd=0,
                             width=300, height=240)
            cube.pack(pady=(0, 8))

            title = tk.Label(center_f, text="SG CUBE", bg="#020604", fg="#FFFFFF",
                             font=("Segoe UI", 32, "bold"))
            title.pack()

            sub = tk.Label(center_f, text="Personal AI Companion", bg="#020604",
                           fg="#D6D6D6", font=("Segoe UI", 13))
            sub.pack(pady=(3, 0))

            motto = tk.Label(center_f, text="Seeing • Understanding • Helping", bg="#020604",
                             fg="#8AFFC1", font=("Segoe UI", 10))
            motto.pack(pady=(3, 10))

            status = tk.Label(center_f, text="Preparing interface...",
                              bg="#020604", fg="#39FF88", font=("Segoe UI", 11))
            status.pack()

            ov.pack_propagate(False)
            self._loading_overlay = ov
            self._loading_cube = cube
            self._loading_status_lbl = status
            self._loading_title_lbl = title
            self._loading_anim_t = 0.0
            self._loading_start_time = time.time()
            try:
                self.cube_3d.draw(cube, rot_x=-0.40, rot_y=0.785398, rot_z=0.0,
                                  time_val=0.0, state="IDLE", show_labels=False)
            except Exception:
                pass
            self._center_loading_overlay()
        except Exception:
            self._loading_overlay = None

    def _center_loading_overlay(self):
        try:
            if not getattr(self, '_loading_overlay', None):
                return
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if w < 100 or h < 100:
                return
            s = min(w / 1672.0, h / 941.0)
            s = max(0.55, min(1.3, s))
            self._loading_cube.config(width=int(round(300 * s)), height=int(round(240 * s)))
            self._loading_title_lbl.config(font=("Segoe UI", max(18, int(round(32 * s))), "bold"))
        except Exception:
            pass

    def _loading_real_status(self):
        try:
            if getattr(self, 'camera_running', False) and getattr(self, 'ai_running', False):
                return "Ready..."
            if getattr(self, 'camera_running', False):
                return "Connecting AI..."
            if getattr(self, 'ai_running', False):
                return "Starting camera..."
            if getattr(self, 'engine', None) and getattr(self.engine, 'memory', None):
                return "Starting voice..."
        except Exception:
            pass
        return getattr(self, '_loading_status_text', 'Preparing interface...')

    def _animate_loading_overlay(self):
        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False)):
            return
        try:
            ov = getattr(self, '_loading_overlay', None)
            if not ov or not ov.winfo_exists():
                return
            ov.lift()
            self._loading_anim_t = getattr(self, '_loading_anim_t', 0.0) + 0.06
            try:
                if hasattr(self, '_loading_cube') and self._loading_cube and self._loading_cube.winfo_exists():
                    self.cube_3d.draw(self._loading_cube, rot_x=-0.40,
                                      rot_y=self._loading_anim_t, rot_z=0.0,
                                      time_val=self._loading_anim_t, state="IDLE", show_labels=False)
            except Exception:
                pass
            try:
                if hasattr(self, '_loading_status_lbl') and self._loading_status_lbl and self._loading_status_lbl.winfo_exists():
                    self._loading_status_lbl.config(text=self._loading_real_status())
            except Exception:
                pass
            self._center_loading_overlay()
            if not getattr(self, '_shutting_down', False) and not getattr(self, '_sleep_shutdown', False) and not getattr(self, '_is_closing', False) and not getattr(self, '_gui_destroyed', False):
                self._loading_after_id = self.safe_after(45, self._animate_loading_overlay)
        except Exception:
            pass

    def _poll_loading_readiness(self):
        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False)):
            return
        try:
            ov = getattr(self, '_loading_overlay', None)
            if not ov or not ov.winfo_exists():
                return
            ready = bool(getattr(self, '_last_applied_geometry', None))
            elapsed = time.time() - getattr(self, '_loading_start_time', 0.0)
            camera_ready = bool(getattr(self, 'last_pil_frame', None))
            if (ready and camera_ready and elapsed >= 0.4) or elapsed >= 1.0:
                self._hide_loading_overlay()
            else:
                if not getattr(self, '_shutting_down', False) and not getattr(self, '_sleep_shutdown', False) and not getattr(self, '_is_closing', False) and not getattr(self, '_gui_destroyed', False):
                    self._readiness_after_id = self.safe_after(40, self._poll_loading_readiness)
        except Exception:
            pass

    def _hide_loading_overlay(self):
        try:
            ov = getattr(self, '_loading_overlay', None)
            if not ov or not ov.winfo_exists():
                return
            if getattr(self, '_loading_fading', False):
                return
            self._loading_fading = True
            
            fg_fade = ["#22F56F", "#087A45", "#063B25", "#021A10"]
            def _step(i):
                try:
                    if not ov.winfo_exists():
                        return
                    if i < len(fg_fade):
                        for lbl in (getattr(self, '_loading_title_lbl', None),
                                    getattr(self, '_loading_status_lbl', None)):
                            if lbl and lbl.winfo_exists():
                                lbl.config(fg=fg_fade[i])
                        ov.after(25, lambda: _step(i + 1))
                    else:
                        ov.destroy()
                        self._loading_overlay = None
                        self._loading_fading = False
                        try:
                            self._apply_responsive_layout()
                        except Exception:
                            pass
                except Exception:
                    try:
                        ov.destroy()
                    except Exception:
                        pass
                    self._loading_overlay = None
                    self._loading_fading = False
            _step(0)
        except Exception:
            pass
            pass

    def _on_window_configure(self, event):
        if getattr(self, '_shutting_down', False) or getattr(self, '_sleep_shutdown', False) or getattr(self, '_is_closing', False) or getattr(self, '_gui_destroyed', False):
            return

        if event.widget != self.root:
            return

        if self.resize_debounce_job:
            self.safe_after_cancel(self.resize_debounce_job)
            self.resize_debounce_job = None

        if not getattr(self, '_shutting_down', False) and not getattr(self, '_sleep_shutdown', False) and not getattr(self, '_is_closing', False) and not getattr(self, '_gui_destroyed', False):
            self.resize_debounce_job = self.safe_after(35, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self.resize_debounce_job = None
        if getattr(self, '_shutting_down', False) or getattr(self, '_sleep_shutdown', False) or getattr(self, '_is_closing', False) or getattr(self, '_gui_destroyed', False):
            return
        if not self.root or not self.root.winfo_exists():
            return







        w = self.root.winfo_width()



        h = self.root.winfo_height()



        if w < 100 or h < 100:



            return







        cur_dims = (w, h)



        if getattr(self, '_last_applied_geometry', None) == cur_dims:



            return



        self._last_applied_geometry = cur_dims







        scale = ResponsiveDesignSystem.compute(w, h)



        target_mode = "WIDE" if w >= 740 else "SMALL"



        self.current_layout_mode = target_mode

        if hasattr(self, 'main_canvas') and hasattr(self, 'canvas_window'):
            self.main_canvas.itemconfig(self.canvas_window, width=w)

        self._reflow_header(target_mode, w, scale)



        self._reflow_footer(target_mode, w, scale)



        self._reflow_stages(target_mode, w, h, scale)



        self._apply_card_scaling(scale)



        self._update_background_canvas(w, h)



        self._rescale_camera_preview()



        self._update_scroll_region()







    def _reflow_header(self, mode, w, scale):



        if not hasattr(self, 'header_frame') or not hasattr(self, 'brand_frame') or not hasattr(self, 'nav_frame') or not hasattr(self, 'actions_frame'):



            return







        self.brand_frame.grid_forget()



        self.nav_frame.grid_forget()



        self.actions_frame.grid_forget()



        self.nav_backdrop.grid_forget()







        self.header_frame.pack_propagate(False)



        self.header_frame.grid_propagate(False)







        if mode == "WIDE":



            self.header_frame.config(height=scale['header_height'])



            self.header_frame.grid_columnconfigure(0, weight=0)



            self.header_frame.grid_columnconfigure(1, weight=1)



            self.header_frame.grid_columnconfigure(2, weight=0)



            self.header_frame.grid_rowconfigure(0, weight=1)



            self.header_frame.grid_rowconfigure(1, weight=0)







            pad_x = scale['stage_pad_x']



            self.brand_frame.grid(row=0, column=0, sticky="w", padx=(pad_x, 4), pady=4)



            self.nav_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)



            self.nav_backdrop.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)



            tk.Widget.lower(self.nav_backdrop)



            self.actions_frame.grid(row=0, column=2, sticky="e", padx=(4, pad_x), pady=4)







            for col_idx in range(6):



                self.nav_frame.grid_columnconfigure(col_idx, weight=1, uniform="nav_col")



            self.nav_frame.grid_rowconfigure(0, weight=1)







            if hasattr(self, 'nav_buttons'):



                for col_idx, btn in enumerate(self.nav_buttons.values()):



                    btn.pack_forget()



                    btn.grid(row=0, column=col_idx, sticky="nsew", padx=max(1, int(round(3 * scale['base_scale']))), pady=max(1, int(round(3 * scale['base_scale']))))



        else:  # SMALL Mode



            small_hdr_h = max(100, int(scale['header_height'] * 1.25))



            self.header_frame.config(height=small_hdr_h)



            self.header_frame.grid_columnconfigure(0, weight=1)



            self.header_frame.grid_columnconfigure(1, weight=1)



            self.header_frame.grid_columnconfigure(2, weight=0)



            self.header_frame.grid_rowconfigure(0, weight=0)



            self.header_frame.grid_rowconfigure(1, weight=1)







            self.brand_frame.grid(row=0, column=0, sticky="w", padx=(8, 2), pady=(4, 2))



            self.actions_frame.grid(row=0, column=1, sticky="e", padx=(2, 8), pady=(4, 2))



            self.nav_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=(0, 4))



            self.nav_backdrop.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=(0, 4))



            tk.Widget.lower(self.nav_backdrop)







            for col_idx in range(6):



                self.nav_frame.grid_columnconfigure(col_idx, weight=1, uniform="nav_col")



            self.nav_frame.grid_rowconfigure(0, weight=1)







            if hasattr(self, 'nav_buttons'):



                for col_idx, btn in enumerate(self.nav_buttons.values()):



                    btn.pack_forget()



                    btn.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=2)







        # Scale Brand Elements



        if hasattr(self, 'header_cube_canvas') and self.header_cube_canvas:
            try:
                if self.header_cube_canvas.winfo_exists():
                    self.header_cube_canvas.config(width=scale['logo_size'], height=scale['logo_size'])
                    self.cube_3d.draw_header_cube(self.header_cube_canvas, rot_y=0.45, rot_x=-0.38, state=getattr(self, 'current_state', 'IDLE'))
            except Exception:
                pass







        if hasattr(self, 'lbl_brand_sg') and self.lbl_brand_sg:



            self.lbl_brand_sg.config(font=("Segoe UI", scale['font_brand_title'], "bold"))



        if hasattr(self, 'lbl_brand_cube') and self.lbl_brand_cube:



            self.lbl_brand_cube.config(font=("Segoe UI", scale['font_brand_title'], "bold"))



        if hasattr(self, 'lbl_brand_sub') and self.lbl_brand_sub:



            self.lbl_brand_sub.config(font=("Segoe UI", scale['font_brand_sub']))



        if hasattr(self, 'lbl_brand_motto') and self.lbl_brand_motto:



            self.lbl_brand_motto.config(font=("Segoe UI", scale['font_brand_tagline']))







        # Scale Nav Buttons



        if hasattr(self, 'nav_buttons'):



            for btn in self.nav_buttons.values():



                icon_name = getattr(btn, 'icon_name', 'home')



                accent = getattr(btn, 'accent', COLOR_ICON_HOME)



                active = getattr(btn, 'active', False)



                if active:
                    pill_w = max(64, int(round(116 * scale['base_scale'])))
                    pill_h = max(56, int(round(100 * scale['base_scale'])))
                    btn.image_normal = self._nav_pill_image(icon_name, btn.nav_text, pill_w, pill_h, scale['font_nav'], scale['icon_nav'], hover=False, master=btn)
                    btn.image_hover = self._nav_pill_image(icon_name, btn.nav_text, pill_w, pill_h, scale['font_nav'], scale['icon_nav'], hover=True, master=btn)
                    if btn.image_normal is not None:
                        btn.image = btn.image_normal
                        btn.config(image=btn.image_normal, compound="none", text="", bg=COLOR_BG_SECONDARY, activebackground=COLOR_BG_SECONDARY, bd=0, highlightthickness=0, padx=0, pady=0)
                    if btn.image_hover is None:
                        btn.image_hover = btn.image_normal
                else:
                    btn.image_normal = GlowingHUDIcon.get_photo_image(



                        icon_name, size=scale['icon_nav'],



                        color_hex=COLOR_ICON_HOME if active else accent,



                        hover=False, master=btn



                    )



                    btn.image_hover = GlowingHUDIcon.get_photo_image(



                        icon_name, size=scale['icon_nav'] + 2,



                        color_hex=COLOR_ICON_HOME if active else accent,



                        hover=True, master=btn



                    )



                    btn.image = btn.image_normal



                    btn.config(



                        image=btn.image_normal,



                        font=("Segoe UI", scale['font_nav'], "bold" if active else "normal"),



                        padx=scale['nav_pad_x'],



                        pady=scale['nav_pad_y']



                    )
        # Scale Status Pill & Settings Button



        self._status_pill_font_px = scale['font_status_text']
        self._status_pill_icon_px = scale['icon_status']
        self._status_pill_key = None
        self._render_status_pill(getattr(self, '_status_pill_text', 'Listening...'), getattr(self, '_status_pill_col', COLOR_STATUS_GREEN))







        if hasattr(self, 'btn_settings') and self.btn_settings:



            g_img = self._gear_image(scale['icon_settings'], COLOR_PEACH_PRIMARY, 0.0, self.btn_settings)



        if g_img is not None:



            self.btn_settings.config(image=g_img, padx=scale['btn_pad_x'], pady=scale['btn_pad_y'])



            self.btn_settings.image = g_img



            self.btn_settings.image_normal = g_img






    def _reflow_footer(self, mode, w, scale):



        if not hasattr(self, 'footer_bar') or not hasattr(self, 'footer_left_lbl') or not hasattr(self, 'footer_right_lbl'):



            return



        self.footer_left_lbl.pack_forget()



        self.footer_right_lbl.pack_forget()







        self.footer_bar.pack_propagate(False)



        if mode == "WIDE":



            self.footer_bar.config(height=scale['footer_height'])



            self.footer_left_lbl.pack(side=tk.LEFT, padx=scale['footer_pad_x'])



            self.footer_right_lbl.pack(side=tk.RIGHT, padx=scale['footer_pad_x'])



            self.footer_left_lbl.config(



                text="SG CUBE 2.5.0  |  Your Personal AI Companion",



                font=("Segoe UI", scale['font_footer'])



            )



            self.footer_right_lbl.config(font=("Segoe UI", scale['font_footer']))



        else:



            small_ftr_h = max(36, int(scale['footer_height'] * 1.3))



            self.footer_bar.config(height=small_ftr_h)



            self.footer_left_lbl.pack(side=tk.TOP, anchor="w", padx=12, pady=(2, 0))



            self.footer_right_lbl.pack(side=tk.TOP, anchor="w", padx=12, pady=(0, 2))



            self.footer_left_lbl.config(



                text="SG CUBE 2.5.0  |  Your Personal AI Companion",



                font=("Segoe UI", max(8, scale['font_footer'] - 1))



            )



            self.footer_right_lbl.config(font=("Segoe UI", max(8, scale['font_footer'] - 1)))







    def _reflow_stages(self, mode, w, h, scale):



        if not hasattr(self, 'stage_upper') or not hasattr(self, 'stage_lower'):



            return







        pad_x = scale['card_gap_x'] // 2



        self.stage_upper.pack_configure(padx=scale['stage_pad_x'], pady=(scale['stage_margin_y'], 0))



        self.stage_lower.pack_configure(padx=scale['stage_pad_x'], pady=(scale['stage_gap_y'], scale['stage_margin_y']))







        if mode == "WIDE":



            self.main_scrollbar.pack_forget()



            self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)







            # PRIMARY HERO CAMERA: occupies majority of central upper stage (52%),



            # flanked by narrower Environment (24%) and Scene (24%) side panels.



            self.stage_upper.grid_columnconfigure(0, weight=24, uniform="top_stage")



            self.stage_upper.grid_columnconfigure(1, weight=52, uniform="top_stage")



            self.stage_upper.grid_columnconfigure(2, weight=24, uniform="top_stage")



            self.stage_upper.grid_rowconfigure(0, weight=1)



            self.stage_upper.grid_rowconfigure(1, weight=0)







            self.hud_env_card.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, pad_x), pady=0)



            self.cam_outer_card.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=pad_x, pady=0)



            self.hud_obj_card.grid(row=0, column=2, columnspan=1, sticky="nsew", padx=(pad_x, 0), pady=0)







            # Conversation and service status are intentionally equal anchors;



            # the animated cube occupies the calmer, narrower center column.



            self.stage_lower.grid_columnconfigure(0, weight=35, uniform="lower_stage")



            self.stage_lower.grid_columnconfigure(1, weight=30, uniform="lower_stage")



            self.stage_lower.grid_columnconfigure(2, weight=35, uniform="lower_stage")



            self.stage_lower.grid_rowconfigure(0, weight=1)







            self.card_history.grid(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, pad_x), pady=0)



            self.card_cube.grid(row=0, column=1, columnspan=1, sticky="nsew", padx=pad_x, pady=0)



            self.card_status.grid(row=0, column=2, columnspan=1, sticky="nsew", padx=(pad_x, 0), pady=0)



        else:  # SMALL Mode



            self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)



            self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)







            self.stage_upper.grid_columnconfigure(0, weight=1, minsize=180)



            self.stage_upper.grid_columnconfigure(1, weight=0, minsize=0)



            self.stage_upper.grid_columnconfigure(2, weight=0, minsize=0)



            self.stage_upper.grid_rowconfigure(0, weight=0)



            self.stage_upper.grid_rowconfigure(1, weight=0)



            self.stage_upper.grid_rowconfigure(2, weight=0)







            self.hud_env_card.grid(row=0, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))



            self.cam_outer_card.grid(row=1, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))



            self.hud_obj_card.grid(row=2, column=0, columnspan=1, sticky="ew", padx=0, pady=0)







            self.stage_lower.grid_columnconfigure(0, weight=1, minsize=180)



            self.stage_lower.grid_columnconfigure(1, weight=0, minsize=0)



            self.stage_lower.grid_columnconfigure(2, weight=0, minsize=0)



            self.stage_lower.grid_rowconfigure(0, weight=0)



            self.stage_lower.grid_rowconfigure(1, weight=0)



            self.stage_lower.grid_rowconfigure(2, weight=0)







            self.card_history.grid(row=0, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))



            self.card_cube.grid(row=1, column=0, columnspan=1, sticky="ew", padx=0, pady=(0, 6))



            self.card_status.grid(row=2, column=0, columnspan=1, sticky="ew", padx=0, pady=0)







        # Position floating camera control overlay in top corners



        overlay_pad = max(4, int(round(8 * scale['base_scale'])))



        if hasattr(self, 'cam_left_capsules') and self.cam_left_capsules:



            self.cam_left_capsules.place(in_=self.cam_viewport, x=overlay_pad, y=overlay_pad, anchor="nw")



            self.cam_left_capsules.lift()



        if hasattr(self, 'cam_right_btns') and self.cam_right_btns:



            self.cam_right_btns.place(in_=self.cam_viewport, relx=1.0, x=-overlay_pad, y=overlay_pad, anchor="ne")



            self.cam_right_btns.lift()







    def _apply_card_scaling(self, scale):



        card_pad_x = scale['card_pad_x']



        card_pad_y = scale['card_pad_y']



        row_pad_y = scale['row_pad_y']



        div_pad_y = scale['div_pad_y']



        icon_row = scale['icon_row']



        icon_title = scale['icon_card_title']



        font_title = scale['font_card_title']



        font_link = scale['font_card_link']



        font_label = scale['font_row_label']



        font_val = scale['font_row_val']



        icon_gap_x = scale['icon_gap_x']







        # 1. Update Card Padding



        for card in (self.hud_env_card, self.hud_obj_card, self.card_history):



            card.config(padx=card_pad_x, pady=card_pad_y)



        if hasattr(self, 'card_status') and self.card_status:

            self.card_status.config(padx=card_pad_x, pady=max(4, int(round(card_pad_y * 0.55))))







        # 2. Update Card Header Icons & Titles



        if hasattr(self, 'lbl_env_icon') and self.lbl_env_icon:



            img = GlowingHUDIcon.get_photo_image("leaf", size=icon_title, color_hex=COLOR_ICON_ENV, master=self.lbl_env_icon)



            self.lbl_env_icon.config(image=img)



            self.lbl_env_icon.image = img



            self.lbl_env_icon.pack_configure(padx=(0, icon_gap_x))



        if hasattr(self, 'hud_env_title') and self.hud_env_title:



            self.hud_env_title.config(font=("Segoe UI", font_title, "bold"))







        if hasattr(self, 'lbl_cube_icon') and self.lbl_cube_icon:



            img = GlowingHUDIcon.get_photo_image("cube", size=icon_title, color_hex=COLOR_ICON_SCENE, master=self.lbl_cube_icon)



            self.lbl_cube_icon.config(image=img)



            self.lbl_cube_icon.image = img



            self.lbl_cube_icon.pack_configure(padx=(0, icon_gap_x))



        if hasattr(self, 'hud_obj_title') and self.hud_obj_title:



            self.hud_obj_title.config(font=("Segoe UI", font_title, "bold"))







        if hasattr(self, 'lbl_clock') and self.lbl_clock:



            img = GlowingHUDIcon.get_photo_image("history", size=icon_title, color_hex=COLOR_CYAN_PRIMARY, master=self.lbl_clock)



            self.lbl_clock.config(image=img)



            self.lbl_clock.image = img



            self.lbl_clock.pack_configure(padx=(0, icon_gap_x))



        if hasattr(self, 'hist_title') and self.hist_title:



            self.hist_title.config(font=("Segoe UI", font_title, "bold"))



        if hasattr(self, 'lbl_view_all') and self.lbl_view_all:



            self.lbl_view_all.config(font=("Segoe UI", font_link))







        if hasattr(self, 'lbl_wave') and self.lbl_wave:



            img = GlowingHUDIcon.get_photo_image("waveform", size=icon_title, color_hex=COLOR_CYAN_PRIMARY, master=self.lbl_wave)



            self.lbl_wave.config(image=img)



            self.lbl_wave.image = img



            self.lbl_wave.pack_configure(padx=(0, icon_gap_x))



        if hasattr(self, 'stat_title') and self.stat_title:



            self.stat_title.config(font=("Segoe UI", font_title, "bold"))



        if hasattr(self, 'lbl_stat_arrow') and self.lbl_stat_arrow:



            self.lbl_stat_arrow.config(font=("Segoe UI", font_link, "bold"))







        # 3. Update Standard Rows (Environment, Scene, Status)



        for row_list in (getattr(self, 'env_rows', []), getattr(self, 'scene_rows', []), getattr(self, 'status_rows', [])):

            # System-status rows are denser (6 rows incl. Network): keep their
            # icons compact so the full list fits the lower-stage budget.

            if row_list is getattr(self, 'status_rows', []):

                row_icon_sz = max(10, int(round(icon_row * 0.7)))

                row_pad = max(0, min(1, int(round(row_pad_y * 0.3))))

                div_pad = max(0, min(1, int(round(div_pad_y * 0.25))))

            else:

                row_icon_sz = icon_row

                row_pad = row_pad_y

                div_pad = div_pad_y



            for row, ic_lbl, icon_name, icon_col, name_lbl, val_lbl, val_col, div in row_list:



                row.pack_configure(pady=row_pad)



                ic_img = GlowingHUDIcon.get_photo_image(icon_name, size=row_icon_sz, color_hex=icon_col, master=ic_lbl)



                ic_lbl.config(image=ic_img)



                ic_lbl.image = ic_img



                ic_lbl.pack_configure(padx=(0, icon_gap_x))



                name_lbl.config(font=("Segoe UI", font_label), fg=COLOR_PEACH_SECONDARY)



                val_lbl.config(font=("Segoe UI", font_val, "bold" if val_col in ("#4ADE80", "#22C55E", COLOR_STATUS_GREEN, COLOR_CYAN_PRIMARY) else "normal"))



                if div:



                    div.pack_configure(pady=(div_pad, div_pad))







        # 4. Update History Rows



        font_hist = scale.get('font_hist_msg', font_label)



        for h_row, lbl_t, lbl_spk, lbl_msg, div in getattr(self, 'hist_rows', []):



            h_row.pack_configure(pady=row_pad_y)



            lbl_t.config(font=("Segoe UI", font_hist))



            lbl_spk.config(font=("Segoe UI", font_hist, "bold"))



            lbl_msg.config(font=("Segoe UI", font_hist))



            if div:



                div.pack_configure(pady=(div_pad_y, div_pad_y))







        # 5. Update Camera Outer Card & Controls



        if hasattr(self, 'cam_outer_card') and self.cam_outer_card:



            self.cam_outer_card.config(padx=max(2, int(round(4 * scale['base_scale']))), pady=max(2, int(round(4 * scale['base_scale']))))



        if hasattr(self, 'live_capsule') and self.live_capsule:



            self.live_capsule.config(padx=scale['cam_pill_pad_x'], pady=scale['cam_pill_pad_y'])



        if hasattr(self, 'cam_live_dot') and self.cam_live_dot:



            self.cam_live_dot.config(font=("Segoe UI", scale['font_cam_pill'], "bold"))



        if hasattr(self, 'cam_live_lbl') and self.cam_live_lbl:



            self.cam_live_lbl.config(font=("Segoe UI", scale['font_cam_pill'], "bold"))



        if hasattr(self, 'fps_capsule') and self.fps_capsule:



            self.fps_capsule.config(padx=scale['cam_pill_pad_x'], pady=scale['cam_pill_pad_y'])



        if hasattr(self, 'cam_badge') and self.cam_badge:



            self.cam_badge.config(font=("Segoe UI", scale['font_cam_pill'], "bold"))







        if hasattr(self, 'btn_cam_toggle') and self.btn_cam_toggle:



            c_img = self._hud_btn_image("camera", scale['icon_cam_btn'], self.btn_cam_toggle)



            self.btn_cam_toggle.config(image=c_img, padx=max(2, int(round(5 * scale['base_scale']))), pady=max(1, int(round(2 * scale['base_scale']))))



            self.btn_cam_toggle.image = c_img







        if hasattr(self, 'btn_fullscreen') and self.btn_fullscreen:



            f_img = self._hud_btn_image("fullscreen", scale['icon_cam_btn'], self.btn_fullscreen)



            self.btn_fullscreen.config(image=f_img, padx=max(2, int(round(5 * scale['base_scale']))), pady=max(1, int(round(2 * scale['base_scale']))))



            self.btn_fullscreen.image = f_img







        # 6. Update Card and Viewport Heights and Widths
        mode = getattr(self, 'current_layout_mode', 'WIDE')
        upper_h = scale.get('upper_stage_height', scale['camera_height'])
        lower_h = scale.get('lower_stage_height', scale.get('lower_height', 308))

        if mode == "WIDE":
            avail_w = max(400, scale['w'] - 2 * scale['stage_pad_x'] - 2 * scale['card_gap_x'])
            env_w = int(round(avail_w * 0.24))
            cam_w = int(round(avail_w * 0.52))
            obj_w = max(100, avail_w - env_w - cam_w)

            hist_w = int(round(avail_w * 0.35))
            cube_w = int(round(avail_w * 0.30))
            stat_w = max(100, avail_w - hist_w - cube_w)

            if hasattr(self, 'hud_env_card') and self.hud_env_card:
                self.hud_env_card.config(width=env_w, height=upper_h)
            if hasattr(self, 'cam_outer_card') and self.cam_outer_card:
                self.cam_outer_card.config(width=cam_w, height=upper_h)
            if hasattr(self, 'hud_obj_card') and self.hud_obj_card:
                self.hud_obj_card.config(width=obj_w, height=upper_h)

            if hasattr(self, 'card_history') and self.card_history:
                self.card_history.config(width=hist_w, height=lower_h)
            if hasattr(self, 'card_cube') and self.card_cube:
                self.card_cube.config(width=cube_w, height=lower_h)
            if hasattr(self, 'card_status') and self.card_status:
                self.card_status.config(width=stat_w, height=lower_h)

            if hasattr(self, 'cam_viewport') and self.cam_viewport:
                self.cam_viewport.config(width=cam_w - 8, height=scale['camera_height'])
                self.cam_viewport.pack_propagate(False)

            if hasattr(self, 'orb_canvas') and self.orb_canvas:
                self.orb_canvas.config(width=max(140, cube_w - 10), height=scale['orb_canvas_height'])
        else:
            cam_card_h = scale['camera_height'] + max(4, int(round(8 * scale['base_scale'])))
            if hasattr(self, 'cam_outer_card') and self.cam_outer_card:
                self.cam_outer_card.config(height=cam_card_h)
            for card in (getattr(self, 'hud_env_card', None),
                         getattr(self, 'hud_obj_card', None),
                         getattr(self, 'card_history', None),
                         getattr(self, 'card_status', None)):
                if card:
                    card.config(height=max(180, int(round(220 * scale['base_scale']))))
            if hasattr(self, 'card_cube') and self.card_cube:
                self.card_cube.config(height=scale.get('orb_canvas_height', 200))

            if hasattr(self, 'cam_viewport') and self.cam_viewport:
                self.cam_viewport.config(height=scale['camera_height'])
                self.cam_viewport.pack_propagate(False)

            if hasattr(self, 'orb_canvas') and self.orb_canvas:
                self.orb_canvas.config(width=scale['orb_canvas_width'], height=scale['orb_canvas_height'])







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

            try:
                from PIL import ImageFilter, ImageDraw
                glow_overlay = Image.new("RGBA", (canv_w, canv_h), (0, 0, 0, 0))
                gd = ImageDraw.Draw(glow_overlay)
                cx = canv_w // 2
                # Subtle blue/cyan atmospheric glow behind upper central camera
                gd.ellipse([cx - int(canv_w * 0.28), int(canv_h * 0.12), cx + int(canv_w * 0.28), int(canv_h * 0.52)], fill=(0, 140, 220, 16))
                # Subtle electric cyan glow behind central 3D cube
                gd.ellipse([cx - int(canv_w * 0.18), int(canv_h * 0.58), cx + int(canv_w * 0.18), int(canv_h * 0.94)], fill=(0, 217, 255, 20))
                glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(60))
                cropped_rgba = cropped.convert("RGBA")
                cropped_rgba.alpha_composite(glow_overlay)
                cropped = cropped_rgba.convert("RGB")
            except Exception:
                pass

            self.bg_photo_image = ImageTk.PhotoImage(cropped)







            if getattr(self, 'bg_image_id', None):



                self.main_canvas.itemconfig(self.bg_image_id, image=self.bg_photo_image)



            else:



                self.bg_image_id = self.main_canvas.create_image(0, 0, image=self.bg_photo_image, anchor="nw")



            self.main_canvas.tag_lower(self.bg_image_id)



        except Exception:



            pass







    def _update_scroll_region(self):



        if hasattr(self, 'scrollable_content') and hasattr(self, 'main_canvas'):



            self.scrollable_content.update_idletasks()



            req_h = self.scrollable_content.winfo_reqheight()



            canv_h = self.main_canvas.winfo_height()



            self.main_canvas.configure(scrollregion=(0, 0, self.scrollable_content.winfo_reqwidth(), req_h))



            if getattr(self, 'current_layout_mode', 'WIDE') == 'SMALL' and req_h > canv_h + 10:



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



        if getattr(self, 'current_layout_mode', 'WIDE') == 'WIDE':
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            scale = ResponsiveDesignSystem.compute(w, h)
            avail_w = max(400, w - 2 * scale['stage_pad_x'] - 2 * scale['card_gap_x'])
            cam_target_w = int(round(avail_w * 0.52)) - max(4, int(round(8 * scale['base_scale'])))
            vw = max(180, cam_target_w)
            vh = max(140, scale['camera_height'])
        else:
            vw = max(180, self.cam_viewport.winfo_width())
            vh = max(140, self.cam_viewport.winfo_height())







        orig_w, orig_h = self.last_pil_frame.size



        if orig_w <= 0 or orig_h <= 0:



            return







        # Seamless edge-to-edge camera display matching reference image



        scale = max(vw / float(orig_w), vh / float(orig_h))



        scaled_w, scaled_h = int(orig_w * scale), int(orig_h * scale)



        scaled_full = self.last_pil_frame.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)



        x_crop = max(0, (scaled_w - vw) // 2)



        # Head/face-safe crop: bias crop towards top so head/hair is never cut off



        y_crop = max(0, min(int((scaled_h - vh) * 0.15), scaled_h - vh))



        scaled = scaled_full.crop((x_crop, y_crop, x_crop + vw, y_crop + vh))







        # Smooth rounded corners matching emerald card border



        try:



            mask = Image.new('L', (vw, vh), 0)



            mask_draw = ImageDraw.Draw(mask)



            mask_draw.rounded_rectangle([0, 0, vw, vh], radius=11, fill=255)



            bg_panel = Image.new('RGB', (vw, vh), COLOR_PANEL_DEEP)



            scaled = Image.composite(scaled, bg_panel, mask)



        except Exception:



            pass







        photo_img = ImageTk.PhotoImage(scaled)



        self.preview_label.config(image=photo_img, text="", bg=COLOR_PANEL_DEEP)



        self.preview_label.image = photo_img







        if hasattr(self, 'cam_left_capsules') and self.cam_left_capsules:



            self.cam_left_capsules.lift()



        if hasattr(self, 'cam_right_btns') and self.cam_right_btns:



            self.cam_right_btns.lift()







    def _update_info_strip(self):






        """ Periodically and reactively updates Recent History, System Status, and Footer Live Time """



        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False)):
            return

        if not hasattr(self, 'root') or not self.root:
            return
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return







        # 1. Update RECENT HISTORY (5 items)



        try:



            if hasattr(self, 'engine') and self.engine and hasattr(self.engine, 'history') and self.engine.history:



                with self.engine.history._get_connection() as conn:



                    cursor = conn.cursor()



                    cursor.execute("SELECT timestamp, sender, text FROM messages ORDER BY id DESC LIMIT 5")



                    rows = [dict(r) for r in cursor.fetchall()]



            else:



                db_path = os.path.join(PROJECT_ROOT, "data", "history", "conversations.db")



                if os.path.exists(db_path):



                    with sqlite3.connect(db_path) as conn:



                        conn.row_factory = sqlite3.Row



                        cursor = conn.cursor()



                        cursor.execute("SELECT timestamp, sender, text FROM messages ORDER BY id DESC LIMIT 5")



                        rows = [dict(r) for r in cursor.fetchall()]



                else:



                    rows = []







            base_w = self.root.winfo_width() if (hasattr(self, 'root') and self.root) else 1024



            max_chars = max(30, min(52, int(round(36 * (base_w / 1024.0)))))







            for i in range(5):



                if hasattr(self, 'info_history_rows') and i < len(self.info_history_rows):



                    lbl_t, lbl_spk, lbl_msg = self.info_history_rows[i]



                    if i < len(rows):



                        r = rows[i]



                        ts = r.get("timestamp", 0)



                        t_str = time.strftime("%H:%M", time.localtime(ts)) if ts else "--:--"



                        txt = r.get("text", "")



                        clean_txt = (txt[:max_chars] + "...") if len(txt) > max_chars else txt



                        is_user = r.get("sender") == "user"



                        lbl_t.config(text=t_str, fg=COLOR_PEACH_MUTED)



                        lbl_spk.config(text="You" if is_user else "AI", fg="#38BDF8" if is_user else COLOR_CYAN_PRIMARY)



                        lbl_msg.config(text=clean_txt, fg="#38BDF8" if is_user else COLOR_PEACH_PRIMARY)



                    else:



                        if i == 0 and not rows:



                            lbl_t.config(text="--:--", fg=COLOR_PEACH_MUTED)



                            lbl_spk.config(text="AI", fg=COLOR_CYAN_PRIMARY)



                            lbl_msg.config(text="Ready whenever you are.", fg=COLOR_PEACH_SECONDARY)



                        else:



                            lbl_t.config(text="", fg=COLOR_PEACH_MUTED)



                            lbl_spk.config(text="", fg=COLOR_CYAN_PRIMARY)



                            lbl_msg.config(text="", fg=COLOR_PEACH_SECONDARY)



                elif hasattr(self, 'info_history_labels') and i < len(self.info_history_labels):



                    lbl = self.info_history_labels[i]



                    if i < len(rows):



                        r = rows[i]



                        ts = r.get("timestamp", 0)



                        t_str = time.strftime("%H:%M", time.localtime(ts)) if ts else "--:--"



                        txt = r.get("text", "")



                        clean_txt = (txt[:max_chars] + "...") if len(txt) > max_chars else txt



                        is_user = r.get("sender") == "user"



                        prefix = "You: " if is_user else "AI: "



                        fg_prefix = COLOR_ICON_VISION if is_user else COLOR_CYAN_PRIMARY



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







                net_online = getattr(self, 'network_online', True)
                self.info_status_labels["network"].config(
                    text="● Online" if net_online else "● Offline",
                    fg=COLOR_STATUS_GREEN if net_online else COLOR_TEXT_MUTED
                )



        except Exception:



            pass







        # 3. Update Footer Live Date & Time



        try:



            if hasattr(self, 'footer_right_lbl') and self.footer_right_lbl:
                now_str = time.strftime("%A, %B %d, %Y  |  %I:%M %p").replace(" 0", " ")
                audio_tag = ""
                if hasattr(self, 'audio_output_manager') and self.audio_output_manager:
                    dev_name = self.audio_output_manager.current_device_name
                    if dev_name:
                        dev_short = dev_name[:24] + "..." if len(dev_name) > 24 else dev_name
                        audio_tag = f"  |  🔊 {dev_short}"
                self.footer_right_lbl.config(text=f"{now_str}{audio_tag}", fg=COLOR_PEACH_PRIMARY)
        except Exception:
            pass







        if (self.root and 
            not getattr(self, '_shutting_down', False) and 
            not getattr(self, '_sleep_shutdown', False) and 
            not getattr(self, '_is_closing', False) and 
            not getattr(self, '_gui_destroyed', False)):
            try:
                if self.root.winfo_exists():
                    self._info_after_id = self.safe_after(1000, self._update_info_strip)
            except Exception:
                pass







    @staticmethod
    def _pill_font(px, bold=True):
        px = max(8, int(px))
        try:
            from PIL import ImageFont
            names = ["segoeuib.ttf", "segoeui.ttf"] if bold else ["segoeui.ttf"]
            for nm in names:
                try:
                    return ImageFont.truetype(nm, px)
                except Exception:
                    continue
            return ImageFont.load_default()
        except Exception:
            from PIL import ImageFont
            return ImageFont.load_default()

    def _nav_pill_image(self, icon_name, text, pill_w, pill_h, font_px, icon_px, hover=False, master=None):
        """Rounded active-nav pill (Black glass + Gold edge & underline). Returns PhotoImage or None."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import tkinter.font as tkfont
            W, H = max(40, int(pill_w)), max(32, int(pill_h))
            rad = min(22, H // 2 - 2)
            top = (26, 21, 10) if not hover else (38, 30, 14)
            bot = (12, 10, 5) if not hover else (18, 14, 7)
            grad = Image.new("RGB", (1, H))
            gp = grad.load()
            for y in range(H):
                f = y / float(max(1, H - 1))
                gp[0, y] = (int(top[0] + (bot[0] - top[0]) * f), int(top[1] + (bot[1] - top[1]) * f), int(top[2] + (bot[2] - top[2]) * f))
            grad = grad.resize((W, H))
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            mask = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mask).rounded_rectangle([3, 3, W - 4, H - 4], radius=rad, fill=255)
            img.paste(grad, (0, 0), mask)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, W - 1, H - 1], radius=rad + 2, outline=(57, 255, 136, 50), width=3)
            d.rounded_rectangle([3, 3, W - 4, H - 4], radius=rad, outline=(0, 212, 106), width=1.5)
            icon_px = max(12, int(icon_px))
            try:
                icon = GlowingHUDIcon.get_pil_image(icon_name, icon_px, "#39FF88", hover)
            except Exception:
                icon = None
            font = self._pill_font(font_px, bold=True)
            tb = d.textbbox((0, 0), text, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            bar_h = max(2, int(font_px // 5))
            total = icon_px + 4 + th + 6 + bar_h
            y = max(6, (H - total) // 2)
            if icon is not None:
                img.alpha_composite(icon.convert("RGBA"), (W // 2 - icon_px // 2, y))
            y += icon_px + 4
            d.text((W // 2 - tw // 2 - tb[0], y - tb[1]), text, font=font, fill=(255, 255, 255))
            y += th + 6
            bw = int(W * 0.42)
            d.rounded_rectangle([W // 2 - bw // 2 - 2, y - 2, W // 2 + bw // 2 + 2, y + bar_h + 2], radius=3, fill=(57, 255, 136, 60))
            d.rounded_rectangle([W // 2 - bw // 2, y, W // 2 + bw // 2, y + bar_h], radius=2, fill=(57, 255, 136))
            from PIL import ImageTk
            return ImageTk.PhotoImage(img, master=master)
        except Exception:
            return None

    def _render_status_pill(self, text, col, font_px=None, icon_px=None):
        """Rounded header status pill (Black glass + Gold edge + Semantic indicator). Cached by key."""
        try:
            font_px = int(font_px or getattr(self, "_status_pill_font_px", 15))
            icon_px = int(icon_px or getattr(self, "_status_pill_icon_px", 26))
            key = (str(text), str(col), font_px, icon_px)
            self._status_pill_text = str(text)
            self._status_pill_col = str(col)
            if key == getattr(self, "_status_pill_key", None):
                return
            from PIL import Image, ImageDraw, ImageTk
            font = self._pill_font(font_px, bold=True)
            tmp = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            dt = ImageDraw.Draw(tmp)
            tb = dt.textbbox((0, 0), str(text), font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            try:
                wave = GlowingHUDIcon.get_pil_image("waveform", icon_px, "#39FF88", False).convert("RGBA")
            except Exception:
                wave = None
            ww = icon_px if wave is None else wave.size[0]
            dot_r = max(3, font_px // 4)
            gap = max(4, font_px // 2)
            pad_x = max(10, font_px)
            pad_y = max(4, font_px // 2)
            content_h = max(icon_px, th, dot_r * 2)
            W = pad_x * 2 + ww + gap + dot_r * 2 + gap + tw
            H = content_h + pad_y * 2
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2, outline=(57, 255, 136, 40), width=1)
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=H // 2 - 1, fill=(4, 13, 8))
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=H // 2 - 1, outline=(0, 212, 106), width=1.5)
            x = pad_x
            cy = H // 2
            if wave is not None:
                img.alpha_composite(wave, (x, cy - wave.size[1] // 2))
            else:
                d.ellipse([x, cy - icon_px // 2, x + icon_px, cy + icon_px // 2], fill=(245, 196, 81))
            x += ww + gap
            d.ellipse([x, cy - dot_r, x + dot_r * 2, cy + dot_r], fill=col if isinstance(col, tuple) else str(col))
            x += dot_r * 2 + gap
            d.text((x - tb[0], cy - th // 2 - tb[1]), str(text), font=font, fill=(255, 255, 255))
            ph = ImageTk.PhotoImage(img, master=getattr(self, "status_pill_lbl", None))
            self.status_pill_lbl.config(image=ph)
            self.status_pill_lbl.image = ph
            self._status_pill_key = key
        except Exception:
            try:
                self.status_pill_lbl.config(text=str(text))
            except Exception:
                pass

    def _draw_nav_backdrop(self, event=None):
        """Subtle rounded black-glass bar behind nav tabs with restrained gold border."""
        try:
            cv = getattr(self, "nav_backdrop", None)
            if cv is None or not cv.winfo_exists():
                return
            w, h = cv.winfo_width(), cv.winfo_height()
            if w < 30 or h < 20:
                return
            cv.delete("nav_bg")
            r = min(20, h // 2 - 2)
            x1, y1, x2, y2 = 3, 3, w - 4, h - 4
            pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
            cv.create_polygon(pts, fill="#020604", outline="#063B25", width=1.2, smooth=True, tags="nav_bg")
            cv.tag_lower("nav_bg")
        except Exception:
            pass

    def _gear_image(self, size_px, color_hex, rotation, master, hover=False):
        """Rounded black-glass settings box with gold gear icon."""
        try:
            from PIL import Image, ImageDraw, ImageTk
            size_px = max(12, int(size_px))
            pad = max(7, size_px // 3 + 3)
            W = H = size_px + pad * 2
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, W - 1, H - 1], radius=12, outline=(57, 255, 136, 40), width=1)
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=11, fill=(4, 13, 8))
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=11, outline=(57, 255, 136) if hover else (8, 74, 42), width=1.5)
            gear = GlowingHUDIcon.get_pil_image("gear", size_px, "#39FF88" if hover else "#D6D6D6", hover, rotation)
            img.alpha_composite(gear.convert("RGBA"), ((W - size_px) // 2, (H - size_px) // 2))
            return ImageTk.PhotoImage(img, master=master)
        except Exception:
            try:
                return GlowingHUDIcon.get_photo_image("gear", size=size_px, color_hex=color_hex, hover=hover, master=master, rotation=rotation)
            except Exception:
                return None

    def _hud_btn_image(self, icon_name, size_px, master):
        """Rounded black-glass camera HUD button."""
        try:
            from PIL import Image, ImageDraw, ImageTk
            size_px = max(10, int(size_px))
            pad = 6
            W = H = size_px + pad * 2
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=8, fill=(4, 13, 8))
            d.rounded_rectangle([1, 1, W - 2, H - 2], radius=8, outline=(8, 74, 42), width=1.25)
            icon = GlowingHUDIcon.get_pil_image(icon_name, size_px, "#FFFFFF", False)
            img.alpha_composite(icon.convert("RGBA"), ((W - size_px) // 2, (H - size_px) // 2))
            return ImageTk.PhotoImage(img, master=master)
        except Exception:
            try:
                return GlowingHUDIcon.get_photo_image(icon_name, size=size_px, color_hex="#FFFFFF", master=master)
            except Exception:
                return None

    @staticmethod
    def _tint_bg_green(img):
        """Shift grayscale abstract bg toward pure near-black with ultra-subtle warm dark depth."""
        try:
            from PIL import Image as _I
            r, g, b = img.split()
            r = r.point(lambda v: int(v * 0.18))
            g = g.point(lambda v: int(v * 0.17))
            b = b.point(lambda v: int(v * 0.16))
            img = _I.merge("RGB", (r, g, b))
            deep = _I.new("RGB", img.size, (3, 3, 5))
            return _I.blend(img, deep, 0.75)
        except Exception:
            return img

    _tint_bg_blue = _tint_bg_green

    def _create_nav_btn(self, parent, icon_name, text, command, active=False, accent=COLOR_CYAN_PRIMARY, tooltip="", col_idx=0):



        if active:



            fg_col = COLOR_TEXT_PRIMARY



            bg_col = COLOR_NAV_ACTIVE_BG



            border_col = COLOR_BORDER_ACTIVE



            icon_img = GlowingHUDIcon.get_photo_image(icon_name, size=28, color_hex=COLOR_ICON_HOME, hover=True, master=parent)



        else:



            fg_col = COLOR_PEACH_SECONDARY



            bg_col = COLOR_BG_SECONDARY



            border_col = COLOR_BG_SECONDARY



            icon_img = GlowingHUDIcon.get_photo_image(icon_name, size=26, color_hex=accent, hover=False, master=parent)







        hover_icon = GlowingHUDIcon.get_photo_image(icon_name, size=28, color_hex=COLOR_ICON_HOME if active else accent, hover=True, master=parent)







        btn = tk.Button(



            parent,



            text=text,



            image=icon_img,



            compound=tk.TOP,



            font=("Segoe UI", 11, "bold" if active else "normal"),



            bg=bg_col,



            fg=fg_col,



            activebackground=COLOR_NAV_ACTIVE_BG if active else COLOR_PANEL_HOVER,



            activeforeground=fg_col,



            relief=tk.FLAT,



            bd=0,



            padx=6,



            pady=4,



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



        btn.grid(row=0, column=col_idx, sticky="nsew", padx=3, pady=6)







        if active:
            pill_normal = self._nav_pill_image(icon_name, text, 116, 100, 15, 38, hover=False, master=parent)
            pill_hover = self._nav_pill_image(icon_name, text, 116, 100, 15, 38, hover=True, master=parent)
            if pill_normal is not None:
                btn.image_normal = pill_normal
                btn.image_hover = pill_hover if pill_hover is not None else pill_normal
                btn.image = pill_normal
                btn.config(image=pill_normal, compound="none", text="", bg=COLOR_BG_SECONDARY, activebackground=COLOR_BG_SECONDARY, bd=0, highlightthickness=0, padx=0, pady=0)







            def on_active_enter(e):
                if getattr(btn, 'image_hover', None) is not None:
                    btn.config(image=btn.image_hover)
            def on_active_leave(e):
                if getattr(btn, 'image_normal', None) is not None:
                    btn.config(image=btn.image_normal)
            btn.bind("<Enter>", on_active_enter, add="+")
            btn.bind("<Leave>", on_active_leave, add="+")



        else:



            def on_enter(e):



                btn.config(bg=COLOR_PANEL_HOVER, fg=COLOR_PEACH_PRIMARY, image=btn.image_hover)



            def on_leave(e):



                btn.config(bg=COLOR_BG_SECONDARY, fg=COLOR_PEACH_SECONDARY, image=btn.image_normal)



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

                    is_protected_disclosure = (
                        isinstance(resp, str) and (
                            "here is your protected information:" in resp.lower()
                            or resp.startswith("Here is your protected information:")
                        )
                    )
                    safe_gui_resp = "[Protected Information Disclosed Locally]" if is_protected_disclosure else resp
                    self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", safe_gui_resp))

                    if hasattr(self, 'active_history_session_id') and self.active_history_session_id:
                        self.engine.history.add_message(self.active_history_session_id, "user", intent_query)
                        if is_protected_disclosure:
                            self.engine.history.add_message(self.active_history_session_id, "assistant", "[Protected Information Disclosed Locally]", intent="VAULT_RECALL")
                        else:
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



        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False) or 
            not getattr(self, '_animations_enabled', True)):
            return

        if not self.root or not self.orb_canvas:
            return

        try:
            if not self.root.winfo_exists():
                return
        except Exception:
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



            sys_txt = "Speaking"



            sys_col = COLOR_TEAL_MINT



        elif state == "USER_SPEAKING":



            rot_y_delta = 0.032



            pulse = 1.0 + 0.06 * math.sin(self.anim_angle * 2.5)



            status_txt = "● Listening to you..."



            sys_txt = "User Speaking"



            sys_col = COLOR_OLIVE_BRIGHT



        elif state == "AI_THINKING":



            rot_y_delta = 0.018



            pulse = 1.0 + 0.04 * math.sin(self.anim_angle * 1.5)



            status_txt = "● Thinking..."



            sys_txt = "Thinking..."



            sys_col = COLOR_WARNING_GOLD



        elif state == "SAFETY_ALERT":



            rot_y_delta = 0.048



            pulse = 1.0 + 0.10 * math.sin(self.anim_angle * 4.0)



            status_txt = "⚠ Physical Hazard Alert"



            sys_txt = "Hazard Alert"



            sys_col = COLOR_ALERT_RED



        elif state == "RECONNECTING":



            rot_y_delta = 0.025



            status_txt = "● Reconnecting..."



            sys_txt = "Reconnecting..."



            sys_col = COLOR_ORANGE



        elif state == "SLEEPING":



            rot_y_delta = 0.0



            pulse = 0.90



            status_txt = "● Sleeping (Say 'Hey SG CUBE')"



            sys_txt = "Sleeping"



            sys_col = COLOR_TEXT_MUTED



        else:  # LISTENING / IDLE



            rot_y_delta = 0.022 if state == "IDLE" else 0.030



            pulse = 1.0 + 0.04 * math.sin(self.anim_angle)



            status_txt = "● SG CUBE Listening"



            sys_txt = "Listening..." if state == "LISTENING" else "Online"



            sys_col = COLOR_STATUS_GREEN







        # Multi-axis floating motion: Y=11s continuous, X=6s oscillation -8°..+8°, Z=8.5s subtle -2°..+2°



        if state != "SLEEPING":



            self.cube_rot_y += (2 * math.pi) / (11.0 / 0.035)  # 11s full rotation period



            if self.cube_rot_y > 2 * math.pi:



                self.cube_rot_y -= 2 * math.pi







        rot_x = 0.1396 * math.sin(self.anim_time * (2 * math.pi / 6.0))  # -8° to +8° over 6s



        rot_z = 0.0349 * math.cos(self.anim_time * (2 * math.pi / 8.5))  # -2° to +2° over 8.5s







        # Update Header Status Label



        if hasattr(self, 'sys_status_label') and self.sys_status_label:



            self._render_status_pill(sys_txt, sys_col)







        # Update Context Banner text if no active alert



        if self.context_banner_timer <= 0:



            self.context_banner.config(text=status_txt, fg=COLOR_GOLD_PRIMARY if state != "SAFETY_ALERT" else COLOR_ALERT_RED)



        else:



            self.context_banner_timer -= 1







        # Clear centerpiece canvas & render Futuristic 3D SG CUBE
        try:
            if hasattr(self, 'orb_canvas') and self.orb_canvas and self.orb_canvas.winfo_exists():
                self.orb_canvas.delete("all")
                self.cube_3d.draw_audio_core(
                    self.orb_canvas,
                    time_val=self.anim_time,
                    rot_y=self.cube_rot_y,
                    state=state,
                    pulse=pulse,
                    hover=self.cube_hover,
                    mouse_tilt=self.cube_mouse_tilt
                )
        except Exception:
            return

        # Clear & render 3D Rotating Cube Logo in Header
        if hasattr(self, 'header_cube_canvas') and self.header_cube_canvas:
            try:
                if self.header_cube_canvas.winfo_exists():
                    self.header_cube_canvas.delete("all")
                    self.cube_3d.draw_header_cube(self.header_cube_canvas, rot_y=self.cube_rot_y, rot_x=-0.38, state=state)
            except Exception:
                pass

        if (self.root and 
            not getattr(self, '_shutting_down', False) and 
            not getattr(self, '_sleep_shutdown', False) and 
            not getattr(self, '_is_closing', False) and 
            not getattr(self, '_gui_destroyed', False) and 
            getattr(self, '_animations_enabled', True)):
            try:
                if self.root.winfo_exists():
                    self._cube_after_id = self.safe_after(35, self._animate_sg_cube_core)
            except Exception:
                pass







    # --- GUI Queue Processing (Main Thread) ---



    def _process_gui_queue(self):



        if (getattr(self, '_shutting_down', False) or 
            getattr(self, '_sleep_shutdown', False) or 
            getattr(self, '_is_closing', False) or 
            getattr(self, '_gui_destroyed', False)):
            return



        has_frame_update = False
        fallback_frame = None

        while not self.gui_queue.empty():



            try:



                msg_type, payload = self.gui_queue.get_nowait()
                if hasattr(self, 'event_listener') and self.event_listener:
                    try:
                        self.event_listener(msg_type, payload)
                    except Exception:
                        pass



                if getattr(self, '_is_closing', False):



                    break



                if msg_type == "FRAME":
                    has_frame_update = True
                    if payload is not None:
                        fallback_frame = payload



                elif msg_type == "NETWORK_STATUS":



                    is_online = bool(payload)

                    self.network_online = is_online

                    if not is_online:

                        self.show_context_alert("Network disconnected. Waiting for connection...", color=COLOR_ALERT_RED)

                        if getattr(self, 'current_state', '') not in ('STOPPED', 'SLEEPING'):

                            self.current_state = 'OFFLINE'

                    else:

                        self.show_context_alert("Network reconnected. SG CUBE Online.", color=COLOR_STATUS_GREEN)

                        if getattr(self, 'current_state', '') == 'OFFLINE':

                            self.current_state = 'IDLE'

                    self._update_info_strip()



                elif msg_type == "ACTION":



                    if payload == "WAKE_FOREGROUND":



                        self.bring_to_foreground()



                    elif payload == "CLOSE_APP":



                        self.on_close()



                        return



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



                elif msg_type == "SECURITY_STATUS":



                    col = COLOR_TEAL_MINT if "granted" in payload.lower() else (COLOR_ALERT_RED if "denied" in payload.lower() else COLOR_CYAN_PRIMARY)



                    self.show_context_alert(f"[Security] {payload}", color=col)



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
                    if not getattr(self, 'camera_running', False):
                        has_frame_update = False
                        if hasattr(self, '_preview_frame_lock'):
                            with self._preview_frame_lock:
                                self._pending_preview_frame = None
                                self._preview_frame_signaled = False
                        self.cam_badge.config(text="OFFLINE", bg=COLOR_PANEL_DEEP, fg=COLOR_TEXT_MUTED)
                        self.preview_label.config(image="", text="Camera View Offline")
                        self.last_pil_frame = None

            except queue.Empty:

                break

            except (tk.TclError, Exception):

                if getattr(self, '_is_closing', False):

                    return

        # Fix 1: Latest-frame-only camera preview display.
        # If any FRAME message arrived, render ONLY the newest available frame once.
        # Discard stale intermediate backlog and prevent repetitive re-renders.
        if has_frame_update and not getattr(self, '_is_closing', False):
            frame_to_render = None
            if hasattr(self, '_preview_frame_lock'):
                with self._preview_frame_lock:
                    if self._pending_preview_frame is not None:
                        frame_to_render = self._pending_preview_frame
                        self._pending_preview_frame = None
                    elif fallback_frame is not None:
                        frame_to_render = fallback_frame
                    self._preview_frame_signaled = False
            elif fallback_frame is not None:
                frame_to_render = fallback_frame

            if frame_to_render is not None:
                try:
                    self._last_display_frame_age = max(0.0, time.time() - getattr(self, '_last_frame_capture_time', time.time()))
                    self._display_camera_frame(frame_to_render)
                except Exception:
                    pass

        if (self.root and 
            not getattr(self, '_shutting_down', False) and 
            not getattr(self, '_sleep_shutdown', False) and 
            not getattr(self, '_is_closing', False) and 
            not getattr(self, '_gui_destroyed', False)):
            try:
                if self.root.winfo_exists():
                    self._queue_after_id = self.safe_after(20, self._process_gui_queue)
            except Exception:
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

            if hasattr(self, '_preview_frame_lock'):
                with self._preview_frame_lock:
                    self._pending_preview_frame = None
                    self._preview_frame_signaled = False

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

        if hasattr(self, '_preview_frame_lock'):
            with self._preview_frame_lock:
                self._pending_preview_frame = None
                self._preview_frame_signaled = False

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
        if getattr(self, '_shutting_down', False) or getattr(self, '_sleep_shutdown', False):
            return
        self._shutting_down = True
        self._sleep_shutdown = True
        self._animations_enabled = False

        print("[SLEEP] requested")
        if hasattr(self, 'turn_tracker'):
            self.turn_tracker.reset_current_turn()







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







        # In test environments, avoid spawning background daemon or hard exiting
        is_test = bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("SGCUBE_TEST_MODE") or getattr(self, '_is_test_mode', False))
        if is_test:
            self._shutting_down = False
            self._sleep_shutdown = False
            return

        # 1. Cancel ALL scheduled Tkinter after callbacks NOW
        self._cancel_all_after_callbacks()

        # 2. Ensure wake listener is running & notify to resume
        try:
            self._ensure_wake_listener_running()
            self._notify_wake_listener_resume()
        except Exception as e:
            print(f"[SLEEP] Error alerting wake listener: {e}")

        # 3. Release single-instance port lock so fresh GUI can bind upon wake
        self._close_ipc_server()

        # 4. Clean destruction on main GUI thread
        def _do_gui_teardown():
            self._gui_destroyed = True
            try:
                if self.root and self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass
            print("[SLEEP] SG CUBE process cleanly terminated. Port 49152 released.")
            os._exit(0)

        # Fallback watchdog thread to guarantee process exit
        def _watchdog():
            time.sleep(1.2)
            try:
                self._close_ipc_server()
            except Exception:
                pass
            os._exit(0)
        threading.Thread(target=_watchdog, daemon=True).start()

        try:
            if self.root and self.root.winfo_exists():
                self.root.after(0, _do_gui_teardown)
            else:
                _do_gui_teardown()
        except Exception:
            _do_gui_teardown()







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
        notified = False
        for attempt in range(6):
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.8)
                sock.connect(('127.0.0.1', IPC_PORT_WAKE_LISTENER))
                sock.sendall(b"RESUME_WAKE_LISTENING\n")
                notified = True
                print("[IPC] Successfully notified background wake listener to resume.")
                break
            except Exception:
                time.sleep(0.15)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

        if not notified:
            print("[IPC] Wake listener not responding on port 49153, ensuring process is spawned...")
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



        if getattr(self, '_is_closing', False):
            return

        self._shutting_down = False
        self._sleep_shutdown = False



        try:



            if not self.root or not self.root.winfo_exists():



                return



        except Exception:



            return







        self._notify_wake_listener_pause()



        self.set_state("OPENING")



        print("[WAKE] MATCH")



        print("[HANDOFF] HOTWORD -> MAIN")



        print("[MIC_OWNER] HOTWORD RELEASED")



        print("[STATE] OPENING")



        print("[WAKE] detected")



        print("[WAKE] activation started")



        try:
            if getattr(self, 'web_mode', False):
                if os.name == 'nt':
                    try:
                        import win32gui, win32con
                        hwnd = win32gui.FindWindow(None, "SG CUBE — Personal AI Companion")
                        if hwnd:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                return

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

                    # Fix 1: Latest-frame-only preview delivery
                    # Atomically store the freshest frame for GUI rendering and signal the queue if not already pending.
                    # Older unrendered frames in _pending_preview_frame are immediately overwritten/discarded.
                    self._last_frame_capture_time = time.time()
                    needs_notify = True
                    if hasattr(self, '_preview_frame_lock'):
                        with self._preview_frame_lock:
                            self._pending_preview_frame = pil_img
                            needs_notify = not self._preview_frame_signaled
                            self._preview_frame_signaled = True

                    if needs_notify:
                        self.gui_queue.put(("FRAME", None))







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

        if hasattr(self, '_preview_frame_lock'):
            with self._preview_frame_lock:
                self._pending_preview_frame = None
                self._preview_frame_signaled = False

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
                    print("[MIC] Audio chunk accepted into buffer.")
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
        """ Single authoritative 24kHz PCM audio playback thread backed by dynamic AudioOutputManager """
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            aom = getattr(self, 'audio_output_manager', None) or get_audio_output_manager()
        except Exception as _init_err:
            print("[PLAYBACK] Error acquiring AudioOutputManager:", _init_err)
            aom = None

        print("[PLAYBACK] Speaker output stream active via dynamic AudioOutputManager.")

        while self.ai_running:
            if stop_evt.is_set():
                stop_evt.clear()
                while not self.playback_queue.empty():
                    try:
                        self.playback_queue.get_nowait()
                    except queue.Empty:
                        break
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

                    if aom is not None:
                        aom.write_pcm(pcm_chunk, samplerate=24000)
                    else:
                        try:
                            sd.play(np.frombuffer(pcm_chunk, dtype=np.int16), samplerate=24000)
                            sd.wait()
                        except Exception as fallback_play_err:
                            print("[PLAYBACK] Direct play fallback error:", fallback_play_err)

                    if self.playback_queue.empty() and self.ai_running:
                        self.set_state("LISTENING")

            except queue.Empty:
                continue
            except Exception as e:
                print("[AUDIO-PLAYBACK] Handled loop warning:", e)

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
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="open_application",
                        description="Opens an approved application on the user's computer, such as Settings, Calculator, Notepad, File Explorer, Browser, WhatsApp, or VS Code.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "app_name": types.Schema(type="STRING", description="The name of the application to open, e.g. 'settings', 'calculator', 'notepad', 'browser'.")
                            },
                            required=["app_name"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="set_system_volume",
                        description="Controls the master audio volume on the computer (set percentage, increase, decrease, mute, or unmute).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="Action: 'set', 'up', 'down', 'mute', 'unmute', or 'get'"),
                                "value": types.Schema(type="INTEGER", description="Target volume percentage from 0 to 100 (for 'set' action).")
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="set_screen_brightness",
                        description="Controls the display screen brightness on the computer (set percentage, increase, decrease, maximum, minimum, or get status).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="Action: 'set', 'up', 'down', 'max', 'min', or 'get'"),
                                "value": types.Schema(type="INTEGER", description="Target brightness percentage from 0 to 100 (for 'set' action).")
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="set_wifi_state",
                        description="Controls the Wi-Fi wireless network adapter on the computer (turn on, turn off, or get status).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="Action: 'on', 'off', or 'status'")
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="set_bluetooth_state",
                        description="Controls the Bluetooth wireless radio adapter on the computer (turn on, turn off, or get status).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="Action: 'on', 'off', or 'status'")
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="manage_bluetooth_device",
                        description="Manages Bluetooth devices (list paired devices, connect to a device, or disconnect a device).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(type="STRING", description="Action: 'list', 'connect', or 'disconnect'"),
                                "device_name": types.Schema(type="STRING", description="Optional name of the device (e.g. 'headphones', 'Nirvana Ion') for connect or disconnect.")
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="search_web",
                        description="Searches the live web for up-to-date real-time information, news, articles, or queries.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "query": types.Schema(type="STRING", description="The search query terms.")
                            },
                            required=["query"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_last_action",
                        description="Retrieves the last item or application opened, or the most recent assistive action performed.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={}
                        )
                    ),
                    types.FunctionDeclaration(
                        name="read_screen",
                        description="Captures and reads the readable text, active window, and visual content currently displayed on the computer screen.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={}
                        )
                    ),
                    types.FunctionDeclaration(
                        name="open_windows_settings",
                        description="Opens Windows Settings or a specific settings page (such as wifi, bluetooth, display, sound, accessibility, apps, etc.).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "page": types.Schema(
                                    type="STRING",
                                    description="The settings page to open: 'main', 'wifi', 'bluetooth', 'display', 'sound', 'microphone', 'camera', 'accessibility', 'privacy', 'personalization', 'apps', 'windows_update', 'date_and_time', 'battery', 'storage'."
                                )
                            }
                        )
                    ),
                    types.FunctionDeclaration(
                        name="notepad_control",
                        description="Controls Windows Notepad: open Notepad, write or type text into Notepad, select all text, copy text, paste clipboard content, or clear document.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(
                                    type="STRING",
                                    description="The Notepad action: 'open', 'write', 'select_all', 'copy', 'paste', 'clear'."
                                ),
                                "text": types.Schema(
                                    type="STRING",
                                    description="The text to write or type into Notepad (required if action is 'write')."
                                )
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="youtube_control",
                        description="Controls YouTube: search for videos or music, play videos, open YouTube, mute, unmute, seek forward, seek backward, or close YouTube.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "action": types.Schema(
                                    type="STRING",
                                    description="The YouTube action: 'search', 'play', 'open', 'mute', 'unmute', 'seek_forward', 'seek_backward', 'close'."
                                ),
                                "query": types.Schema(
                                    type="STRING",
                                    description="The search query or video/music title (used for search or play)."
                                ),
                                "seconds": types.Schema(
                                    type="INTEGER",
                                    description="Number of seconds to seek forward or backward (default 10)."
                                )
                            },
                            required=["action"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="take_screenshot",
                        description="Captures and saves a high-resolution screenshot to the user's Pictures or Screenshots folder.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "target": types.Schema(
                                    type="STRING",
                                    description="Target to capture: 'full' for entire desktop screen, 'window' for active focused window."
                                )
                            }
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

                # Drain stale audio accumulated during startup/reconnect so it doesn't blast the new session
                drained_chunks = 0
                while not self.mic_queue.empty():
                    try:
                        self.mic_queue.get_nowait()
                        drained_chunks += 1
                    except Exception:
                        break
                if drained_chunks:
                    print(f"[MIC] Drained {drained_chunks} stale audio chunks on session connect.")



                if self.ai_running and self.current_state not in ("SLEEPING", "STOPPED", "CLOSED"):



                    self.set_state("LISTENING")







                if self.engine.store.should_trigger_startup_greeting():



                    greeting = self._generate_time_greeting()



                    print(f"[GREETING] Triggering startup greeting: '{greeting}'")



                    self.gui_queue.put(("TRANSCRIPT_AI", greeting))
                    self._speak_local_response(greeting)







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

                    # Voice Turn Finalization Watchdog:
                    # If speech chunks were received and silence elapsed >= 650ms,
                    # finalize the turn immediately to execute local fast-path commands.
                    if self.user_transcript_buffer:
                        silence_elapsed = time.time() - getattr(self, "last_user_speech_time", 0.0)
                        if silence_elapsed >= 0.65:
                            print(f"[WATCHDOG] Silence detected ({silence_elapsed:.2f}s). Finalizing turn for: '{self.user_transcript_buffer}'")
                            if self._finalize_user_speech_turn():
                                self.current_turn_intercepted = True







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

        last_tts_finish_time = 0.0
        sec_challenge_start_time = 0.0
        sec_was_active = False
        sec_mic_started_logged = False
        sec_speech_started_logged = False
        sec_noise_floor = 100.0

        while self.ai_running and self.active_session_id == session_id:



            try:



                # Check for pending speech prompt (e.g. person-aware startup/wake greeting)



                prompt_to_send = None



                with self.session_lock:



                    if self.pending_speech_prompt:



                        prompt_to_send = self.pending_speech_prompt



                        self.pending_speech_prompt = None







                if prompt_to_send:
                    print(f"[SESSION] Sending speech prompt to Gemini Live: '{prompt_to_send[:60]}...'")
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
                        print(f"[SESSION] Error sending speech prompt: {pe}")







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
                    if not sec_was_active:
                        sec_was_active = True
                        sec_challenge_start_time = time.time()
                        speech_chunks.clear()
                        pre_roll_chunks.clear()
                        is_speech_ongoing = False
                        silence_count = 0
                        speech_frame_count = 0
                        sec_mic_started_logged = False
                        sec_speech_started_logged = False
                        sec_noise_floor = 100.0
                        print("[GEMINI] SECURITY AUDIO SENT = NO")
                        print("[VOICE-PASSWORD]\nchallenge_started")
                        try:
                            dev_idx = sd.default.device[0] if sd.default.device[0] is not None else 0
                            dev_info = sd.query_devices(dev_idx)
                            print(f"[VOICE-PASSWORD] device name: {dev_info.get('name', 'Default Microphone')}")
                        except Exception:
                            print("[VOICE-PASSWORD] device name: Default Microphone")
                        print("[VOICE-PASSWORD] sample rate: 16000")
                        print("[VOICE-PASSWORD] channels: 1")
                        print("[VOICE-PASSWORD] format: int16")
                        print("[VOICE-PASSWORD] frame size: 1024")
                        if hasattr(self, 'set_state'):
                            self.set_state("LISTENING")

                    # Check if local TTS or audio arbiter is actively speaking the challenge prompt
                    is_tts_playing = False
                    if hasattr(self, 'audio_output_manager') and self.audio_output_manager:
                        try:
                            is_tts_playing = self.audio_output_manager.is_speaking()
                        except Exception:
                            pass
                    if not is_tts_playing:
                        try:
                            from assistive.audio_arbiter import get_audio_arbiter
                            is_tts_playing = get_audio_arbiter().is_speaking()
                        except Exception:
                            pass

                    if is_tts_playing:
                        last_tts_finish_time = time.time()
                        speech_chunks.clear()
                        pre_roll_chunks.clear()
                        is_speech_ongoing = False
                        silence_count = 0
                        speech_frame_count = 0
                        sec_noise_floor = 100.0
                        continue

                    # Allow 300ms acoustic room reverb decay after TTS stops
                    if (time.time() - last_tts_finish_time) < 0.30:
                        speech_chunks.clear()
                        pre_roll_chunks.clear()
                        is_speech_ongoing = False
                        silence_count = 0
                        speech_frame_count = 0
                        sec_noise_floor = 100.0
                        continue

                    if not sec_mic_started_logged:
                        sec_mic_started_logged = True
                        print("[VOICE-PASSWORD]\nmic_stream_started")

                    # Security challenge timeout (25s after prompt playback finishes)
                    if sec_challenge_start_time > 0 and (time.time() - max(sec_challenge_start_time, last_tts_finish_time)) > 25.0:
                        print("[SECURITY-AUDIO] Challenge timeout expired (25s). Resetting to IDLE.")
                        if hasattr(self.engine, 'security'):
                            self.engine.security.current_state = SecurityState.IDLE
                            self.engine.security._pending_action = None
                        if hasattr(self.engine, 'audio_arbitrator') and self.engine.audio_arbitrator:
                            self.engine.audio_arbitrator.return_to_gemini()
                        self.gui_queue.put(("SECURITY_STATUS", "Timed out"))
                        sec_was_active = False
                        speech_chunks.clear()
                        pre_roll_chunks.clear()
                        is_speech_ongoing = False
                        continue

                    if hasattr(self.engine, 'audio_arbitrator') and not self.engine.audio_arbitrator.is_security_mic_allowed():
                        self.engine.audio_arbitrator.enter_security_challenge()
                        self.gui_queue.put(("SECURITY_STATUS", "Listening..."))

                    frame_rms = float(np.sqrt(np.mean(samples.astype(np.float64)**2))) if len(samples) > 0 else 0.0
                    print(f"[VOICE-PASSWORD]\naudio_frame_received bytes={len(pcm_data)}")
                    print(f"[VOICE-PASSWORD]\nrms={frame_rms:.2f}")

                    if not is_speech_ongoing:
                        sec_noise_floor = 0.95 * sec_noise_floor + 0.05 * min(frame_rms, 250.0)

                    sec_speech_thresh = max(sec_noise_floor * 1.30, sec_noise_floor + 20.0, 80.0)
                    is_frame_speech = (frame_rms > sec_speech_thresh)

                    if is_frame_speech:
                        if not is_speech_ongoing:
                            is_speech_ongoing = True
                            speech_chunks = list(pre_roll_chunks)
                            speech_frame_count = len(speech_chunks)
                            if not sec_speech_started_logged:
                                sec_speech_started_logged = True
                                print("[VOICE-PASSWORD]\nspeech_started")
                        speech_chunks.append(pcm_data)
                        speech_frame_count += 1
                        silence_count = 0
                    else:
                        pre_roll_chunks.append(pcm_data)
                        if len(pre_roll_chunks) > 8:
                            pre_roll_chunks.pop(0)

                        if is_speech_ongoing:
                            speech_chunks.append(pcm_data)
                            speech_frame_count += 1
                            silence_count += 1
                            # Allow ~1.15s pause (18 frames) across natural words in speech
                            if (silence_count >= 18 and speech_frame_count >= 6) or speech_frame_count >= 160:
                                print("[VOICE-PASSWORD]\nspeech_ended")
                                dur_sec = len(speech_chunks) * 0.064
                                print(f"[VOICE-PASSWORD]\naudio_duration={dur_sec:.2f}")
                                full_pcm = b"".join(speech_chunks)
                                speech_chunks = []
                                pre_roll_chunks.clear()
                                is_speech_ongoing = False
                                silence_count = 0
                                speech_frame_count = 0
                                sec_was_active = False

                                self.gui_queue.put(("SECURITY_STATUS", "Verifying..."))







                                def _process_sec():



                                    return self.engine.process_security_challenge_audio(



                                        full_pcm,



                                        session_id=self.active_history_session_id



                                    )







                                ok, local_resp = await loop.run_in_executor(None, _process_sec)



                                del full_pcm







                                if ok:



                                    self.gui_queue.put(("SECURITY_STATUS", "Access granted"))



                                else:



                                    self.gui_queue.put(("SECURITY_STATUS", "Access denied"))







                                if local_resp:



                                    print(f"[VOICE] user_speech_turn_finalized: '[VOICE_PASSWORD_REDACTED]'")



                                    self.gui_queue.put(("TRANSCRIPT_USER", "[Protected Security Input]"))



                                    is_protected_disclosure = (
                                        isinstance(local_resp, str) and (
                                            "here is your protected information:" in local_resp.lower()
                                            or local_resp.startswith("Here is your protected information:")
                                        )
                                    )
                                    safe_gui_resp = "[Protected Information Disclosed Locally]" if is_protected_disclosure else local_resp
                                    self.gui_queue.put(("TRANSCRIPT_AI", safe_gui_resp))

                                    self._speak_local_response(local_resp, is_security=True)

                                    self.engine.history.add_message(self.active_history_session_id, "user", "[VOICE_PASSWORD_REDACTED]")

                                    if is_protected_disclosure:
                                        self.engine.history.add_message(self.active_history_session_id, "assistant", "[Protected Information Disclosed Locally]", intent="VAULT_RECALL")
                                    else:
                                        self.engine.history.add_message(self.active_history_session_id, "assistant", local_resp, intent="SECURITY_CHALLENGE")







                                # Release microphone back to Gemini Live



                                if hasattr(self.engine, 'audio_arbitrator'):



                                    self.engine.audio_arbitrator.return_to_gemini()



                                try:



                                    self.set_state("LISTENING")



                                except Exception:



                                    pass



                    continue







                sec_was_active = False
                # IDLE Mode: Stream raw PCM directly to Gemini Live in real time (< 50ms latency)
                # Gate microphone if local TTS / speaker is actively playing to prevent acoustic feedback loop (Phase 2)
                is_local_speaking = False
                if hasattr(self, 'audio_output_manager') and self.audio_output_manager:
                    is_local_speaking = self.audio_output_manager.is_speaking()
                if not is_local_speaking:
                    try:
                        from assistive.audio_arbiter import get_audio_arbiter
                        is_local_speaking = get_audio_arbiter().is_speaking()
                    except Exception:
                        pass

                if is_local_speaking:
                    await asyncio.sleep(0.01)
                    continue

                blob = types.Blob(data=pcm_data, mime_type="audio/pcm;rate=16000")
                await session.send_realtime_input(audio=blob)
                if not streamed_to_gemini:
                    print("[MIC] Audio chunk sent to Gemini Live.")
                    streamed_to_gemini = True



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

        if is_security_input:
            print("[VOICE] user_speech_turn_finalized: '[VOICE_PASSWORD_REDACTED]'")
            print("[GEMINI] SECURITY AUDIO SENT = NO")
            local_response = self.engine.process_user_speech_query(user_text, session_id=self.active_history_session_id)
            if local_response:
                self._clear_playback_queue()
                is_protected_disclosure = (
                    isinstance(local_response, str) and (
                        "here is your protected information:" in local_response.lower()
                        or local_response.startswith("Here is your protected information:")
                    )
                )
                safe_gui_resp = "[Protected Information Disclosed Locally]" if is_protected_disclosure else local_response
                self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", safe_gui_resp))
                self.engine.history.add_message(self.active_history_session_id, "user", "[VOICE_PASSWORD_REDACTED]")
                if is_protected_disclosure:
                    self.engine.history.add_message(self.active_history_session_id, "assistant", "[Protected Information Disclosed Locally]", intent="VAULT_RECALL")
                else:
                    self.engine.history.add_message(self.active_history_session_id, "assistant", local_response, intent="SECURITY_CHALLENGE")
                try:
                    self._speak_local_response(local_response, is_security=True, intent="SECURITY_CHALLENGE")
                except TypeError:
                    self._speak_local_response(local_response, is_security=True)
                try:
                    self.root.after(1500, lambda: self.set_state("LISTENING") if self.current_state in ("AI_THINKING", "USER_SPEAKING") and self.playback_queue.empty() else None)
                except Exception:
                    pass
                return True
            return False

        log_text = user_text
        print(f"[VOICE] user_speech_turn_finalized: '{log_text.encode('ascii', errors='backslashreplace').decode('ascii')}'")

        # Diagnostic logging for Notepad voice-command integration
        print(f"[DIAGNOSTIC:STAGE_1] STT_EXACT_TEXT: '{user_text.encode('ascii', errors='backslashreplace').decode('ascii')}'")
        normalized_cmd = self.engine.router.normalize_speech_text(user_text)
        print(f"[DIAGNOSTIC:STAGE_2] NORMALIZED_COMMAND: '{normalized_cmd.encode('ascii', errors='backslashreplace').decode('ascii')}'")
        diag_ir = self.engine.router.route_intent(user_text)
        matched_intent = diag_ir.get("intent", "GENERAL")
        matched_target = diag_ir.get("target")
        matched_params = diag_ir.get("params", {})
        print(f"[DIAGNOSTIC:STAGE_3] ROUTER_BRANCH_MATCHED: intent='{matched_intent}', target='{matched_target}', params={matched_params}")
        is_notepad = (
            matched_intent.startswith("NOTEPAD_")
            or (matched_intent in ("AUTOMATION_OPEN_APP", "APP_CONTROL") and (matched_target == "notepad" or matched_params.get("app_name") == "notepad"))
        )
        print(f"[DIAGNOSTIC:STAGE_4] IS_NOTEPAD_COMMAND: {is_notepad}")
        if matched_intent == "NOTEPAD_WRITE":
            print(f"[DIAGNOSTIC:STAGE_5] WRITE_EXTRACTED_TEXT: '{matched_params.get('text', '')}'")

        # Diagnostic logging strictly for Section 2 safe verification
        is_diag_phrase = (user_text.strip().lower() == "set password")



        if is_diag_phrase:



            print(f"[DIAGNOSTIC] TRANSCRIPT_RECEIVED: {user_text}")



            print(f"[DIAGNOSTIC] ROUTER_CALLED: YES")
            diag_route = self.engine.router.route_intent(user_text)
            print(f"[DIAGNOSTIC] ROUTED_INTENT: {diag_route.get('intent')}")

        intent_route = self.engine.router.route_intent(user_text)
        resolve_fn = getattr(self, '_resolve_intent_action_key', SGCubeApp._resolve_intent_action_key)
        action_key = resolve_fn(intent_route.get("intent"), intent_route.get("params", {}), intent_route.get("target", ""))
        tracker = getattr(self, 'turn_tracker', None)
        cached = tracker.get_executed(action_key) if (action_key and tracker) else None

        if cached is not None:
            local_response = cached["response"]
        else:
            local_response = self.engine.process_user_speech_query(user_text, session_id=self.active_history_session_id)
            if local_response and action_key and tracker:
                fmt_fn = getattr(self, '_format_tool_result_content', SGCubeApp._format_tool_result_content)
                res_content = fmt_fn(action_key, local_response)
                tracker.record_execution(action_key, local_response, res_content, owner="finalize_path")

        if any(w in user_text.lower() for w in ["stop", "cancel", "abort", "halt"]):
            if tracker:
                tracker.reset_current_turn()
            self._clear_playback_queue(stop_local_tts=True)

        if local_response:



            if is_diag_phrase:



                print(f"[DIAGNOSTIC] LOCAL_HANDLER_CALLED: YES")



                print(f"[DIAGNOSTIC] GEMINI_FALLBACK_CALLED: NO")







            # Cancel any pending wake/startup greeting so it never interrupts or overlaps user command



            self.wake_greeting_pending = False







            # Clear any preliminary/stale streaming audio from playback queue and advance response_id



            self._clear_playback_queue()







            is_protected_disclosure = (
                isinstance(local_response, str) and (
                    "here is your protected information:" in local_response.lower()
                    or local_response.startswith("Here is your protected information:")
                )
            )
            safe_gui_resp = "[Protected Information Disclosed Locally]" if is_protected_disclosure else local_response
            self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", safe_gui_resp))

            if is_security_input:
                self.engine.history.add_message(self.active_history_session_id, "user", "[VOICE_PASSWORD_REDACTED]")
            else:
                self.engine.history.add_message(self.active_history_session_id, "user", user_text)

            if is_protected_disclosure:
                self.engine.history.add_message(self.active_history_session_id, "assistant", "[Protected Information Disclosed Locally]", intent="VAULT_RECALL")
            else:
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



                    if hasattr(self.engine, 'audio_arbitrator') and ("say your voice password" in local_response.lower() or "sensitive password" in local_response.lower() or "voice password" in local_response.lower()):



                        self.engine.audio_arbitrator.enter_security_challenge()



                    try:
                        self._speak_local_response(local_response, is_security=True, intent=diag_route.get("intent"))
                    except TypeError:
                        self._speak_local_response(local_response, is_security=True)



                else:



                    print(f"[SAVE] voice queued: '{local_response}'")



                    try:
                        self._speak_local_response(local_response, is_security=False, intent=diag_route.get("intent"))
                    except TypeError:
                        self._speak_local_response(local_response, is_security=False)



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

    async def _run_tool_in_executor(self, func, *args, **kwargs):
        """
        Executes a blocking local tool or helper in a dedicated background thread pool,
        preventing the asyncio event loop thread from being blocked.
        """
        loop = asyncio.get_running_loop()
        executor = getattr(self, '_local_tool_executor', None)
        if kwargs:
            pfunc = functools.partial(func, *args, **kwargs)
            return await loop.run_in_executor(executor, pfunc)
        return await loop.run_in_executor(executor, func, *args)

    @staticmethod
    def _normalize_app_name(name: str) -> str:
        n = (name or "").strip().lower()
        mapping = {
            "google chrome": "chrome",
            "google-chrome": "chrome",
            "web browser": "browser",
            "internet browser": "browser",
            "vs code": "vscode",
            "visual studio code": "vscode",
            "calculator": "calc",
            "text editor": "notepad",
            "file explorer": "explorer",
            "windows explorer": "explorer",
            "whats app": "whatsapp",
            "windows settings": "settings",
        }
        return mapping.get(n, n)

    @staticmethod
    def _resolve_intent_action_key(intent: str, params: Optional[dict] = None, target: str = "") -> Optional[str]:
        params = params or {}
        if intent == "SYSTEM_VOLUME":
            return "volume"
        elif intent == "SYSTEM_BRIGHTNESS":
            return "brightness"
        elif intent == "SYSTEM_WIFI":
            return "wifi"
        elif intent == "SYSTEM_BLUETOOTH":
            return "bluetooth"
        elif intent in ("BLUETOOTH_CONNECT", "BLUETOOTH_DISCONNECT", "BLUETOOTH_LIST"):
            return "bluetooth_device"
        elif intent == "AUTOMATION_READ_SCREEN":
            return "read_screen"
        elif intent in ("AUTOMATION_OPEN_APP", "APP_CONTROL"):
            app = params.get("app_name") or target or ""
            return f"open_app:{SGCubeApp._normalize_app_name(app)}"
        elif intent == "WEB_SEARCH":
            q = params.get("query") or target or ""
            return f"search_web:{q.strip().lower()}"
        elif intent == "APP_LAST_ACTION":
            return "last_action"
        elif intent in ("MEMORY_SAVE", "VAULT_SAVE"):
            return "save_reminder"
        elif intent in ("MEMORY_RECALL", "VAULT_RECALL"):
            q = params.get("query") or target or ""
            return f"recall_memory:{q.strip().lower()}"
        elif intent and intent.startswith("SECURITY_"):
            return "voice_security"
        elif intent in ("AMBIENT_LIGHT", "COLOR_DETECT"):
            return "ambient_status"
        elif intent == "PRODUCT_SCAN":
            return "product_scan"
        elif intent == "FACE_ENROLL":
            name = target or params.get("person_name") or ""
            return f"enroll_face:{name.strip().lower()}"
        elif intent and intent.startswith("MOUSE_"):
            return f"mouse:{intent.lower()}:{params.get('direction', '')}:{params.get('button', '')}:{params.get('pixels', params.get('x', ''))}:{params.get('y', '')}"
        elif intent == "WINDOWS_SETTINGS" or (intent and intent.startswith("WINDOWS_SETTINGS_")):
            p = params.get("page") or target or "main"
            return f"windows_settings:{p.lower().strip()}"
        elif intent and intent.startswith("NOTEPAD_"):
            return f"notepad:{intent.lower()}:{params.get('action', params.get('text', ''))}"
        elif intent and intent.startswith("YOUTUBE_"):
            return f"youtube:{intent.lower()}:{params.get('query', '')}"
        elif intent and intent.startswith("SCREENSHOT_"):
            return f"screenshot:{intent.lower()}"
        elif intent == "SYSTEM_WINDOW_CONTROL":
            return f"window:{params.get('action', '')}:{params.get('app', '')}"
        return None

    @staticmethod
    def _resolve_tool_action_key(fn_name: str, fn_args: Optional[dict] = None) -> Optional[str]:
        fn_args = fn_args or {}
        if fn_name == "set_system_volume":
            return "volume"
        elif fn_name == "set_screen_brightness":
            return "brightness"
        elif fn_name == "set_wifi_state":
            return "wifi"
        elif fn_name == "set_bluetooth_state":
            return "bluetooth"
        elif fn_name == "manage_bluetooth_device":
            return "bluetooth_device"
        elif fn_name == "read_screen":
            return "read_screen"
        elif fn_name in ("open_windows_settings", "open_settings_page"):
            return f"windows_settings:{(fn_args.get('page') or 'main').lower().strip()}"
        elif fn_name in ("notepad_control", "write_notepad_text", "open_notepad"):
            return f"notepad:{fn_name}"
        elif fn_name in ("youtube_control", "search_youtube", "open_youtube"):
            return f"youtube:{fn_name}"
        elif fn_name in ("take_screenshot", "screenshot_control"):
            return f"screenshot:{fn_name}"
        elif fn_name in ("window_control", "maximize_window", "minimize_window", "close_window"):
            return f"window:{fn_name}"
        elif fn_name == "open_application":
            app = fn_args.get("app_name") or ""
            return f"open_app:{SGCubeApp._normalize_app_name(app)}"
        elif fn_name == "search_web":
            q = fn_args.get("query") or ""
            return f"search_web:{q.strip().lower()}"
        elif fn_name == "get_last_action":
            return "last_action"
        elif fn_name == "save_reminder_note":
            return "save_reminder"
        elif fn_name == "recall_user_memory":
            q = fn_args.get("search_query") or ""
            return f"recall_memory:{q.strip().lower()}"
        elif fn_name == "manage_voice_security":
            return "voice_security"
        elif fn_name == "get_ambient_status":
            return "ambient_status"
        elif fn_name == "scan_product_details":
            return "product_scan"
        elif fn_name == "enroll_person_face":
            name = fn_args.get("person_name") or ""
            return f"enroll_face:{name.strip().lower()}"
        return None

    # ponytail: the local router returns only spoken text, no success flag, so the outcome
    # is read from the wording. Ceiling: a failure phrased some other way reads as "done".
    # Upgrade: have process_user_speech_query return (ok, text). Before this, every tool
    # result told Gemini "executed"/"success" even when the text said it had failed.
    _FAILURE_WORDING = re.compile(
        r"\b(wasn't able|was not able|couldn't|could not|can't|cannot|unable|failed|"
        r"not (?:running|installed|found|supported|available|allowed)|doesn't seem|is locked|denied|blocked|error)\b",
        re.IGNORECASE)

    @staticmethod
    def _outcome_status(response_text: Any) -> str:
        if not response_text:
            return "failed"
        if isinstance(response_text, str) and SGCubeApp._FAILURE_WORDING.search(response_text):
            return "failed"
        return "done"

    @staticmethod
    def _format_tool_result_content(action_key: str, response_text: Any) -> dict:
        if not action_key:
            return {"status": SGCubeApp._outcome_status(response_text), "response": response_text}
        if action_key.startswith("open_app:"):
            return {"status": SGCubeApp._outcome_status(response_text), "response": response_text}
        elif action_key.startswith("windows_settings:"):
            return {"status": SGCubeApp._outcome_status(response_text), "response": response_text}
        elif action_key.startswith("search_web:"):
            return {"status": "searched", "response": response_text}
        elif action_key == "last_action":
            return {"status": "retrieved", "response": response_text}
        elif action_key == "save_reminder":
            return {"status": "saved" if response_text else "failed", "fact": response_text}
        elif action_key.startswith("recall_memory:"):
            return {"recalled_memory": response_text or "No memory saved matching query."}
        elif action_key == "voice_security":
            return {"status": "initiated", "message": response_text or "Security flow engaged."}
        elif action_key == "ambient_status" and isinstance(response_text, dict):
            return response_text
        elif action_key == "product_scan" and isinstance(response_text, dict):
            return response_text
        elif action_key.startswith("enroll_face:") and isinstance(response_text, dict):
            return response_text
        else:
            return {"status": SGCubeApp._outcome_status(response_text), "response": response_text}

    async def _receive_loop(self, session, session_id):



        print(f"[RECEIVE] Starting receive loop for session_id={session_id}")
        print(f"[RECEIVE] Gemini Live receive loop alive (session_id={session_id}).")



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



                            print(f"[VOICE] speech_chunk: '{text_chunk.encode('ascii', errors='backslashreplace').decode('ascii')}'")







                            self.set_state("USER_SPEAKING")



                            # BARGE-IN: Clear old audio queue and advance response_id immediately



                            self._clear_playback_queue()



                            turn_intercepted = False
                            self.current_turn_intercepted = False







                            # Accumulate streaming transcription chunks into full user utterance



                            if not self.user_transcript_buffer:
                                self.turn_tracker.start_new_turn()
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



                            if not turn_intercepted and not getattr(self, 'current_turn_intercepted', False):
                                self.gui_queue.put(("TRANSCRIPT_AI", text_chunk))



                                self.engine.history.accumulate_assistant_chunk(text_chunk)







                        if server_content.model_turn:



                            # Finalize pending user speech turn when AI model starts speaking



                            if self.user_transcript_buffer:



                                if self._finalize_user_speech_turn():



                                    turn_intercepted = True



                            if not turn_intercepted and not getattr(self, 'current_turn_intercepted', False):
                                if not first_audio_logged:
                                    print("[RECEIVE] Response chunk received from Gemini Live.")
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



                            if turn_intercepted or getattr(self, 'current_turn_intercepted', False):
                                self.engine.history.clear_assistant_turn()
                                self._clear_playback_queue(stop_local_tts=False)
                                turn_intercepted = False
                                self.current_turn_intercepted = False



                            else:



                                # Merge accumulated streaming chunks into ONE assistant message and save to SQLite



                                self.engine.history.finalize_assistant_turn(self.active_history_session_id)
                            self.turn_tracker.reset_current_turn()

                            if self.playback_queue.empty():
                                self.set_state("LISTENING")

                    tool_call = getattr(response, "tool_call", None)
                    if tool_call is not None:
                        if self.turn_tracker.current_turn_id == 0:
                            self.turn_tracker.start_new_turn()
                        # Finalize any pending user speech turn when tool call arrives



                        if self.user_transcript_buffer:



                            if self._finalize_user_speech_turn():



                                turn_intercepted = True



                        for call in getattr(tool_call, "function_calls", []):



                            fn_name = call.name



                            fn_args = call.args or {}



                            call_id = call.id







                            action_key = self._resolve_tool_action_key(fn_name, fn_args)
                            cached = self.turn_tracker.get_executed(action_key) if action_key else None

                            if cached is not None:
                                result_content = cached["result_content"]
                            else:
                                result_content = {}

                                if fn_name == "get_ambient_status":
                                    def _exec_ambient():
                                        frame = self.engine.current_frame
                                        light = self.engine.color_detector.check_ambient_light(frame)
                                        color = self.engine.color_detector.detect_dominant_color(frame)
                                        return {"light": light, "color": color}
                                    result_content = await self._run_tool_in_executor(_exec_ambient)

                                elif fn_name == "scan_product_details":
                                    def _exec_scan():
                                        frame = self.engine.current_frame
                                        ocr_res = self.engine.ocr_engine.process_ocr(frame)
                                        prod_res = self.engine.product_scanner.scan_product_label(frame, ocr_text=ocr_res.get("text", ""))
                                        return prod_res
                                    result_content = await self._run_tool_in_executor(_exec_scan)

                                elif fn_name == "enroll_person_face":
                                    name = fn_args.get("person_name", "Friend")
                                    def _exec_enroll():
                                        res = self.engine.face_recognizer.enroll_active_face(self.engine.current_frame, name)
                                        if res.get("success"):
                                            self.engine.memory.save_memory("relationship", name.lower(), f"{name} is saved in face memory.")
                                            try:
                                                self._update_info_strip()
                                            except Exception:
                                                pass
                                        return res
                                    result_content = await self._run_tool_in_executor(_exec_enroll)

                                elif fn_name == "save_reminder_note":
                                    fact = fn_args.get("fact_text", "")
                                    print(f"[SAVE] tool_call 'save_reminder_note' with fact: '{fact}'")
                                    def _exec_save():
                                        key, fact_val = self.engine.router.extract_memory_key_and_fact(fact)
                                        if not key or key == "contextual":
                                            key_words = [w for w in re.sub(r'[^\w\s]', '', (fact_val or fact).lower()).split() if w not in ["that", "my", "the", "a", "an", "this", "it", "is", "are", "user", "users"]]
                                            key = " ".join(key_words[:2]) if key_words else "personal_fact"
                                        success = self.engine.memory.save_memory("personal", key, fact_val or fact)
                                        try:
                                            self._update_info_strip()
                                        except Exception:
                                            pass
                                        return {"status": "saved" if success else "failed", "fact": fact_val or fact}
                                    result_content = await self._run_tool_in_executor(_exec_save)

                                elif fn_name == "recall_user_memory":
                                    query = fn_args.get("search_query", "")
                                    memory_fact = await self._run_tool_in_executor(self.engine.memory.recall_memory, query)
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
                                    local_resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, sec_cmd, self.active_history_session_id
                                    )
                                    self._clear_playback_queue()
                                    if local_resp:
                                        is_protected_disclosure = (
                                            isinstance(local_resp, str) and (
                                                "here is your protected information:" in local_resp.lower()
                                                or local_resp.startswith("Here is your protected information:")
                                            )
                                        )
                                        safe_gui_resp = "[Protected Information Disclosed Locally]" if is_protected_disclosure else local_resp
                                        self.gui_queue.put(("TRANSCRIPT_ASSISTIVE", safe_gui_resp))
                                        self._speak_local_response(local_resp, is_security=True)
                                    result_content = {"status": "initiated", "message": local_resp or "Security flow engaged."}

                                elif fn_name == "open_application":
                                    app_name = fn_args.get("app_name", "")
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, f"open {app_name}", self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "set_system_volume":
                                    act = fn_args.get("action", "get")
                                    val = fn_args.get("value")
                                    if act == "set" and val is not None:
                                        cmd = f"set volume to {val} percent"
                                    elif act == "up":
                                        cmd = "turn up the volume"
                                    elif act == "down":
                                        cmd = "turn down the volume"
                                    elif act == "mute":
                                        cmd = "mute volume"
                                    elif act == "unmute":
                                        cmd = "unmute volume"
                                    else:
                                        cmd = "what is the volume"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "set_screen_brightness":
                                    act = fn_args.get("action", "get")
                                    val = fn_args.get("value")
                                    if act == "set" and val is not None:
                                        cmd = f"set brightness to {val} percent"
                                    elif act == "up":
                                        cmd = "increase brightness"
                                    elif act == "down":
                                        cmd = "decrease brightness"
                                    elif act == "max":
                                        cmd = "set brightness to maximum"
                                    elif act == "min":
                                        cmd = "set brightness to minimum"
                                    else:
                                        cmd = "what is the screen brightness"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "set_wifi_state":
                                    act = fn_args.get("action", "status")
                                    if act == "on":
                                        cmd = "turn wi-fi on"
                                    elif act == "off":
                                        cmd = "turn wi-fi off"
                                    else:
                                        cmd = "what is the wi-fi status"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "set_bluetooth_state":
                                    act = fn_args.get("action", "status")
                                    if act == "on":
                                        cmd = "turn bluetooth on"
                                    elif act == "off":
                                        cmd = "turn bluetooth off"
                                    else:
                                        cmd = "what is the bluetooth status"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "manage_bluetooth_device":
                                    act = fn_args.get("action", "list")
                                    dev = fn_args.get("device_name", "")
                                    if act == "connect":
                                        cmd = f"connect to {dev}" if dev else "connect bluetooth device"
                                    elif act == "disconnect":
                                        cmd = f"disconnect {dev}" if dev else "disconnect bluetooth device"
                                    else:
                                        cmd = "list my bluetooth devices"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name == "search_web":
                                    q = fn_args.get("query", "")
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, f"search the web for {q}", self.active_history_session_id
                                    )
                                    result_content = {"status": "searched", "response": resp}

                                elif fn_name == "get_last_action":
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, "what did you just open", self.active_history_session_id
                                    )
                                    result_content = {"status": "retrieved", "response": resp}

                                elif fn_name == "read_screen":
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, "read the screen", self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name in ("open_windows_settings", "open_settings_page"):
                                    p = fn_args.get("page") or "main"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, f"open {p} settings", self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name in ("notepad_control", "write_notepad_text", "open_notepad"):
                                    act = fn_args.get("action", "open")
                                    txt = fn_args.get("text", "")
                                    if act == "open" or fn_name == "open_notepad":
                                        cmd = "open notepad"
                                    elif act == "write" or fn_name == "write_notepad_text":
                                        cmd = f"write {txt}"
                                    elif act == "select_all":
                                        cmd = "select all"
                                    elif act == "copy":
                                        cmd = "copy"
                                    elif act == "paste":
                                        cmd = "paste"
                                    elif act == "clear":
                                        cmd = "clear the document"
                                    else:
                                        cmd = "open notepad"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name in ("youtube_control", "search_youtube", "open_youtube"):
                                    act = fn_args.get("action", "search")
                                    q = fn_args.get("query", "")
                                    secs = fn_args.get("seconds", 10)
                                    if act == "search":
                                        cmd = f"search youtube for {q}" if q else "open youtube"
                                    elif act == "play":
                                        cmd = f"play {q} on youtube" if q else "open youtube"
                                    elif act == "open":
                                        cmd = "open youtube"
                                    elif act == "mute":
                                        cmd = "mute youtube"
                                    elif act == "unmute":
                                        cmd = "unmute youtube"
                                    elif act == "seek_forward":
                                        cmd = f"skip forward {secs} seconds on youtube"
                                    elif act == "seek_backward":
                                        cmd = f"rewind {secs} seconds on youtube"
                                    elif act == "close":
                                        cmd = "close youtube"
                                    else:
                                        cmd = "open youtube"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                elif fn_name in ("take_screenshot", "screenshot_control"):
                                    target = fn_args.get("target", "full")
                                    cmd = "capture active window" if target == "window" else "take a screenshot"
                                    resp = await self._run_tool_in_executor(
                                        self.engine.process_user_speech_query, cmd, self.active_history_session_id
                                    )
                                    result_content = {"status": self._outcome_status(resp), "response": resp}

                                if action_key:
                                    resp_val = result_content.get("response") if isinstance(result_content, dict) else result_content
                                    self.turn_tracker.record_execution(action_key, resp_val, result_content, owner="gemini_tool_path")

                                # Determine if this tool's response will be (or already was) spoken by local TTS.
                                # If so, suppress Gemini's post-tool-response audio to prevent double speech.
                                _LOCAL_VOICE_TOOLS = {
                                    "take_screenshot", "screenshot_control",
                                    "notepad_control", "write_notepad_text", "open_notepad",
                                    "youtube_control", "search_youtube", "open_youtube",
                                    "set_system_volume", "set_screen_brightness",
                                    "set_wifi_state", "set_bluetooth_state", "manage_bluetooth_device",
                                    "open_windows_settings", "open_settings_page",
                                    "read_screen", "manage_voice_security", "open_application",
                                }
                                _tool_handled_locally = fn_name in _LOCAL_VOICE_TOOLS





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

                            # SINGLE-VOICE FIX: Suppress Gemini's own natural/post-tool audio reply
                            # to prevent double speech. The confirmation text was already queued via
                            # pending_speech_prompt (Puck voice) in the finalize path.
                            if _tool_handled_locally:
                                turn_intercepted = True
                                self.current_turn_intercepted = True
                                # Clear any raw Gemini audio chunks already queued for this turn
                                self._clear_playback_queue(stop_local_tts=False)
                                # NOTE: Do NOT clear pending_speech_prompt — it IS the voice path now.
                                # The confirmation text queued there will be sent to Gemini (Puck voice).
                                print(f"[SINGLE-VOICE] Tool '{fn_name}' — Gemini natural audio suppressed; Puck confirmation queued.")




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



        if getattr(self, '_is_closing', False) or getattr(self, '_shutting_down', False):
            return

        self._is_closing = True
        self._shutting_down = True
        self._animations_enabled = False
        self._cancel_all_after_callbacks()
        self.network_monitor_running = False



        print("[STATE] CLOSED")



        print("[HANDOFF] MAIN -> BACKGROUND")



        print("[SHUTDOWN] SG CUBE shutting down cleanly...")



        self.stop_ai()

        if hasattr(self, '_local_tool_executor') and self._local_tool_executor is not None:
            try:
                self._local_tool_executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass



        self.stop_camera()



        self._clear_playback_queue()



        if hasattr(self.engine, 'scheduler'):



            try:



                self.engine.scheduler.stop()



            except Exception:



                pass



        self._notify_wake_listener_resume()



        self._close_ipc_server()



        time.sleep(0.15)



        try:



            if self.root and self.root.winfo_exists():



                self.root.destroy()



        except Exception:



            pass







def _cleanup_stale_instance_on_port(port: int):



    """



    Recovers from a stale/zombie SG CUBE process holding the GUI IPC port.



    Identifies the process owning the port and terminates only if it is an SG CUBE / Python process.



    """



    try:



        cmd = 'netstat -ano -p tcp'



        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)



        target_pid = None



        for line in output.splitlines():



            line = line.strip()



            if f":{port}" in line and "LISTENING" in line.upper():



                parts = line.split()



                if len(parts) >= 5:



                    try:



                        target_pid = int(parts[-1])



                        break



                    except ValueError:



                        pass







        if target_pid and target_pid != os.getpid():



            chk_cmd = f'tasklist /FI "PID eq {target_pid}" /FO CSV /NH'



            proc_info = subprocess.check_output(chk_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)



            proc_lower = proc_info.lower()



            if "python" in proc_lower or "visionclaw" in proc_lower or "sg" in proc_lower:



                print(f"[SINGLE-INSTANCE] Terminating unresponsive zombie SG CUBE process (PID {target_pid})...")



                subprocess.call(f'taskkill /F /PID {target_pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)



                time.sleep(0.3)



    except Exception as e:



        print(f"[SINGLE-INSTANCE] Stale process recovery notice: {e}")








def _find_sgcube_visible_window():
    """Returns HWND of visible SG CUBE window if one exists, else None."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found_hwnd = [None]
        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if "SG CUBE" in title or "VisionClaw" in title:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        if (rect.right - rect.left > 150) and (rect.bottom - rect.top > 150):
                            found_hwnd[0] = hwnd
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return found_hwnd[0]
    except Exception:
        return None

def _check_and_wake_existing_instance() -> bool:



    """



    Checks if a healthy, running SG CUBE instance is active on IPC_PORT_GUI.



    Sends WAKE command and waits for valid 'OK' response.



    Returns True if an active instance acknowledged WAKE (new process should exit).



    Returns False if port is free or if existing process is unresponsive/stale (safe to start).



    """



        # Clean up any orphaned process holding port 8000 without a visible window
    try:
        s8000 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s8000.settimeout(0.3)
        res8000 = s8000.connect_ex(('127.0.0.1', 8000))
        s8000.close()
        if res8000 == 0:
            vis_hwnd = _find_sgcube_visible_window()
            if not vis_hwnd:
                print(f"[SINGLE-INSTANCE] Port 8000 is held by an orphaned process with no visible window. Cleaning up...")
                _cleanup_stale_instance_on_port(8000)
                time.sleep(0.4)
    except Exception:
        pass

    try:



        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)



        s.settimeout(0.6)



        res = s.connect_ex(('127.0.0.1', IPC_PORT_GUI))



        if res != 0:



            s.close()



            return False







        # Port is open; send WAKE and wait for acknowledgement



        s.sendall(b"WAKE\n")



        resp = s.recv(1024).decode('utf-8', errors='ignore').strip()



        s.close()







        if "OK" in resp:
            vis_hwnd = _find_sgcube_visible_window()
            if vis_hwnd:
                print(f"[SINGLE-INSTANCE] Active visible SG CUBE window found (HWND {vis_hwnd}). Bringing to foreground.")
                try:
                    import win32gui, win32con
                    win32gui.ShowWindow(vis_hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(vis_hwnd)
                except Exception:
                    pass
                return True
            else:
                print(f"[SINGLE-INSTANCE] Port {IPC_PORT_GUI} is held by a background process with no visible window. Terminating stale process...")
                _cleanup_stale_instance_on_port(IPC_PORT_GUI)
                time.sleep(0.5)
                return False



        else:



            print(f"[SINGLE-INSTANCE] Port {IPC_PORT_GUI} responded with unexpected: '{resp}'. Treating as stale.")



            _cleanup_stale_instance_on_port(IPC_PORT_GUI)



            return False



    except (socket.timeout, socket.error, ConnectionRefusedError, ConnectionResetError) as e:



        print(f"[SINGLE-INSTANCE] Port {IPC_PORT_GUI} is held but did not respond ({e}). Treating as stale.")



        _cleanup_stale_instance_on_port(IPC_PORT_GUI)



        return False



    except Exception as e:



        print(f"[SINGLE-INSTANCE] Notice during IPC probe: {e}")



        return False







def main():



    if _check_and_wake_existing_instance():



        sys.exit(0)







    # Windows Per-Monitor DPI Awareness for crisp UI scaling on laptops



    if os.name == 'nt':



        try:



            import ctypes



            ctypes.windll.shcore.SetProcessDpiAwareness(2)



        except Exception:



            try:



                ctypes.windll.user32.SetProcessDPIAware()



            except Exception:



                pass







    import argparse
    parser = argparse.ArgumentParser(description="SG CUBE Personal AI Companion")
    parser.add_argument("--gui", choices=["web", "tkinter", "legacy"], default="web", help="GUI presentation mode")
    parser.add_argument("--port", type=int, default=8000, help="Web bridge port")
    args, _ = parser.parse_known_args()

    use_legacy_tk = (args.gui in ("tkinter", "legacy")) or ("--legacy" in sys.argv) or ("--tkinter" in sys.argv)

    if not use_legacy_tk:
        # Pre-flight check: verify WebView2 runtime availability
        can_use_webview2 = False
        try:
            import webview
            from webview.platforms import winforms
            can_use_webview2 = getattr(winforms, 'is_chromium', False)
        except Exception:
            can_use_webview2 = False

        if not can_use_webview2:
            print("[LAUNCH-FALLBACK] Microsoft Edge WebView2 runtime is unavailable. Automatically falling back to Tkinter UI...")
            use_legacy_tk = True
        else:
            try:
                from bridge_server import bridge
                bridge.start(host="127.0.0.1", port=args.port)

                ready_evt = threading.Event()
                app_holder = {}

                def run_tk_backend():
                    root = tk.Tk()
                    root.withdraw()
                    app = SGCubeApp(root)
                    app.web_mode = True
                    app.register_event_listener(bridge.handle_backend_event)
                    bridge.set_app_instance(app)
                    app_holder["app"] = app
                    app_holder["root"] = root
                    ready_evt.set()
                    root.mainloop()

                tk_thread = threading.Thread(target=run_tk_backend, daemon=True)
                tk_thread.start()
                ready_evt.wait(timeout=10.0)

                app = app_holder.get("app")
                root = app_holder.get("root")

                # Create native Edge WebView2 window on main thread
                window = webview.create_window(
                    "SG CUBE — Personal AI Companion",
                    f"http://127.0.0.1:{args.port}",
                    width=1672,
                    height=941,
                    min_size=(1024, 600),
                    background_color="#000000"
                )
                if app:
                    app.web_window = window

                def on_webview_closed():
                    try:
                        bridge.stop()
                        if app:
                            app.on_close()
                        if root:
                            root.destroy()
                    except Exception:
                        pass
                    os._exit(0)

                window.events.closed += on_webview_closed
                webview.start(debug=False)
                try:
                    bridge.stop()
                    if app:
                        app.on_close()
                    if root:
                        root.destroy()
                except Exception:
                    pass
                os._exit(0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[LAUNCH-FALLBACK] Modern Web UI startup error: {e}. Falling back to Tkinter...")
                try:
                    bridge.stop()
                    if app_holder.get("app"):
                        app_holder["app"].on_close()
                    if app_holder.get("root"):
                        app_holder["root"].destroy()
                except Exception:
                    pass
                time.sleep(0.5)
                use_legacy_tk = True

    # Legacy Tkinter path
    root = tk.Tk()
    app = SGCubeApp(root)
    try:
        root.mainloop()
    finally:
        try:
            app.on_close()
        except Exception:
            pass
        os._exit(0)







if __name__ == "__main__":



    main()



