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
from lightdm_gtk_greeter_settings import helpers


__all__ = [
    'BaseGroup',
    'OneToManyEntryAdapter',
    'SimpleGroup']


# Broken solution - too complex
class BaseGroup(GObject.GObject):

    def __init__(self, widgets):
        super().__init__()
        self.__entries_wrapper = helpers.SimpleDictWrapper(self._get_entry)
        self.__defaults_wrapper = helpers.SimpleDictWrapper(self._get_default)

    def read(self, config):
        '''Read group content from specified GreeterConfig object'''
        raise NotImplementedError(self.__class__)

    def write(self, config, is_changed=None):
        '''Writes content of this group to specified GreeterConfig object'''
        raise NotImplementedError(self.__class__)

    def clear(self):
        '''Removes all entries'''
        raise NotImplementedError(self.__class__)

    @property
    def entries(self):
        '''entries["key"] - key => Entry mapping. Read only.'''
        return self.__entries_wrapper

    @property
    def defaults(self):
        '''defaults["key"] - default value for "key" entry. Read only.'''
        return self.__defaults_wrapper

    def _get_entry(self, key):
        raise NotImplementedError(self.__class__)

    def _get_default(self, key):
        raise NotImplementedError(self.__class__)

    @GObject.Signal
    def entry_added(self, source: object, entry: BaseEntry, key: str):
        '''New entry has been added to this group'''
        pass

    @GObject.Signal
    def entry_removed(self, source: object, entry: BaseEntry, key: str):
        '''Entry has been removed from this group'''
        pass


class SimpleGroup(BaseGroup):

    def __init__(self, name, widgets, options=None):
        super().__init__(widgets)
        self._name = name
        self._options_to_init = options
        self._widgets = WidgetsWrapper(widgets)
        self._entries = {}
        self._defaults = {}

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def options(self):
        pass

    @options.setter
    def options(self, options):
        self.clear()

        for key, (klass, default) in options.items():
            entry = klass(WidgetsWrapper(self._widgets, key))
            if default is not None:
                entry.value = default
            self._entries[key] = entry
            self._defaults[key] = default
            self.entry_added.emit(self, entry, key)

    def read(self, config):
        if self._options_to_init is not None:
            self.options = self._options_to_init
            self._options_to_init = None

        for key, entry in self._entries.items():
            value = config[self._name, key]
            entry.value = value if value is not None else self._defaults[key]
            entry.enabled = value is not None

    def write(self, config, is_changed=None):
        for key, entry in self._entries.items():
            if is_changed and not is_changed(entry):
                continue
            config[self._name, key] = entry.value if entry.enabled else None, self._get_default(key)

    def clear(self):
        if not self._entries:
            return
        for key, entry in self._entries.items():
            self.entry_removed.emit(self, entry, key)
        self._entries.clear()

    def _get_entry(self, key):
        return self._entries.get(key)

    def _get_default(self, key):
        return self._defaults.get(key)


class OneToManyEntryAdapter:

    class Error(Exception):
        pass

    class InvalidEntry(Error):
        pass

    class WrongAdapter(Error):
        pass

    class NoBaseEntryError(Error):
        pass

    class EntryWrapper(BaseEntry):

        def __init__(self, adapter):
            super().__init__(helpers.WidgetsWrapper(None))
            self._adapter = adapter
            self._value = None
            self._error = None
            self._enabled = False

        def _get_value(self):
            return self._value

        def _set_value(self, value):
            self._value = value
            if self._adapter._active == self and self._adapter._base_entry:
                self._adapter._base_entry._set_value(value)

        def _get_error(self):
            return self._error

        def _set_error(self, text):
            self._error = text
            if self._adapter._active == self and self._adapter._base_entry:
                self._adapter._base_entry._set_error(text)

        def _get_enabled(self):
            return self._enabled

        def _set_enabled(self, value):
            self._enabled = value
            if self._adapter._active == self and self._adapter._base_entry:
                self._adapter._base_entry._set_enabled(value)

    def __init__(self, entry=None):
        self._base_entry = None
        self._active = None

        self._on_changed_id = None
        self._on_menu_id = None

        self.base_entry = entry

    @property
    def base_entry(self):
        return self._base_entry

    @base_entry.setter
    def base_entry(self, entry):
        if self._base_entry:
            self._base_entry.disconnect(self._on_changed_id)
            self._base_entry.disconnect(self._on_menu_id)
            self._on_changed_id = None
            self._on_menu_id = None
        self._base_entry = entry
        if entry:
            self._on_changed_id = entry.changed.connect(self._on_changed)
            self._on_menu_id = entry.show_menu.connect(self._on_show_menu)

    def new_entry(self, widgets=None):
        return OneToManyEntryAdapter.EntryWrapper(self)

    def activate(self, entry):
        if not isinstance(entry, OneToManyEntryAdapter.EntryWrapper):
            raise OneToManyEntryAdapter.InvalidEntry()
        if not entry._adapter == self:
            raise OneToManyEntryAdapter.WrongAdapter()
        if not self._base_entry:
            raise OneToManyEntryAdapter.NoBaseEntryError()

        self._active = entry
        with self._base_entry.handler_block(self._on_changed_id):
            self._base_entry._set_value(entry._value)
            self._base_entry._set_enabled(entry._enabled)
            self._base_entry._set_error(entry._error)

    def _on_changed(self, entry):
        if self._active:
            self._active._enabled = entry._get_enabled()
            self._active._value = entry._get_value()
            self._active._emit_changed()

    def _on_show_menu(self, base_entry):
        if self._active:
            self._active.show_menu.emit()
