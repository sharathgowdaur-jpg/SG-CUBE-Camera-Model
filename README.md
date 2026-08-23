<div align="center">

# 🧊 SG CUBE
### *Next-Generation Multimodal AI Companion & Assistive Vision System*

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%20Live%20API-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00f2fe?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Tests](https://img.shields.io/badge/Tests-196%20Passed%20(100%25)-00ff88?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

<p align="center">
  <strong>An intelligent, low-latency, real-time vision assistant and personal companion engineered for visually impaired, blind, and hands-free users.</strong>
</p>

[Key Features](#-key-features) •
[Architecture](#-system-architecture) •
[Quick Start](#-quick-start) •
[Voice Commands](#-voice-commands--interaction) •
[Installation Package](#-one-click-windows-installer) •
[Credits & Attribution](#-credits--acknowledgments) •
[License](#-license)

---

</div>

## 🌌 Overview

**SG CUBE** transforms standard webcams and microphones into an intuitive, person-aware sensory assistant. Powered by **Google Gemini Multimodal Live Streaming** combined with an **Edge Computer Vision Suite**, SG CUBE provides spatial reasoning, instant text recognition, banknote validation, face identification, long-term memory recall, and seamless hands-free wake-word standby.

Designed with accessibility at its core, the system prioritizes **natural conversational responses**, **spatially descriptive audio feedback** (e.g. *"slightly to your left, about 2 feet away"*), and **zero-lag continuous interaction**.

---

## ✨ Key Features

### ⚡ 1. Continuous Multimodal Intelligence
- **Real-Time Gemini Live Streaming**: Continuous bidirectional audio and video comprehension.
- **Low-Latency Spoken Responses**: Streaming 24kHz PCM audio playback with responsive barge-in support.
- **Warm & Intelligent Persona**: Spatially grounded descriptions designed specifically for accessibility.

### 🔑 2. Multi-API Key Failover & Resilience
- **3-Tier Key Rotation**: Seamless switching across **Primary**, **Secondary**, and **Tertiary** Gemini API keys.
- **Instant Quota Recovery**: Automatically handles `HTTP 429 (Resource Exhausted)` and network errors without interrupting ongoing conversations.
- **Local In-App Key Manager**: Secure, obfuscated in-memory and local storage with live test & validation controls.

### 👤 3. Edge Face Recognition & Face Memory
- **256-D Feature Vector**: Hybrid representation using HSV color distribution (96-D) + 4x4 spatial gradient grids (160-D) with L2 unit normalization.
- **Local Cosine Similarity Matcher**: Instant matching against enrolled loved ones and friends with strict threshold rejection (`threshold = 0.55`).
- **Zero-Cloud Privacy**: Face crops and embeddings are stored 100% locally on your machine.

### 👁️ 4. Assistive Edge Vision Suite
| Engine | Capability | Output Description |
| :--- | :--- | :--- |
| 📖 **OCR Engine** | Text extraction & parsing | Reads documents, book pages, product labels, and signs aloud. |
| 💵 **Currency Detector** | Banknote detection | Identifies banknote denominations and currencies instantly. |
| 🧭 **Spatial & Object Locator** | Relative geometry & distance | Detects everyday objects with clock-face directions (*"Cup at 2 o'clock"*). |
| 🎨 **Color & Light Sensor** | Ambient luminance & palette | Evaluates room illumination and dominant clothing/surface colors. |
| 📦 **Product Scanner** | Packaging & barcode analysis | Extracts product names, brands, and key ingredients. |
| 🛡️ **Safety Analyzer** | Hazard awareness | Warns of obstacles, stairs, doorways, and moving items. |

### 🎙️ 5. Two-Stage Standby Wake Listener
- **Stage 1 (VAD)**: Energy and zero-crossing Voice Activity Detector processing 100ms frames (<100ms latency).
- **Stage 2 (Phonetic Classification)**: Rolling circular buffer acoustic matcher listening for `"Hey SG CUBE"` / `"SG CUBE"`.
- **Authoritative Microphone Handoff**: Strict single-owner audio routing ensuring zero competition between background listening and active conversation.

### 🧠 6. Long-Term Memory & SQLite History
- **Fact & Preference Store**: SQLite WAL-mode memory database for personal facts (*"Remember my favorite tea is Earl Grey"*).
- **Conversations Journal**: Offline SQLite history tracking past interaction transcripts and timestamps.

### 🎨 7. Modern Cyberpunk GUI & 3D Orb Visualizer
- **Animated Audio Orb**: Smooth pulsing neon states reflecting listening, thinking, speaking, and sleeping modes.
- **High-Contrast Dark Theme**: Clean visual hierarchy crafted for low-vision clarity and easy debugging.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph Input_Sources [Sensory Inputs]
        MIC[Authoritative Microphone]
        CAM[USB / Integrated Camera]
    end

    subgraph Audio_Routing [Audio & Microphone Lifecycle]
        WAKE[Background Standby Listener]
        MAIN_MIC[Active Gemini Microphone]
        LOCK[Single-Instance IPC Mutex :49152-:49154]
    end

    subgraph AI_Core [Intelligence & Vision Core]
        GEMINI[Gemini Multimodal Live API]
        FAILOVER[Multi-Key Failover Manager]
        VISION[Assistive Vision Engine]
    end

    subgraph Assistive_Engines [Edge Vision Modules]
        FACE[Face Memory & Recognition 256-D]
        OCR[OCR Text Extraction Engine]
        CURR[Currency Detector]
        OBJ[Spatial & Object Analyzer]
        COLOR[Color & Light Sensor]
    end

    subgraph Persistence [Local Encrypted Storage]
        DB_MEM[(Memory DB - SQLite WAL)]
        DB_HIST[(History DB - SQLite WAL)]
        FACE_DIR[(Local Face Profiles)]
        PREFS[(User Preferences & Keys)]
    end

    subgraph Output [Sensory Output]
        TTS[Authoritative 24kHz Speaker Worker]
        GUI[3D Cyberpunk Orb GUI]
    end

    CAM --> VISION
    MIC --> WAKE
    MIC --> MAIN_MIC
    WAKE -- "Wake Match" --> LOCK
    LOCK --> MAIN_MIC
    MAIN_MIC --> GEMINI
    VISION --> FACE & OCR & CURR & OBJ & COLOR
    GEMINI <--> FAILOVER
    FAILOVER <--> PREFS
    GEMINI --> TTS
    VISION --> GEMINI
    FACE <--> FACE_DIR
    GEMINI <--> DB_MEM
    GEMINI <--> DB_HIST
    TTS --> GUI

## 👥 Team Members

SG CUBE is developed and maintained by the following team members:

| Team Member       | Role                       | GitHub                                               |
| :---------------- | :------------------------- | :--------------------------------------------------- |
| **Sharath U R**   | AI/ML & System Development | [@SharathUR](https://github.com/SharathUR)           |
| **Team Member 2** | —                          | [@GitHubUsername](https://github.com/GitHubUsername) |
| **Team Member 3** | —                          | [@GitHubUsername](https://github.com/GitHubUsername) |
| **Team Member 4** | —                          | [@GitHubUsername](https://github.com/GitHubUsername) |

> 💡 **Repository Credit:**
> This repository represents the collaborative work of the SG CUBE development team. All contributors are credited for their respective contributions to the project's research, development, testing, documentation, and design.

### 🔗 Project Repository

**SG CUBE — Next-Generation Multimodal AI Companion & Assistive Vision System**

[View the SG CUBE Repository](https://github.com/your-username/SG-CUBE)

---
## 🙏 Original Repository & Attribution

SG CUBE is based on and developed upon the work of the original repository created by **[Original Author Name]**.

### 🔗 Original Repository

* **Original Author:** [Original Author Name]
* **GitHub:** [@OriginalGitHubUsername](https://github.com/OriginalGitHubUsername)
* **Original Repository:** [Repository Name](https://github.com/OriginalGitHubUsername/OriginalRepository)

We sincerely acknowledge and credit the original author for the source code, architecture, concepts, and/or implementation that served as the foundation for this project.

SG CUBE includes modifications, extensions, integrations, and additional features developed for this project.

> **Credit:** This project does not claim the original work as entirely original. Appropriate credit is given to the original author and repository from which this project was derived.



## 📜 License

SG CUBE is released under the **MIT License**. See the [`LICENSE`](LICENSE) file for details.

