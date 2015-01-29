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
import sys
from copy import deepcopy
from glob import iglob

from gi.repository import Gtk

from lightdm_gtk_greeter_settings import (
    IconEntry,
    OptionEntry)
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    bool2string,
    string2bool,
    get_data_path,
    get_greeter_version,
    SimpleEnum,
    WidgetsEnum,
    WidgetsWrapper)
from lightdm_gtk_greeter_settings.IndicatorsEntry import (
    EmptyIndicators,
    Indicators,
    LayoutSet,
    Option)


__all__ = ['IndicatorPropertiesDialog']


class IndicatorPath(OptionEntry.StringPathEntry):

    class Row(SimpleEnum):
        Title = ()
        Type = ()
        Icon = ()


class IndicatorIconEntry(IconEntry.IconEntry):

    DefaultValue = ()

    def __init__(self, widgets):
        self._label = widgets['label']
        super().__init__(widgets)

    def _set_value(self, value):
        super()._set_value(self.DefaultValue if value is None else value)
        self._label.set_markup(self._current_item.menuitem.get_label())
        self._image.props.visible = value not in (None, self.DefaultValue)

    def _get_value(self):
        return super()._get_value() or None

    def _get_items(self):
        for item in super()._get_items():
            yield item
        yield -1, (self._update_default, self._ask_default)

    def _update_default(self, value, just_label):
        if just_label or value is not self.DefaultValue:
            return C_('option-entry|indicators', 'Use default value...'), None
        self._image.props.icon_name = ''
        label = C_('option-entry|indicators', '<b>Using default value</b>')
        return label, label

    def _ask_default(self, oldvalue):
        return self.DefaultValue


class IndicatorTypeEntry(OptionEntry.BaseEntry):

    def __init__(self, widgets):
        super().__init__(widgets)

        self._types = widgets['types']
        self._indicator_choice = widgets['indicator_choice']
        self._spacer_choice = widgets['spacer_choice']
        self._separator_choice = widgets['separator_choice']

        self._types.connect('changed', self._emit_changed)
        self._indicator_choice.connect('toggled', self._on_choice_changed, None,
                                       (self._types, widgets['indicator_box']))
        self._spacer_choice.connect('toggled', self._on_choice_changed, Indicators.Spacer)
        self._separator_choice.connect('toggled', self._on_choice_changed, Indicators.Separator)

        self._value = None

    def add_type(self, name, title):
        if name not in EmptyIndicators:
            self._types.append(name, title or name)

    def _get_value(self):
        if self._indicator_choice.props.active:
            return self._types.props.active_id
        else:
            return self._value

    def _set_value(self, value):
        if value == Indicators.Spacer:
            button = self._spacer_choice
        elif value == Indicators.Separator:
            button = self._separator_choice
        else:
            button = self._indicator_choice

        self._value = value
        self._types.set_active_id(value)

        if button.props.active:
            button.toggled()
        else:
            button.props.active = True

    def _on_choice_changed(self, button, value, widgets=[]):
        for w in widgets:
            w.props.sensitive = button.props.active

        if button.props.active:
            self._value = value if value else self._types.props.active_id
            self._emit_changed()


class IndicatorPropertiesDialog(Gtk.Dialog):
    __gtype_name__ = 'IndicatorPropertiesDialog'

    class Widgets(WidgetsEnum):
        add = 'add_button'
        ok = 'ok_button'
        infobar = 'infobar'
        message = 'message'
        common_options = 'common_options_box'
        custom_options = 'custom_options_box'
        path = 'option_path_combo'
        path_model = 'option_path_model'
        hide_disabled = 'option_power_hide_disabled'

    def __new__(cls, *args, **kwargs):
        builder = Gtk.Builder()
        builder.add_from_file(get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('indicator_properties_dialog')
        window.builder = builder
        builder.connect_signals(window)
        window.init_window(*args, **kwargs)
        return window

    def init_window(self, is_duplicate=None, get_defaults=None, get_name=str):
        self._widgets = self.Widgets(builder=self.builder)
        self._get_defaults = get_defaults
        self._add_indicator = None
        self._is_duplicate = is_duplicate
        self._get_name = get_name
        self._indicator_loaded = False
        self._name = None
        self._reversed = False

        self._name2page = {}
        for i in range(0, self._widgets.custom_options.get_n_pages()):
            page = self._widgets.custom_options.get_nth_page(i)
            name = Gtk.Buildable.get_name(page)
            self._name2page['~' + name.rsplit('_')[-1]] = i

        if get_greeter_version() < 0x020100:
            self._widgets.common_options.props.visible = False

            self._name2page = {
                Indicators.External: self._name2page[Indicators.External],
                Indicators.Text: self._name2page[Indicators.Text]}
            text_prefix = 'option_text_fallback'
        else:
            self._name2page[Indicators.Text] = -1
            text_prefix = 'option_text'

        self._option_type = IndicatorTypeEntry(WidgetsWrapper(self.builder, 'option_type'))
        self._option_text = OptionEntry.StringEntry(WidgetsWrapper(self.builder, text_prefix))
        self._option_image = IndicatorIconEntry(WidgetsWrapper(self.builder, 'option_image'))
        self._option_path = IndicatorPath(WidgetsWrapper(self.builder, 'option_path'))
        self._option_hide_disabled = \
            OptionEntry.BooleanEntry(WidgetsWrapper(self.builder, 'option_hide_disabled'))

        for entry in (self._option_type, self._option_path):
            entry.changed.connect(self._on_option_changed)

        for name in Indicators:
            self._option_type.add_type(name, self._get_name(name))

        # Hiding first column created by Gtk.ComboBoxText
        self._widgets.path.get_cells()[0].props.visible = False

        for path in sorted(iglob(os.path.join(sys.prefix, 'share', 'unity', 'indicators', '*'))):
            name = os.path.basename(path)
            parts = name.rsplit('.', maxsplit=1)
            if len(parts) == 2 and parts[0] == 'com.canonical.indicator':
                name = parts[1]
            row = IndicatorPath.Row._make(Type=IndicatorPath.ItemType.Value,
                                          Title=name,
                                          Icon='application-x-executable')
            self._widgets.path_model.append(row)

        for path in sorted(iglob(os.path.join(sys.prefix, 'lib', 'indicators3', '7', '*.so'))):
            row = IndicatorPath.Row._make(Type=IndicatorPath.ItemType.Value,
                                          Title=os.path.basename(path),
                                          Icon='application-x-executable')
            self._widgets.path_model.append(row)

    def _on_option_changed(self, entry=None):
        if not self._indicator_loaded:
            return

        name = self._option_type.value
        error = None
        warning = None

        if name == Indicators.External:
            if not str(self._option_path.value).strip():
                error = C_('option-entry|indicators', 'Path/Service field is not filled')
        elif name != self._name:
            if self._is_duplicate and self._is_duplicate(name):
                warning = C_('option-entry|indicators',
                             'Indicator "{name}" is already in the list.\n'
                             'It will be overwritten.').format(name=self._get_name(name, name))

        self._widgets.ok.props.sensitive = error is None
        self._widgets.add.props.sensitive = error is None
        self._widgets.infobar.props.visible = error or warning
        self._widgets.message.props.label = error or warning

        if error:
            self._widgets.infobar.props.message_type = Gtk.MessageType.WARNING
        elif warning:
            self._widgets.infobar.props.message_type = Gtk.MessageType.INFO
        else:
            self._widgets.infobar.props.message_type = Gtk.MessageType.OTHER

    def on_option_type_types_changed(self, combo):
        current = self._widgets.custom_options.props.page
        if current != -1:
            self._widgets.custom_options.get_nth_page(current).props.visible = False
        current = self._name2page.get(combo.props.active_id, -1)
        if current != -1:
            self._widgets.custom_options.get_nth_page(current).props.visible = True
            self._widgets.custom_options.props.page = current
        if self._indicator_loaded:
            defaults = self._get_defaults(combo.props.active_id)
            self._option_text.enabled = Option.Text in defaults
            self._option_image.enabled = Option.Image in defaults

    def on_add_clicked(self, widget):
        self._add_callback(self.get_indicator())
        self._options = deepcopy(self._options)
        self._on_option_changed()

    @property
    def add_callback(self):
        return self._add_callback

    @add_callback.setter
    def add_callback(self, value):
        self._add_callback = value
        self._widgets.add.props.visible = value is not None

    def set_indicator(self, options):
        self._indicator_loaded = False
        self._options = deepcopy(options)
        self._name = options[Option.Name]

        self._option_type.value = options[Option.Name]
        self._option_path.value = options.get(Option.Path)

        self._option_text.value = options.get(Option.Text, '')
        self._option_text.enabled = Option.Text in options

        self._option_image.value = options.get(Option.Image)
        self._option_image.enabled = Option.Image in options

        self._reversed = Option.Layout in options and LayoutSet.Reversed in options[Option.Layout]

        hide_disabled = options.get(Option.HideDisabled, bool2string(False))
        self._option_hide_disabled.value = hide_disabled or bool2string(True)

        self._indicator_loaded = True
        self._on_option_changed()

    def get_indicator(self):
        options = self._options

        name = self._option_type.value
        options[Option.Name] = name

        options[Option.Layout] = set()
        if name not in EmptyIndicators:
            if self._option_text.enabled:
                options[Option.Text] = self._option_text.value or None
                options[Option.Layout].add(LayoutSet.Text)
            if self._option_image.enabled:
                options[Option.Image] = self._option_image.value or None
                options[Option.Layout].add(LayoutSet.Image)
            if self._option_text.enabled and self._option_image.enabled and self._reversed:
                options[Option.Layout].add(LayoutSet.Reversed)

        if LayoutSet.Text not in options[Option.Layout] and Option.Text in options:
            del options[Option.Text]
        if LayoutSet.Image not in options[Option.Layout] and Option.Image in options:
            del options[Option.Image]

        if name == Indicators.External:
            options[Option.Path] = self._option_path.value
        else:
            options.pop(Option.Path, None)

        if name == Indicators.Power and string2bool(self._option_hide_disabled.value):
            options[Option.HideDisabled] = None
        elif Option.HideDisabled in options:
            options.pop(Option.HideDisabled, None)

        return options
