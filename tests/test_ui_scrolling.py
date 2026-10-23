import sys
from types import SimpleNamespace
from unittest.mock import Mock
import tkinter as tk

import customtkinter as ctk
import pytest

from uav_downloader.ui.scrolling import install_touchpad_scrolling


@pytest.fixture
def root():
    try:
        window = ctk.CTk()
    except tk.TclError as error:
        pytest.skip(f'Tk display unavailable: {error}')
    window.geometry('500x400')
    install_touchpad_scrolling(window)
    window.update()
    yield window
    window.destroy()


def make_list(parent):
    frame = ctk.CTkScrollableFrame(parent, width=180, height=200)
    frame.pack(side='left', fill='both', expand=True)
    for number in range(40):
        ctk.CTkLabel(frame, text=f'Item {number}').pack(pady=4)
    parent.update()
    return frame


def touchpad(widget, dx=0, dy=-12):
    if not widget.tk.call('info', 'commands', 'tk::PreciseScrollDeltas'):
        pytest.skip('Tk runtime uses MouseWheel for touchpads')
    widget.event_generate('<TouchpadScroll>', delta=(dx << 16) | (dy & 0xffff))
    widget.update()


def test_touchpad_scrolls_both_directions_over_card_children(root):
    frame = make_list(root)
    child = frame.winfo_children()[0]._label
    canvas = frame._parent_canvas
    start = canvas.yview()[0]
    touchpad(child)
    down = canvas.yview()[0]
    assert down > start
    touchpad(child, dy=12)
    assert canvas.yview()[0] < down


def test_touchpad_scrolls_only_target_list_and_ignores_horizontal_motion(root):
    left, right = make_list(root), make_list(root)
    start = right._parent_canvas.yview()
    touchpad(left.winfo_children()[0], dx=25)
    assert left._parent_canvas.yview()[0] > 0
    assert right._parent_canvas.yview() == start
    before = left._parent_canvas.yview()
    touchpad(left.winfo_children()[0], dx=-25, dy=0)
    assert left._parent_canvas.yview() == before


def test_mouse_wheel_still_scrolls_both_directions(root):
    frame = make_list(root)
    child = frame.winfo_children()[0]
    canvas = frame._parent_canvas
    if sys.platform.startswith('linux'):
        down, up, amount = '<Button-5>', '<Button-4>', {}
    else:
        down = up = '<MouseWheel>'
        amount = {'delta': -120 if sys.platform.startswith('win') else -3}
    child.event_generate(down, **amount)
    root.update()
    position = canvas.yview()[0]
    assert position > 0
    if amount:
        amount['delta'] *= -1
    child.event_generate(up, **amount)
    root.update()
    assert canvas.yview()[0] < position


def test_nested_list_and_textbox_do_not_scroll_outer_list(root):
    outer = make_list(root)
    inner = make_list(outer)
    outer._parent_canvas.yview_moveto(0.5)
    start = outer._parent_canvas.yview()
    touchpad(inner.winfo_children()[0])
    assert inner._parent_canvas.yview()[0] > 0
    assert outer._parent_canvas.yview() == start
    text = ctk.CTkTextbox(outer, height=80)
    text.pack()
    text.insert('1.0', '\n'.join(str(i) for i in range(50)))
    root.update()
    start = outer._parent_canvas.yview()
    touchpad(text._textbox)
    assert text._textbox.yview()[0] > 0
    assert outer._parent_canvas.yview() == start


def test_touchpad_survives_list_rebuild_and_dialog_close(root):
    frame = make_list(root)
    frame.destroy()
    frame = make_list(root)
    dialog = ctk.CTkToplevel(root)
    listing = make_list(dialog)
    touchpad(listing.winfo_children()[0])
    assert listing._parent_canvas.yview()[0] > 0
    dialog.destroy()
    touchpad(frame.winfo_children()[0])
    assert frame._parent_canvas.yview()[0] > 0


def test_tk86_keeps_existing_wheel_bindings():
    root = SimpleNamespace(tk=Mock(), bind_all=Mock())
    root.tk.call.return_value = ''
    install_touchpad_scrolling(root)
    root.bind_all.assert_not_called()
