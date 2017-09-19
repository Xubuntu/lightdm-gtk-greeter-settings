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
import os
import shlex
import sys
from functools import partialmethod
from glob import iglob
from itertools import chain
from locale import gettext as _

from gi.repository import (
    Gdk,
    GLib,
    Gtk)
from gi.repository import Pango
from gi.repository.GObject import markup_escape_text as escape_markup

from lightdm_gtk_greeter_settings import (
    Config,
    helpers,
    IconEntry,
    IndicatorsEntry,
    OptionEntry,
    PositionEntry)
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    string2bool,
    SimpleEnum,
    WidgetsEnum,
    WidgetsWrapper)
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

    GreeterGroupSetup = {
        # Appearance
        'theme-name': (OptionEntry.StringEntry, ''),
        'icon-theme-name': (OptionEntry.StringEntry, ''),
        'font-name': (OptionEntry.FontEntry, 'Sans 10'),
        'xft-antialias': (OptionEntry.BooleanEntry, None),
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
        'allow-debugging': (OptionEntry.BooleanEntry, 'false'), }

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

        if self.mode == WindowMode.Embedded:
            self.on_entry_removed = self.on_entry_removed_embedded
            self.on_entry_changed = self.on_entry_changed_embedded
            self._write = self._write_embedded

            self._widgets.buttons.hide()
            self._widgets.content.reorder_child(self._widgets.infobar, 0)
            self._widgets.content.connect('destroy', self.on_destroy, True)
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

        self._config = Config.Config()

        self._entry_menu = None
        self._initial_values = {}
        self._entries = None

        self._changed_entries = None
        self._new_entries = None
        self._removed_entries = None

        self._groups = (
            SimpleGroup('greeter', WidgetsWrapper(self.builder, 'greeter'), self.GreeterGroupSetup),
            MonitorsGroup(self.builder))

        for group in self._groups:
            group.entry_added.connect(self.on_entry_added)
            group.entry_removed.connect(self.on_entry_removed)

        self._allow_edit = self._config.is_writable()
        self._update_apply_button()

        if not self._allow_edit:
            self._set_message(_('You don\'t have permissions to change greeter configuration'),
                              Gtk.MessageType.WARNING)
            if self.mode != WindowMode.Embedded:
                helpers.show_message(
                    text=_('No permissions to save configuration'),
                    secondary_text=_(
                        'It seems that you don\'t have permissions to write to '
                        'file:\n{path}\n\nTry to run this program using "sudo" '
                        'or "pkexec"').format(path=helpers.get_config_path()),
                    message_type=Gtk.MessageType.WARNING)

        self._read()

    def _set_message(self, message, type_=Gtk.MessageType.INFO):
        if not message:
            self._widgets.infobar.hide()

        self._widgets.infobar.props.message_type = type_
        self._widgets.infobar_label.props.label = message
        self._widgets.infobar.show()

    def _update_apply_button(self):
        allow = (self._allow_edit and
                 (self._changed_entries or self._new_entries or self._removed_entries))
        self._widgets.apply.props.sensitive = allow

    def _read(self):
        self._config.read()
        self._changed_entries = None
        self._new_entries = None
        self._removed_entries = None

        for group in self._groups:
            group.read(self._config)

        self._initial_values = {entry: InitialValue(entry.value, entry.enabled)
                                for entry in self._initial_values.keys()}

        self._changed_entries = set()
        self._new_entries = set()
        self._removed_entries = set()

        self._update_apply_button()

    def _write(self):
        changed = self._changed_entries | self._new_entries
        for group in self._groups:
            group.write(self._config, changed.__contains__)

        if self.mode != WindowMode.Embedded:
            for entry in changed:
                self._initial_values[entry] = InitialValue(entry.value, entry.enabled)

        self._changed_entries.clear()
        self._new_entries.clear()
        self._removed_entries.clear()

        try:
            self._config.write()
        except OSError as e:
            helpers.show_message(e, Gtk.MessageType.ERROR)

        self._update_apply_button()

    _write_timeout_id = None

    def _write_embedded(self, delay=750):
        if self._write_timeout_id:
            GLib.Source.remove(self._write_timeout_id)
        if delay:
            self._write_timeout_id = GLib.timeout_add(delay, self.on_write_timeout)
        else:
            self._write_timeout_id = None
            self.on_write_timeout()

    def on_write_timeout(self):
        self._write_timeout_id = None
        self.__class__._write(self)
        return False

    def on_entry_added(self, group, source, entry, key):
        if isinstance(source, SimpleGroup) and (source.name, key) in self.entries_setup:
            for action in self.entries_setup[(source.name, key)]:
                fname = 'on_entry_%s_%s_%s' % (action, source.name, key)
                f = getattr(self, fname.replace('-', '_'))
                if action == 'setup':
                    f(entry)
                else:
                    entry.connect(action, f)

        entry.show_menu.connect(self.on_show_menu, source, key)
        entry.changed.connect(self.on_entry_changed)

        self._initial_values[entry] = InitialValue(entry.value, entry.enabled)
        self.on_entry_changed(entry, forced=True)

        if self._new_entries is not None:
            self._new_entries.add(entry)

    def on_entry_removed(self, source, group, entry, key):
        if self._changed_entries is None:
            return

        self._initial_values.pop(entry, None)
        if entry in self._new_entries:
            self._new_entries.discard(entry)
            self._changed_entries.discard(entry)
        else:
            self._removed_entries.add(entry)

        self._update_apply_button()

    def on_entry_removed_embedded(self, source, group, entry, key):
        if self._removed_entries is None:
            return

        self._initial_values.pop(entry, None)
        self._removed_entries.add(entry)
        if self._allow_edit:
            self._write()

    def on_entry_changed(self, entry, forced=False):
        if self._changed_entries is None:
            return

        initial = self._initial_values[entry]
        if forced or entry.enabled != initial.enabled or \
           (entry.enabled and entry.value != initial.value):
            self._changed_entries.add(entry)
        else:
            self._changed_entries.discard(entry)

        self._update_apply_button()

    def on_entry_changed_embedded(self, entry, forced=False):
        if self._changed_entries is not None:
            self._changed_entries.add(entry)
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

    def on_show_menu(self, entry, group, key):

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

        if not self._entry_menu:
            class EntryMenu:
                menu = Gtk.Menu()
                group = new_item()
                value = new_item()
                file = new_item()
                error_separator = Gtk.SeparatorMenuItem()
                error = new_item()
                error_action = new_item(self.on_entry_fix_clicked)
                reset_separator = Gtk.SeparatorMenuItem()
                initial = new_item(self.on_entry_reset_clicked)
                default = new_item(self.on_entry_reset_clicked)
                other = []

                menu.append(group)
                menu.append(value)
                menu.append(file)
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

        # [group]
        if group.name:
            menu.group.props.label = '[{group}]'.format(group=group.name)
            menu.group.show()
        else:
            menu.group.hide()

        # key = value
        if entry.enabled:
            menu.value.props.label = '{key} = {value}'.format(
                key=key, value=format_value(value=entry.value, enabled=entry.enabled))
        else:
            menu.value.props.label = '# {key} ='.format(key=key)

        # File with key definition
        config_values = self._config.key_values[group.name, key]
        if entry not in self._changed_entries and \
           config_values and config_values[-1][0] != helpers.get_config_path():
            menu.file.props.label = _('Value defined in file: {path}')\
                .format(path=escape_markup(config_values[-1][0]))
            menu.file.set_tooltip_text(config_values[-1][0])
            menu.file.show()
        else:
            menu.file.hide()

        # Error message
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
            menu.error.set_label(escape_markup(error))

        menu.error.props.visible = error is not None
        menu.error_action.props.visible = error_action is not None
        menu.error_separator.props.visible = error_action is not None

        # Reset to initial value
        initial = self._initial_values[entry]
        if initial.enabled != entry.enabled or initial.value != entry.value:
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

        # Reset to default value
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

        # Reset to values from all other (.conf
        item_idx = 0
        if config_values and len(config_values) > 1:
            values = {None, default, self._initial_values[entry].value, entry.value}
            for __, value in config_values[:-1]:
                if value in values:
                    continue

                if len(menu.other) <= item_idx:
                    item = new_item(self.on_entry_reset_clicked)
                    menu.other.append(item)
                    menu.menu.append(item)
                else:
                    item = menu.other[item_idx]
                item._reset_entry_data = entry, value, None
                value = format_value(value=value)
                item.set_tooltip_markup(value)
                item.props.label = _('Reset to value: <b>{value}</b>').format(value=value)
                item.show()
                item_idx += 1
        for item in menu.other[item_idx:]:
            item.hide()

        menu.reset_separator.props.visible = \
            menu.initial.props.visible or menu.default.props.visible or \
            any(item.props.visible for item in menu.other)

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
    # LP: #1709864, Support gtk-3.* themes
    GtkThemesPattern = (sys.prefix, 'share', 'themes', '*', 'gtk-3.*', 'gtk.css')

    def on_entry_setup_greeter_theme_name(self, entry, pattern=GtkThemesPattern):
        values = entry.widgets['values']
        themes = []
        idx = pattern.index('*') - len(pattern)
        for path in sorted(iglob(os.path.join(*pattern))):
            theme = path.split(os.path.sep)[idx]
            if theme not in themes:
                themes.append(theme)

        themes = sorted(themes, key=lambda theme: theme.lower())

        for theme in themes:
            values.append_text(theme)

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

    def on_destroy(self, widget, write=False):
        if write and self._write_timeout_id:
            self._write_embedded(delay=None)
        Gtk.main_quit()

    def on_apply_clicked(self, *unused):
        self._write()

    def on_reset_clicked(self, *unused):
        self._read()

    def on_close_clicked(self, *unused):
        self.destroy()
