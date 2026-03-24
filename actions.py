"""
actions.py
==========
Maps menu option names to system actions.
Uses subprocess for cross-platform launches with sensible fallbacks.
"""

import subprocess
import sys
import webbrowser
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
def _run(*args, **kwargs):
    """Fire-and-forget subprocess launch, suppressing window on Windows."""
    kwargs.setdefault("start_new_session", True)
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen(list(args), **kwargs)
        logger.info("Launched: %s", args)
    except FileNotFoundError:
        logger.warning("Command not found: %s", args[0])


# ──────────────────────────────────────────────────────────────────────
def open_browser():
    webbrowser.open("https://www.google.com")


def open_music():
    if sys.platform == "win32":
        _run("cmd", "/c", "start", "mswindowsmusic:")
    elif sys.platform == "darwin":
        _run("open", "-a", "Music")
    else:
        for app in ("rhythmbox", "amarok", "clementine", "spotify"):
            try:
                _run(app)
                return
            except Exception:
                pass
        webbrowser.open("https://music.youtube.com")


def open_files():
    if sys.platform == "win32":
        _run("explorer")
    elif sys.platform == "darwin":
        _run("open", "~")
    else:
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "xdg-open"):
            try:
                _run(fm, "~" if fm == "xdg-open" else "")
                return
            except Exception:
                pass


def open_calculator():
    if sys.platform == "win32":
        _run("calc")
    elif sys.platform == "darwin":
        _run("open", "-a", "Calculator")
    else:
        for app in ("gnome-calculator", "kcalc", "galculator", "xcalc"):
            try:
                _run(app)
                return
            except Exception:
                pass


def open_blender():
    if sys.platform == "win32":
        _run("blender")
    elif sys.platform == "darwin":
        _run("open", "-a", "Blender")
    else:
        _run("blender")


def open_settings():
    if sys.platform == "win32":
        _run("ms-settings:")
    elif sys.platform == "darwin":
        _run("open", "-a", "System Preferences")
    else:
        for app in ("gnome-control-center", "xfce4-settings-manager",
                    "systemsettings5"):
            try:
                _run(app)
                return
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────────────
# Registry used by the menu
ACTION_MAP = {
    "Browser":    open_browser,
    "Music":      open_music,
    "Files":      open_files,
    "Calculator": open_calculator,
    "Blender":    open_blender,
    "Settings":   open_settings,
}


def execute(option_name: str):
    fn = ACTION_MAP.get(option_name)
    if fn:
        try:
            fn()
        except Exception as e:
            logger.error("Action '%s' failed: %s", option_name, e)
    else:
        logger.warning("Unknown option: %s", option_name)
