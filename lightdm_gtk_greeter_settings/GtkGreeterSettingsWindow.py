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


import collections
import configparser
import os
import sys
from glob import iglob
from itertools import chain
from locale import gettext as _

from gi.repository import (
    Gdk,
    Gtk)

from lightdm_gtk_greeter_settings import (
    helpers,
    IndicatorsEntry,
    OptionEntry,
    PositionEntry)
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    string2bool,
    WidgetsWrapper, WidgetsEnum)
from lightdm_gtk_greeter_settings.MonitorsGroup import MonitorsGroup
from lightdm_gtk_greeter_settings.OptionGroup import SimpleGroup


__all__ = ['GtkGreeterSettingsWindow']


InitialValue = collections.namedtuple('InitialValue', ('value', 'enabled'))


class GtkGreeterSettingsWindow(Gtk.Window):

    __gtype_name__ = 'GtkGreeterSettingsWindow'

    class Widgets(WidgetsEnum):
        apply = 'apply_button'
        infobar = 'infobar'

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('settings_window')
        window.builder = builder
        builder.connect_signals(window)
        window.init_window()
        return window

    builder = None

    entries_setup = {
        ('greeter', 'allow-debugging'): ('changed',),
        ('greeter', 'background'): ('changed',),
        ('greeter', 'default-user-image'): ('changed',),
        ('greeter', 'screensaver-timeout'): ('setup', 'get', 'set'),
        ('greeter', 'theme-name'): ('setup', 'changed'),
        ('greeter', 'icon-theme-name'): ('setup', 'changed')}

    def init_window(self):
        self._widgets = self.Widgets(builder=self.builder)

        self._multihead_dialog = None
        self._initial_values = {}
        self._changed_entries = None
        self._entries = None
        self._groups = (
            SimpleGroup('greeter', self.builder, {
                # Appearance
                'theme-name': (OptionEntry.StringEntry, None),
                'icon-theme-name': (OptionEntry.StringEntry, None),
                'font-name': (OptionEntry.FontEntry, 'Sans 10'),
                'xft-antialias': (OptionEntry.BooleanEntry, 'false'),
                'xft-dpi': (OptionEntry.StringEntry, None),
                'xft-rgba': (OptionEntry.ChoiceEntry, None),
                'xft-hintstyle': (OptionEntry.ChoiceEntry, None),
                'background': (OptionEntry.BackgroundEntry, '#000000'),
                'user-background': (OptionEntry.BooleanEntry, 'true'),
                'hide-user-image': (OptionEntry.InvertedBooleanEntry, 'false'),
                'default-user-image': (OptionEntry.IconEntry, '#avatar-default'),
                # Panel
                'clock-format': (OptionEntry.ClockFormatEntry, '%a, %H:%M'),
                'indicators': (IndicatorsEntry.IndicatorsEntry,
                               '~host;~spacer;~clock;~spacer;~language;~session;~a11y;~power'),
                # Position
                'position': (PositionEntry.PositionEntry, '50%,center'),
                # Misc
                'screensaver-timeout': (OptionEntry.AdjustmentEntry, 60),
                'keyboard': (OptionEntry.StringPathEntry, None),
                'reader': (OptionEntry.StringPathEntry, None),
                'a11y-states': (OptionEntry.AccessibilityStatesEntry, None),
                'allow-debugging': (OptionEntry.BooleanEntry, 'false'), }),
            MonitorsGroup(WidgetsWrapper(self.builder)))

        for group in self._groups:
            group.entry_added.connect(self.on_entry_added)
            group.entry_removed.connect(self.on_entry_removed)

        self._config_path = helpers.get_config_path()
        self._allow_edit = self._has_access_to_write(self._config_path)
        self._widgets.infobar.props.visible = not self._allow_edit
        self._widgets.apply.props.visible = self._allow_edit
        if not self._allow_edit:
            helpers.show_message(
                text=_('No permissions to save configuration'),
                secondary_text=_(
                    'It seems that you don\'t have permissions to write to '
                    'file:\n{path}\n\nTry to run this program using "sudo" '
                    'or "pkexec"').format(path=self._config_path),
                message_type=Gtk.MessageType.WARNING)

        self._config = configparser.RawConfigParser(strict=False)
        self._read()

    def _has_access_to_write(self, path):
        if os.path.exists(path) and os.access(self._config_path, os.W_OK):
            return True
        return os.access(os.path.dirname(self._config_path), os.W_OK | os.X_OK)

    def _read(self):
        self._config.clear()
        try:
            if not self._config.read(self._config_path):
                helpers.show_message(text=_('Failed to read configuration '
                                            'file: {path}')
                                     .format(path=self._config_path),
                                     message_type=Gtk.MessageType.ERROR)
        except (configparser.DuplicateSectionError,
                configparser.MissingSectionHeaderError):
            pass

        self._changed_entries = None

        for group in self._groups:
            group.read(self._config)

        self._initial_values = {entry: InitialValue(entry.value, entry.enabled)
                                for entry in self._initial_values.keys()}
        self._changed_entries = set()
        self._widgets.apply.props.sensitive = False

    def _write(self):
        for group in self._groups:
            group.write(self._config)

        for entry in self._changed_entries:
            self._initial_values[entry] = InitialValue(entry.value, entry.enabled)

        self._changed_entries.clear()
        self._widgets.apply.props.sensitive = False

        try:
            with open(self._config_path, 'w') as file:
                self._config.write(file)
        except OSError as e:
            helpers.show_message(e, Gtk.MessageType.ERROR)

    def on_entry_added(self, group, entry, key):
        if isinstance(group, SimpleGroup) and (group.name, key) in self.entries_setup:
            for action in self.entries_setup[(group.name, key)]:
                fname = 'on_entry_%s_%s_%s' % (action, group.name, key)
                f = getattr(self, fname.replace('-', '_'))
                if action == 'setup':
                    f(entry)
                else:
                    entry.connect(action, f)

        entry.changed.connect(self.on_entry_changed)
        self._initial_values[entry] = InitialValue(entry.value, entry.enabled)
        self.on_entry_changed(entry, force=True)

    def on_entry_removed(self, group, entry, key):
        self._initial_values.pop(entry)
        if self._changed_entries is None:
            return

        self._changed_entries.discard(entry)
        self._widgets.apply.props.sensitive = self._allow_edit and self._changed_entries

    def on_entry_changed(self, entry, force=False):
        if self._changed_entries is None:
            return

        initial = self._initial_values[entry]
        if force or entry.enabled != initial.enabled or \
           (entry.enabled and entry.value != initial.value):
            self._changed_entries.add(entry)
        else:
            self._changed_entries.discard(entry)

        self._widgets.apply.props.sensitive = self._allow_edit and self._changed_entries

    # [greeter] screensaver-timeout
    def on_entry_setup_greeter_screensaver_timeout(self, entry):
        view = entry.widgets['view']
        adjustment = entry.widgets['adjustment']
        end_label = entry.widgets['end-label']
        for mark in chain((range(10, 61, 10)),
                          (range(69, int(adjustment.props.upper), 10))):
            view.add_mark(mark, Gtk.PositionType.BOTTOM, None)
        total = int(adjustment.props.upper - 60) + 1
        end_label.props.label = C_('option|greeter|screensaver-timeout',
                                   '{count} min').format(count=total)

        view.connect('format-value',
                     self.on_entry_format_scale_greeter_screensaver_timeout,
                     adjustment)

    def on_entry_get_greeter_screensaver_timeout(self, entry=None, value=None):
        value = int(float(value))
        if value > 60:
            return (value - 59) * 60
        return value

    def on_entry_set_greeter_screensaver_timeout(self, entry=None, value=None):
        value = int(float(value))
        if value > 60:
            return value // 60 + 59
        return value

    def on_entry_format_scale_greeter_screensaver_timeout(self, scale, value, adjustment):
        if value != adjustment.props.lower and value != adjustment.props.upper:
            value = self.on_entry_get_greeter_screensaver_timeout(value=value)
            return '%02d:%02d' % (value // 60, value % 60)
        return ''

    # [greeter] theme-name
    def on_entry_setup_greeter_theme_name(self, entry):
        values = entry.widgets['values']
        for theme in sorted(iglob(os.path.join(sys.prefix, 'share', 'themes', '*', 'gtk-3.0'))):
            values.append_text(theme.split(os.path.sep)[-2])

    def on_entry_changed_greeter_theme_name(self, entry):
        if not entry.value or \
                entry.value in (row[0] for row in entry.widgets['values'].props.model):
            entry.error = None
        else:
            entry.error = C_('option|greeter|theme-name', 'Selected theme is not available')

    # [greeter] icon-theme-name
    def on_entry_setup_greeter_icon_theme_name(self, entry):
        values = entry.widgets['values']
        for theme in sorted(iglob(os.path.join(sys.prefix, 'share', 'icons', '*', 'index.theme'))):
            values.append_text(theme.split(os.path.sep)[-2])

    def on_entry_changed_greeter_icon_theme_name(self, entry):
        if not entry.value or \
                entry.value in (row[0] for row in entry.widgets['values'].props.model):
            entry.error = None
        else:
            entry.error = C_('option|greeter|icon-theme-name', 'Selected theme is not available')

    # [greeter] allow-debugging
    def on_entry_changed_greeter_allow_debugging(self, entry):
        if (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION, Gtk.MICRO_VERSION) < (3, 14, 0) and \
                string2bool(entry.value):
            entry.error = C_('option|greeter|allow-debugging',
                             'GtkInspector is not available on your system')
        else:
            entry.error = None

    # [greeter] default-user-image
    def on_entry_changed_greeter_default_user_image(self, entry):
        value = entry.value
        if value.startswith('#'):
            entry.error = None
        else:
            entry.error = helpers.check_path_accessibility(value)

    # [greeter] background
    def on_entry_changed_greeter_background(self, entry):
        value = entry.value
        if not value or Gdk.RGBA().parse(value):
            entry.error = None
        else:
            entry.error = helpers.check_path_accessibility(value)

    def on_destroy(self, *unused):
        Gtk.main_quit()

    def on_apply_clicked(self, *unused):
        self._write()

    def on_reset_clicked(self, *unused):
        self._read()

    def on_close_clicked(self, *unused):
        self.destroy()
