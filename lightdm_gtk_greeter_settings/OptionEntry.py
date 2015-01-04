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


import os
import time
from locale import gettext as _

from gi.repository import (
    Gdk,
    GLib,
    GObject,
    Gtk)
from lightdm_gtk_greeter_settings import helpers
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    bool2string,
    string2bool, SimpleEnum)
from lightdm_gtk_greeter_settings.IconChooserDialog import IconChooserDialog


__all__ = [
    'AccessibilityStatesEntry',
    'AdjustmentEntry',
    'BackgroundEntry',
    'BaseEntry',
    'BooleanEntry',
    'ChoiceEntry',
    'ClockFormatEntry',
    'IconEntry',
    'InvertedBooleanEntry',
    'StringEntry',
    'StringPathEntry']


class BaseEntry(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()
        self._widgets = widgets
        self._use = widgets['use']
        self._widgets_to_disable = []
        if self._use:
            self._use.connect('notify::active', self._on_use_toggled)
        self._error = widgets['error']

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
        if self._error:
            return self._error.props.tooltip_text
        return None

    def _set_error(self, text):
        if self._error:
            self._error.props.visible = text is not None
            self._error.props.tooltip_text = text

    def _set_enabled(self, value):
        if self._widgets_to_disable:
            for widget in self._widgets_to_disable:
                widget.props.sensitive = value

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
        self._widgets_to_disable.append(self._value)

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
        self._widgets_to_disable.append(self._value)
        if isinstance(self._value.props.parent, Gtk.ComboBox):
            self._widgets_to_disable += [self._value.props.parent]
        self._value.connect('changed', self._emit_changed)

    def _get_value(self):
        return self._value.props.text

    def _set_value(self, value):
        self._value.props.text = value or ''


class StringPathEntry(BaseEntry):

    class Row(helpers.SimpleEnum):
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
        self._widgets_to_disable.append(self._combo)
        self._filters = ()

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
        self._view = widgets['view']
        self._widgets_to_disable.append(self._view)
        self._value.connect('value-changed', self._emit_changed)

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
        self._widgets_to_disable.append(self._value)
        self._value.connect('changed', self._emit_changed)

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

        self._color_choice.connect('toggled', self._on_color_choice_toggled)
        self._color_value.connect('color-set', self._on_color_set)
        self._image_value.connect('file-set', self._on_file_set)

    def _get_value(self):
        if self._image_choice.props.active:
            return self._image_value.get_filename() or ''
        else:
            return self._color_value.props.rgba.to_string()

    def _set_value(self, value):
        if value is None:
            value = ''

        rgba = Gdk.RGBA()
        if not rgba.parse(value):
            rgba = None

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
        self._widgets_to_disable.append(self._value)
        self._value.connect('font-set', self._emit_changed)

    def _get_value(self):
        return self._value.get_font_name()

    def _set_value(self, value):
        self._value.props.font_name = value or ''


class IconEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = None
        self._button = widgets['button']
        self._image = widgets['image']
        self._icon_item = widgets['icon_item']
        self._path_item = widgets['path_item']
        self._widgets_to_disable.append(self._button)
        self._icon_dialog = None
        self._path_dialog = None

        self._icon_item.connect('activate', self._on_select_icon)
        self._path_item.connect('activate', self._on_select_path)

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
        self._update(icon=icon)
        self._emit_changed()

    def _set_path(self, path):
        self._value = path
        failed = not self._set_image_from_path(self._image, path)
        self._update(path=path, failed=failed)
        self._emit_changed()

    def _update(self, icon=None, path=None, failed=False):
        if icon:
            markup = C_('option-entry|icon', '<b>Icon: {icon}</b>').format(icon=icon)
            self._icon_item.get_child().set_markup(markup)
            self._button.set_tooltip_markup(markup)
        else:
            self._icon_item.get_child().set_markup(
                C_('option-entry|icon', 'Select icon name...'))

        if path:
            if failed:
                markup = C_('option-entry|icon', '<b>File: {path}</b> (failed to load)')
            else:
                markup = C_('option-entry|icon', '<b>File: {path}</b>')
            markup = markup.format(path=os.path.basename(path))
            self._path_item.get_child().set_markup(markup)
            self._button.set_tooltip_markup(markup)
        else:
            self._path_item.get_child().set_markup(
                C_('option-entry|icon', 'Select file...'))

    def _set_image_from_path(self, image, path):
        if not path or not os.path.isfile(path):
            image.props.icon_name = 'unknown'
        else:
            try:
                width, height = image.get_size_request()
                if -1 in (width, height):
                    width, height = 64, 64
                pixbuf = helpers.pixbuf_from_file_scaled_down(path, width, height)
                image.set_from_pixbuf(pixbuf)
                return True
            except GLib.Error:
                image.props.icon_name = 'file-broken'
        return False

    def _on_select_icon(self, item):
        if not self._icon_dialog:
            self._icon_dialog = IconChooserDialog()
            self._icon_dialog.props.transient_for = self._image.get_toplevel()
        if self._value and self._value.startswith('#'):
            self._icon_dialog.select_icon(self._value[1:])
        if self._icon_dialog.run() == Gtk.ResponseType.OK:
            self._set_icon(self._icon_dialog.get_selected_icon())
        self._icon_dialog.hide()

    def _on_select_path(self, item):
        if not self._path_dialog:
            builder = Gtk.Builder()
            builder.add_from_file(helpers.get_data_path('ImageChooserDialog.ui'))

            self._path_dialog = builder.get_object('dialog')
            self._path_dialog.props.transient_for = self._image.get_toplevel()
            self._path_dialog.connect('update-preview', self._on_update_path_preview)

            preview_size = self._image.props.pixel_size
            preview = self._path_dialog.props.preview_widget
            preview.props.pixel_size = preview_size
            preview.set_size_request(preview_size, preview_size)

        if self._value:
            self._path_dialog.select_filename(self._value)
        if self._path_dialog.run() == Gtk.ResponseType.OK:
            self._set_path(self._path_dialog.get_filename())
        self._path_dialog.hide()

    def _on_update_path_preview(self, chooser):
        self._set_image_from_path(chooser.props.preview_widget, chooser.get_filename())


class AccessibilityStatesEntry(BaseEntry):

    Options = {'keyboard', 'reader', 'contrast', 'font'}

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
