# SG CUBE — AI Vision Companion & Assistive Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SG CUBE** is an intelligent, real-time AI vision companion and assistive assistant designed for visually impaired and blind users, pairing continuous multimodal streaming with edge computer vision.

---

## ✨ Features

- **Continuous Multimodal Intelligence**: Real-time streaming conversation powered by Google Gemini with low-latency audio feedback.
- **Multi-API Key Management & Failover**: Automatic seamless switching across Primary, Secondary, and Tertiary Gemini API keys on quota exhaustion (HTTP 429) or transient network errors.
- **Edge Face Recognition & Memory**: 256-dimensional unit-normalized HSV + spatial gradient face embeddings with local cosine similarity matching and profile persistence.
- **Assistive Vision Engines**:
  - **OCR Engine**: Rapid text extraction and natural language reading.
  - **Currency Detector**: Identification and verification of banknotes.
  - **Object & Spatial Analyzer**: Real-time detection with intuitive clock-face and distance positioning.
  - **Color & Light Sensor**: Ambient illumination and dominant color assessment.
  - **Product Scanner**: Barcode and package text scanning.
- **Two-Stage Background Wake Listener**:
  - Standby listening for `"Hey SG CUBE"` / `"SG CUBE"`.
  - Energy & zero-crossing Voice Activity Detector (VAD) + rolling audio buffer.
  - Authoritative microphone ownership handoff between background listener and main UI.
- **Local Persistence & Privacy**: Long-term fact memory and conversation history stored locally in SQLite WAL databases.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Microphone and Webcam

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/SG-CUBE.git
cd SG-CUBE
```

### 3. Create Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure Gemini API Key
You can configure your Gemini API Key in two ways:
1. **Via Environment File**:
   Copy `.env.example` to `.env` and paste your Gemini API key:
   ```bash
   cp .env.example .env
   ```
2. **Via In-App Settings**:
   Launch the app and click **⚙️ Settings → API Keys** to configure Primary, Secondary, and Tertiary keys with built-in validation.

### 5. Launch SG CUBE
```bash
python visionclaw_gui.py
```

### 6. (Optional) Run Background Wake Listener
```bash
python wake_listener.py
```

---

## 🧪 Running Tests

SG CUBE includes a comprehensive unit and regression test suite:

```bash
pytest tests/
```

---

## 📂 Project Architecture

```text
SG-CUBE/
├── assistive/                     # Core Assistive & Vision Modules
│   ├── api_key_manager.py         # Multi-key secure storage & failover
│   ├── command_router.py          # Intent classification & routing
│   ├── conversation_history.py    # Local SQLite conversation sessions
│   ├── face_memory.py             # 256-D face embedding store
│   ├── face_recognition.py        # Face detection & cosine matcher
│   ├── memory_manager.py          # Long-term fact memory SQLite DB
│   ├── ocr_engine.py              # Optical character recognition
│   ├── currency_detector.py       # Banknote detection
│   ├── object_detector.py         # Real-time object recognition
│   └── vision_engine.py           # Unified vision orchestration
├── data/                          # Runtime user storage (created dynamically)
│   ├── face_memory/               # Enrolled face profiles
│   ├── history/                   # Conversation session databases
│   ├── memory/                    # Quick & long-term fact memory databases
│   └── user_preferences/          # Obfuscated credentials & settings
├── tests/                         # Full automated test suite
├── visionclaw_gui.py              # Main Application GUI & voice interaction
├── wake_listener.py               # Background standby wake listener
├── wake_word_matcher.py           # Fuzzy phonetic wake-word matching
├── requirements.txt               # Dependencies
└── run.bat                        # Windows launch script
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
