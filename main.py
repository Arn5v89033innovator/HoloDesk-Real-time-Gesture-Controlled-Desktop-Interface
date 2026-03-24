"""
main.py
=======
HoloDesk – Gesture Controlled Desktop Interface
------------------------------------------------
MODE-BASED GESTURE SYSTEM
--------------------------
The program runs in one of two modes at all times:

  ┌─────────────────────────────────────────────────────────┐
  │  DESKTOP CONTROL MODE  (menu_open = False)              │
  │  ─────────────────────────────────────────────────────  │
  │  • POINTING        → move mouse cursor                  │
  │  • PINCH           → left click  (or drag if moved)     │
  │  • POINTING+swipe  → vertical scroll                     │
  │  • OPEN_PALM+swipe → 4-finger desktop switch              │
  │  • OPEN_PALM       → switch to Menu Interaction Mode    │
  └─────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────┐
  │  MENU INTERACTION MODE  (menu_open = True)              │
  │  ─────────────────────────────────────────────────────  │
  │  • POINTING        → hover over radial menu items       │
  │  • PINCH + dwell   → select highlighted menu item       │
  │  • FIST            → close menu → Desktop Control Mode  │
  └─────────────────────────────────────────────────────────┘

Gesture priority:
  1. OPEN_PALM  → always activates menu (from either mode)
  2. menu_open? → route to handle_menu_gestures()
  3. else       → route to handle_desktop_gestures()

Run:
    python main.py

Keys:
    Q / ESC  → quit
    M        → manually toggle menu (for testing)
"""

import sys
import time
import math
import logging
import cv2
import numpy as np
import pygame

# Local modules
from hand_tracking     import HandTracker
from gesture_detection import GestureDetector, Gesture
from menu_ui           import RadialMenu, OverlayRenderer
from desktop_controls  import DesktopController
from actions           import execute
from utils             import Timer

# ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("holodesk.main")

# ──────────────────────────────────────────────────────────────────────
# ── Top-level config  (edit these to tune behaviour) ─────────────────

WINDOW_W      = 1280
WINDOW_H      = 720
TARGET_FPS    = 30
CAM_INDEX     = 0        # change if webcam is not device 0
MIRROR_CAM    = True     # flip image so it feels like a mirror

# How long to hold a pinch before a menu selection fires (seconds)
PINCH_DWELL_S = 0.45

# After firing a menu selection, block further selections for this long
POST_SELECT_COOLDOWN_S = 6.0

# How many consecutive frames OPEN_PALM must be seen before menu opens
# (prevents accidental opens mid-gesture)
PALM_OPEN_DEBOUNCE = 6


# ──────────────────────────────────────────────────────────────────────
def numpy_to_pygame(frame_bgr: np.ndarray,
                    target_w: int, target_h: int) -> pygame.Surface:
    """Convert an OpenCV BGR frame to a Pygame Surface at target size."""
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = cv2.resize(frame_rgb, (target_w, target_h))
    return pygame.surfarray.make_surface(np.transpose(frame_rgb, (1, 0, 2)))


# ──────────────────────────────────────────────────────────────────────
def draw_mode_banner(screen: pygame.Surface, menu_open: bool,
                     font: pygame.font.Font):
    """
    Top-centre banner that always shows the active mode.
    Green = Desktop Mode   Cyan = Menu Mode
    """
    if menu_open:
        label = "  MENU MODE  —  point to hover  |  pinch to select  |  fist to close  "
        color = (0, 220, 255)
        bg    = (0, 30, 60, 190)
    else:
        label = "  DESKTOP MODE  —  point=cursor  |  pinch=click  |  swipe=scroll  |  palm-swipe=desktop  |  palm=menu  "
        color = (0, 255, 160)
        bg    = (0, 50, 25, 190)

    text_surf = font.render(label, True, color)
    tw = text_surf.get_width() + 24
    th = text_surf.get_height() + 10
    banner = pygame.Surface((tw, th), pygame.SRCALPHA)
    banner.fill(bg)
    pygame.draw.rect(banner, (*color, 140), (0, 0, tw, th), 1)
    banner.blit(text_surf, (12, 5))
    screen.blit(banner, (WINDOW_W // 2 - tw // 2, 10))


def draw_hud_info(screen: pygame.Surface, fps: float,
                  gesture: Gesture, hand_detected: bool,
                  menu_open: bool, font: pygame.font.Font,
                  cooldown_remaining: float = 0.0):
    """Bottom-left HUD: fps / hand state / gesture / mode / cooldown."""
    lines = [
        f"FPS:     {fps:5.1f}",
        f"HAND:    {'YES' if hand_detected else 'NO '}",
        f"GESTURE: {gesture.name}",
        f"MODE:    {'MENU' if menu_open else 'DESKTOP'}",
    ]
    if cooldown_remaining > 0:
        lines.append(f"COOLDOWN:{cooldown_remaining:.1f}s")

    y = WINDOW_H - 14 * len(lines) - 8
    for line in lines:
        color = (220, 80, 60) if "COOLDOWN" in line else (0, 140, 160)
        surf = font.render(line, True, color)
        screen.blit(surf, (10, y))
        y += 14


def draw_desktop_cursor(screen: pygame.Surface,
                        finger_screen: tuple | None):
    """
    In Desktop Mode, show a bright green crosshair at the fingertip
    so the user can see exactly where the mouse cursor will move.
    """
    if finger_screen is None:
        return
    fx, fy = finger_screen
    color  = (0, 255, 160)

    # Soft glow rings
    glow = pygame.Surface((64, 64), pygame.SRCALPHA)
    for r, a in [(26, 25), (20, 55), (14, 90), (8, 130)]:
        pygame.draw.circle(glow, (*color, a), (32, 32), r, 1)
    screen.blit(glow, (fx - 32, fy - 32))

    # Crosshair lines
    pygame.draw.line(screen, (*color, 200), (fx - 14, fy), (fx + 14, fy), 1)
    pygame.draw.line(screen, (*color, 200), (fx, fy - 14), (fx, fy + 14), 1)

    # Centre dot
    pygame.draw.circle(screen, color, (fx, fy), 4)
    pygame.draw.circle(screen, (220, 255, 235), (fx, fy), 2)


# ──────────────────────────────────────────────────────────────────────
def handle_desktop_gestures(gesture: Gesture,
                             finger_screen: tuple | None,
                             palm_pos: tuple | None,
                             desktop: DesktopController) -> bool:
    """
    DESKTOP CONTROL MODE — translate gestures into OS mouse actions.

    Gesture mapping:
      POINTING   → move mouse cursor to fingertip position
      PINCH      → click (short) or drag (pinch + move)
      POINTING + vertical movement → vertical scroll
      OPEN_PALM + horizontal swipe → desktop switch
      OPEN_PALM  → (handled by caller) open menu

    Returns True if OPEN_PALM detected and caller should open menu.
    """
    if gesture == Gesture.OPEN_PALM:
        desktop.release_all()
        return True   # signal to open menu

    desktop.update(
        gesture_name  = gesture.name,
        finger_screen = finger_screen,
        palm_screen   = palm_pos,
    )
    return False


def handle_menu_gestures(gesture: Gesture,
                          finger_screen: tuple | None,
                          palm_pos: tuple | None,
                          menu: RadialMenu,
                          pinch_state: dict,
                          dt: float) -> bool:
    """
    MENU INTERACTION MODE — control the radial holographic menu.

    Gesture mapping:
      POINTING   → hover over menu items (menu.hovered_idx updates autoed menu item after PINCH_DWELL_S seconds
      FIST       → close menu, return to Desktop Mode

    pinch_state keys: dwelling, timer, last_matically)
      PINCH+hold → select the hoveridx,
                      in_cooldown, cooldown_timer, was_active

    Returns True if FIST detected and caller should close menu.
    """

    # Keep menu anchored to palm position
    if palm_pos:
        menu.set_anchor(palm_pos)

    # FIST → close menu
    if gesture == Gesture.FIST:
        return True

    ps = pinch_state

    # Tick down the post-selection cooldown
    if ps["in_cooldown"] and ps["cooldown_timer"].elapsed() >= POST_SELECT_COOLDOWN_S:
        ps["in_cooldown"] = False

    # Track pinch release so we require a fresh pinch after each selection
    pinch_now = (gesture == Gesture.PINCH)
    if not pinch_now:
        ps["was_active"] = False   # pinch released → can arm again

    # Only process pinch when: actively pinching, cooldown over, fresh pinch
    if pinch_now and not ps["in_cooldown"] and not ps["was_active"]:
        if not ps["dwelling"]:
            # Start dwell timer on this menu item
            ps["dwelling"] = True
            ps["timer"].reset()
            ps["last_idx"] = menu.hovered_idx
        else:
            if menu.hovered_idx != ps["last_idx"]:
                # Finger moved to a different item — restart dwell
                ps["timer"].reset()
                ps["last_idx"] = menu.hovered_idx
            elif ps["timer"].elapsed() >= PINCH_DWELL_S:
                # Dwell complete → fire selection
                idx = menu.hovered_idx
                items = _menu_items()
                if 0 <= idx < len(items):
                    item_name = items[idx]
                    logger.info("MENU SELECT: %s  (cooldown %.0fs)",
                                item_name, POST_SELECT_COOLDOWN_S)
                    menu.trigger_ripple(idx)
                    execute(item_name)
                # Lock out until cooldown expires AND pinch is released
                ps["dwelling"]        = False
                ps["last_idx"]        = -1
                ps["in_cooldown"]     = True
                ps["was_active"]      = True
                ps["cooldown_timer"].reset()
    else:
        if not pinch_now:
            ps["dwelling"] = False

    return False   # menu stays open


# ──────────────────────────────────────────────────────────────────────
def _draw_pinch_progress(screen: pygame.Surface, elapsed: float,
                          total: float, pos: tuple | None):
    """Circular fill arc around fingertip showing pinch dwell progress."""
    if pos is None:
        return
    t  = min(1.0, elapsed / total)
    cx, cy = pos
    r  = 24
    surf = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
    pygame.draw.circle(surf, (0, 200, 255, 35), (r + 3, r + 3), r, 3)
    steps = max(3, int(t * 48))
    pts   = [(r + 3, r + 3)]
    for i in range(steps + 1):
        a = math.radians(-90 + 360 * t * i / steps)
        pts.append((r + 3 + r * math.cos(a), r + 3 + r * math.sin(a)))
    if len(pts) >= 3:
        pygame.draw.polygon(surf, (0, 255, 200, 130), pts)
    screen.blit(surf, (cx - r - 3, cy - r - 3))


def _menu_items() -> list:
    """Ordered menu item names — must match RadialMenu.MENU_ITEMS order."""
    from menu_ui import MENU_ITEMS
    return MENU_ITEMS


# ──────────────────────────────────────────────────────────────────────
def main():
    # ── Pygame init ───────────────────────────────────────────────────
    pygame.init()
    screen = pygame.display.set_mode(
        (WINDOW_W, WINDOW_H), pygame.DOUBLEBUF | pygame.HWSURFACE
    )
    pygame.display.set_caption("HoloDesk  ·  Gesture Interface")
    clock = pygame.time.Clock()

    hud_font    = pygame.font.SysFont("consolas,monospace", 11)
    banner_font = pygame.font.SysFont("consolas,monospace", 12, bold=True)

    # ── OpenCV webcam ─────────────────────────────────────────────────
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        logger.error("Cannot open webcam (index %d). "
                     "Change CAM_INDEX in main.py.", CAM_INDEX)
        pygame.quit()
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WINDOW_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WINDOW_H)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    # ── Core objects ──────────────────────────────────────────────────
    tracker  = HandTracker(max_hands=1)
    detector = GestureDetector()
    menu     = RadialMenu(WINDOW_W, WINDOW_H)
    overlay  = OverlayRenderer(WINDOW_W, WINDOW_H)
    desktop  = DesktopController(WINDOW_W, WINDOW_H)

    # ── MODE STATE ────────────────────────────────────────────────────
    # This boolean drives ALL gesture routing in the main loop.
    #   False → Desktop Control Mode
    #   True  → Menu Interaction Mode
    menu_open = False

    # Debounce: OPEN_PALM must be seen this many frames before mode switches
    palm_frame_count = 0

    # ── Pinch state (shared dict so handle_menu_gestures can mutate it) ─
    pinch_state = {
        "dwelling"      : False,   # currently dwelling on a menu item
        "timer"         : Timer(), # dwell timer
        "last_idx"      : -1,      # item index when dwell started
        "in_cooldown"   : False,   # locked out after a selection
        "cooldown_timer": Timer(), # cooldown timer
        "was_active"    : True,    # True forces a pinch release before re-arm
    }

    # ── Timing ────────────────────────────────────────────────────────
    prev_time = time.perf_counter()
    fps       = 0.0

    logger.info("HoloDesk ready.")
    logger.info("DESKTOP MODE: point=cursor | pinch=click | swipe=scroll | palm-swipe=desktop-switch | palm=menu")

    # ──────────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────────
    running = True
    while running:

        # ── System events ─────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_m:
                    # Manual toggle for testing / debugging
                    menu_open = not menu_open
                    if menu_open:
                        menu.open((WINDOW_W // 2, WINDOW_H // 2))
                        desktop.release_all()
                        logger.info("[M] → MENU MODE")
                    else:
                        menu.close()
                        logger.info("[M] → DESKTOP MODE")

        # ── Frame timing ──────────────────────────────────────────────
        now       = time.perf_counter()
        dt        = now - prev_time
        prev_time = now
        fps       = 0.9 * fps + 0.1 * (1.0 / max(dt, 1e-6))

        # ── Webcam capture ────────────────────────────────────────────
        ret, frame = cap.read()
        if not ret:
            logger.warning("Empty webcam frame — skipping.")
            continue
        if MIRROR_CAM:
            frame = cv2.flip(frame, 1)

        # ── Hand tracking ─────────────────────────────────────────────
        tracker.process(frame)
        gesture = detector.update(tracker)

        # Scale hand coordinates to window size
        cam_h, cam_w = frame.shape[:2]
        sx = WINDOW_W / cam_w
        sy = WINDOW_H / cam_h

        # Index fingertip position in screen space
        fp = tracker.fingertip_position(cam_w, cam_h)
        finger_screen = (int(fp[0] * sx), int(fp[1] * sy)) if fp else None

        # Palm centre in screen space (used to anchor the menu)
        palm_pos = None
        if tracker.detected:
            w_px = tracker.get_landmark_px(0, cam_w, cam_h)   # wrist
            m_px = tracker.get_landmark_px(9, cam_w, cam_h)   # middle MCP
            if w_px and m_px:
                palm_pos = (
                    int((w_px[0] + m_px[0]) / 2 * sx),
                    int((w_px[1] + m_px[1]) / 2 * sy),
                )

        # (scroll handled inside DesktopController via finger Y velocity)

        # ──────────────────────────────────────────────────────────────
        # GESTURE PRIORITY & MODE ROUTING
        # ──────────────────────────────────────────────────────────────
        #
        # Step 1 — Count OPEN_PALM frames (debounced menu activation)
        if gesture == Gesture.OPEN_PALM:
            palm_frame_count += 1
        else:
            palm_frame_count = 0

        # Step 2 — If OPEN_PALM held long enough, switch to Menu Mode
        if palm_frame_count >= PALM_OPEN_DEBOUNCE and not menu_open:
            menu_open = True
            menu.open(palm_pos or (WINDOW_W // 2, WINDOW_H // 2))
            desktop.release_all()
            pinch_state["was_active"] = True   # require fresh pinch in menu
            logger.info("→ MENU MODE")

        # Step 3 — Route to the correct mode handler
        if menu_open:
            # ── MENU INTERACTION MODE ──────────────────────────────
            should_close = handle_menu_gestures(
                gesture       = gesture,
                finger_screen = finger_screen,
                palm_pos      = palm_pos,
                menu          = menu,
                pinch_state   = pinch_state,
                dt            = dt,
            )
            if should_close:
                menu_open = False
                menu.close()
                palm_frame_count = 0   # require fresh OPEN_PALM to re-open
                logger.info("→ DESKTOP MODE")
        else:
            # ── DESKTOP CONTROL MODE ───────────────────────────────
            # Skip OPEN_PALM here — it is already handled in Step 2
            if gesture != Gesture.OPEN_PALM:
                handle_desktop_gestures(
                    gesture       = gesture,
                    finger_screen = finger_screen,
                    palm_pos      = palm_pos,
                    desktop       = desktop,
                )

        # Keep menu animation updating every frame
        menu.update(dt, finger_screen if menu_open else None)

        # ──────────────────────────────────────────────────────────────
        # RENDER
        # ──────────────────────────────────────────────────────────────

        # 1. Background
        screen.fill((4, 8, 18))

        # 2. Webcam (darkened)
        cam_surf = numpy_to_pygame(frame, WINDOW_W, WINDOW_H)
        overlay.composite_frame(screen, cam_surf)

        # 3. Mode-specific visuals
        if menu_open:
            # Holographic radial menu + cyan finger cursor
            menu.draw(screen, finger_screen, gesture.name)

            # Pinch dwell progress ring around fingertip
            if pinch_state["dwelling"] and pinch_state["last_idx"] >= 0:
                _draw_pinch_progress(
                    screen,
                    pinch_state["timer"].elapsed(),
                    PINCH_DWELL_S,
                    finger_screen,
                )
        else:
            # Green crosshair cursor in desktop mode
            draw_desktop_cursor(screen, finger_screen)

        # 4. Mode banner (top-centre)
        draw_mode_banner(screen, menu_open, banner_font)

        # 5. HUD (bottom-left)
        cooldown_rem = 0.0
        if pinch_state["in_cooldown"]:
            cooldown_rem = max(
                0.0,
                POST_SELECT_COOLDOWN_S - pinch_state["cooldown_timer"].elapsed()
            )
        draw_hud_info(screen, fps, gesture, tracker.detected,
                      menu_open, hud_font, cooldown_rem)

        pygame.display.flip()
        clock.tick(TARGET_FPS)

    # ── Cleanup ───────────────────────────────────────────────────────
    desktop.release_all()
    cap.release()
    pygame.quit()
    logger.info("HoloDesk closed.")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
