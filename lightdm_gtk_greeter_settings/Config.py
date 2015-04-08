#!/usr/bin/env python3
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#   LightDM GTK Greeter Settings
#   Copyright (C) 2015 Andrew P. <pan.pav.7c5@gmail.com>
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

import configparser
import os
import sys
from collections import OrderedDict
from glob import iglob

from gi.repository import GLib

from lightdm_gtk_greeter_settings import helpers


class Config:

    class ConfigGroup:

        def __init__(self, config):
            self._config = config
            self._items = OrderedDict()

        def __iter__(self):
            return iter(self._items)

        def __contains__(self, item):
            return item in self._items

        def __getitem__(self, item):
            values = self._items.get(item)
            return values[-1][1] if values else None

        def __setitem__(self, item, value):
            if isinstance(value, tuple):
                value, default = value
            else:
                default = None

            values = self._items.get(item)

            if values and values[-1][1] == value:
                return

            if values and values[-1][0] == self._config._output_path:
                if len(values) > 1 and values[-2][1] == value:
                    del values[-1]
                elif default is not None and value == default and len(values) == 1:
                    values.clear()
                else:
                    values[-1] = (self._config._output_path, value)
            elif values is not None:
                if default is None or value != default or (values and values[-1][1] != default):
                    values.append((self._config._output_path, value))
            else:
                if default is None or value != default:
                    self._items[item] = [(self._config._output_path, value)]

        def __delitem__(self, item):
            values = self._items.get(item)
            if values is not None:
                if values and values[-1][0] == self._config._output_path:
                    del values[-1]
                if not values:
                    del self._items[item]

    def __init__(self, base_dir='lightdm', base_name='lightdm-gtk-greeter.conf'):
        self._base_dir = base_dir
        self._base_name = base_name
        self._output_path = helpers.get_config_path()
        self._groups = OrderedDict()
        self._key_values = helpers.SimpleDictWrapper(getter=self._get_key_values)

    def read(self):
        self._groups.clear()

        pathes = []
        pathes += GLib.get_system_data_dirs()
        pathes += GLib.get_system_config_dirs()
        pathes.append(os.path.dirname(os.path.dirname(self._output_path)))

        files = []
        for path in pathes:
            files += sorted(iglob(os.path.join(path, self._base_dir,
                                               self._base_name + '.d', '*.conf')))
            files.append(os.path.join(path, self._base_dir, self._base_name))

        for path in filter(os.path.isfile, files):
            config_file = configparser.RawConfigParser(strict=False, allow_no_value=True)
            try:
                if not config_file.read(path):
                    continue
            except configparser.Error as e:
                print(e, file=sys.stderr)
                continue

            for groupname, values in config_file.items():
                if groupname == 'DEFAULT':
                    continue

                if groupname not in self._groups:
                    self._groups[groupname] = Config.ConfigGroup(self)
                group = self._groups[groupname]

                for key, value in values.items():
                    if value is None:
                        print('[{group}] {key}: Keys without values are not allowed'.format(
                            group=groupname, key=key), file=sys.stderr)
                        continue
                    if key.startswith('-'):
                        key = key[1:]
                        value = None

                    if key in group._items:
                        values = group._items[key]
                        if value is not None or values:
                            values.append((path, value))
                    elif value is not None:
                        group._items[key] = [(path, value)]

    def write(self):
        config_file = configparser.RawConfigParser(strict=False)

        for groupname, group in self._groups.items():
            config_section = None
            for key, values in group._items.items():
                if not values or values[-1][0] != self._output_path:
                    continue

                if values[-1][1] is not None or len(values) > 1:
                    if not config_section:
                        config_file.add_section(groupname)
                        config_section = config_file[groupname]
                    if values[-1][1] is None:
                        config_section['-' + key] = ''
                    else:
                        config_section[key] = values[-1][1]

        with open(self._output_path, 'w') as file:
            config_file.write(file)

    def is_writable(self):
        if os.path.exists(self._output_path) and os.access(self._output_path, os.W_OK):
            return True
        return os.access(os.path.dirname(self._output_path), os.W_OK | os.X_OK)

    def items(self):
        return self._groups.items()

    def allitems(self):
        return ((g, k, items[k]) for (g, items) in self._groups.items() for k in items._items)

    def add_group(self, name):
        if name in self._groups:
            return self._groups[name]
        else:
            return self._groups.setdefault(name, Config.ConfigGroup(self))

    @property
    def key_values(self):
        return self._key_values

    def _get_key_values(self, item):
        group = self._groups.get(item[0])
        if group:
            values = group._items.get(item[1])
            if values is not None:
                return tuple(values)
        return None

    def __iter__(self):
        return iter(self._groups)

    def __getitem__(self, item):
        if isinstance(item, tuple):
            group = self._groups.get(item[0])
            return group[item[1]] if group else None
        return self._groups.get(item)

    def __setitem__(self, item, value):
        if isinstance(item, tuple):
            if not item[0] in self._groups:
                self._groups[item[0]] = Config.ConfigGroup(self)
            self._groups[item[0]][item[1]] = value

    def __delitem__(self, item):
        if isinstance(item, tuple):
            group = self._groups.get(item[0])
            if group is not None:
                del group[item[1]]
            return

        group = self._groups.get(item)
        if group is not None:
            if not group:
                del self._groups[item]
                return

            keys_to_remove = []
            for key, values in group._items.items():
                if values[-1][0] == self._output_path:
                    if len(values) == 1:
                        keys_to_remove.append(key)
                    else:
                        values[-1] = (self._output_path, None)
                elif values:
                    values.append((self._output_path, None))

            if len(keys_to_remove) < len(group._items):
                for key in keys_to_remove:
                    del group._items[key]
            else:
                del self._groups[item]
