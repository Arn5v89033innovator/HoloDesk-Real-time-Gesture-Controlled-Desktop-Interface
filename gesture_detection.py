"""
gesture_detection.py
====================
Classifies hand gestures from MediaPipe landmark data.

Gestures detected:
  OPEN_PALM   -> all 4 fingers extended           -> open menu
  POINTING    -> only index finger up              -> move cursor / hover
  PINCH       -> thumb + index tip close           -> click / select / drag
  FOUR_FINGER -> 4 fingers extended + horizontal   -> desktop switch (swipe)
  FIST        -> all fingers closed                -> close menu
  NONE        -> transitional / unknown

Priority order inside _classify():
  1. PINCH       (thumb-index distance, highest priority)
  2. OPEN_PALM   (all 4 up)
  3. FOUR_FINGER (all 4 up but detected before OPEN_PALM collapses — same
                  raw state; swipe direction resolved in desktop_controls)
  4. POINTING    (index only)
  5. FIST        (nothing up)
  6. NONE

NOTE: FOUR_FINGER and OPEN_PALM share the same finger-extension state.
      They are distinguished in desktop_controls.py by tracking horizontal
      hand velocity — a fast sideways swipe triggers FOUR_FINGER logic.
"""

import math
from enum import Enum, auto
from hand_tracking import HandTracker


class Gesture(Enum):
    NONE        = auto()
    OPEN_PALM   = auto()
    POINTING    = auto()
    FOUR_FINGER = auto()   # 4 fingers up + swipe detected externally
    PINCH       = auto()
    FIST        = auto()


# ── Helpers ───────────────────────────────────────────────────────────
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _finger_extended(lm_list, tip_idx, mcp_idx, pip_idx):
    """True when fingertip is farther from wrist than the PIP joint."""
    wrist = lm_list[HandTracker.WRIST]
    tip   = lm_list[tip_idx]
    pip   = lm_list[pip_idx]
    return _dist(tip, wrist) > _dist(pip, wrist)


# ── Detector ──────────────────────────────────────────────────────────
class GestureDetector:
    """
    Stateful gesture classifier with debounce hysteresis.
    Requires DEBOUNCE_FRAMES consecutive matching frames before
    confirming a gesture change, preventing rapid flicker.
    """

    PINCH_THRESHOLD = 0.07   # normalised thumb-to-index distance
    DEBOUNCE_FRAMES = 4      # frames needed to confirm a new gesture

    def __init__(self):
        self._candidate       = Gesture.NONE
        self._candidate_count = 0
        self.current          = Gesture.NONE

    def update(self, tracker) -> "Gesture":
        """Call once per frame after tracker.process()."""
        raw = self._classify(tracker)
        if raw == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate       = raw
            self._candidate_count = 1
        if self._candidate_count >= self.DEBOUNCE_FRAMES:
            self.current = self._candidate
        return self.current

    def _classify(self, tracker) -> "Gesture":
        if not tracker.detected or len(tracker.lm_list) < 21:
            return Gesture.NONE

        lm = tracker.lm_list

        # 1. Pinch (highest priority — checked before anything else)
        if _dist(lm[HandTracker.THUMB_TIP], lm[HandTracker.INDEX_TIP]) < self.PINCH_THRESHOLD:
            return Gesture.PINCH

        # 2. Finger extension flags
        #    PIP joints: index=6, middle=10, ring=14, pinky=18
        idx_up   = _finger_extended(lm, 8,  5,  6)
        mid_up   = _finger_extended(lm, 12, 9,  10)
        ring_up  = _finger_extended(lm, 16, 13, 14)
        pinky_up = _finger_extended(lm, 20, 17, 18)
        n_up     = sum([idx_up, mid_up, ring_up, pinky_up])

        # 3. All 4 fingers up -> OPEN_PALM
        #    (FOUR_FINGER swipe is resolved in desktop_controls from velocity)
        if n_up == 4:
            return Gesture.OPEN_PALM

        # 4. Only index finger up -> POINTING
        if idx_up and not mid_up and not ring_up and not pinky_up:
            return Gesture.POINTING

        # 5. No fingers up -> FIST
        if n_up == 0:
            return Gesture.FIST

        return Gesture.NONE

    # Convenience properties
    @property
    def is_pinch(self):      return self.current == Gesture.PINCH
    @property
    def is_open_palm(self):  return self.current == Gesture.OPEN_PALM
    @property
    def is_pointing(self):   return self.current in (Gesture.POINTING,
                                                      Gesture.OPEN_PALM)
    @property
    def is_fist(self):       return self.current == Gesture.FIST
