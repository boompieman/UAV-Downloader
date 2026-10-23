"""Tk touchpad compatibility for the shared CustomTkinter scroll areas."""

import tkinter as tk

import customtkinter as ctk


def install_touchpad_scrolling(root):
    # Tk 8.6 sends MouseWheel; Tk 9 sends packed TouchpadScroll deltas.
    if not root.tk.call('info', 'commands', 'tk::PreciseScrollDeltas'):
        return

    def scroll(event):
        widget = event.widget
        while isinstance(widget, tk.Misc):
            if isinstance(widget, (tk.Text, tk.Listbox, ctk.CTkTextbox,
                                   ctk.CTkSlider)):
                return
            if isinstance(widget, ctk.CTkScrollableFrame):
                _, delta_y = root.tk.call('tk::PreciseScrollDeltas', event.delta)
                if delta_y and widget.cget('orientation') == 'vertical':
                    # shortcut: use CTk's canvas until it supports TouchpadScroll upstream.
                    root.tk.call('tk::ScrollByPixels', widget._parent_canvas,
                                 0, delta_y)
                    return 'break'
                return
            widget = widget.master

    root.bind_all('<TouchpadScroll>', scroll, add='+')
