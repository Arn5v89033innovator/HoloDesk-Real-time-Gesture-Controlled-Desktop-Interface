"""
hand_tracking.py
================
Handles MediaPipe hand tracking, landmark extraction,
and provides normalized + screen-space coordinates.
"""

import cv2
import mediapipe as mp
import numpy as np


class HandTracker:
    """Wraps MediaPipe Hands for real-time hand tracking."""

    # Landmark indices (MediaPipe convention)
    WRIST       = 0
    THUMB_TIP   = 4
    INDEX_TIP   = 8
    INDEX_MCP   = 5   # index finger base knuckle
    MIDDLE_TIP  = 12
    RING_TIP    = 16
    PINKY_TIP   = 20
    MIDDLE_MCP  = 9
    RING_MCP    = 13
    PINKY_MCP   = 17

    def __init__(self, max_hands: int = 1, detection_conf: float = 0.7,
                 tracking_conf: float = 0.6):
        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=detection_conf,
            min_tracking_confidence=tracking_conf,
        )
        self._mp_draw = mp.solutions.drawing_utils
        self._draw_style = mp.solutions.drawing_styles

        # Latest results
        self.landmarks = None       # raw mediapipe NormalizedLandmarkList
        self.lm_list: list = []     # [(x_norm, y_norm, z_norm), ...]
        self.detected: bool = False

    # ------------------------------------------------------------------
    def process(self, frame_bgr: np.ndarray) -> np.ndarray:
        """
        Run hand detection on a BGR frame.
        Returns the annotated frame (RGB-safe for pygame).
        """
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        self.lm_list = []
        self.detected = False
        self.landmarks = None

        if results.multi_hand_landmarks:
            self.detected = True
            # Track only the first hand
            hand_lm = results.multi_hand_landmarks[0]
            self.landmarks = hand_lm
            for lm in hand_lm.landmark:
                self.lm_list.append((lm.x, lm.y, lm.z))

        return frame_bgr

    # ------------------------------------------------------------------
    def get_landmark_px(self, idx: int, frame_w: int, frame_h: int
                        ) -> tuple[int, int] | None:
        """Return (x_px, y_px) of landmark `idx` in pixel space."""
        if not self.lm_list or idx >= len(self.lm_list):
            return None
        x, y, _ = self.lm_list[idx]
        return int(x * frame_w), int(y * frame_h)

    # ------------------------------------------------------------------
    def get_all_landmarks_px(self, frame_w: int, frame_h: int
                              ) -> list[tuple[int, int]]:
        """Return all landmarks as pixel tuples."""
        return [
            (int(x * frame_w), int(y * frame_h))
            for x, y, _ in self.lm_list
        ]

    # ------------------------------------------------------------------
    def fingertip_position(self, frame_w: int, frame_h: int
                           ) -> tuple[int, int] | None:
        """Pixel position of index fingertip."""
        return self.get_landmark_px(self.INDEX_TIP, frame_w, frame_h)

    # ------------------------------------------------------------------
    def draw_landmarks(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Draw skeleton on frame (for debug view)."""
        if self.landmarks:
            self._mp_draw.draw_landmarks(
                frame_bgr,
                self.landmarks,
                self._mp_hands.HAND_CONNECTIONS,
                self._draw_style.get_default_hand_landmarks_style(),
                self._draw_style.get_default_hand_connections_style(),
            )
        return frame_bgr
