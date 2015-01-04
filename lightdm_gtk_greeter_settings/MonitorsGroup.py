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


from gi.repository import Gtk

from lightdm_gtk_greeter_settings.helpers import WidgetsWrapper
from lightdm_gtk_greeter_settings.MultiheadSetupDialog import MultiheadSetupDialog
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry
from lightdm_gtk_greeter_settings.OptionGroup import BaseGroup


__all__ = ['MonitorsGroup']


class MonitorsGroup(BaseGroup):
    GROUP_PREFIX = 'monitor:'

    def __init__(self, widgets):
        super().__init__(widgets)
        self._entries = {}
        self._widgets = WidgetsWrapper(widgets, 'multihead')
        self._dialog = None
        self._widgets['label'].connect('activate-link', self._on_label_link_activate)

    def read(self, config):
        self._entries.clear()
        for name, section in config.items():
            if not name.startswith(self.GROUP_PREFIX):
                continue
            name = name[len(self.GROUP_PREFIX):].strip()
            entry = MonitorEntry(self._widgets)
            entry['background'] = section.get('background', None)
            entry['user-background'] = section.getboolean('user-background', None)
            entry['laptop'] = section.getboolean('laptop', None)
            self._entries[name] = entry
            self.entry_added.emit(entry, name)

    def write(self, config):
        for name in config.sections():
            if name.startswith(self.GROUP_PREFIX):
                config.remove_section(name)
        for name, entry in self._entries.items():
            section = '{prefix} {name}'.format(prefix=self.GROUP_PREFIX, name=name)
            config.add_section(section)
            for key, value in entry:
                if value is not None:
                    config.set(section, key, value)

    def _on_label_link_activate(self, label, uri):
        if not self._dialog:
            self._dialog = MultiheadSetupDialog()
            self._dialog.props.transient_for = self._widgets['label'].get_toplevel()

        self._dialog.set_model(self._entries)

        if self._dialog.run() == Gtk.ResponseType.OK:
            current_names = set(self._entries.keys())
            for name, values in self._dialog.get_model().items():
                if name in self._entries:
                    self._entries[name].assign(values)
                    current_names.discard(name)
                else:
                    entry = MonitorEntry(self._widgets, values)
                    self._entries[name] = entry
                    self.entry_added.emit(entry, name)
            for name in current_names:
                self.entry_added.emit(self._entries.pop(name), name)
        self._dialog.hide()
        return True


class MonitorEntry(BaseEntry):

    def __init__(self, widgets, values=None):
        super().__init__(widgets)
        self._values = values or {}

    def _get_value(self):
        return self._values.copy()

    def _set_value(self, value):
        self._values = value.copy()

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value

    def __iter__(self):
        return iter(self._values.items())

    def assign(self, values):
        if not self._values == values:
            self._values.update(values)
            self._emit_changed()
