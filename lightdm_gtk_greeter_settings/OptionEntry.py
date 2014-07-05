#!/usr/bin/env python3
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

from builtins import isinstance
from collections import OrderedDict
from itertools import product
from locale import gettext as _
import os
import time
from gi.repository import Gtk, Gdk, GObject, GLib

from lightdm_gtk_greeter_settings.helpers import C_
from lightdm_gtk_greeter_settings.helpers import ModelRowEnum
from lightdm_gtk_greeter_settings.IndicatorChooserDialog import \
    IndicatorChooserDialog
from lightdm_gtk_greeter_settings.IconChooserDialog import IconChooserDialog


__all__ = ['BaseEntry', 'BooleanEntry', 'StringEntry', 'ClockFormatEntry',
           'BackgroundEntry', 'IconEntry', 'IndicatorsEntry', 'PositionEntry',
           'AdjustmentEntry', 'ChoiceEntry']


class BaseEntry(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()
        self._use = widgets['use']
        if self._use:
            self._use.connect('notify::active', self._on_use_toggled)

    @property
    def value(self):
        '''Option value'''
        value = self._get_value()
        formatted = self.get.emit(value)
        return value if formatted is None else formatted

    @value.setter
    def value(self, value):
        if self._use:
            self._use.props.active = True
        formatted = self.set.emit(value)
        self._set_value(value if formatted is None else formatted)

    @property
    def enabled(self):
        '''Visual option state. You can get/set value of disabled option'''
        if self._use:
            return self._use.props.active
        return True

    @enabled.setter
    def enabled(self, value):
        if self._use:
            self._use.props.active = value

    @GObject.Signal
    def changed(self):
        pass

    @GObject.Signal(flags=GObject.SIGNAL_RUN_CLEANUP)
    def get(self, value: str) -> str:  # @IgnorePep8
        pass

    @GObject.Signal(flags=GObject.SIGNAL_RUN_CLEANUP)
    def set(self, value: str) -> str:  # @IgnorePep8
        pass

    def __repr__(self):
        try:
            value = self._get_value()
        except NotImplemented:
            value = '<Undefined>'
        return '%s(%s:%s)' % (self.__class__.__name__, int(self.enabled),
                              value)

    def _get_value(self):
        raise NotImplementedError(self.__class__)

    def _set_value(self, value):
        raise NotImplementedError(self.__class__)

    def _set_enabled(self, value):
        raise NotImplementedError(self.__class__)

    def _on_use_toggled(self, toggle, *args):
        self._set_enabled(self._use.props.active)
        self._emit_changed()

    def _emit_changed(self, *unused):
        self.changed.emit()


class BooleanEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('notify::active', self._emit_changed)

    def _get_value(self):
        return 'true' if self._value.props.active else 'false'

    def _set_value(self, value):
        self._value.props.active = value and value.lower() not in (
            'false', 'no', '0')

    def _set_enabled(self, value):
        self._value.props.sensitive = value


class StringEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('changed', self._emit_changed)

    def _get_value(self):
        return self._value.props.text

    def _set_value(self, value):
        self._value.props.text = value or ''

    def _set_enabled(self, value):
        self._value.props.sensitive = value


class AdjustmentEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['adjustment']
        self._view = widgets['view']
        self._value.connect('value-changed', self._emit_changed)

    def _get_value(self):
        return str(self._value.props.value)

    def _set_value(self, value):
        try:
            self._value.props.value = float(value or '')
        except ValueError:
            self._value.props.value = 0

    def _set_enabled(self, value):
        self._view.props.sensitive = value


class ChoiceEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('changed', self._emit_changed)

    def _get_value(self):
        return self._value.props.active_id

    def _set_value(self, value):
        self._value.props.active_id = value or ''

    def _set_enabled(self, value):
        self._value.props.sensitive = value


class ClockFormatEntry(StringEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._preview = widgets['preview']
        self._value.connect('changed', self._on_changed)
        GLib.timeout_add_seconds(1, self._on_changed, self._value)

    def _on_changed(self, entry):
        self._preview.props.label = time.strftime(self._value.props.text)
        return True


class BackgroundEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._image_choice = widgets['image_choice']
        self._color_choice = widgets['color_choice']
        self._image_value = widgets['image_value']
        self._color_value = widgets['color_value']

        self._color_choice.connect('toggled', self._on_color_choice_toggled)
        self._color_value.connect('color-set', self._on_color_set)
        self._image_value.connect('file-set', self._on_file_set)

    def _get_value(self):
        if self._image_choice.props.active:
            return self._image_value.get_filename() or ''
        else:
            return self._color_value.props.color.to_string()

    def _set_value(self, value):
        if value is None:
            value = ''

        color = Gdk.color_parse(value)

        self._color_choice.props.active = color is not None
        self._image_choice.props.active = color is None

        if color is not None:
            self._color_value.props.color = color
            self._image_value.unselect_all()
        else:
            if value:
                self._image_value.select_filename(value)
            else:
                self._image_value.unselect_all()

    def _on_color_choice_toggled(self, toggle):
        self._emit_changed()

    def _on_color_set(self, button):
        if not self._color_choice.props.active:
            self._color_choice.props.active = True
        else:
            self._emit_changed()

    def _on_file_set(self, button):
        if not self._image_choice.props.active:
            self._image_choice.props.active = True
        else:
            self._emit_changed()


class FontEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('font-set', self._emit_changed)

    def _get_value(self):
        return self._value.get_font_name()

    def _set_value(self, value):
        self._value.props.font_name = value or ''


class IconEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = None
        self._image = widgets['image']
        self._button = widgets['button']
        self._menu = widgets['menu']
        self._icon_item = widgets['icon_item']
        self._path_item = widgets['path_item']
        self._path_dialog = widgets['path_dialog']
        self._path_dialog_preview = widgets['path_dialog_preview']
        self._icon_dialog = None

        self._button.connect('toggled', self._on_button_toggled)
        self._menu.connect('hide', self._on_menu_hide)
        self._icon_item.connect('activate', self._on_select_icon)
        self._path_item.connect('activate', self._on_select_path)
        self._path_dialog.connect(
            'update-preview', self._on_update_path_preview)

    def _get_value(self):
        return self._value

    def _set_value(self, value):
        if value.startswith('#'):
            self._set_icon(value[1:])
        else:
            self._set_path(value)

    def _set_icon(self, icon):
        self._value = '#' + icon
        self._image.set_from_icon_name(icon, Gtk.IconSize.DIALOG)
        self._update_menu_items(icon=icon)
        self._emit_changed()

    def _set_path(self, path):
        self._value = path
        self._image.set_from_file(path)
        self._update_menu_items(path=path)
        self._emit_changed()

    def _update_menu_items(self, icon=None, path=None):
        if icon:
            self._icon_item.get_child().set_markup(C_('option-entry|icon',
                                                      '<b>Icon: {icon}</b>')
                                                   .format(icon=icon))
        else:
            self._icon_item.get_child().set_markup(
                C_('option-entry|icon', 'Select icon name...'))

        if path:
            self._path_item.get_child()\
                .set_markup(C_('option-entry|icon',
                               '<b>File: {path}</b>')
                            .format(path=os.path.basename(path)))
        else:
            self._path_item.get_child().set_markup(
                C_('option-entry|icon', 'Select file...'))

    def _get_menu_position(self, menu, widget):
        allocation = widget.get_allocation()
        x, y = widget.get_window().get_position()
        x += allocation.x
        y += allocation.y + allocation.height
        return (x, y, False)

    def _on_button_toggled(self, toggle):
        if toggle.props.active:
            self._menu.popup(None, None, self._get_menu_position,
                             self._button, 3, Gtk.get_current_event_time())

    def _on_menu_hide(self, toggle):
        self._button.props.active = False

    def _on_select_icon(self, item):
        if not self._icon_dialog:
            self._icon_dialog = IconChooserDialog()
            self._icon_dialog.props.transient_for = self._image.get_toplevel()
        if self._value.startswith('#'):
            self._icon_dialog.select_icon(self._value[1:])
        if self._icon_dialog.run() == Gtk.ResponseType.OK:
            self._set_icon(self._icon_dialog.get_iconname())
        self._icon_dialog.hide()

    def _on_select_path(self, item):
        self._path_dialog.select_filename(self._value)
        if self._path_dialog.run() == Gtk.ResponseType.OK:
            self._set_path(self._path_dialog.get_filename())
        self._path_dialog.hide()

    def _on_update_path_preview(self, chooser):
        path = chooser.get_filename()
        if not path or not os.path.isfile(path):
            self._path_dialog_preview.props.icon_name = 'unknown'
            return
        self._path_dialog_preview.set_from_file(path)

class IndicatorsEntry(BaseEntry):
    ROW = ModelRowEnum('NAME', 'TOOLTIP', 'EDITABLE', 'HAS_STATE', 'STATE')
    NAMES_DELIMITER = ';'
    DEFAULT_TOOLTIPS = {'~spacer': C_('option-entry|indicators', 'Expander'),
                        '~separator': C_('option-entry|indicators', 'Separator')}

    def __init__(self, widgets):
        super().__init__(widgets)
        self._toolbar = widgets['toolbar']
        self._treeview = widgets['treeview']
        self._selection = widgets['selection']
        self._state_renderer = widgets['state_renderer']
        self._name_column = widgets['name_column']
        self._name_renderer = widgets['name_renderer']
        self._add = widgets['add']
        self._remove = widgets['remove']
        self._up = widgets['up']
        self._down = widgets['down']
        self._model = widgets['model']
        self._indicators_dialog = None
        self._initial_items = OrderedDict((item.NAME, item)
                                          for item in map(self.ROW, self._model))

        self._treeview.connect('key-press-event', self._on_key_press)
        self._selection.connect('changed', self._on_selection_changed)
        self._state_renderer.connect('toggled', self._on_state_toggled)
        self._name_renderer.connect('edited', self._on_name_edited)
        self._add.connect('clicked', self._on_add)
        self._remove.connect('clicked', self._on_remove)
        self._up.connect('clicked', self._on_up)
        self._down.connect('clicked', self._on_down)

        self._model.connect('row-changed', self._on_model_changed)
        self._model.connect('row-deleted', self._on_model_changed)
        self._model.connect('row-inserted', self._on_model_changed)
        self._model.connect('rows-reordered', self._on_model_changed)

    def _on_model_changed(self, *unused):
        self._emit_changed()

    def _get_value(self):
        names = (row[self.ROW.NAME] for row in self._model
                 if not row[self.ROW.HAS_STATE] or row[self.ROW.STATE])
        return self.NAMES_DELIMITER.join(names)

    def _set_value(self, value):
        self._model.clear()
        last_options = self._initial_items.copy()
        if value:
            for name in value.split(self.NAMES_DELIMITER):
                try:
                    self._model[self._model.append(last_options.pop(name))]\
                         [self.ROW.STATE] = True
                except KeyError:
                    self._model.append(self._get_indicator_tuple(name))

        for item in list(last_options.values()):
            self._model.append(item)

        self._selection.select_path(0)

    def _set_enabled(self, value):
        self._toolbar.props.sensitive = value
        self._treeview.props.sensitive = value

    def _remove_selection(self):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            previter = model.iter_previous(rowiter)
            model.remove(rowiter)
            if previter:
                self._selection.select_iter(previter)

    def _move_selection(self, move_up):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            if move_up:
                model.swap(rowiter, model.iter_previous(rowiter))
            else:
                model.swap(rowiter, model.iter_next(rowiter))
            self._on_selection_changed(self._selection)

    def _check_indicator(self, name):
        ''' Returns True if name is valid, error message or False otherwise '''
        if not name:
            return False
        elif name not in ('~spacer', '~separator'):
            if any(row[self.ROW.NAME] == name for row in self._model):
                return C_('option-entry|indicators',
                          'Indicator "{indicator}" is already in the list')\
                    .format(indicator=name)
        return True

    def _add_indicator(self, name):
        if name:
            rowiter = self._model.append(self._get_indicator_tuple(name))
            self._selection.select_iter(rowiter)
            self._treeview.grab_focus()

    def _get_indicator_tuple(self, name):
        tooltip = self.DEFAULT_TOOLTIPS.get(name,
                        C_('option-entry|indicators', 'Indicator: {name}')
                           .format(name=name))
        editable = name not in ('~spacer', '~separator')
        return self.ROW(NAME=name, TOOLTIP=tooltip, EDITABLE=editable,
                        HAS_STATE=False, STATE=False)

    def _on_key_press(self, treeview, event):
        if Gdk.keyval_name(event.keyval) == 'Delete':
            self._remove_selection()
        elif Gdk.keyval_name(event.keyval) == 'F2':
            model, rowiter = self._selection.get_selected()
            if rowiter and model[rowiter][self.COLUMN.EDITABLE]:
                self._treeview.set_cursor(
                    model.get_path(rowiter), self.COLUMN.NAME, True)
        else:
            return False
        return True

    def _on_state_toggled(self, renderer, path):
        self._model[path][self.ROW.STATE] = not self._model[path]\
                                                        [self.ROW.STATE]

    def _on_name_edited(self, renderer, path, name):
        check = self._check_indicator(name)
        if not isinstance(check, str) and check:
            self._model[path][self.ROW.NAME] = name

    def _on_selection_changed(self, selection):
        model, rowiter = selection.get_selected()
        has_selection = rowiter is not None
        self._remove.props.sensitive = has_selection and \
                                       not model[rowiter][self.ROW.HAS_STATE]
        self._down.props.sensitive = has_selection and model.iter_next(
            rowiter) is not None
        self._up.props.sensitive = has_selection and model.iter_previous(
            rowiter) is not None
        if has_selection:
            self._treeview.scroll_to_cell(model.get_path(rowiter))

    def _on_add(self, *args):
        if not self._indicators_dialog:
            self._indicators_dialog = IndicatorChooserDialog(
                check_callback=self._check_indicator,
                add_callback=self._add_indicator)
            self._indicators_dialog.props.transient_for = \
                self._treeview.get_toplevel()
        name = self._indicators_dialog.get_indicator()
        if name:
            self._add_indicator(name)

    def _on_remove(self, *args):
        self._remove_selection()

    def _on_up(self, *args):
        self._move_selection(move_up=True)

    def _on_down(self, *args):
        self._move_selection(move_up=False)


class PositionEntry(BaseEntry):

    class Dimension:

        def __init__(self, name, widgets, anchors, on_changed):
            self.__dict__.update(('_%s' % w, widgets['%s_%s' % (name, w)])
                                 for w in ('value', 'percents', 'mirror',
                                           'adjustment'))
            self._name = name
            self._on_changed = on_changed
            self._anchor = ''

            self._percents.connect('toggled', self._on_percents_toggled)
            self._mirror.connect('toggled', self._on_mirror_toggled)
            self._on_value_changed_id = self._adjustment.connect(
                'value-changed',
                self._on_value_changed)

            for (x, y), widget in list(anchors.items()):
                widget.connect('toggled', self._on_anchor_toggled, self,
                               x if self._name == 'x' else y)

        @property
        def value(self):
            return '%s%d%s,%s' % ('-' if self._mirror.props.active else '',
                                  int(self._value.props.value),
                                  '%' if self._percents.props.active else '',
                                  self._anchor)

        @value.setter
        def value(self, dim_value):
            value, _, anchor = dim_value.partition(',')

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

            self._percents.props.active = percents
            self._adjustment.props.upper = 100 if self._percents.props.active \
                else 10000
            self._mirror.props.active = negative
            with self._adjustment.handler_block(self._on_value_changed_id):
                self._adjustment.props.value = -p if negative else p

        @property
        def anchor(self):
            return self._anchor

        def get_scaled_position(self, screen, window, scale):
            screen_size = screen[0] if self._name == 'x' else screen[1]
            window_size = window[0] if self._name == 'x' else window[1]

            p = int(self._adjustment.props.value)
            if self._percents.props.active:
                p = screen_size * p / 100
            else:
                p *= scale

            if self._mirror.props.active:
                p = screen_size - p

            if self._anchor == 'center':
                p -= window_size / 2
            elif self._anchor == 'end':
                p -= window_size

            p = int(p)

            if p + window_size > screen_size:
                p = screen_size - window_size
            if p < 0:
                p = 0

            return p

        def _on_value_changed(self, widget):
            self._on_changed(self)

        def _on_percents_toggled(self, toggle):
            self._adjustment.props.upper = 100 if toggle.props.active \
                else 10000
            self._on_changed(self)

        def _on_mirror_toggled(self, toggle):
            self._on_changed(self)

        def _on_anchor_toggled(self, toggle, dimension, anchor):
            if dimension == self and toggle.props.active \
                    and anchor != self._anchor:
                self._anchor = anchor
                self._on_changed(self)

    REAL_WINDOW_SIZE = 430, 210

    def __init__(self, widgets):
        super().__init__(widgets)
        self._screen = widgets['screen']
        self._window = widgets['window']
        self._screen_pos = (0, 0)
        self._screen_size = (0, 0)

        self._anchors = {(x, y): widgets['base_%s_%s' % (x, y)]
                         for x, y in product(('start', 'center', 'end'),
                                             repeat=2)}

        self._on_resize_id = self._screen.connect(
            'size-allocate', self._on_resize)
        self._screen.connect('draw', self._on_draw_screen_border)
        self._screen.connect('screen-changed', self._on_gdkscreen_changed)
        self._on_gdkscreen_monitors_changed_id = \
            self._screen.get_screen().connect('monitors-changed',
                                              self.
                                              _on_gdkscreen_monitors_changed)

        self._x = PositionEntry.Dimension(
            'x', widgets, self._anchors, self._on_dimension_changed)
        self._y = PositionEntry.Dimension(
            'y', widgets, self._anchors, self._on_dimension_changed)

    def _get_value(self):
        return self._x.value + ' ' + self._y.value

    def _set_value(self, value):
        if value:
            x, _, y = value.partition(' ')
            self._x.value = x
            self._y.value = y or x
            self._anchors[self._x.anchor, self._y.anchor].props.active = True
            self._update_layout()

    def _update_layout(self):
        screen = self._screen.get_toplevel().get_screen()
        geometry = screen.get_monitor_geometry(screen.get_primary_monitor())
        window_allocation = self._window.get_allocation()
        window_size = window_allocation.width, window_allocation.height
        scale = self._screen_size[0] / geometry.width

        x = self._screen_pos[0] + \
            self._x.get_scaled_position(self._screen_size, window_size, scale)
        y = self._screen_pos[1] + \
            self._y.get_scaled_position(self._screen_size, window_size, scale)

        self._screen.move(self._window, x, y)
        self._screen.check_resize()

    def _on_resize(self, widget, allocation):
        screen = self._screen.get_toplevel().get_screen()
        geometry = screen.get_monitor_geometry(screen.get_primary_monitor())
        screen_scale = geometry.height / geometry.width

        width = allocation.width
        height = int(width * screen_scale)

        if height > allocation.height:
            height = allocation.height
            width = min(width, int(height / screen_scale))
        self._screen_pos = int((allocation.width - width) / 2), 0
        self._screen_size = (width, height)

        with self._screen.handler_block(self._on_resize_id):
            scale = width / geometry.width
            self._window.set_size_request(
                PositionEntry.REAL_WINDOW_SIZE[0] * scale,
                PositionEntry.REAL_WINDOW_SIZE[1] * scale)
            self._update_layout()

    def _on_draw_screen_border(self, widget, cr):
        width, height = self._screen_size
        x, y = self._screen_pos
        line_width = 2
        width -= line_width
        height -= line_width

        x += line_width / 2
        y += line_width / 2
        cr.set_source_rgba(0.2, 0.1, 0.2, 0.8)
        cr.set_line_width(line_width)

        cr.move_to(x, y)
        cr.line_to(x + width, y)
        cr.line_to(x + width, y + height)
        cr.line_to(x, y + height)
        cr.line_to(x, y - line_width / 2)
        cr.stroke_preserve()

        return False

    def _on_gdkscreen_changed(self, widget, prev_screen):
        widget.queue_resize()
        if prev_screen:
            prev_screen.disconnect(self._on_gdkscreen_monitors_changed_id)
        self._on_gdkscreen_monitors_changed_id = widget.get_screen().connect(
            'monitors-changed',
            self._on_gdkscreen_monitors_changed)

    def _on_gdkscreen_monitors_changed(self, screen):
        self._screen.queue_resize()

    def _on_dimension_changed(self, dimension):
        with self._screen.handler_block(self._on_resize_id):
            self._update_layout()
            self._emit_changed()
