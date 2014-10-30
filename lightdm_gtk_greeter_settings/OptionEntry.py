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
from locale import gettext as _
import os
import time

from gi.repository import Gtk, Gdk, GObject, GLib
from lightdm_gtk_greeter_settings.IconChooserDialog import IconChooserDialog
from lightdm_gtk_greeter_settings.IndicatorChooserDialog import \
    IndicatorChooserDialog
from lightdm_gtk_greeter_settings.helpers import C_
from lightdm_gtk_greeter_settings.helpers import ModelRowEnum
from lightdm_gtk_greeter_settings.helpers import string2bool, bool2string


__all__ = ['BaseEntry', 'BooleanEntry', 'InvertedBooleanEntry',
           'StringEntry', 'StringPathEntry', 'ClockFormatEntry',
           'BackgroundEntry', 'IconEntry', 'IndicatorsEntry',
           'AdjustmentEntry', 'ChoiceEntry', 'AccessibilityStatesEntry']


class BuilderWrapper:

    def __init__(self, builder, base):
        self._builder = builder
        self._base = base

    def __getitem__(self, key):
        return self._builder.get_object('%s_%s' % (self._base, key))


class BaseEntry(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()
        self._widgets = widgets
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

    @property
    def widgets(self):
        return self._widgets

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
        return bool2string(self._value.props.active)

    def _set_value(self, value):
        self._value.props.active = string2bool(value)

    def _set_enabled(self, value):
        self._value.props.sensitive = value


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
        self._value.connect('changed', self._emit_changed)

    def _get_value(self):
        return self._value.props.text

    def _set_value(self, value):
        self._value.props.text = value or ''

    def _set_enabled(self, value):
        self._value.props.sensitive = value


class StringPathEntry(BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)

        self._file_dialog = None

        self._combo = widgets['combo']
        self._entry = widgets['entry']

        self._entry.connect('changed', self._emit_changed)
        self._combo.connect('format-entry-text', self._on_combobox_format)

        self._combo.set_row_separator_func(self._row_separator_callback, None)

    def _get_value(self):
        return self._entry.props.text

    def _set_value(self, value):
        self._entry.props.text = value or ''

    def _set_enabled(self, value):
        self._combo.props.sensitive = value

    def _row_separator_callback(self, model, rowiter, data):
        return model[rowiter][0] == '-'

    def _on_combobox_format(self, combobox, path):
        value = ''
        item_id = combobox.get_active_id()
        if item_id == 'select-path':
            if not self._file_dialog:
                self._file_dialog = Gtk.FileChooserDialog(
                                            parent=self._combo.get_toplevel(),
                                            buttons=(_('_OK'), Gtk.ResponseType.OK,
                                                     _('_Cancel'), Gtk.ResponseType.CANCEL),
                                            title=C_('option|StringPathEntry', 'Select path'))
            if self._file_dialog.run() == Gtk.ResponseType.OK:
                value = self._file_dialog.get_filename()
            else:
                value = combobox.get_active_text()
            self._file_dialog.hide()
        elif item_id == 'value':
            value = combobox.props.model[path][0]
        combobox.set_active(-1)
        return value


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

        self._icon_item.connect('activate', self._on_select_icon)
        self._path_item.connect('activate', self._on_select_path)
        self._path_dialog.connect('update-preview', self._on_update_path_preview)

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
    DEFAULT_TOOLTIPS = {'~spacer': C_('option-entry|indicators', 'Spacer'),
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
        self._model[path][self.ROW.STATE] = not self._model[path][self.ROW.STATE]

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


class AccessibilityStatesEntry(BaseEntry):

    OPTIONS = {'keyboard', 'reader', 'contrast', 'font'}

    def __init__(self, widgets):
        super().__init__(widgets)

        self._states = {name: widgets[name] for name in self.OPTIONS}

        for w in self._states.values():
            w.connect('changed', self._emit_changed)

    def _get_value(self):
        states = {name: widget.props.active_id for (name, widget) in self._states.items()}
        return ';'.join(state + name
                        for (name, state) in states.items() if state not in {None, '-'})

    def _set_value(self, value):
        if value:
            states = dict((v[1:], v[0]) if v[0] in ('-', '+', '~') else (v, '-')
                          for v in value.split(';') if v)
        else:
            states = {}
        for name in self.OPTIONS:
            self._states[name].props.active_id = states.get(name, '-')

