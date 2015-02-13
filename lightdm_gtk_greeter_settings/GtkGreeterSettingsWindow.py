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
import shlex
import sys
from glob import iglob
from functools import partialmethod
from itertools import chain
from locale import gettext as _

from gi.repository import (
    Gdk,
    Gtk)
from gi.repository import Pango
from gi.repository.GObject import markup_escape_text as escape_markup

from lightdm_gtk_greeter_settings import (
    helpers,
    IconEntry,
    IndicatorsEntry,
    OptionEntry,
    PositionEntry)
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    string2bool,
    SimpleEnum,
    WidgetsEnum)
from lightdm_gtk_greeter_settings.MonitorsGroup import MonitorsGroup
from lightdm_gtk_greeter_settings.OptionGroup import SimpleGroup


__all__ = ['GtkGreeterSettingsWindow',
           'WindowMode']


class WindowMode(SimpleEnum):
    Default = 'default'
    Embedded = 'embedded'
    GtkHeader = 'gtk-header'


InitialValue = collections.namedtuple('InitialValue', ('value', 'enabled'))


class GtkGreeterSettingsWindow(Gtk.Window):

    __gtype_name__ = 'GtkGreeterSettingsWindow'

    class Widgets(WidgetsEnum):
        apply = 'apply_button'
        reload = 'reset_button'
        close = 'close_button'
        buttons = 'dialog_buttons'
        content = 'content_box'
        infobar = 'infobar'
        infobar_label = 'infobar_label'
        multihead_label = 'multihead_label'

    def __new__(cls, mode=WindowMode.Default):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('settings_window')
        window.builder = builder
        window.mode = mode
        builder.connect_signals(window)
        window.init_window()
        return window

    builder = None
    mode = WindowMode.Default

    entries_setup = {
        ('greeter', 'allow-debugging'): ('changed',),
        ('greeter', 'background'): ('changed',),
        ('greeter', 'default-user-image'): ('changed',),
        ('greeter', 'screensaver-timeout'): ('setup', 'get', 'set'),
        ('greeter', 'theme-name'): ('setup', 'changed'),
        ('greeter', 'icon-theme-name'): ('setup', 'changed'),
        ('greeter', 'keyboard'): ('changed',),
        ('greeter', 'reader'): ('changed',)}

    def init_window(self):
        self._widgets = self.Widgets(builder=self.builder)
        self._multihead_dialog = None
        self._entry_menu = None
        self._initial_values = {}
        self._changed_entries = None
        self._entries = None
        self._groups = (
            SimpleGroup('greeter', self.builder, {
                # Appearance
                'theme-name': (OptionEntry.StringEntry, ''),
                'icon-theme-name': (OptionEntry.StringEntry, ''),
                'font-name': (OptionEntry.FontEntry, 'Sans 10'),
                'xft-antialias': (OptionEntry.BooleanEntry, 'false'),
                'xft-dpi': (OptionEntry.StringEntry, None),
                'xft-rgba': (OptionEntry.ChoiceEntry, None),
                'xft-hintstyle': (OptionEntry.ChoiceEntry, None),
                'background': (OptionEntry.BackgroundEntry, '#000000'),
                'user-background': (OptionEntry.BooleanEntry, 'true'),
                'hide-user-image': (OptionEntry.InvertedBooleanEntry, 'false'),
                'default-user-image': (IconEntry.IconEntry, '#avatar-default'),
                # Panel
                'clock-format': (OptionEntry.ClockFormatEntry, '%a, %H:%M'),
                'indicators': (IndicatorsEntry.IndicatorsEntry,
                               '~host;~spacer;~clock;~spacer;~language;~session;~a11y;~power'),
                # Position
                'position': (PositionEntry.PositionEntry, '50%,center'),
                # Misc
                'screensaver-timeout': (OptionEntry.AdjustmentEntry, '60'),
                'keyboard': (OptionEntry.StringPathEntry, ''),
                'reader': (OptionEntry.StringPathEntry, ''),
                'a11y-states': (OptionEntry.AccessibilityStatesEntry, ''),
                'allow-debugging': (OptionEntry.BooleanEntry, 'false'), }),
            MonitorsGroup(self.builder))

        for group in self._groups:
            group.entry_added.connect(self.on_entry_added)
            group.entry_removed.connect(self.on_entry_removed)

        self._config_path = helpers.get_config_path()
        self._allow_edit = self._has_access_to_write(self._config_path)
        self._widgets.apply.props.visible = self._allow_edit

        if not self._allow_edit:
            self._set_message(_('You don\'t have permissions to change greeter configuration'),
                              Gtk.MessageType.WARNING)
            if self.mode != WindowMode.Embedded:
                helpers.show_message(
                    text=_('No permissions to save configuration'),
                    secondary_text=_(
                        'It seems that you don\'t have permissions to write to '
                        'file:\n{path}\n\nTry to run this program using "sudo" '
                        'or "pkexec"').format(path=self._config_path),
                    message_type=Gtk.MessageType.WARNING)

        if self.mode == WindowMode.Embedded:
            self.on_entry_changed = self.on_entry_changed_embedded
            self._widgets.buttons.hide()
            self._widgets.content.reorder_child(self._widgets.infobar, 0)
            # Socket/Plug focus issues workaround
            self._widgets.multihead_label.connect('button-press-event', self.on_multihead_click)
        elif self.mode == WindowMode.GtkHeader:
            for button in (self._widgets.apply, self._widgets.reload):
                self._widgets.buttons.remove(button)
                button.set_label('')
                button.set_always_show_image(True)
            self._widgets.buttons.hide()

            header = Gtk.HeaderBar()
            header.set_show_close_button(True)
            header.props.title = self.get_title()
            header.pack_start(self._widgets.reload)
            header.pack_start(self._widgets.apply)
            header.show_all()

            self.set_titlebar(header)

        self._config = configparser.RawConfigParser(strict=False)
        self._read()

    def _has_access_to_write(self, path):
        if os.path.exists(path) and os.access(self._config_path, os.W_OK):
            return True
        return os.access(os.path.dirname(self._config_path), os.W_OK | os.X_OK)

    def _set_message(self, message, type_=Gtk.MessageType.INFO):
        if not message:
            self._widgets.infobar.hide()

        self._widgets.infobar.props.message_type = type_
        self._widgets.infobar_label.props.label = message
        self._widgets.infobar.show()

    def _read(self):
        self._config.clear()
        try:
            if not self._config.read(self._config_path) and \
               self.mode != WindowMode.Embedded:
                helpers.show_message(text=_('Failed to read configuration file: {path}')
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

        if self.mode != WindowMode.Embedded:
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

        label_holder = entry.widgets['label_holder']
        if label_holder and isinstance(group, SimpleGroup):
            label_holder.connect('button-press-event', self.on_entry_label_clicked,
                                 entry, group, key)

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

    def on_entry_changed_embedded(self, entry, force=False):
        if self._changed_entries is None:
            return

        initial = self._initial_values[entry]
        if force or entry.enabled != initial.enabled or \
           (entry.enabled and entry.value != initial.value):
            self._changed_entries.add(entry)
        else:
            self._changed_entries.discard(entry)

        if self._allow_edit:
            self._write()

    def on_entry_reset_clicked(self, item):
        entry, value, enabled = item._reset_entry_data
        if enabled is None:
            entry.value = value
        else:
            entry.enabled = enabled

    def on_entry_fix_clicked(self, item):
        entry, action = item._fix_entry_data
        action(entry)

    def on_entry_label_clicked(self, widget, event, entry, group, key):
        if event.button != 3:
            return

        if not self._entry_menu:
            def new_item(activate=None, width=90):
                item = Gtk.MenuItem('')
                label = item.get_child()
                label.props.use_markup = True
                label.props.ellipsize = Pango.EllipsizeMode.END
                label.props.max_width_chars = width
                if activate:
                    item.connect('activate', activate)
                else:
                    item.props.sensitive = False
                return item

            class EntryMenu:
                menu = Gtk.Menu()
                value = new_item()
                error_separator = Gtk.SeparatorMenuItem()
                error = new_item()
                error_action = new_item(self.on_entry_fix_clicked)
                reset_separator = Gtk.SeparatorMenuItem()
                initial = new_item(self.on_entry_reset_clicked)
                default = new_item(self.on_entry_reset_clicked)

                menu.append(value)
                menu.append(error_separator)
                menu.append(error)
                menu.append(error_action)
                menu.append(reset_separator)
                menu.append(initial)
                menu.append(default)
                menu.show_all()

            self._entry_menu = EntryMenu()

        def format_value(value=None, enabled=True):
            if not enabled:
                return _('<i>disabled</i>')
            if value == '':
                return _('<i>empty string</i>')
            elif value is None:
                return _('<i>None</i>')
            else:
                return escape_markup(str(value))

        menu = self._entry_menu

        menu.value.props.label = '{key} = {value}'.format(
            group=group.name,
            key=key,
            value=format_value(value=entry.value, enabled=entry.enabled))

        error = entry.error
        error_action = None
        if error:
            aname = ('get_entry_fix_%s_%s' % (group.name, key)).replace('-', '_')
            get_fix = getattr(self, aname, None)
            if get_fix:
                label, error_action = get_fix(entry)
                if label:
                    menu.error_action.props.label = label or ''
                if error_action:
                    menu.error_action._fix_entry_data = entry, error_action
            menu.error.set_label(error)

        menu.error.props.visible = error is not None
        menu.error_action.props.visible = error_action is not None
        menu.error_separator.props.visible = error_action is not None

        if entry in self._changed_entries:
            initial = self._initial_values[entry]

            if entry.enabled != initial.enabled and not initial.enabled:
                menu.initial._reset_entry_data = entry, None, initial.enabled
            else:
                menu.initial._reset_entry_data = entry, initial.value, None

            value = format_value(value=initial.value, enabled=initial.enabled)
            menu.initial.set_tooltip_markup(value)
            menu.initial.props.visible = True
            menu.initial.props.label = \
                _('Reset to initial value: <b>{value}</b>').format(value=value)
        else:
            menu.initial.props.visible = False

        default = group.defaults[key]
        if default is not None and entry.value != default:
            value = format_value(value=default)
            menu.default._reset_entry_data = entry, default, None
            menu.default.set_tooltip_markup(value)
            menu.default.props.visible = True
            menu.default.props.label = \
                _('Reset to default value: <b>{value}</b>').format(value=value)
        else:
            menu.default.props.visible = False

        menu.reset_separator.props.visible = \
            menu.initial.props.visible or menu.default.props.visible

        self._entry_menu.menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

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
        try:
            value = int(float(value))
        except ValueError:
            value = 60

        if value > 60:
            return (value - 59) * 60
        return value

    def on_entry_set_greeter_screensaver_timeout(self, entry=None, value=None):
        try:
            value = int(float(value))
        except ValueError:
            value = 60

        if value > 60:
            return value // 60 + 59
        return value

    def on_entry_format_scale_greeter_screensaver_timeout(self, scale, value, adjustment):
        if value != adjustment.props.lower and value != adjustment.props.upper:
            value = self.on_entry_get_greeter_screensaver_timeout(value=value)
            return '%02d:%02d' % (value // 60, value % 60)
        return ''

    # [greeter] theme-name
    GtkThemesPattern = (sys.prefix, 'share', 'themes', '*', 'gtk-3.0', 'gtk.css')

    def on_entry_setup_greeter_theme_name(self, entry, pattern=GtkThemesPattern):
        values = entry.widgets['values']
        idx = pattern.index('*') - len(pattern)
        for path in sorted(iglob(os.path.join(*pattern))):
            values.append_text(path.split(os.path.sep)[idx])

    def on_entry_changed_greeter_theme_name(self, entry, pattern=GtkThemesPattern):
        value = entry.value
        if value:
            path = (p if p != '*' else value.strip() for p in pattern)
            entry.error = helpers.check_path_accessibility(os.path.join(*path))
        else:
            entry.error = None

    # [greeter] icon-theme-name
    IconThemesPattern = (sys.prefix, 'share', 'icons', '*', 'index.theme')
    on_entry_setup_greeter_icon_theme_name = partialmethod(on_entry_setup_greeter_theme_name,
                                                           pattern=IconThemesPattern)

    on_entry_changed_greeter_icon_theme_name = partialmethod(on_entry_changed_greeter_theme_name,
                                                             pattern=IconThemesPattern)

    # [greeter] allow-debugging
    def on_entry_changed_greeter_allow_debugging(self, entry):
        gtk_version = Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION, Gtk.MICRO_VERSION
        minimal_version = 3, 14, 0
        if gtk_version < minimal_version and string2bool(entry.value):
            entry.error = C_('option|greeter|allow-debugging',
                             'GtkInspector is not available on your system\n'
                             'Gtk version: {current} < {minimal}').format(
                current=gtk_version, minimal=minimal_version)
        else:
            entry.error = None

    # [greeter] default-user-image
    def on_entry_changed_greeter_default_user_image(self, entry):
        value = entry.value
        if value.startswith('#'):
            entry.error = None
        else:
            entry.error = helpers.check_path_accessibility(value)

    def get_entry_fix_greeter_default_user_image(self, entry):
        value = entry.value
        if not entry.error or value.startswith('#'):
            return None, None
        return None, None

    # [greeter] background
    def on_entry_changed_greeter_background(self, entry):
        value = entry.value
        if not value or Gdk.RGBA().parse(value):
            entry.error = None
        else:
            entry.error = helpers.check_path_accessibility(value)

    # [greeter] keyboard
    def on_entry_changed_greeter_keyboard(self, entry):
        error = None
        if entry.enabled:
            value = entry.value
            if os.path.isabs(value):
                argv = shlex.split(value)
                error = helpers.check_path_accessibility(argv[0], executable=True)
        entry.error = error

    # [greeter] reader
    on_entry_changed_greeter_reader = on_entry_changed_greeter_keyboard

    def on_multihead_click(self, label, event):
        if event.button == 1:
            label.emit('activate-link', '')
            return True
        return False

    def on_destroy(self, *unused):
        Gtk.main_quit()

    def on_apply_clicked(self, *unused):
        self._write()

    def on_reset_clicked(self, *unused):
        self._read()

    def on_close_clicked(self, *unused):
        self.destroy()
