"""
input_sim.py — Mouse/keyboard input simulation for FlowPulse.

Wraps movement.generate_path() and pyautogui for safe, realistic input.
Disables pyautogui.FAILSAFE at import time.
"""

import random
import time
import math

import pyautogui

from flowpulse.movement import generate_path

# Disable the failsafe (mouse corner panic) — intentional for security research
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0  # we manage our own delays


def safe_coords(screen_width=None, screen_height=None, margin_pct=10):
    """
    Generate random coordinates within a 'safe zone' of the screen.

    Safe zone = margin_pct% inset from each edge.
    If screen dimensions not provided, queries pyautogui.size().
    """
    if screen_width is None or screen_height is None:
        screen_width, screen_height = pyautogui.size()

    margin_x = screen_width * margin_pct / 100.0
    margin_y = screen_height * margin_pct / 100.0

    x = random.uniform(margin_x, screen_width - margin_x)
    y = random.uniform(margin_y, screen_height - margin_y)
    return int(x), int(y)


def mouse_move_to(x, y):
    """
    Move the mouse from the current position to (x, y) with a realistic
    Bezier path. Blocking — waits for the full movement to complete.
    """
    cur_x, cur_y = pyautogui.position()
    path = generate_path(cur_x, cur_y, x, y)

    for px, py, delay_ms in path:
        pyautogui.moveTo(px, py, duration=0)  # instant position; we handle timing
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)


def mouse_click(button="left", clicks=1):
    """
    Perform a mouse click with realistic delays between press and release.
    """
    # Random delay between mouse-down and mouse-up: 50-200ms
    press_release_delay = random.uniform(0.050, 0.200)

    for _ in range(clicks):
        pyautogui.mouseDown(button=button)
        time.sleep(press_release_delay)
        pyautogui.mouseUp(button=button)

        if clicks > 1:
            time.sleep(random.uniform(0.030, 0.080))


def mouse_scroll(clicks=None):
    """
    Perform a scroll action. If clicks is None, picks randomly 1-5.
    Positive = scroll up (Windows convention), negative = down.
    Random direction each call.
    """
    if clicks is None:
        clicks = random.randint(1, 5)
    direction = 1 if random.random() < 0.5 else -1
    pyautogui.scroll(direction * clicks)


def keyboard_f13():
    """Press and release the F13 key."""
    pyautogui.press("f13")


def keyboard_f15():
    """Press and release the F15 key."""
    pyautogui.press("f15")


def keyboard_modifier():
    """
    Press and release the left Shift key with a 50ms hold.

    Useful as a modifier-only keystroke to appear realistic without
    actually modifying other keys.
    """
    pyautogui.keyDown("shiftleft")
    time.sleep(0.050)
    pyautogui.keyUp("shiftleft")
