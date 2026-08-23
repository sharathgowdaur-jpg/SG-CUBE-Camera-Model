# 🧊 SG CUBE — AI Vision Companion & Assistive Assistant

<p align="center">

**See. Understand. Remember. Assist.**

A real-time multimodal AI vision companion and assistive assistant designed primarily for visually impaired and blind users, while also providing general-purpose AI assistance.

</p>

---

## 🌟 Overview

SG CUBE is an intelligent, real-time multimodal AI vision companion and assistive assistant that combines:

* 🎙️ Real-time voice interaction
* 🤖 Google Gemini Live multimodal AI
* 👁️ Real-time computer vision
* 👤 Face detection and recognition
* 🧠 Personal memory
* 💬 Conversation history
* 📖 OCR and text reading
* 💵 Indian currency recognition
* 📦 Object finding
* 🧭 Spatial awareness
* 🌍 Environment and scene understanding
* ⚠️ Safety monitoring
* 🎨 Color detection
* 💡 Light detection
* 📦 Product and medicine scanning
* 🎧 Background wake-word listening
* 💤 Sleep and wake control
* 🔑 Multiple Gemini API key management and failover
* 🔐 Local persistent storage

## 🎯 Project Vision

The vision of SG CUBE is to create a natural AI companion that can:

**Listen → Understand → See → Analyze → Remember → Respond → Assist**

Instead of relying only on traditional buttons and text interfaces, SG CUBE provides a voice-first interaction model supported by real-time camera perception.

---

## 🧠 Core Architecture

```text
                         ┌──────────────────────┐
                         │       SG CUBE        │
                         │   Multimodal Core    │
                         └──────────┬───────────┘
                                    │
             ┌──────────────────────┼────────────────────────┐
             │                      │                        │
             ▼                      ▼                        ▼
      🎙️ Voice System        👁️ Vision System          🧠 Memory
             │                      │                        │
             ▼                      ▼                        ▼
      Background Wake        Face Recognition         Personal Memory
      Speech Input           OCR                       Conversation History
      Gemini Live            Currency                  User Profile
      Speaker                Objects                   Face Memory
                             Spatial
                             Environment
                             Safety
                             Color
                             Light
             │                      │                        │
             └──────────────────────┼────────────────────────┘
                                    │
                                    ▼
                             🔊 Response System
                                    │
                                    ▼
                              User Assistance
```

---

# ✨ Key Features

## 🎙️ Voice & Conversational AI

SG CUBE uses Google Gemini Live for real-time multimodal interaction.

### Capabilities

* Real-time bidirectional communication
* Streaming audio interaction
* Vision-aware conversation
* Multi-turn dialogue
* Continuous conversation
* Spoken responses
* Low-latency interaction
* Barge-in / interruption
* Dedicated speaker management
* Voice confirmations
* Assistive spoken output

### Example

**User:**

> What do you see?

**SG CUBE:**

> I can see a person standing in front of you.

---

## 🎧 Background Wake Listener

SG CUBE includes a dedicated background wake listener designed for low-latency standby listening.

### Example wake phrases

* `SG CUBE`
* `Hey SG CUBE`
* `S G CUBE`
* `Ess Gee Cube`
* `Es Gee Cube`
* `SG Cub`
* `SG Cue`

The wake system is designed to handle reasonable phonetic variations.

### Wake Pipeline

```text
Microphone
    ↓
Voice Activity Detection
    ↓
Rolling Audio Buffer
    ↓
Wake Word Matcher
    ↓
Wake Event
    ↓
SG CUBE
```

The listener uses a two-stage approach:

1. Low-cost speech activity detection
2. Phonetic/acoustic wake-word matching

---

# 🔄 Application Lifecycle

SG CUBE uses a state-aware voice lifecycle.

```text
WINDOWS LOGIN
     ↓
Background Listener ON
     ↓
User says "Hey SG CUBE"
     ↓
SG CUBE Opens
     ↓
Main Voice System Active
     ↓
Background Listener OFF
```

### Sleep

```text
ACTIVE
   ↓
"Go to sleep"
   ↓
Main microphone OFF
Camera OFF
Gemini OFF
   ↓
Background Listener ON
   ↓
Wait for wake word
```

### Closed Application

```text
SG CUBE CLOSED
      ↓
Background Listener ON
      ↓
Wait for wake word
      ↓
"Hey SG CUBE"
      ↓
SG CUBE opens again
```

### Microphone Ownership

| State           | Main Microphone | Background Listener |
| --------------- | --------------- | ------------------- |
| Windows Login   | OFF             | ON                  |
| Closed          | OFF             | ON                  |
| Sleep           | OFF             | ON                  |
| Open + Active   | ON              | OFF                 |
| System Shutdown | OFF             | OFF                 |

This prevents competing microphone streams.

---

# 👁️ Computer Vision

SG CUBE contains multiple assistive computer vision engines.

## 👤 Face Detection

Features include:

* Real-time face detection
* Multiple face detection
* Bounding boxes
* Live camera processing
* Integration with face recognition

## 🧑 Face Recognition

SG CUBE supports local face recognition using feature embeddings and similarity matching.

Features include:

* Face enrollment
* Face recognition
* Unknown-face handling
* Local face profiles
* Profile persistence
* Face profile deletion
* Recognition after restart

### 🧠 Face Memory

Users can explicitly save people into local face memory.

**Example:**

> Save this face as Rahul.

Later:

> Who is this?

SG CUBE can attempt to recognize the enrolled person.

---

# 📖 OCR — Text Reading

The OCR engine provides visual text assistance.

### Capabilities

* Text extraction
* Image preprocessing
* Adaptive thresholding
* Multi-line text handling
* Spoken text reading
* Camera-based text assistance

**Example:**

> Read this.

SG CUBE processes the visible text and provides the result through the voice system.

---

# 💵 Indian Currency Recognition

SG CUBE includes Indian banknote recognition.

### Supported denominations

* ₹10
* ₹20
* ₹50
* ₹100
* ₹200
* ₹500
* ₹2000

The result can be provided through the assistant's visual and spoken response systems.

---

# 📦 Object Finder

SG CUBE can help locate objects in the user's surroundings.

**Example:**

> Find my phone.

Possible spatial results:

* Left
* Center
* Right
* Near
* Far

---

# 🧭 Spatial Awareness

The spatial system provides relative object positioning.

Examples:

* Left
* Center
* Right
* Near
* Far
* Relative position

**Example response:**

> Your phone is on the right and nearby.

---

# 🌍 Environment & Scene Awareness

SG CUBE can analyze the surrounding environment and provide structured information.

Possible information includes:

* People count
* Room/environment context
* Detected objects
* Lighting conditions
* Spatial relationships
* Scene changes

---

# ⚠️ Safety Monitoring

SG CUBE includes assistive safety analysis.

Potential detections include:

* Nearby obstacles
* Close objects
* Stairs and steps
* Collision risks
* Proximity hazards

Safety information can be delivered through the assistant's voice system.

> ⚠️ SG CUBE is an assistive system and should not be treated as a replacement for emergency services or professional assistance.

---

# 🎨 Color Detection

SG CUBE can identify dominant colors in visible objects and clothing.

**Example:**

> What color is this?

**Possible output:**

> Blue.

---

# 💡 Light Detection

The light analysis system classifies ambient lighting.

Possible states:

* Dark
* Dim
* Normal
* Bright

**Example:**

> Is the room dark?

---

# 📦 Product & Medicine Scanner

The product scanner can analyze supported packaging and labels.

### Capabilities

* Barcode detection
* QR code detection
* Package text
* Product information extraction
* Expiration-date parsing

**Example:**

```text
EXP: 08/2027
```

---

# 🧠 Personal Memory

SG CUBE provides persistent local personal memory.

**Example:**

> Remember my favorite color is blue.

Later:

> What is my favorite color?

**Expected response:**

> Blue.

The memory system supports saving, recalling, and forgetting supported information.

---

# 💬 Conversation History

SG CUBE stores multi-session conversation history locally.

The history system can preserve:

* User messages
* Assistant responses
* Conversation sessions
* Session metadata

This allows the application to maintain continuity across sessions.

---

# 👤 User Profile

SG CUBE supports first-run user profile setup.

The user can configure:

* Name
* Display name
* Preferences
* Application settings
* API configuration

A fresh setup does not use a hardcoded personal identity.

---

# 🔑 Gemini API Key Management

SG CUBE supports multiple Gemini API keys.

```text
Primary Key
     ↓
Secondary Key
     ↓
Tertiary Key
```

Automatic failover can move between configured keys for supported quota and transient network failures.

### Security

**Never publish real credentials.**

Example development configuration:

```env
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
```

Keys can also be configured through the application's Settings system where supported.

---

# 🔐 Privacy & Local Storage

SG CUBE uses local persistent storage for user-specific information.

Typical runtime storage:

```text
data/
├── face_memory/
├── history/
├── memory/
└── user_preferences/
```

This may contain:

* Face profiles
* Personal memories
* Conversation history
* Preferences
* Local credentials

### Never publish

```text
❌ API keys
❌ Passwords
❌ Tokens
❌ Private credentials
❌ Personal memory databases
❌ Face profiles
❌ Private conversations
❌ Private logs
❌ Machine-specific secrets
```

Use `.gitignore` to prevent accidental publication.

---

# 🏗️ Project Structure

```text
SG-CUBE/
│
├── assistive/
│   ├── api_key_manager.py
│   ├── command_router.py
│   ├── conversation_history.py
│   ├── face_memory.py
│   ├── face_recognition.py
│   ├── memory_manager.py
│   ├── ocr_engine.py
│   ├── currency_detector.py
│   ├── object_detector.py
│   └── vision_engine.py
│
├── tests/
│
├── data/
│   ├── face_memory/
│   ├── history/
│   ├── memory/
│   └── user_preferences/
│
├── visionclaw_gui.py
├── wake_listener.py
├── wake_word_matcher.py
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

Runtime `data/` contents should be created locally and should not contain private user information in the public repository.

---

# 🛠️ Technology Stack

### Programming

* Python 3.10+
* SQLite
* Tkinter

### AI

* Google Gemini Live
* Multimodal streaming AI
* Conversational AI
* Vision-aware AI

### Computer Vision

* OpenCV
* Face recognition
* OCR
* Object detection
* Image preprocessing
* Spatial reasoning

### Audio

* Microphone streaming
* Voice Activity Detection
* Wake-word matching
* Audio buffering
* Speech output

### Storage

* SQLite
* WAL-based local storage
* Local persistence

### Windows Integration

* Windows startup
* Background wake listener

### IPC

* Single-instance protection
* System tray
* Hardware recovery

---

# 🚀 Installation

## Prerequisites

Recommended:

* Windows 10 or Windows 11
* Python 3.10, 3.11, 3.12, or 3.13
* Webcam
* Microphone
* Speaker or headphones
* Internet connection for Gemini Live

## Clone the Repository

```bash
git clone https://github.com/<your-username>/SG-CUBE.git
cd SG-CUBE
```

## Create a Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🔑 Configure Gemini API Keys

## Option 1 — Environment File

Copy:

```text
.env.example
```

to:

```text
.env
```

Then add your own values:

```env
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
```

**Never commit `.env` to GitHub.**

## Option 2 — In-App Settings

Launch SG CUBE and use the application settings for API key management when supported.

The application is designed to support primary, secondary, and tertiary keys with failover.

---

# ▶️ Run SG CUBE

```bash
python visionclaw_gui.py
```

For Windows:

```text
run.bat
```

---

# 🎧 Run the Background Wake Listener

For development/testing:

```bash
python wake_listener.py
```

Production deployments can configure the background listener to start automatically with Windows.

---

# 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

Run a specific test:

```bash
pytest tests/test_memory_manager.py
```

Example:

```bash
pytest tests/test_face_recognition_master.py
```

---

# 📊 Current Verification Status

The latest project verification includes:

| Area                           | Result |
| ------------------------------ | ------ |
| Background Listener Lifecycle  | ✅ PASS |
| Sleep → Wake                   | ✅ PASS |
| Closed → Wake                  | ✅ PASS |
| Background Listener Regression | ✅ PASS |
| Memory Save Verification       | ✅ PASS |
| Face Recognition Verification  | ✅ PASS |
| Camera                         | ✅ PASS |
| Voice                          | ✅ PASS |
| Gemini                         | ✅ PASS |
| Persistence                    | ✅ PASS |

### Latest reported verification numbers

* **196/196** full background-listener lifecycle regression tests passed
* **20/20** Sleep → Wake cycles passed
* **20/20** Close → Wake cycles passed
* **9/9** installed memory-save tests passed
* **180/180** memory/save regression tests passed
* **9/9** face-recognition master tests passed
* **189/189** face-recognition regression tests passed

These figures represent the latest reported test runs and should be rerun for each future release.

---

# ✅ Recommended Release Validation

Before publishing a new release, verify:

* [ ] Application startup
* [ ] Camera
* [ ] Microphone
* [ ] Speaker
* [ ] Gemini Live
* [ ] Background listener
* [ ] Windows startup
* [ ] Wake detection
* [ ] Wake from closed
* [ ] Wake from sleep
* [ ] Sleep
* [ ] Continuous conversation
* [ ] Barge-in
* [ ] Face detection
* [ ] Face recognition
* [ ] Face memory
* [ ] OCR
* [ ] Currency
* [ ] Object finder
* [ ] Spatial awareness
* [ ] Environment analysis
* [ ] Safety monitoring
* [ ] Color detection
* [ ] Light detection
* [ ] Product scanning
* [ ] Personal memory
* [ ] Conversation history
* [ ] API key management
* [ ] API failover
* [ ] Frontend actions
* [ ] Single instance
* [ ] Clean shutdown
* [ ] Recovery
* [ ] Security

---

# 🗣️ Example Voice Commands

## General

```text
"Hey SG CUBE"
"What do you see?"
"How are you?"
"Tell me something."
```

## Vision

```text
"Describe what you see."
"Who is in front of me?"
"Read this."
"What color is this?"
"Is the room dark?"
"Find my phone."
"Is it safe?"
```

## Memory

```text
"Remember my favorite color is blue."
"What is my favorite color?"
"Remember my dog name is Bruno."
"Forget that information."
"Save this information."
```

## Face Memory

```text
"Save this face as Rahul."
"Who is this?"
```

## Sleep / Wake

```text
"Go to sleep."
"Hey SG CUBE."
```

---

# 🔄 Example User Journey

```text
Windows Login
     ↓
Background Listener ON
     ↓
"Hey SG CUBE"
     ↓
SG CUBE Opens
     ↓
Greeting
     ↓
Camera + Main Voice System + Gemini
     ↓
Continuous Conversation
     ↓
Vision / Memory / Safety Features
     ↓
"Go to sleep"
     ↓
Main Assistant Sleeps
     ↓
Background Listener ON
     ↓
"Hey SG CUBE"
     ↓
SG CUBE Wakes
```

### Closed application

```text
SG CUBE
   ↓
Close
   ↓
Main Application OFF
   ↓
Background Listener ON
   ↓
"Hey SG CUBE"
   ↓
SG CUBE Opens Again
```

---

# 📸 Screenshots

Recommended repository structure:

```text
docs/
├── home.png
├── vision.png
├── memory.png
├── history.png
├── people.png
└── settings.png
```

Add screenshots here.

---

# 🎥 Demo

Add your project demonstration video here:

> ▶️ Watch SG CUBE Demo

---

# 👑 Original Author & Founder

**[ORIGINAL AUTHOR NAME]**

Original Author · Founder · Project Lead

SG CUBE was originally created and developed as an AI vision and assistive assistant project focused on:

* Multimodal AI
* Computer vision
* Voice interaction
* Accessibility
* Environmental understanding
* Personal memory
* Safety assistance
* Intelligent automation

### Core Contributions

* System architecture
* AI integration
* Gemini Live integration
* Voice interaction
* Background wake listener
* Computer vision pipeline
* Face recognition and face memory
* OCR integration
* Currency recognition
* Object and spatial analysis
* Personal memory
* Conversation history
* API key management
* Application integration
* Overall project development

### GitHub

```text
https://github.com/<your-username>
```

Replace `[ORIGINAL AUTHOR NAME]` and the GitHub URL with the official project owner's details before publishing.

---

# 👥 Project Team & Contributors

Add the actual team members below.

| Name              | Role                   | Main Contribution                            | GitHub  |
| ----------------- | ---------------------- | -------------------------------------------- | ------- |
| [Original Author] | Founder / Project Lead | Architecture, AI, Voice, Vision, Integration | Profile |
| [Team Member 1]   | AI / ML Developer      | AI models and perception                     | Profile |
| [Team Member 2]   | Backend Developer      | Backend, APIs, persistence                   | Profile |
| [Team Member 3]   | Frontend Developer     | UI/UX and interaction system                 | Profile |
| [Team Member 4]   | QA / Testing           | Testing, debugging, validation               | Profile |

Replace the placeholders with the actual contributors, roles, contributions, and GitHub profiles.

---

# 🏆 Original Authorship & Credit

## Original Project

**SG CUBE**

### Original Author / Founder

**[ORIGINAL AUTHOR NAME]**

This repository contains the generalized public source of the SG CUBE project.

All contributors should receive appropriate credit for their respective work.

### Copyright

```text
Copyright (c) 2026 [ORIGINAL AUTHOR NAME] and SG CUBE Contributors
```

---

# 🤝 Contributing

Contributions are welcome.

### Contribution Workflow

```text
Fork
 ↓
Create Feature Branch
 ↓
Develop
 ↓
Test
 ↓
Commit
 ↓
Push
 ↓
Pull Request
 ↓
Review
 ↓
Merge
```

Example:

```bash
git checkout -b feature/new-vision-module
```

Then:

```bash
git add .
git commit -m "Add new vision module"
git push origin feature/new-vision-module
```

Open a Pull Request through GitHub.

---

# 🐛 Bug Reports

When reporting a bug, include:

* Operating system
* Python version
* SG CUBE version
* Steps to reproduce
* Expected behavior
* Actual behavior
* Error messages
* Relevant logs
* Screenshots when useful

### Never upload

```text
❌ API keys
❌ Passwords
❌ Private credentials
❌ Personal memory databases
❌ Face profiles
❌ Private conversation history
❌ Private logs
```

---

# 💡 Feature Requests

Feature proposals are welcome.

Please explain:

* What problem the feature solves
* Why it is useful
* Expected behavior
* Possible implementation approach

---

# 🔒 Security

If you discover a security vulnerability, avoid publishing sensitive information in a public issue.

Never expose:

```text
❌ API keys
❌ Passwords
❌ Tokens
❌ Private credentials
❌ Private databases
```

Use responsible disclosure where possible.

---

# 🗺️ Roadmap

Potential future directions include:

* Improved wake-word robustness
* Stronger noise rejection
* Better low-light vision
* Expanded assistive vision capabilities
* More languages
* Improved accessibility
* Smart-glasses integration
* Expanded spatial reasoning
* Additional environmental sensors
* More intelligent assistive workflows
* Broader deployment options

> Roadmap items are future goals and should not be interpreted as completed features.

---

# 🎯 Project Goals

## ♿ Accessibility

Provide natural voice and vision assistance for visually impaired and blind users.

## 🤖 Intelligent Assistance

Create an assistant capable of understanding user requests and surrounding context.

## 👁️ Real-Time Perception

Combine camera-based perception with multimodal AI.

## 🧠 Personalization

Provide optional local memory, profile information, and face profiles.

## 🛡️ Safety

Help users identify environmental hazards and nearby objects.

## 🗣️ Natural Interaction

Enable voice-first interaction rather than relying only on traditional UI controls.

---

# 📌 Project Information

| Property         | Details                           |
| ---------------- | --------------------------------- |
| Project          | SG CUBE                           |
| Version          | 2.4.6                             |
| Platform         | Windows                           |
| Primary Language | Python                            |
| AI Engine        | Google Gemini Live                |
| Computer Vision  | OpenCV + Assistive Vision Engines |
| Database         | SQLite                            |
| License          | MIT                               |
| Status           | Production Release Candidate      |

---

# 🔌 Optional / External Integrations

## Meta Glass

SG CUBE includes Meta Glass-related integration points, but full end-to-end functionality depends on the required physical hardware and gateway/runtime infrastructure.

Do not assume full hardware support is available in every environment.

## Web3D

SG CUBE includes Web3D-related assets/integration points, but full external rendering depends on the required standalone server/runtime infrastructure.

---

# 🙏 Acknowledgements

SG CUBE builds upon open-source and public technologies including:

* Python
* OpenCV
* SQLite
* Google Gemini
* Tkinter
* WebSocket technologies
* Python ecosystem libraries
* Open-source computer vision research

We acknowledge and appreciate the developers, researchers, and maintainers behind the technologies used by this project.

---

# ⭐ Support SG CUBE

If you find SG CUBE useful or interesting:

* ⭐ Star the repository
* 🍴 Fork the project
* 🐛 Report bugs
* 💡 Suggest improvements
* 🤝 Contribute
* 📢 Share the project

---

# 📜 License

This project is licensed under the **MIT License**.

See the `LICENSE` file for complete license details.

---

<p align="center">

# 🧊 SG CUBE

**See. Understand. Remember. Assist.**

Built with ❤️ for accessible and intelligent AI assistance.

</p>
