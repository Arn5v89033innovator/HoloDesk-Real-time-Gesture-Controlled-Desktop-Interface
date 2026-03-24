# 🖐 HoloDesk
### Real-time Gesture-Controlled Desktop Interface

HoloDesk uses your webcam to detect hand gestures and lets you control your entire computer — move the mouse, click, drag, scroll, switch virtual desktops, and launch apps — all without touching a keyboard or mouse. A Tony Stark–style holographic radial menu appears when you raise your open palm.

---

## Project Structure

```
HoloDesk/
├── main.py                ← Run this to start the app
├── requirements.txt
│
├── hand_tracking.py       # MediaPipe landmark extraction
├── gesture_detection.py   # Gesture classifier (palm/pinch/point/fist)
├── desktop_controls.py    # Mouse, drag, scroll, desktop switching
├── menu_ui.py             # Holographic radial menu renderer (Pygame)
└── actions.py             # App launcher (browser, files, blender etc.)
```

---

## Quick Start

### 1 — Install dependencies

```bash
# Python 3.10 – 3.11 recommended
pip install -r requirements.txt
```

> ⚠️ **MediaPipe compatibility fix** — if you get a protobuf error on startup:
> ```bash
> pip uninstall protobuf -y
> pip install protobuf==3.20.3
> ```

### 2 — Run HoloDesk

```bash
python main.py
```

| Key | Action |
|-----|--------|
| `M` | Manually toggle the holographic menu (for testing) |
| `Q` / `ESC` | Quit |

---

## How It Works

HoloDesk operates in **two modes** at all times:

### 🖥️ Desktop Control Mode *(default — green banner)*

| Gesture | Action |
|---------|--------|
| ☝ Index finger point + move | Moves the mouse cursor |
| 🤏 Pinch (quick release) | Left click |
| 🤏 Pinch + move hand | Drag a window or object |
| ☝ Point + flick finger up/down | Scroll the page |
| 🖐 Open palm + swipe right | Switch to next virtual desktop |
| 🖐 Open palm + swipe left | Switch to previous virtual desktop |
| 🖐 Hold open palm still | Opens the holographic menu |

### 🌐 Menu Interaction Mode *(cyan banner)*

| Gesture | Action |
|---------|--------|
| ☝ Point at a menu item | Highlights / hovers the item |
| 🤏 Pinch + hold (~0.45 s) | Selects and launches the app |
| ✊ Fist | Closes the menu, returns to Desktop Mode |

---

## Holographic Menu Options

| Icon | Option | Action |
|------|--------|--------|
| 🌐 | Browser | Opens default browser |
| 🎵 | Music | Opens music player |
| 📁 | Files | Opens file explorer |
| 🔢 | Calculator | Opens system calculator |
| 🌀 | Blender | Launches Blender 3D |
| ⚙ | Settings | Opens system settings |

---

## Gesture Priority System

To prevent conflicts, gestures are evaluated in this order every frame:

```
1. OPEN_PALM (held still)  →  open holographic menu
2. menu_open == True?      →  handle menu gestures only
3. OPEN_PALM + fast swipe  →  desktop switch (Ctrl+Win+Left/Right)
4. PINCH                   →  click or drag
5. POINTING + movement     →  move cursor / scroll
```

---

## Architecture Overview

```
Webcam frame
    │
    ▼
HandTracker  (MediaPipe — 21 landmarks per hand)
    │  normalised (x, y, z) coordinates
    ▼
GestureDetector  (rule-based classifier)
    │  OPEN_PALM / POINTING / PINCH / FIST
    ▼
Mode Router  (menu_open flag)
    │
    ├── Desktop Control Mode
    │       DesktopController  (PyAutoGUI)
    │       • cursor movement with sensitivity + smoothing
    │       • click / drag detection
    │       • vertical scroll via finger velocity
    │       • 4-finger desktop switch via palm swipe velocity
    │
    └── Menu Interaction Mode
            RadialMenu  (Pygame)
            • holographic HUD rendered on webcam feed
            • pinch dwell selection with progress ring
            • 6-second cooldown after each selection
            Actions  (subprocess / webbrowser)
            • cross-platform app launching
    │
    ▼
Screen output  🖥️  +  OS mouse / keyboard actions  🖱️⌨️
```

---

## Configuration

All tuning constants are at the top of their respective files:

### `main.py`
| Variable | Default | Description |
|----------|---------|-------------|
| `WINDOW_W / WINDOW_H` | `1280 × 720` | Display resolution |
| `TARGET_FPS` | `30` | Target frame rate |
| `CAM_INDEX` | `0` | Webcam device index |
| `MIRROR_CAM` | `True` | Flip camera horizontally |
| `PINCH_DWELL_S` | `0.45` | Seconds to hold pinch before menu selection fires |
| `POST_SELECT_COOLDOWN_S` | `6.0` | Lockout after a menu selection |
| `PALM_OPEN_DEBOUNCE` | `6` | Frames of open palm needed to open menu |

### `desktop_controls.py`
| Variable | Default | Description |
|----------|---------|-------------|
| `CURSOR_SENSITIVITY` | `2.0` | Hand movement amplification (1.0 = 1:1) |
| `CURSOR_SMOOTHING` | `0.35` | EMA smoothing factor (lower = smoother) |
| `SCROLL_THRESHOLD_PX` | `8` | Min finger movement to trigger scroll |
| `SCROLL_AMOUNT` | `3` | Scroll units per tick |
| `SWIPE_VELOCITY_PX` | `55` | Palm speed needed for desktop switch |
| `SWIPE_BLOCKS_MENU_S` | `1.5` | Seconds menu is blocked after a swipe |

---

## Tips for Best Results

- Keep your hand **30–60 cm** from the webcam
- Use **good lighting** — it dramatically improves detection accuracy
- Watch the **bottom-left HUD** — it shows your current detected gesture in real time
- Perform gestures **slowly and deliberately**, especially pinch
- After launching an app, wait for the **red COOLDOWN timer** to expire before selecting again
- If desktop switching accidentally opens the menu, increase `SWIPE_BLOCKS_MENU_S`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Webcam not found | Change `CAM_INDEX = 1` (or `2`) in `main.py` |
| `AttributeError: 'MessageFactory'` | `pip install protobuf==3.20.3` |
| Blender not opening | Set the full path in `actions.py` → `open_blender()` |
| Cursor moves too slowly | Increase `CURSOR_SENSITIVITY` in `desktop_controls.py` |
| Menu opens during swipe | Increase `SWIPE_BLOCKS_MENU_S` in `desktop_controls.py` |
| App launches multiple times | Increase `POST_SELECT_COOLDOWN_S` in `main.py` |
| Low FPS / laggy | Lower `WINDOW_W / WINDOW_H` in `main.py` |
| Gestures not recognised | Ensure good lighting; re-check hand distance from camera |

---

## Requirements

```
opencv-python>=4.8.0
mediapipe==0.10.9
pygame>=2.5.0
numpy>=1.24.0
pyautogui>=0.9.54
protobuf==3.20.3
```

---

## About

HoloDesk is a Python computer-vision project that turns your webcam into a futuristic gesture controller. Using MediaPipe for hand tracking and Pygame for the holographic UI, it lets you operate your entire desktop — cursor, clicks, scrolling, virtual desktops, and app launching — using only hand gestures, with no physical input device required.

---

## Contributors

**Arnav Upadhyay** — [@Arn5v89033innovator](https://github.com/Arn5v89033innovator)

---

## Languages

![Python](https://img.shields.io/badge/Python-100%25-blue?logo=python)

---

*Built with OpenCV · MediaPipe · Pygame · PyAutoGUI*
