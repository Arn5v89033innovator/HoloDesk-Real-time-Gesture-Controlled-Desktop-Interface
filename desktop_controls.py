"""
desktop_controls.py
===================
Handles all desktop-control gestures when the holographic menu is CLOSED.

Gesture → Action mapping
─────────────────────────────────────────────────────────────────────────
POINTING          → move mouse cursor (smoothed)
PINCH  (short)    → left click
PINCH  (+ move)   → drag window / object
OPEN_PALM + swipe → four-finger desktop switch  (Ctrl+Win+Left / Right)
POINTING + v-move → vertical swipe scroll       (pyautogui.scroll)

Design notes
────────────────────────────────────────────────────────────────────────
- All cursor movement uses an exponential moving-average SmoothPoint to
  eliminate MediaPipe jitter without introducing excessive lag.
- Scroll is triggered by measuring vertical velocity of the index finger
  between frames, not by a separate two-finger gesture.
- Desktop switching detects a fast horizontal velocity of the PALM while
  the hand is open (OPEN_PALM), so it does not conflict with the menu-
  open gesture (which fires after PALM_OPEN_DEBOUNCE stable frames).
- After a swipe fires, SWIPE_BLOCKS_MENU_S prevents the menu from
  accidentally opening due to the still-open palm.
"""

import time
import math
import pyautogui
from utils import SmoothPoint

# Suppress pyautogui's built-in delay
pyautogui.PAUSE     = 0
pyautogui.FAILSAFE  = False


# ── Tuning constants ──────────────────────────────────────────────────
CURSOR_SMOOTHING      = 0.35   # EMA factor: lower = smoother, more lag
DRAG_SMOOTHING        = 0.30
DRAG_START_DIST_PX    = 14     # px hand must move before drag engages
CLICK_COOLDOWN_S      = 0.45   # min time between clicks

CURSOR_SENSITIVITY    = 8.0    # amplify hand movement (1.0 = normal, 2.0 = double)

# Scroll via vertical index-finger movement
SCROLL_THRESHOLD_PX   = 8     # minimum px/frame to trigger a scroll tick
SCROLL_AMOUNT         = 3     # pyautogui scroll units per tick
SCROLL_COOLDOWN_S     = 0.08  # max scroll rate (~12 ticks/sec)

# Four-finger desktop swipe
SWIPE_VELOCITY_PX     = 55    # px/frame palm must travel horizontally
SWIPE_COOLDOWN_S      = 1.2   # lockout after a desktop switch fires
SWIPE_BLOCKS_MENU_S   = 1.5   # blocks menu from opening after a swipe fires


class DesktopController:
    """
    Translates smoothed hand positions into real OS mouse/keyboard actions.
    Call update() once per frame with current gesture + positions.
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # ── Cursor ────────────────────────────────────────────────────
        self._cursor = SmoothPoint(screen_w // 2, screen_h // 2,
                                   smoothing=CURSOR_SMOOTHING)

        # ── Click / drag ──────────────────────────────────────────────
        self._pinch_was_active  = False
        self._last_click_time   = 0.0
        self._dragging          = False
        self._drag_origin       = None
        self._drag_cursor       = SmoothPoint(smoothing=DRAG_SMOOTHING)

        # ── Vertical scroll ───────────────────────────────────────────
        self._prev_finger_y     = None
        self._last_scroll_time  = 0.0

        # ── Four-finger desktop switch ────────────────────────────────
        self._prev_palm_x       = None
        self._last_swipe_time   = 0.0
        self._swipe_armed       = False
        self._palm_stable_count = 0
        self._swipe_just_fired  = False   # blocks menu after swipe
        self._swipe_fired_time  = 0.0

    # ── Public API ────────────────────────────────────────────────────
    def update(self, gesture_name: str,
               finger_screen: tuple | None,
               palm_screen:   tuple | None):
        """
        Call every frame.

        Parameters
        ----------
        gesture_name   : Gesture.name string ("POINTING", "PINCH", ...)
        finger_screen  : (x, y) index fingertip in window pixel coords
        palm_screen    : (x, y) palm centre in window pixel coords
        """

        now = time.perf_counter()

        # ── 1. Four-finger desktop switch (OPEN_PALM + fast sideways) ──
        if gesture_name == "OPEN_PALM" and palm_screen:
            self._handle_desktop_switch(palm_screen, now)
        else:
            self._prev_palm_x       = None
            self._swipe_armed       = False
            self._palm_stable_count = 0

        # ── 2. Cursor movement (POINTING only) with sensitivity ────────
        if gesture_name == "POINTING" and finger_screen:
            cx = self.screen_w // 2
            cy = self.screen_h // 2
            ax = cx + (finger_screen[0] - cx) * CURSOR_SENSITIVITY
            ay = cy + (finger_screen[1] - cy) * CURSOR_SENSITIVITY
            ax = max(0, min(self.screen_w,  int(ax)))
            ay = max(0, min(self.screen_h, int(ay)))
            sx, sy = self._cursor.update(ax, ay)
            pyautogui.moveTo(int(sx), int(sy))

        # ── 3. Pinch → click or drag ──────────────────────────────────
        pinch_active = (gesture_name == "PINCH")
        if pinch_active and finger_screen:
            if not self._pinch_was_active:
                self._drag_origin = finger_screen
                self._drag_cursor.x.value = finger_screen[0]
                self._drag_cursor.y.value = finger_screen[1]

            if self._drag_origin:
                dist = math.hypot(finger_screen[0] - self._drag_origin[0],
                                  finger_screen[1] - self._drag_origin[1])
                if dist > DRAG_START_DIST_PX and not self._dragging:
                    self._dragging = True
                    pyautogui.mouseDown()

            if self._dragging:
                dx, dy = self._drag_cursor.update(*finger_screen)
                pyautogui.moveTo(int(dx), int(dy))
        else:
            if self._dragging:
                pyautogui.mouseUp()
                self._dragging = False
            elif self._pinch_was_active:
                if now - self._last_click_time >= CLICK_COOLDOWN_S:
                    pyautogui.click()
                    self._last_click_time = now
            self._drag_origin = None

        self._pinch_was_active = pinch_active

        # ── 4. Vertical swipe scroll (POINTING + vertical movement) ───
        if gesture_name == "POINTING" and finger_screen:
            self._handle_scroll(finger_screen[1], now)
        else:
            self._prev_finger_y = None

    # ── Internals ─────────────────────────────────────────────────────
    def _handle_desktop_switch(self, palm_screen: tuple, now: float):
        """
        Detect a fast horizontal swipe of an open palm and fire
        Ctrl+Win+Left/Right to switch Windows virtual desktops.
        """
        px = palm_screen[0]

        if self._prev_palm_x is None:
            self._prev_palm_x       = px
            self._swipe_armed       = True
            self._palm_stable_count = 0
            return

        velocity = px - self._prev_palm_x
        self._prev_palm_x = px

        if abs(velocity) < 5:
            self._palm_stable_count += 1
        else:
            self._palm_stable_count = 0

        if self._palm_stable_count > 8:
            self._swipe_armed = True

        if not self._swipe_armed:
            return

        if now - self._last_swipe_time < SWIPE_COOLDOWN_S:
            return

        if velocity > SWIPE_VELOCITY_PX:
            pyautogui.hotkey("ctrl", "win", "right")
            self._last_swipe_time   = now
            self._swipe_armed       = False
            self._palm_stable_count = 0
            self._swipe_fired_time  = now
            self._swipe_just_fired  = True

        elif velocity < -SWIPE_VELOCITY_PX:
            pyautogui.hotkey("ctrl", "win", "left")
            self._last_swipe_time   = now
            self._swipe_armed       = False
            self._palm_stable_count = 0
            self._swipe_fired_time  = now
            self._swipe_just_fired  = True

    def _handle_scroll(self, finger_y: float, now: float):
        """
        Scroll based on vertical velocity of the index fingertip.
        Finger moves UP   → scroll page DOWN
        Finger moves DOWN → scroll page UP
        """
        if self._prev_finger_y is None:
            self._prev_finger_y = finger_y
            return

        delta = finger_y - self._prev_finger_y
        self._prev_finger_y = finger_y

        if abs(delta) < SCROLL_THRESHOLD_PX:
            return

        if now - self._last_scroll_time < SCROLL_COOLDOWN_S:
            return

        direction = 1 if delta > 0 else -1
        pyautogui.scroll(direction * SCROLL_AMOUNT)
        self._last_scroll_time = now

    def swipe_recently_fired(self) -> bool:
        """
        Returns True if a desktop swipe fired recently.
        main.py calls this to block the menu from opening
        immediately after a swipe gesture.
        """
        if self._swipe_just_fired:
            if time.perf_counter() - self._swipe_fired_time < SWIPE_BLOCKS_MENU_S:
                return True
            self._swipe_just_fired = False
        return False

    def release_all(self):
        """Call when switching away from Desktop Mode to clean up state."""
        if self._dragging:
            pyautogui.mouseUp()
            self._dragging = False
        self._pinch_was_active  = False
        self._drag_origin       = None
        self._prev_finger_y     = None
        self._prev_palm_x       = None
        self._swipe_armed       = False
        self._palm_stable_count = 0
        self._swipe_just_fired  = False