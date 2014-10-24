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


from gi.repository import GObject
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry
from lightdm_gtk_greeter_settings.helpers import WidgetsWrapper


__all__ = ['BaseGroup', 'SimpleGroup']


# Broken solution - too complex

class BaseGroup(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()

    def read(self, config):
        raise NotImplementedError(self.__class__)

    def write(self, config):
        raise NotImplementedError(self.__class__)

    @GObject.Signal
    def entry_added(self, entry: BaseEntry, key: str):
        '''New entry has been added to this group'''
        pass

    @GObject.Signal
    def entry_removed(self, entry: BaseEntry, key: str):
        '''Entry has been removed from this group'''
        pass


class SimpleGroup(BaseGroup):

    def __init__(self, name, widgets, options):
        super().__init__(widgets)
        self._name = name
        self._widgets = WidgetsWrapper(widgets, name)
        self._options = options
        self._entries = {}
        self._defaults = {}

    @property
    def name(self):
        return self._name

    def read(self, config):

        if not self._entries:
            for key, (klass, default) in self._options.items():
                entry = klass(WidgetsWrapper(self._widgets, key))
                self._entries[key] = entry
                self._defaults[key] = default
                self.entry_added.emit(entry, key)

        for key, entry in self._entries.items():
            if config.has_option(self._name, key):
                entry.value = config.get(self._name, key)
                entry.enabled = True
            else:
                entry.value = self._defaults[key]
                entry.enabled = False

    def write(self, config):

        if not config.has_section(self._name):
            config.add_section(self._name)

        for key, entry in self._entries.items():
            if entry.enabled:
                config.set(self._name, key, entry.value)
            else:
                config.remove_option(self._name, key)

