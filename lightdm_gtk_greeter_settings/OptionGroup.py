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

from lightdm_gtk_greeter_settings.helpers import WidgetsWrapper
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry


__all__ = [
    'BaseGroup',
    'SimpleGroup']


# Broken solution - too complex
class BaseGroup(GObject.GObject):

    class __DictWrapper:

        def __init__(self, getter):
            self._getter = getter

        def __getitem__(self, key):
            return self._getter(key)

    def __init__(self, widgets):
        super().__init__()
        self.__entries_wrapper = None
        self.__defaults_wrapper = None

    def read(self, config):
        '''Read group content from specified GreeterConfig object'''
        raise NotImplementedError(self.__class__)

    def write(self, config, changed=None):
        '''Writes content of this group to specified GreeterConfig object'''
        raise NotImplementedError(self.__class__)

    @property
    def entries(self):
        '''entries["key"] - key => Entry mapping. Read only.'''
        if not self.__entries_wrapper:
            self.__entries_wrapper = BaseGroup.__DictWrapper(self._get_entry)
        return self.__entries_wrapper

    @property
    def defaults(self):
        '''defaults["key"] - default value for "key" entry. Read only.'''
        if not self.__defaults_wrapper:
            self.__defaults_wrapper = BaseGroup.__DictWrapper(self._get_default)
        return self.__defaults_wrapper

    def _get_entry(self, key):
        raise NotImplementedError(self.__class__)

    def _get_default(self, key):
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
            value = config[self._name, key]
            entry.value = value if value is not None else self._defaults[key]
            entry.enabled = value is not None

    def write(self, config, changed=None):
        for key, entry in self._entries.items():
            if changed and not changed(entry):
                continue
            del config[self._name, key]
            if entry.enabled:
                config[self._name, key] = entry.value, self._get_default(key)

    def _get_entry(self, key):
        return self._entries.get(key)

    def _get_default(self, key):
        return self._defaults.get(key)
