# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#   LightDM GTK Greeter Settings
#   Copyright (C) 2014 Andrew P. <pan.pav.7c5@gmail.com>
#
#   This program is free software: you can redistribute it and/or modify it
#   under the terms of the GNU General Public License version 3, as published
#   by the Free Software Foundation.
#
#   This program is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranties of
#   MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program.  If not, see <http://www.gnu.org/licenses/>.


from itertools import product

from gi.repository import (
    Gdk,
    Gtk)

from lightdm_gtk_greeter_settings.helpers import WidgetsWrapper
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry


__all__ = ['PositionEntry']


class PositionEntry(BaseEntry):

    class Dimension:

        def __init__(self, widgets, on_changed):
            self._entry = widgets['entry']
            self._percents = widgets['percents']
            self._mirror = widgets['mirror']
            self._adjustment = widgets['adjustment']
            self._on_changed = on_changed

            self._anchor = None

            self._on_percents_id = self._percents.connect('toggled', self._on_percents_toggled)
            self._on_mirror_id = self._mirror.connect('toggled', self._on_mirror_toggled)
            self._on_value_id = self._adjustment.connect('value-changed', self._on_value_changed)

        @property
        def value(self):
            return '%s%d%s,%s' % ('-' if self._mirror.props.active else '',
                                  int(self._entry.props.value),
                                  '%' if self._percents.props.active else '',
                                  self._anchor)

        @value.setter
        def value(self, s):
            if isinstance(s, tuple):
                p, percents, negative, anchor = s
            else:
                value, __, anchor = s.partition(',')

                percents = value and value[-1] == '%'
                if percents:
                    value = value[:-1]

                try:
                    p = int(value)
                except ValueError:
                    p = 0

                negative = (p < 0) or (p == 0 and value and value[0] == '-')

                if not anchor or anchor not in ('start', 'center', 'end'):
                    if negative:
                        anchor = 'end'
                    else:
                        anchor = 'start'

            self._anchor = anchor
            with self._percents.handler_block(self._on_percents_id):
                self._percents.props.active = percents
            self._adjustment.props.upper = 100 if self._percents.props.active else 10000
            with self._mirror.handler_block(self._on_mirror_id):
                self._mirror.props.active = negative
            with self._adjustment.handler_block(self._on_value_id):
                self._adjustment.props.value = -p if negative else p

        @property
        def anchor(self):
            return self._anchor

        @anchor.setter
        def anchor(self, value):
            self._anchor = value

        @property
        def negative(self):
            return self._mirror.props.active

        @negative.setter
        def negative(self, value):
            self._mirror.props.active = value

        def get_value_for_screen(self, screen: int):
            p = int(self._adjustment.props.value)

            if self._percents.props.active:
                p = screen * p / 100
            if self._mirror.props.active:
                p = screen - p

            return int(p)

        def _on_percents_toggled(self, toggle):
            self._adjustment.props.upper = 100 if toggle.props.active else 10000
            self._on_changed(self)

        def _on_mirror_toggled(self, toggle):
            self._on_changed(self)

        def _on_value_changed(self, widget):
            self._on_changed(self)

    AssumedWindowSize = 430, 240

    def __init__(self, widgets):
        super().__init__(widgets)

        self._screen_size = None
        self._last_overlay_size = None
        self._last_window_allocation = None

        self._screen_frame = widgets['screen_frame']
        self._screen_overlay = widgets['screen_overlay']
        window_box = widgets['window_box']
        grid = widgets['window_grid']

        self._motion = False

        window_box.connect('motion-notify-event', self._on_window_motion)
        window_box.connect('button-press-event', self._on_window_button_press)
        window_box.connect('button-release-event', self._on_window_button_release)

        # Creating points grid
        anchors_align = (Gtk.Align.START, Gtk.Align.CENTER, Gtk.Align.END)
        anchors = [(x, y, Gtk.RadioButton())
                   for x, y in product(enumerate(('start', 'center', 'end')), repeat=2)]

        self._anchors = {}
        self._anchors_handlers = {}
        for (left, x_anchor), (top, y_anchor), w in anchors:
            w.props.halign = anchors_align[left]
            w.props.valign = anchors_align[top]
            if w != anchors[0][-1]:
                w.props.group = anchors[0][-1]
            grid.attach(w, left, top, 1, 1)
            self._anchors[x_anchor, y_anchor] = w
            self._anchors_handlers[w] = w.connect('toggled', self._on_anchor_toggled,
                                                  x_anchor, y_anchor)

        grid.show_all()

        self._x = PositionEntry.Dimension(WidgetsWrapper(widgets, 'x'), self._on_dimension_changed)
        self._y = PositionEntry.Dimension(WidgetsWrapper(widgets, 'y'), self._on_dimension_changed)

        self._on_gdk_screen_changed()

        self._screen_overlay.connect('get-child-position',
                                     self._on_screen_overlay_get_child_position)
        self._screen_overlay.connect('screen-changed', self._on_gdk_screen_changed)

    def _get_value(self):
        x = self._x.value
        y = self._y.value
        return x + ' ' + y if x != y else x

    def _set_value(self, value):
        self._last_window_allocation = None
        if value:
            x, __, y = value.partition(' ')
            self._x.value = x
            self._y.value = y or x
            anchor = self._anchors[self._x.anchor, self._y.anchor]
            with anchor.handler_block(self._anchors_handlers[anchor]):
                anchor.props.active = True
        self._screen_overlay.queue_resize()
        self._emit_changed()

    def _get_corrected_position(self, p, screen, window, anchor):
        if anchor == 'center':
            p -= window / 2
        elif anchor == 'end':
            p -= window

        if p + window > screen:
            p = screen - window
        if p < 0:
            p = 0

        return int(p)

    def _on_dimension_changed(self, dimension):
        self._last_window_allocation = None
        self._screen_overlay.queue_resize()
        self._emit_changed()

    def _on_screen_overlay_get_child_position(self, overlay, child, allocation):
        screen = overlay.get_allocation()

        if self._last_window_allocation and \
                self._last_overlay_size == (screen.width, screen.height):
            (allocation.x, allocation.y,
             allocation.width, allocation.height) = self._last_window_allocation
            return True
        self._last_overlay_size = screen.width, screen.height

        scale = screen.width / self._screen_size[0]

        width = int(self.AssumedWindowSize[0] * scale)
        height = int(self.AssumedWindowSize[1] * scale)

        # Set desired size
        child.set_size_request(width, height)
        # And check what actually we have now
        width, height = child.size_request().width, child.size_request().height

        x = int(self._x.get_value_for_screen(self._screen_size[0]) * scale)
        y = int(self._y.get_value_for_screen(self._screen_size[1]) * scale)

        x = self._get_corrected_position(x, screen.width, width, self._x.anchor)
        y = self._get_corrected_position(y, screen.height, height, self._y.anchor)

        self._last_window_allocation = x, y, width, height
        allocation.x, allocation.y, allocation.width, allocation.height = x, y, width, height

        return True

    def _on_anchor_toggled(self, toggle, x, y):
        if not toggle.props.active:
            return
        self._x.anchor = x
        self._y.anchor = y
        self._last_window_allocation = None
        self._screen_overlay.queue_resize()
        self._emit_changed()

    def _on_gdk_screen_changed(self, widget=None, prev_screen=None):
        screen = self._screen_overlay.get_toplevel().get_screen()
        geometry = screen.get_monitor_geometry(screen.get_primary_monitor())
        self._screen_size = geometry.width, geometry.height
        self._screen_frame.props.ratio = geometry.width / geometry.height

    def _on_window_motion(self, widget, event):
        if not event.state & Gdk.ModifierType.BUTTON1_MASK:
            return False

        screen = self._screen_overlay.get_allocation()
        x, y = widget.translate_coordinates(self._screen_overlay, event.x, event.y)

        for d, p in ((self._x, int(100 * x / screen.width)),
                     (self._y, int(100 * y / screen.height))):
            if p < 0:
                p = 0
            elif p > 100:
                p = 100
            if d.negative:
                d.value = p - 100, True, True, d.anchor
            else:
                d.value = p, True, False, d.anchor

        self._motion = True
        self._last_window_allocation = None
        self._screen_overlay.queue_resize()
        return True

    def _on_window_button_press(self, widget, event):
        if event.button == 1:
            self._motion = False

    def _on_window_button_release(self, widget, event):
        if self._motion and event.button == 1:
            self._motion = False
            self._emit_changed()
