# SG CUBE 2.5 — Advanced Scene Understanding & Spatial Context Architecture

## Overview
SG CUBE 2.5 Feature 3 upgrades the visual perception system from isolated object detections into structured, deterministic 2D image-space scene understanding. SG CUBE interprets multi-object environments, spatial relationships (e.g. *on the table*, *near the laptop*, *to your left*), path obstructions, and changes over time while upholding strict privacy, safety, and non-hallucination guarantees.

---

## 1. System Architecture

```
                       ┌─────────────────────────┐
                       │    RGB Camera Stream    │
                       └────────────┬────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
┌──────────▼──────────┐  ┌──────────▼──────────┐  ┌──────────▼──────────┐
│ Face Recognizer     │  │ Object Detector     │  │ Color & Light       │
│ (YuNet + SFace)     │  │ (Salient Contours)  │  │ Detector (HSV/LAB)  │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │ Raw Detections
                         ┌──────────▼──────────┐
                         │ Spatial Relationship│
                         │       Engine        │
                         └──────────┬──────────┘
                                    │ Geometric Graph & Zones
                         ┌──────────▼──────────┐
                         │   Scene Analyzer    │
                         │  (Temporal Tracker) │
                         └──────────┬──────────┘
                                    │ Structured Scene Object
           ┌────────────────────────┴────────────────────────┐
           │                                                 │
┌──────────▼──────────┐                           ┌──────────▼──────────┐
│ Scene Query Engine  │                           │ Vision UI HUD Card  │
│ (Local Audio Resp)  │                           │ (Structured State)  │
└─────────────────────┘                           └─────────────────────┘
```

---

## 2. Structured Scene Data Models

### Scene (`assistive/scene_model.py`)
- `timestamp`: Float Unix timestamp of the frame.
- `frame_size`: `(width, height)` in pixels (typically 640x480).
- `objects`: List of `SceneObject` records.
- `people`: List of `ScenePerson` records with strict privacy gating.
- `relationships`: List of pairwise `SceneRelationship` records.
- `obstructions`: List of detected `SceneObstruction` warnings in the navigation corridor.
- `environment`: Ambient lighting level and room illumination metrics.
- `safety_flags`: Physical hazard alerts from `SafetyAnalyzer`.
- `summary`: Concisely formatted spoken scene description.

### Spatial Relationships (`SpatialRelationType`)
- `ON`: Top object rests vertically on top of surface with $\ge 35\%$ horizontal overlap.
- `UNDER`: Inverse of `ON`.
- `INSIDE`: Bounding box area containment $\ge 75\%$.
- `NEAR`: Normalized centroid Euclidean distance $d < 0.28$.
- `FAR`: Normalized centroid Euclidean distance $d > 0.55$.
- `LEFT_OF` / `RIGHT_OF`: Horizontal separation $|cx_A - cx_B| > 0.16 \times W$.
- `ABOVE` / `BELOW`: Vertical separation $|cy_A - cy_B| > 0.20 \times H$.
- `PATH_BLOCKING`: Lower-center navigation footprint ($y_2 > 0.60 \times H$, $0.30 \le cx/W \le 0.70$).

---

## 3. Camera-Relative User Positioning

Image space is segmented into deterministic horizontal and vertical sectors:

### Horizontal Sectors
- $cx < 0.28 \implies$ `LEFT` ("to your left")
- $0.28 \le cx < 0.40 \implies$ `CENTER_LEFT` ("slightly to your left")
- $0.40 \le cx \le 0.60 \implies$ `CENTER` ("directly ahead" / "in front of you")
- $0.60 < cx \le 0.72 \implies$ `CENTER_RIGHT` ("slightly to your right")
- $cx > 0.72 \implies$ `RIGHT` ("on your right")

### Vertical Sectors
- $cy < 0.35 \implies$ `TOP` ("above")
- $0.35 \le cy \le 0.65 \implies$ `MIDDLE` ("at eye level")
- $cy > 0.65 \implies$ `BOTTOM` ("below / on the ground")

---

## 4. Privacy & Face Safeguards

To prevent unauthorized biometric or identity disclosures:
- Person names are disclosed **only** when all 5 conditions are met:
  1. `state == KNOWN`
  2. `is_confirmed == True` (3 of 5 temporal confirmation)
  3. `liveness_ok == True` (passed anti-spoofing and micro-motion validation)
  4. `quality_ok == True` (passed brightness, contrast, alignment quality gates)
  5. `name` is non-empty and not `"Unknown"`
- If any condition is unsatisfied, the person is described generically as *"a person"* or *"someone"*.

---

## 5. Memory Integration (Feature 2) Boundary

- Visual observations are strictly **transient in-memory scene state**.
- SG CUBE **never** automatically writes visual observations into SQLite permanent memory.
- Permanent memories are only created upon explicit user voice commands (e.g. *"Remember that my laptop is on the table"*).

---

## 6. RGB Camera Limitations & Safety Disclaimers

> [!WARNING]
> Standard RGB webcams do not provide 3D LiDAR, Time-of-Flight, or stereoscopic depth telemetry. All distance, scale, and proximity measurements are estimated via 2D bounding box geometry and image height proportions. SG CUBE uses conservative image-relative language and never guarantees complete real-world path safety.
