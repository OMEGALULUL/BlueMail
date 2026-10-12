"""Lightweight UI micro-animations (Claude-level clean).

Helpers:
  prime      pre-hide a widget for a staggered entrance (no animation yet)
  fade_in    fade a widget in
  fade_window  native top-level window opacity fade (painter-safe on X11)
  slide_in   fade + slide a widget inside its layout (reading pane)
  pulse      gentle infinite breathing (welcome CTA)
  stagger    prime + cascade several widgets into view
  stop       halt any animation on a widget, pin opacity 1, restore layout

All helpers are no-ops (and ``prime`` does nothing) when the environment
variable ``OT_NO_ANIM=1`` is set (used by tests and screenshots).

X11 safety: widget ``QGraphicsOpacityEffect`` animations must never run
while the widget repaints (sync storms / content load) — Qt then complains
"paint device can only be painted by one painter". Callers that mutate
content call ``stop()`` first; top-level windows fade with native
``windowOpacity`` instead of effects.
"""

import os

from PyQt5.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    QVariantAnimation,
    Qt,
    QObject,
)
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QVBoxLayout, QWidget

ANIM_EASE = QEasingCurve.OutCubic
ANIM_EASE_SOFT = QEasingCurve.OutQuart
ANIM_EASE_IN_OUT = QEasingCurve.InOutCubic
ANIM_EASE_OUT_BACK = QEasingCurve.OutBack
ANIM_EASE_ELASTIC = QEasingCurve.OutElastic


def enabled():
    return os.environ.get("OT_NO_ANIM") != "1"


def _opacity_effect(widget):
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    return eff


def _stop_previous(widget):
    prev = getattr(widget, "_ot_anim", None)
    if isinstance(prev, QAbstractAnimation):
        try:
            if prev.state() == QAbstractAnimation.Running:
                prev.stop()
        except RuntimeError:
            pass


def prime(widget):
    """Make *widget* invisible for a later staggered entrance.

    Re-prime applies cleanly (previous effect reused). When animations are
    disabled, does nothing so the widget stays visible.
    """
    if not enabled() or widget is None:
        return None
    try:
        _stop_previous(widget)
        eff = _opacity_effect(widget)
        eff.setOpacity(0.0)
        return eff
    except RuntimeError:
        return None


def fade_in(widget, duration=320, start=0.0, end=1.0,
            curve=ANIM_EASE_SOFT):
    """Fade a widget in. Returns the animation, or ``None`` when disabled."""
    if not enabled() or widget is None:
        return None
    try:
        _stop_previous(widget)
        eff = _opacity_effect(widget)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        widget._ot_anim = anim
        anim.start()
        return anim
    except RuntimeError:      # widget deleted before a deferred start
        return None


def fade_window(window, duration=360, start=0.0, end=1.0,
                curve=ANIM_EASE_SOFT):
    """Animate a top-level window's native opacity (painter-safe on X11)."""
    if not enabled() or window is None:
        return None
    try:
        _stop_previous(window)
        window.setWindowOpacity(start)
        anim = QPropertyAnimation(window, b"windowOpacity", window)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        window._ot_anim = anim
        anim.start()
        return anim
    except RuntimeError:
        return None


def _restore_layout(widget):
    layout = getattr(widget, "_ot_layout", None)
    base = getattr(widget, "_ot_base_margins", None)
    if layout is not None and base is not None:
        try:
            layout.setContentsMargins(base)
        except RuntimeError:
            pass
    widget._ot_layout = None
    widget._ot_axis = None
    widget._ot_base_margins = None


def slide_in(widget, layout, distance=12, duration=340, axis=Qt.Vertical,
             curve=ANIM_EASE_SOFT):
    """Fade in *widget* while it slides *distance* px inside *layout*.

    ``axis == Qt.Vertical``  rises up (reading pane),
    ``axis == Qt.Horizontal`` slides in from the left.
    """
    if not enabled() or widget is None:
        return None
    try:
        _stop_previous(widget)
        _restore_layout(widget)
        eff = _opacity_effect(widget)
        eff.setOpacity(0.0)
        base = layout.contentsMargins()
        layout.setContentsMargins(base)
        widget._ot_layout = layout
        widget._ot_axis = axis
        widget._ot_base_margins = base

        anim = QVariantAnimation(widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(curve)

        def apply(t, eff=eff, layout=layout, base=base, widget=widget,
                  distance=distance, axis=axis):
            eff.setOpacity(t)
            if axis == Qt.Horizontal:
                left = base.left() - int(round(distance * (1 - t)))
                layout.setContentsMargins(left, base.top(),
                                          base.right(), base.bottom())
            else:
                top = base.top() + int(round(distance * (1 - t)))
                layout.setContentsMargins(base.left(), top,
                                          base.right(), base.bottom())

        anim.valueChanged.connect(apply)
        widget._ot_anim = anim
        anim.start()
        return anim
    except RuntimeError:
        return None


def stagger(spec, base_delay=0):
    """Prime *spec* and cascade them into view.

    ``spec`` is an iterable of ``(widget, delay_ms, duration_ms)``. The
    first call primes; later re-staggers start from the current opacity.
    """
    if not enabled():
        return
    for widget, delay, duration in spec:
        if widget is None:
            continue
        prime(widget)
        QTimer.singleShot(
            int(base_delay + delay),
            lambda w=widget, d=int(duration): fade_in(w, d, ease=ANIM_EASE_SOFT))


def pulse(widget, duration=2000, low=0.72):
    """Gentle infinite breathing pulse (welcome CTA). Returns anim or None."""
    if not enabled() or widget is None:
        return None
    try:
        _stop_previous(widget)
        eff = _opacity_effect(widget)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(duration)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.5, low)
        anim.setKeyValueAt(1.0, 1.0)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(-1)
        widget._ot_anim = anim
        anim.start()
        return anim
    except RuntimeError:
        return None


def stop(widget):
    """Stop any animation on *widget*, pin opacity to 1, restore layout."""
    if widget is None:
        return
    anim = getattr(widget, "_ot_anim", None)
    if isinstance(anim, QAbstractAnimation):
        try:
            anim.stop()
        except RuntimeError:
            pass
    widget._ot_anim = None
    _restore_layout(widget)
    eff = widget.graphicsEffect()
    if isinstance(eff, QGraphicsOpacityEffect):
        try:
            eff.setOpacity(1.0)
        except RuntimeError:
            pass