# HoloDesk — Gesture Controlled Desktop Interface

> *Tony Stark–style holographic interface controlled entirely by hand gestures.*

---

## ✦ Demo Overview

When you raise an **open palm** in front of your webcam, a glowing radial menu
materialises around your hand. Point your **index finger** to hover over options.
Perform a **pinch gesture** (hold for ~0.35 s) to launch an app. Make a **fist**
to dismiss the menu.

---

## ✦ Requirements

| Requirement     | Version       |
|-----------------|---------------|
| Python          | ≥ 3.10        |
| Webcam          | Any USB / built-in |
| OS              | Windows / macOS / Linux |

---

## ✦ Installation

```bash
# 1. Clone or download the project
cd holodesk

# 2. (Recommended) Create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

> **Linux users:** if pygame audio gives errors, install:
> `sudo apt install python3-pygame libsdl2-dev`

---

## ✦ Running the Program

```bash
python main.py
```

Press **Q** or **ESC** to quit at any time.

---

## ✦ Gesture Reference

| Gesture          | Effect                          |
|------------------|---------------------------------|
| 🖐 Open Palm      | Open / keep the menu active     |
| ☝ Index Finger   | Hover over menu options         |
| 🤏 Pinch (hold)  | Select the highlighted option   |
| ✊ Fist           | Close the menu                  |

---

## ✦ Menu Options

| Option      | Action                                 |
|-------------|----------------------------------------|
| 🌐 Browser   | Opens Google Chrome (default browser)  |
| 🎵 Music     | Opens system music player              |
| 📁 Files     | Opens file explorer / Finder           |
| 🔢 Calculator| Opens system calculator                |
| 🌀 Blender   | Launches Blender 3D                    |
| ⚙ Settings  | Opens system settings                  |

---

## ✦ Project Structure

```
holodesk/
├── main.py               ← Entry point & main loop
├── hand_tracking.py      ← MediaPipe hand landmark wrapper
├── gesture_detection.py  ← Gesture classifier (palm/pinch/fist/point)
├── menu_ui.py            ← Holographic radial menu renderer (Pygame)
├── actions.py            ← System actions (open apps)
├── utils.py              ← Math helpers, easing, smooth values
├── requirements.txt
└── README.md
```

---

## ✦ Configuration

Edit `main.py` to change:

| Variable         | Default | Description                         |
|------------------|---------|-------------------------------------|
| `WINDOW_W/H`     | 1280×720| Display resolution                  |
| `TARGET_FPS`     | 30      | Target frame rate                   |
| `CAM_INDEX`      | 0       | Webcam device index                 |
| `MIRROR_CAM`     | True    | Flip image horizontally             |
| `PINCH_DWELL_S`  | 0.35    | Seconds to hold pinch for selection |

Edit `actions.py` to remap menu options to any commands you like.

---

## ✦ Tips for Best Results

* **Good lighting** dramatically improves hand detection accuracy.
* Keep your hand **30–70 cm** from the webcam.
* Perform gestures **slowly and deliberately** — the debounce filter needs ~4 frames.
* If the menu drifts, re-raise your open palm to re-anchor it.

---

## ✦ Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot open webcam` | Change `CAM_INDEX = 1` (or 2) in `main.py` |
| Laggy / low FPS | Lower `WINDOW_W/H` or reduce `max_hands` |
| App not launching | Check the app is installed; edit `actions.py` |
| Pinch not registering | Adjust `PINCH_THRESHOLD` in `gesture_detection.py` |

---

*Built with OpenCV · MediaPipe · Pygame . Made by Arnav Upadhyay*
