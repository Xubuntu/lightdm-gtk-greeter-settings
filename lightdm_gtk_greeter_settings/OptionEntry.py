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


import time
from locale import gettext as _

from gi.repository import (
    Gdk,
    GLib,
    GObject,
    Gtk)
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    bool2string,
    string2bool,
    SimpleEnum)


__all__ = [
    'AccessibilityStatesEntry',
    'AdjustmentEntry',
    'BackgroundEntry',
    'BaseEntry',
    'BooleanEntry',
    'ChoiceEntry',
    'ClockFormatEntry',
    'InvertedBooleanEntry',
    'StringEntry',
    'StringPathEntry']


class BaseEntry(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()
        self._widgets = widgets
        self.__widgets_to_disable = []

        self.__use = widgets['use']
        if self.__use:
            self.__use.connect('notify::active', self.__on_use_toggled)

        self.__error = widgets['error']

        self._add_label_widget(widgets['label_holder'])

    @property
    def value(self):
        '''Option value'''
        value = self._get_value()
        formatted = self.get.emit(value)
        return value if formatted is None else formatted

    @value.setter
    def value(self, value):
        if self.__use:
            self.__use.set_active(True)
        formatted = self.set.emit(value)
        self._set_value(value if formatted is None else formatted)

    @property
    def enabled(self):
        return self._get_enabled()

    @enabled.setter
    def enabled(self, value):
        self._set_enabled(value)

    @property
    def error(self):
        return self._get_error()

    @error.setter
    def error(self, value):
        self._set_error(value)

    @property
    def widgets(self):
        return self._widgets

    @GObject.Signal
    def changed(self):
        pass

    @GObject.Signal(flags=GObject.SIGNAL_RUN_CLEANUP)
    def get(self, value: str) -> str:
        pass

    @GObject.Signal(flags=GObject.SIGNAL_RUN_CLEANUP)
    def set(self, value: str) -> str:
        pass

    @GObject.Signal('show-menu')
    def show_menu(self):
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

    def _get_error(self):
        if self.__error:
            return self.__error.props.tooltip_text
        return None

    def _set_error(self, text):
        if self.__error:
            self.__error.props.visible = text is not None
            self.__error.props.tooltip_text = text

    def _get_enabled(self):
        if self.__use:
            return self.__use.get_active()
        return True

    def _set_enabled(self, value):
        if self.__use:
            self.__use.set_active(value)
            for widget in self.__widgets_to_disable:
                widget.props.sensitive = value
        self._emit_changed()

    def _add_label_widget(self, *widgets):
        for widget in widgets:
            if widget:
                widget.connect('button-press-event', self.__on_label_clicked)

    def _add_controlled_by_state_widget(self, *widgets):
        self.__widgets_to_disable += widgets

    def _show_menu(self):
        self.__on_label_clicked()

    def _emit_changed(self, *unused):
        self.changed.emit()

    def __on_use_toggled(self, toggle, *unused):
        self._set_enabled(self.__use.props.active)

    def __on_label_clicked(self, widget, event):
        if event.button == 3:
            self.show_menu.emit()


class BooleanEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('notify::active', self._emit_changed)
        self._add_controlled_by_state_widget(self._value)

    def _get_value(self):
        return bool2string(self._value.props.active)

    def _set_value(self, value):
        self._value.props.active = string2bool(value)


class InvertedBooleanEntry(BooleanEntry):

    def __init__(self, widgets):
        super().__init__(widgets)

    def _get_value(self):
        return bool2string(not self._value.props.active)

    def _set_value(self, value):
        self._value.props.active = not string2bool(value)


class StringEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._add_controlled_by_state_widget(self._value)
        if isinstance(self._value.props.parent, Gtk.ComboBox):
            self._add_controlled_by_state_widget(self._value.props.parent)
        self._value.connect('changed', self._emit_changed)

    def _get_value(self):
        return self._value.props.text

    def _set_value(self, value):
        self._value.props.text = value or ''


class StringPathEntry(BaseEntry):

    class Row(SimpleEnum):
        Title = ()
        Type = ()

    class ItemType(SimpleEnum):
        Select = 'select-path'
        Value = 'value'
        Separator = 'separator'

    def __init__(self, widgets):
        super().__init__(widgets)

        self._file_dialog = None
        self._combo = widgets['combo']
        self._entry = widgets['entry']
        self._filters = ()
        self._add_controlled_by_state_widget(self._combo)

        self._entry.connect('changed', self._emit_changed)
        self._combo.connect('format-entry-text', self._on_combobox_format)

        self._combo.set_row_separator_func(self._row_separator_callback, None)

    def add_filter(self, file_filter):
        if self._file_dialog:
            self._file_dialog.add_filter(file_filter)
        elif self._filters:
            self._filters.append(file_filter)
        else:
            self._filters = [file_filter]

    def _get_value(self):
        return self._entry.props.text

    def _set_value(self, value):
        self._entry.props.text = value or ''

    def _row_separator_callback(self, model, rowiter, data):
        return model[rowiter][self.Row.Type] == self.ItemType.Separator

    def _on_combobox_format(self, combobox, path):
        value = self._entry.props.text
        item_id = combobox.get_active_id()
        if item_id == self.ItemType.Select:
            if not self._file_dialog:
                self._file_dialog = Gtk.FileChooserDialog(
                    parent=self._combo.get_toplevel(),
                    buttons=(_('_OK'), Gtk.ResponseType.OK,
                             _('_Cancel'), Gtk.ResponseType.CANCEL),
                    title=C_('option|StringPathEntry', 'Select path'))
                for f in self._filters:
                    self._file_dialog.add_filter(f)
            if self._file_dialog.run() == Gtk.ResponseType.OK:
                value = self._file_dialog.get_filename()
            self._file_dialog.hide()
        elif item_id == self.ItemType.Value:
            value = combobox.props.model[path][self.Row.Title]

        combobox.set_active(-1)
        combobox.grab_focus()
        return value


class AdjustmentEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['adjustment']
        self._value.connect('value-changed', self._emit_changed)
        self._view = widgets['view']
        self._add_controlled_by_state_widget(self._view)

    def _get_value(self):
        return str(self._value.props.value)

    def _set_value(self, value):
        try:
            self._value.props.value = float(value or '')
        except ValueError:
            self._value.props.value = 0


class ChoiceEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = widgets['value']
        self._value.connect('changed', self._emit_changed)
        self._add_controlled_by_state_widget(self._value)

    def _get_value(self):
        return self._value.props.active_id

    def _set_value(self, value):
        self._value.props.active_id = value or ''


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

        self._add_controlled_by_state_widget(self._image_choice, self._color_choice,
                                             self._image_value, self._color_value)

        self._on_choice_id = self._color_choice.connect('toggled', self._on_color_choice_toggled)
        self._color_value.connect('color-set', self._on_color_set)
        self._image_value.connect('file-set', self._on_file_set)

    def _get_value(self):
        if self._image_choice.props.active:
            return self._image_value.get_filename() or ''
        else:
            r, g, b, __ = (int(0xFF * v) for v in self._color_value.props.rgba)
            return '#%02x%02x%02x' % (r, g, b)

    def _set_value(self, value):
        if value is None:
            value = ''

        rgba = Gdk.RGBA()
        if not rgba.parse(value):
            rgba = None

        with self._color_choice.handler_block(self._on_choice_id):
            self._color_choice.props.active = rgba is not None
            self._image_choice.props.active = rgba is None

        if rgba is not None:
            self._color_value.props.rgba = rgba
            self._image_value.unselect_all()
        else:
            if value:
                self._image_value.select_filename(value)
            else:
                self._image_value.unselect_all()

        self._emit_changed()

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
        self._add_controlled_by_state_widget(self._value)

    def _get_value(self):
        return self._value.get_font_name()

    def _set_value(self, value):
        self._value.props.font_name = value or ''


class AccessibilityStatesEntry(BaseEntry):

    Options = ('keyboard', 'reader', 'contrast', 'font')

    def __init__(self, widgets):
        super().__init__(widgets)

        self._states = {name: widgets[name] for name in self.Options}

        for w in self._states.values():
            w.connect('changed', self._emit_changed)

    def _get_value(self):
        states = {name: widget.props.active_id
                  for (name, widget) in self._states.items()}
        return ';'.join(state + name
                        for (name, state) in states.items() if state not in {None, '-'})

    def _set_value(self, value):
        if value:
            states = dict((v[1:], v[0]) if v[0] in ('-', '+', '~') else (v, '-')
                          for v in value.split(';') if v)
        else:
            states = {}
        for name in self.Options:
            self._states[name].props.active_id = states.get(name, '-')
