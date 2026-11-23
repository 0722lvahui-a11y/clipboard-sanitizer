#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
妮牌净化器 macOS 版
====================
· 左键小狗开关：绿圈 = 工作中，红圈 = 已暂停
· 复制含 act_ 数字的内容（可多行）→ 去前缀排队
· 每次 Cmd+V 自动粘贴下一个数字；最后一行贴完弹气泡提醒
· 右键菜单：隐藏（收起后点 Dock 图标恢复）· 回到右下角 · 使用说明 · 退出
· 开启后爱心只出现 3 秒
"""

import os
import sys
import re
import json
import math
import time
import random
import subprocess
import threading
import traceback
from collections import deque

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageColor, ImageFont, ImageTk

APP_NAME = "妮牌净化器"
APP_VERSION = "2.0.0"
APP_DATA = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "NiiPurifier")
SETTINGS_PATH = os.path.join(APP_DATA, "settings.json")
LOCK_PATH = os.path.join(APP_DATA, "instance.lock")

try:
    os.makedirs(APP_DATA, exist_ok=True)
except Exception:
    pass


def log(msg):
    try:
        with open(os.path.join(APP_DATA, "app.log"), "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


# ======================================================================
# 视觉常量（1x 点）
# ======================================================================
WIN_W, WIN_H = 240, 350
BTN_CX, BTN_CY = 120, 242
IMG_R = 100
RING_OUT = 70.5
RING_W = 6.5
WHITE_R = 73
DISC_R = 63.5
FACE_R = 57
TOAST_BOTTOM = 132
HEART_SHOW_SECONDS = 3.0

COLORS = {
    "on":  {"ring": "#34C77D", "glow": "#8FE7B8", "hl": "#C7F7DD"},
    "off": {"ring": "#FF607A", "glow": "#FFB0C2", "hl": "#FFD8E1"},
}
COLORS_HOVER = {
    "on":  {"ring": "#43D68C", "glow": "#7FE2AE", "hl": "#D7FAE8"},
    "off": {"ring": "#FF7890", "glow": "#FF9FB4", "hl": "#FFE4EA"},
}
HEART_COLORS = ["#FF4F8B", "#FF659D", "#FF7EAF", "#FF96C0", "#FFB0D2", "#FFC6E0"]
CARD_BG = (255, 253, 248, 255)
CARD_BORDER = (243, 166, 190, 255)
CARD_TEXT = (124, 70, 90, 255)
THUMB_RING = (255, 196, 214, 255)

ACT_RE = re.compile(r"act_(\d+)")

_FONT_CACHE = {}
_FACE = None
_BTN_CACHE = {}


def _load_face():
    global _FACE
    try:
        _FACE = Image.open(resource_path("ni_assets", "ni_face.png")).convert("RGBA")
        return _FACE
    except Exception as e:
        log("face asset load failed: %r" % (e,))
        im = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([40, 90, 680, 710], fill=(255, 251, 242, 255))
        d.ellipse([90, 80, 300, 290], fill=(255, 251, 242, 255))
        d.ellipse([420, 80, 630, 290], fill=(255, 251, 242, 255))
        d.ellipse([210, 330, 285, 405], fill=(70, 50, 45, 255))
        d.ellipse([435, 330, 510, 405], fill=(70, 50, 45, 255))
        d.ellipse([320, 430, 400, 500], fill=(70, 50, 45, 255))
        d.arc([290, 470, 430, 580], 20, 160, fill=(210, 120, 140, 255), width=10)
        _FACE = im
        return _FACE


def _get_font(px):
    px = max(8, int(px))
    if px in _FONT_CACHE:
        return _FONT_CACHE[px]
    for path in ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/STHeiti Medium.ttc",
                 "/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        try:
            if os.path.exists(path):
                f = ImageFont.truetype(path, px, index=0)
                _FONT_CACHE[px] = f
                return f
        except Exception:
            continue
    f = ImageFont.load_default()
    _FONT_CACHE[px] = f
    return f


def _circle_mask(size):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    return mask


def render_button(on, hover=False):
    state = "on" if on else "off"
    key = (state, bool(hover))
    if key in _BTN_CACHE:
        return _BTN_CACHE[key]
    colors = COLORS_HOVER[state] if hover else COLORS[state]
    ring = ImageColor.getrgb(colors["ring"])
    glow = ImageColor.getrgb(colors["glow"])
    hl = ImageColor.getrgb(colors["hl"])

    ss = 3
    D = int(round(2 * IMG_R * ss))
    c = D / 2.0
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))

    # 光晕：带 alpha 的模糊圆
    gl = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    gr = (RING_OUT + 3) * ss
    gd.ellipse([c - gr, c - gr, c + gr, c + gr], fill=glow + (150,))
    gl = gl.filter(ImageFilter.GaussianBlur(7 * ss))
    img.alpha_composite(gl)

    d = ImageDraw.Draw(img)
    wr = WHITE_R * ss
    d.ellipse([c - wr, c - wr, c + wr, c + wr], fill=(255, 255, 255, 255))

    ro = RING_OUT * ss
    rw = max(1, int(round(RING_W * ss)))
    d.ellipse([c - ro, c - ro, c + ro, c + ro], outline=ring + (255,), width=rw)

    cr = (RING_OUT - RING_W * 0.5) * ss
    d.arc([c - cr, c - cr, c + cr, c + cr], 200, 318,
          fill=hl + (255,), width=max(1, int(round(RING_W * 0.38 * ss))))

    dr = DISC_R * ss
    d.ellipse([c - dr, c - dr, c + dr, c + dr], fill=(255, 246, 230, 255))

    fb = (FACE_R + 1.6) * ss
    d.ellipse([c - fb, c - fb, c + fb, c + fb],
              outline=(238, 223, 207, 255), width=max(1, int(round(1.2 * ss))))

    fs = FACE_R * ss
    dsz = max(2, int(round(fs * 2)))
    face = _FACE.resize((dsz, dsz), Image.LANCZOS)
    img.paste(face, (int(round(c - fs)), int(round(c - fs))), _circle_mask(dsz))

    out = img.resize((2 * IMG_R, 2 * IMG_R), Image.LANCZOS)
    _BTN_CACHE[key] = out
    return out


def render_bubble(text, fs=14, thumb=True):
    u = 3.0
    fpx = max(10, int(round(fs * u)))
    font = _get_font(fpx)
    pad = 13.0 * u
    gap = 9.0 * u
    thumb_sz = 34.0 * u if thumb else 0.0
    border = max(1, int(round(2.2 * u)))
    radius = 15.0 * u
    tail_w = 14.0 * u
    tail_h = 9.0 * u

    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bb = probe.textbbox((0, 0), text, font=font)
    tw = float(bb[2] - bb[0])
    th = float(bb[3] - bb[1])
    content_h = max(th, thumb_sz)
    card_w = pad * 2 + (thumb_sz + gap if thumb else 0) + tw
    card_h = pad * 2 + content_h
    W4 = max(1, int(round(card_w)))
    H4 = max(1, int(round(card_h + tail_h)))

    img = Image.new("RGBA", (W4, H4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W4 - 1, int(round(card_h)) - 1],
                        radius=radius, fill=CARD_BG,
                        outline=CARD_BORDER, width=border)

    cx = W4 / 2.0
    y0 = card_h - border * 0.5
    tri = [(cx - tail_w / 2, y0), (cx + tail_w / 2, y0), (cx, H4 - 1)]
    d.polygon(tri, fill=CARD_BG)
    d.line([tri[0], tri[2]], fill=CARD_BORDER, width=border)
    d.line([tri[1], tri[2]], fill=CARD_BORDER, width=border)

    x = pad
    ty = (card_h - thumb_sz) / 2.0
    if thumb:
        d.ellipse([x, ty, x + thumb_sz, ty + thumb_sz], fill=THUMB_RING)
        inset = 2.6 * u
        fsz = max(2, int(round(thumb_sz - inset * 2)))
        face = _FACE.resize((fsz, fsz), Image.LANCZOS)
        img.paste(face, (int(round(x + inset)), int(round(ty + inset))), _circle_mask(fsz))
        x += thumb_sz + gap

    text_y = (card_h - th) / 2.0 - bb[1]
    d.text((int(round(x)), int(round(text_y))), text, font=font, fill=CARD_TEXT)

    out = img.resize((max(1, int(round(W4 / u))), max(1, int(round(H4 / u)))), Image.LANCZOS)
    return out


# ======================================================================
# 剪贴板 / 队列
# ======================================================================
def read_clip():
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=1.0)
        if r.returncode == 0:
            return r.stdout
        return None
    except Exception:
        return None


def write_clip(text):
    try:
        r = subprocess.run(["pbcopy"], input=text, text=True, timeout=1.0)
        return r.returncode == 0
    except Exception:
        return False


class ActQueue:
    def __init__(self):
        self.items = []
        self.idx = -1

    @property
    def active(self):
        return 0 <= self.idx < len(self.items)

    @property
    def current(self):
        return self.items[self.idx] if self.active else ""

    @property
    def remaining(self):
        return len(self.items) - self.idx if self.active else 0

    def load(self, nums):
        self.items = list(nums)
        self.idx = 0 if self.items else -1

    def advance(self):
        if not self.active or self.idx >= len(self.items) - 1:
            return None
        self.idx += 1
        return self.current

    def clear(self):
        self.items = []
        self.idx = -1


def extract_numbers(text):
    return ACT_RE.findall(text or "")


# ======================================================================
# 主应用
# ======================================================================
class NiiPurifier:
    def __init__(self):
        _load_face()
        self.enabled = False
        self.running = True
        self.last_content = ""
        self.paste_signal = None
        self.last_advance = 0.0
        self.queue = ActQueue()
        self.hearts = []
        self.next_heart = 0.0
        self.hearts_deadline = 0.0
        self._toast_item = None
        self._toast_photo = None
        self._toast_job = None
        self._toast_bbox = None
        self._toast_kind = None
        self.hover = False
        self._drag = None
        self._moved = False
        self._cmd_held = False
        self._v_held = False
        self._listener = None
        self._icon_photo = None
        self._trusted = True

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.transparent = False
        try:
            self.root.attributes("-transparent", True)
            self.transparent = True
        except Exception as e:
            log("transparent attribute failed: %r" % (e,))
        self.bg = "systemTransparent" if self.transparent else "#FFE4EC"
        try:
            self.root.configure(bg=self.bg)
        except Exception:
            self.bg = "#FFE4EC"
            self.root.configure(bg=self.bg)
        self.root.resizable(False, False)
        self.root.report_callback_exception = self._tk_exception

        self._set_window_icon()
        try:
            self.root.createcommand("tk::mac::ReopenApplication", self._show_from_dock)
        except Exception as e:
            log("reopen binding failed: %r" % (e,))
        self._restore_position()

        self.canvas = tk.Canvas(self.root, width=WIN_W, height=WIN_H, bg=self.bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._photos = {}
        for on in (False, True):
            for hv in (False, True):
                self._photos[(on, hv)] = ImageTk.PhotoImage(render_button(on, hv))
        self._btn_xy = (BTN_CX - IMG_R, BTN_CY - IMG_R)
        self.btn_item = self.canvas.create_image(self._btn_xy[0], self._btn_xy[1],
                                                 image=self._photos[(False, False)],
                                                 anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        for seq in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.canvas.bind(seq, self._on_menu)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        self._build_menu()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._start_listener()
        self._trusted = self._check_trusted()
        self.root.after(60, self._poll)
        self.root.after(30, self._anim_tick)
        self.root.after(600, lambda: self._show_toast("左键开关 · 右键菜单",
                                                      duration=4.6, kind="hint"))
        if not self._trusted:
            self.root.after(5800, lambda: self._show_toast("Cmd+V 需辅助功能权限",
                                                           duration=6.0, kind="perm"))
        log("start version=%s arch=%s trusted=%s" %
            (APP_VERSION, __import__("platform").machine(), self._trusted))

    # ----------------------- 窗口 / Dock -----------------------
    def _set_window_icon(self):
        try:
            img = Image.open(resource_path("ni_assets", "icon_pink.png")).convert("RGBA")
            img = img.resize((64, 64), Image.LANCZOS)
            self._icon_photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self._icon_photo)
        except Exception as e:
            log("iconphoto failed: %r" % (e,))

    def _screen(self):
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _default_pos(self):
        sw, sh = self._screen()
        return sw - WIN_W - 24, sh - WIN_H - 100

    def _restore_position(self):
        x, y = self._default_pos()
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            x = int(data.get("x", x))
            y = int(data.get("y", y))
        except Exception:
            pass
        sw, sh = self._screen()
        x = max(0, min(x, sw - WIN_W))
        y = max(0, min(y, sh - WIN_H))
        self.pos = [x, y]
        self.root.geometry("%dx%d+%d+%d" % (WIN_W, WIN_H, x, y))

    def _save_position(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump({"x": int(self.pos[0]), "y": int(self.pos[1])}, f)
        except Exception:
            pass

    def _show_from_dock(self, *args):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            try:
                self.root.attributes("-transparent", True)
            except Exception:
                pass
            self._refresh_button()
            log("shown from dock")
        except Exception as e:
            log("show from dock failed: %r" % (e,))

    def _hide_to_dock(self):
        self._hide_toast()
        self._save_position()
        try:
            self.root.withdraw()
            log("hidden to dock")
        except Exception as e:
            log("hide failed: %r" % (e,))

    # ----------------------- 菜单 -----------------------
    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg="#FFFDF8", fg="#6B4653",
                            activebackground="#FFE3EC", activeforeground="#6B4653",
                            bd=1, relief="solid", font=("PingFang SC", 10))

    def _on_menu(self, event):
        m = self.menu
        m.delete(0, "end")
        m.add_command(label="暂停净化" if self.enabled else "开启净化",
                      command=self._toggle)
        m.add_separator()
        m.add_command(label="回到右下角", command=self._reset_pos)
        m.add_command(label="隐藏", command=self._hide_to_dock)
        m.add_command(label="使用说明", command=self._show_help)
        m.add_separator()
        m.add_command(label="退出", command=self._close)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return "break"

    def _reset_pos(self):
        x, y = self._default_pos()
        self.pos = [x, y]
        self.root.geometry("%dx%d+%d+%d" % (WIN_W, WIN_H, x, y))
        self._save_position()

    def _show_help(self):
        text = ("妮牌净化器 使用说明\n\n"
                "1. 左键小狗：开启 / 暂停\n"
                "2. 复制含 act_ 数字的内容（可以多行）\n"
                "    例：act_123456、act_234567、act_345678\n"
                "3. 每按一次 Cmd+V，自动粘贴下一个数字\n"
                "4. 最后一行粘贴完，小狗会弹气泡提醒\n\n"
                "右键菜单：隐藏 · 回到右下角 · 使用说明 · 退出\n"
                "隐藏后点 Dock 上的妮牌净化器图标即可恢复。\n\n"
                "如果 Cmd+V 不自动切换：\n"
                "系统设置 → 隐私与安全 → 辅助功能，勾选妮牌净化器。\n"
                "首次打开被拦截：右键 App → 打开。")
        messagebox.showinfo(APP_NAME, text)

    # ----------------------- 拖拽 / 点击 -----------------------
    def _on_enter(self, event):
        self.hover = True
        self.canvas.configure(cursor="hand2")
        self._refresh_button()

    def _on_leave(self, event):
        self.hover = False
        self.canvas.configure(cursor="")
        self._refresh_button()

    def _on_press(self, event):
        if self._toast_bbox and self._toast_kind != "hint" and self._point_in_toast(event.x, event.y):
            self._hide_toast()
            return
        if self._toast_kind == "hint":
            self._hide_toast()
        self._drag = (event.x_root, event.y_root, self.pos[0], self.pos[1])
        self._moved = False

    def _on_motion(self, event):
        if not self._drag:
            return
        dx = event.x_root - self._drag[0]
        dy = event.y_root - self._drag[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._moved = True
        sw, sh = self._screen()
        x = max(0, min(self._drag[2] + dx, sw - WIN_W))
        y = max(0, min(self._drag[3] + dy, sh - WIN_H))
        self.pos = [x, y]
        self.root.geometry("%dx%d+%d+%d" % (WIN_W, WIN_H, x, y))

    def _on_release(self, event):
        if not self._drag:
            return
        self._drag = None
        if self._moved:
            self._save_position()
        else:
            self._toggle()

    def _point_in_toast(self, x, y):
        if not self._toast_bbox:
            return False
        x0, y0, x1, y1 = self._toast_bbox
        return x0 <= x <= x1 and y0 <= y <= y1

    # ----------------------- 开关 / 按钮 -----------------------
    def _toggle(self):
        self.enabled = not self.enabled
        self.paste_signal = None
        self._refresh_button()
        self._bounce()
        self._hide_toast()
        if self.enabled:
            now = time.monotonic()
            self.hearts_deadline = now + HEART_SHOW_SECONDS
            self._burst(10)
            self.next_heart = now + 0.25
            self._reconcile_on_enable()
            log("enabled")
        else:
            self._clear_hearts()
            log("disabled")

    def _refresh_button(self):
        key = (self.enabled, self.hover)
        if key in self._photos:
            self.canvas.itemconfig(self.btn_item, image=self._photos[key])
        self.canvas.tag_raise(self.btn_item)

    def _reconcile_on_enable(self):
        c = read_clip()
        if c is None:
            return
        if extract_numbers(c):
            self._handle_clipboard(c, source="enable")
        elif self.queue.active and c == self.queue.current:
            self.last_content = c
        else:
            self.queue.clear()
            self.last_content = c

    def _bounce(self):
        x0, y0 = self._btn_xy
        offsets = [5, 2, 0]

        def step(i):
            if not self.running:
                return
            self.canvas.coords(self.btn_item, x0, y0 - offsets[i])
            if i + 1 < len(offsets):
                self.root.after(45, lambda: step(i + 1))

        self.root.after(0, lambda: step(0))

    # ----------------------- 气泡 -----------------------
    def _show_toast(self, text, duration=3.6, kind="info"):
        if not self.running:
            return
        try:
            pil = None
            for fs in (14, 13, 12, 11):
                pil = render_bubble(text, fs=fs)
                if pil.width <= WIN_W - 10:
                    break
            photo = ImageTk.PhotoImage(pil)
            w, h = pil.size
            x = BTN_CX - w // 2
            base_top = TOAST_BOTTOM - h
            x = max(2, min(x, WIN_W - w - 2))
            base_top = max(2, base_top)
            self._hide_toast()
            item = self.canvas.create_image(x, base_top + 5, image=photo, anchor="nw")
            self.canvas.tag_raise(item)
            self._toast_item = item
            self._toast_photo = photo
            self._toast_bbox = (x, base_top, x + w, base_top + h)
            self._toast_kind = kind
            self._slide_toast(item, x, base_top + 5, base_top)
            self._toast_job = self.root.after(int(duration * 1000), self._hide_toast)
        except Exception as e:
            log("toast failed: %r" % (e,))

    def _slide_toast(self, item, x, y_from, y_to):
        steps = 6

        def step(i):
            if not self.running or self._toast_item != item:
                return
            y = y_from + (y_to - y_from) * i / steps
            self.canvas.coords(item, x, y)
            if i < steps:
                self.root.after(18, lambda: step(i + 1))

        step(1)

    def _hide_toast(self):
        if self._toast_job:
            try:
                self.root.after_cancel(self._toast_job)
            except Exception:
                pass
            self._toast_job = None
        if self._toast_item:
            try:
                self.canvas.delete(self._toast_item)
            except Exception:
                pass
        self._toast_item = None
        self._toast_photo = None
        self._toast_bbox = None
        self._toast_kind = None

    # ----------------------- 爱心 -----------------------
    def _heart_pts(self, cx, cy, s):
        pts = []
        n = 20
        for i in range(n):
            t = 2.0 * math.pi * i / n
            hx = 16.0 * (math.sin(t) ** 3)
            hy = -(13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
                   - 2.0 * math.cos(3 * t) - math.cos(4 * t))
            pts.extend([cx + hx * s / 16.0, cy + (hy - 6.0) * s / 16.0])
        return pts

    def _spawn_heart(self, burst=False):
        if not self.enabled or time.monotonic() >= self.hearts_deadline:
            return
        if len(self.hearts) >= 20:
            return
        if burst:
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(70, 88)
            speed = random.uniform(14, 30)
            rise = random.uniform(26, 48)
            size = random.uniform(9, 15)
            life = random.uniform(1.4, 2.2)
        else:
            angle = random.uniform(math.pi * 1.05, math.pi * 1.95)
            radius = random.uniform(72, 86)
            speed = random.uniform(6, 15)
            rise = random.uniform(22, 38)
            size = random.uniform(8, 14)
            life = random.uniform(1.5, 2.4)
        cx = BTN_CX + math.cos(angle) * radius
        cy = BTN_CY + math.sin(angle) * radius
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed - rise
        item = self.canvas.create_polygon(
            self._heart_pts(cx, cy, size), fill=random.choice(HEART_COLORS),
            outline="", smooth=False)
        self.hearts.append({
            "id": item, "x0": cx, "y0": cy, "vx": vx, "vy": vy,
            "size": size, "age": 0.0, "life": life,
            "sway": random.uniform(4, 10), "phase": random.uniform(0, 6.283),
            "color": random.choice(HEART_COLORS),
        })

    def _burst(self, n):
        for _ in range(n):
            self._spawn_heart(burst=True)

    def _clear_hearts(self):
        for h in self.hearts:
            try:
                self.canvas.delete(h["id"])
            except Exception:
                pass
        self.hearts = []

    def _anim_tick(self):
        if not self.running:
            return
        now = time.monotonic()
        if self.enabled and now < self.hearts_deadline:
            if now >= self.next_heart:
                if random.random() < 0.82:
                    self._spawn_heart()
                self.next_heart = now + random.uniform(0.24, 0.46)
        elif self.hearts:
            self._clear_hearts()
        alive = []
        for h in self.hearts:
            h["age"] += 0.033
            p = h["age"] / h["life"]
            if p >= 1.0:
                try:
                    self.canvas.delete(h["id"])
                except Exception:
                    pass
                continue
            age = h["age"]
            x = h["x0"] + h["vx"] * age + math.sin(age * 3.1 + h["phase"]) * h["sway"] * p
            y = h["y0"] + h["vy"] * age - 8.0 * age * age
            grow = min(1.0, 0.25 + p / 0.18) if p < 0.18 else 1.0
            shrink = 1.0
            if p > 0.55:
                shrink = max(0.12, 1.0 - (p - 0.55) / 0.45 * 0.88)
            size = h["size"] * grow * shrink
            try:
                self.canvas.coords(h["id"], *self._heart_pts(x, y, size))
            except Exception:
                pass
            idx = min(len(HEART_COLORS) - 1, int(p * len(HEART_COLORS)))
            col = HEART_COLORS[idx]
            if col != h["color"]:
                h["color"] = col
                try:
                    self.canvas.itemconfig(h["id"], fill=col)
                except Exception:
                    pass
            if y < -30 or x < -30 or x > WIN_W + 30:
                try:
                    self.canvas.delete(h["id"])
                except Exception:
                    pass
                continue
            alive.append(h)
        self.hearts = alive
        self.root.after(33, self._anim_tick)

    # ----------------------- 键盘监听 / 权限 -----------------------
    def _check_trusted(self):
        try:
            from ApplicationServices import AXIsProcessTrusted
            return bool(AXIsProcessTrusted())
        except Exception:
            try:
                from Quartz import AXIsProcessTrusted
                return bool(AXIsProcessTrusted())
            except Exception:
                return True

    def _start_listener(self):
        try:
            from pynput import keyboard
        except Exception as e:
            log("pynput import failed: %r" % (e,))
            return

        def is_cmd(k):
            return k in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r)

        def is_v(k):
            try:
                ch = getattr(k, "char", None)
                return bool(ch) and ch.lower() == "v"
            except Exception:
                return False

        def on_press(k):
            if is_cmd(k):
                self._cmd_held = True
            if is_v(k):
                self._v_held = True

        def on_release(k):
            if is_cmd(k):
                if self._v_held:
                    self.paste_signal = time.monotonic()
                self._cmd_held = False
            elif is_v(k):
                if self._cmd_held:
                    self.paste_signal = time.monotonic()
                self._v_held = False

        try:
            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.start()
            log("listener started")
        except Exception as e:
            log("listener failed: %r" % (e,))

    # ----------------------- 剪贴板 / 队列 -----------------------
    def _handle_clipboard(self, content, source=""):
        self.last_content = content
        nums = extract_numbers(content)
        if not nums:
            if self.queue.active:
                self.queue.clear()
            return
        self.queue.load(nums)
        if not write_clip(nums[0]):
            log("write first item failed")
            self.queue.clear()
            return
        self.last_content = nums[0]
        self._burst(4)
        self._show_toast("已排队 %d 行" % len(nums), duration=1.5, kind="load")
        log("queue loaded n=%d %s" % (len(nums), source))

    def _handle_paste(self):
        if not self.enabled or not self.queue.active:
            return
        now = time.monotonic()
        if now - self.last_advance < 0.35:
            return
        self.last_advance = now
        if self.queue.idx >= len(self.queue.items) - 1:
            self.queue.clear()
            self._burst(8)
            self._show_toast("已执行到最后一行", duration=4.2, kind="done")
            log("queue finished")
            return
        nxt = self.queue.advance()
        if nxt is None:
            return
        if write_clip(nxt):
            self.last_content = nxt
            log("advance idx=%d/%d" % (self.queue.idx, len(self.queue.items)))
        else:
            log("advance write failed idx=%d" % self.queue.idx)

    def _poll(self):
        if not self.running:
            return
        if self.enabled:
            c = read_clip()
            if c is not None and c != self.last_content:
                self._handle_clipboard(c, source="copy")
            sig = self.paste_signal
            if sig is not None:
                self.paste_signal = None
                self._handle_paste()
        else:
            self.paste_signal = None
        delay = 80 if (self.enabled and self.queue.active) else 200
        self.root.after(delay, self._poll)

    # ----------------------- 退出 -----------------------
    def _tk_exception(self, exc, val, tb):
        log("TK ERROR:\n" + "".join(traceback.format_exception(exc, val, tb)))

    def _close(self):
        self.running = False
        self._hide_toast()
        self._save_position()
        try:
            if self._listener:
                self._listener.stop()
        except Exception:
            pass
        try:
            if _LOCK_HANDLE:
                _LOCK_HANDLE.close()
        except Exception:
            pass
        log("exit")
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
        log("mainloop returned")


# ======================================================================
# 单实例
# ======================================================================
_LOCK_HANDLE = None


def acquire_instance():
    global _LOCK_HANDLE
    try:
        import fcntl
        f = open(LOCK_PATH, "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return None
        _LOCK_HANDLE = f
        return f
    except Exception as e:
        log("lock failed: %r" % (e,))
        return True


def main():
    if acquire_instance() is None:
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(APP_NAME, "妮牌净化器已经在运行。\n点 Dock 上的图标可以把它叫回来。")
        try:
            r.destroy()
        except Exception:
            pass
        return
    app = NiiPurifier()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        raise
