"""
menu_ui.py
==========
Renders the Tony-Stark-style holographic radial menu using Pygame.

Visual design:
  • Deep-space background with scanlines
  • Neon-cyan / electric-blue palette
  • Radial HUD menu with animated arc segments
  • Pulsing ring around hand anchor
  • Glow overlay for selected/hovered items
  • Expansion / collapse animation
  • Pinch-confirmation ripple
"""

import math
import time
import pygame
import pygame.gfxdraw

from utils import (
    ease_out_cubic, ease_in_out, lerp_color, point_on_circle,
    dist2d, angle_between, SmoothPoint, Timer,
)

# ── Palette ─────────────────────────────────────────────────────────
C_BG          = (4,   8,  18)
C_PANEL       = (0,  20,  45)
C_CYAN        = (0, 240, 255)
C_BLUE        = (0, 120, 255)
C_ACCENT      = (0, 180, 220)
C_WHITE       = (220, 240, 255)
C_DIM         = (30,  80, 110)
C_HOVER       = (0, 255, 220)
C_SELECT      = (255, 200,   0)
C_RING        = (0, 200, 255)
C_WARN        = (255,  80,  80)

# Icon glyphs (emoji substitutes rendered as text)
ICON_MAP = {
    "Browser":    "🌐",
    "Music":      "🎵",
    "Files":      "📁",
    "Calculator": "🔢",
    "Blender":    "🌀",
    "Settings":   "⚙",
}

MENU_ITEMS = list(ICON_MAP.keys())
N_ITEMS    = len(MENU_ITEMS)

# Radial layout
MENU_RADIUS       = 160   # px from centre to item midpoint
ITEM_ICON_RADIUS  = 130
ARC_RADIUS        = 175
INNER_RING        = 50
OUTER_RING        = 200


# ──────────────────────────────────────────────────────────────────────
def _glow_surface(radius: int, color: tuple, intensity: float = 0.6
                  ) -> pygame.Surface:
    """Create a radial glow surface."""
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        alpha = int(intensity * 255 * (1 - r / radius) ** 1.5)
        pygame.draw.circle(surf, (*color[:3], alpha), (radius, radius), r)
    return surf


def _draw_glow_circle(surf: pygame.Surface, cx: int, cy: int,
                      r: int, color: tuple, alpha_max: int = 90,
                      width: int = 2):
    """Draw a soft glowing ring."""
    for i in range(5, 0, -1):
        a = int(alpha_max * (i / 5) ** 2)
        s = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color[:3], a), (r + 10, r + 10),
                           r + (5 - i), width + i - 1)
        surf.blit(s, (cx - r - 10, cy - r - 10))


def _draw_arc_segment(surf, cx, cy, r_inner, r_outer,
                      start_deg, end_deg, color, alpha=180):
    """Draw a filled arc segment (pie slice ring)."""
    steps = max(8, int(abs(end_deg - start_deg)))
    pts_outer = []
    pts_inner = []
    for i in range(steps + 1):
        t = i / steps
        a = math.radians(start_deg + t * (end_deg - start_deg))
        pts_outer.append((cx + r_outer * math.cos(a),
                          cy + r_outer * math.sin(a)))
        pts_inner.append((cx + r_inner * math.cos(a),
                          cy + r_inner * math.sin(a)))

    polygon = pts_outer + list(reversed(pts_inner))
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    if len(polygon) >= 3:
        pygame.draw.polygon(s, (*color[:3], alpha), polygon)
        # bright edge
        pygame.draw.lines(s, (*color[:3], 255), False, pts_outer, 1)
        pygame.draw.lines(s, (*color[:3], 100), False, pts_inner, 1)
    surf.blit(s, (0, 0))


# ──────────────────────────────────────────────────────────────────────
class RadialMenu:
    """Full holographic radial menu."""

    ANIM_DURATION = 0.35   # seconds for open/close animation
    PULSE_PERIOD  = 1.4    # seconds for idle ring pulse

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.visible  = False

        # Animation state
        self._open_t   = 0.0   # 0→closed, 1→fully open
        self._opening  = False
        self._closing  = False
        self._anim_timer = Timer()

        # Hover / selection
        self.hovered_idx: int  = -1
        self.selected_idx: int = -1

        # Ripple (pinch confirmation) animation
        self._ripple_active = False
        self._ripple_r      = 0.0
        self._ripple_max    = 120
        self._ripple_timer  = Timer()
        self._ripple_pos    = (0, 0)
        self._ripple_color  = C_HOVER

        # Menu centre (follows hand anchor smoothly)
        self._centre = SmoothPoint(screen_w // 2, screen_h // 2,
                                   smoothing=0.15)
        self._anchor = (screen_w // 2, screen_h // 2)

        # Fonts
        pygame.font.init()
        self._font_label = pygame.font.SysFont("consolas,monospace", 13,
                                               bold=True)
        self._font_icon  = pygame.font.SysFont("segoeuisymbol,symbola,"
                                               "noto color emoji,monospace",
                                               26)
        self._font_hud   = pygame.font.SysFont("consolas", 11)

        # Pre-render glow surfaces
        self._glow_big   = _glow_surface(220, C_CYAN,  0.25)
        self._glow_small = _glow_surface(60,  C_HOVER, 0.55)
        self._cursor_glow = _glow_surface(30, C_CYAN,  0.8)

        # Scanline overlay (created once)
        self._scanlines = self._make_scanlines(screen_w, screen_h)

    # ------------------------------------------------------------------
    def _make_scanlines(self, w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 3):
            pygame.draw.line(surf, (0, 0, 0, 30), (0, y), (w, y))
        return surf

    # ------------------------------------------------------------------
    def open(self, anchor: tuple[int, int]):
        if not self.visible or self._closing:
            self._anchor = anchor
            self.visible  = True
            self._opening = True
            self._closing = False
            self._anim_timer.reset()

    def close(self):
        if self.visible and not self._closing:
            self._closing = True
            self._opening = False
            self._anim_timer.reset()

    def toggle(self, anchor: tuple[int, int]):
        if self.visible:
            self.close()
        else:
            self.open(anchor)

    # ------------------------------------------------------------------
    def set_anchor(self, pos: tuple[int, int]):
        """Update hand anchor every frame."""
        self._anchor = pos

    # ------------------------------------------------------------------
    def trigger_ripple(self, idx: int):
        if idx < 0 or idx >= N_ITEMS:
            return
        cx, cy = self._centre.pos
        ang = -90 + idx * (360 / N_ITEMS)
        rx, ry = point_on_circle(cx, cy, MENU_RADIUS, ang)
        self._ripple_pos    = (int(rx), int(ry))
        self._ripple_active = True
        self._ripple_r      = 0.0
        self._ripple_timer.reset()
        self._ripple_color  = C_SELECT
        self.selected_idx   = idx

    # ------------------------------------------------------------------
    def update(self, dt: float, finger_pos: tuple[int, int] | None):
        """Call every frame. dt = seconds since last frame."""

        # Smooth centre towards anchor
        self._centre.update(*self._anchor)

        # Open / close animation
        if self._opening:
            elapsed = self._anim_timer.elapsed()
            self._open_t = min(1.0, elapsed / self.ANIM_DURATION)
            if self._open_t >= 1.0:
                self._opening = False
        elif self._closing:
            elapsed = self._anim_timer.elapsed()
            self._open_t = max(0.0, 1.0 - elapsed / self.ANIM_DURATION)
            if self._open_t <= 0.0:
                self._closing = False
                self.visible  = False

        # Ripple animation
        if self._ripple_active:
            speed = 280  # px per second
            self._ripple_r += speed * dt
            if self._ripple_r >= self._ripple_max:
                self._ripple_active = False

        # Hover detection
        self.hovered_idx = -1
        if finger_pos and self.visible and self._open_t > 0.5:
            cx, cy = self._centre.pos
            fd = dist2d(finger_pos[0], finger_pos[1], cx, cy)
            if INNER_RING < fd < OUTER_RING:
                ang = angle_between(cx, cy, finger_pos[0], finger_pos[1])
                # Map angle to item index (items start at -90 deg)
                ang = (ang + 90) % 360
                self.hovered_idx = int(ang / (360 / N_ITEMS)) % N_ITEMS

    # ------------------------------------------------------------------
    def draw(self, surf: pygame.Surface, finger_pos: tuple | None,
             gesture_name: str = ""):
        if not self.visible and not self._ripple_active:
            return

        t  = ease_out_cubic(self._open_t)
        cx, cy = int(self._centre.pos[0]), int(self._centre.pos[1])
        now = time.perf_counter()

        # ── Ambient glow behind menu ──────────────────────────────────
        if t > 0:
            gw = self._glow_big
            gx = cx - gw.get_width()  // 2
            gy = cy - gw.get_height() // 2
            alpha_surf = pygame.Surface(gw.get_size(), pygame.SRCALPHA)
            alpha_surf.blit(gw, (0, 0))
            alpha_surf.set_alpha(int(200 * t))
            surf.blit(alpha_surf, (gx, gy))

        # ── Outer decorative ring ─────────────────────────────────────
        outer_r = int(OUTER_RING * t)
        if outer_r > 5:
            _draw_glow_circle(surf, cx, cy, outer_r, C_DIM,
                              alpha_max=60, width=1)

        # ── Arc segments ─────────────────────────────────────────────
        if t > 0.1:
            seg_angle = 360 / N_ITEMS
            for i, name in enumerate(MENU_ITEMS):
                start = -90 + i * seg_angle - seg_angle * 0.5
                end   = start + seg_angle * 0.95  # slight gap
                # Scale radii with animation
                r_in  = int(INNER_RING + (INNER_RING * 0.1)  * t)
                r_out = int(r_in + (OUTER_RING - INNER_RING) * t * 0.82)

                hov = (i == self.hovered_idx)
                sel = (i == self.selected_idx)

                if hov:
                    color = C_HOVER
                    alpha = 200
                elif sel:
                    color = C_SELECT
                    alpha = 160
                else:
                    color = C_PANEL
                    alpha = int(150 * t)

                _draw_arc_segment(surf, cx, cy, r_in, r_out,
                                  start, end, color, alpha)

                # Bright border on hover
                if hov and t > 0.7:
                    _draw_arc_segment(surf, cx, cy, r_in, r_out,
                                      start, end, C_CYAN, 80)

        # ── Central hub circle ────────────────────────────────────────
        hub_r = int(INNER_RING * t)
        if hub_r > 4:
            pulse = 0.5 + 0.5 * math.sin(now * 2 * math.pi / self.PULSE_PERIOD)
            hub_color = lerp_color(C_DIM, C_CYAN, 0.3 + 0.4 * pulse)
            s = pygame.Surface((hub_r * 2 + 20, hub_r * 2 + 20),
                                pygame.SRCALPHA)
            pygame.draw.circle(s, (*hub_color, int(120 * t)),
                               (hub_r + 10, hub_r + 10), hub_r)
            pygame.draw.circle(s, (*C_CYAN, int(200 * t)),
                               (hub_r + 10, hub_r + 10), hub_r, 1)
            surf.blit(s, (cx - hub_r - 10, cy - hub_r - 10))

        # ── Item icons & labels ───────────────────────────────────────
        if t > 0.4:
            seg_angle = 360 / N_ITEMS
            for i, name in enumerate(MENU_ITEMS):
                angle = -90 + i * seg_angle
                ix, iy = point_on_circle(cx, cy, ITEM_ICON_RADIUS * t, angle)
                ix, iy = int(ix), int(iy)

                hov = (i == self.hovered_idx)
                text_color = C_HOVER if hov else C_WHITE
                label_alpha = int(255 * min(1.0, (t - 0.4) / 0.6))

                # Icon
                icon_surf = self._font_icon.render(ICON_MAP[name], True,
                                                   text_color)
                icon_surf.set_alpha(label_alpha)
                surf.blit(icon_surf, icon_surf.get_rect(center=(ix, iy - 8)))

                # Label
                lbl = self._font_label.render(name, True, text_color)
                lbl.set_alpha(label_alpha)
                surf.blit(lbl, lbl.get_rect(center=(ix, iy + 16)))

                # Hover glow around icon
                if hov:
                    gh = self._glow_small
                    surf.blit(gh, gh.get_rect(center=(ix, iy)))

        # ── Ripple confirmation ring ──────────────────────────────────
        if self._ripple_active:
            rx, ry = self._ripple_pos
            rr = int(self._ripple_r)
            progress = self._ripple_r / self._ripple_max
            alpha = int(255 * (1 - progress))
            if rr > 0:
                s = pygame.Surface((rr * 2 + 6, rr * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(s, (*self._ripple_color, alpha),
                                   (rr + 3, rr + 3), rr, 3)
                surf.blit(s, (rx - rr - 3, ry - rr - 3))

        # ── Finger cursor ─────────────────────────────────────────────
        if finger_pos:
            fx, fy = finger_pos
            # Glow
            cg = self._cursor_glow
            surf.blit(cg, cg.get_rect(center=(fx, fy)))
            # Dot
            pygame.draw.circle(surf, C_CYAN, (fx, fy), 5)
            pygame.draw.circle(surf, C_WHITE, (fx, fy), 3)

        # ── HUD gesture label (top-left corner) ──────────────────────
        if gesture_name:
            hud = self._font_hud.render(f"GESTURE: {gesture_name}",
                                        True, C_DIM)
            surf.blit(hud, (12, 10))


# ──────────────────────────────────────────────────────────────────────
class OverlayRenderer:
    """
    Manages the compositing of webcam feed + holographic overlay.
    The webcam feed is shown as a dark, desaturated background.
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._scanlines = None

    def composite_frame(self, screen: pygame.Surface,
                         cam_surface: pygame.Surface):
        """Draw darkened cam feed, then the UI sits on top."""
        # Darken the camera feed to create depth
        cam_surface.set_alpha(90)
        screen.blit(cam_surface, (0, 0))

        # Subtle dark vignette
        vignette = self._get_vignette(screen.get_width(), screen.get_height())
        screen.blit(vignette, (0, 0))

    def _get_vignette(self, w: int, h: int) -> pygame.Surface:
        # Cache by size
        if not hasattr(self, "_vig_cache"):
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(20):
                t = i / 20
                r = int(40 * (1 - t))
                alpha = int(120 * t)
                border = int(min(w, h) * 0.15 * t)
                pygame.draw.rect(surf, (0, 0, 0, alpha),
                                 (border, border, w - 2 * border,
                                  h - 2 * border),
                                 int(min(w, h) * 0.04))
            self._vig_cache = surf
        return self._vig_cache
