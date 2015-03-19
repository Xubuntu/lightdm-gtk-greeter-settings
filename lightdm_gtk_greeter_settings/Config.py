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
from collections import OrderedDict
from glob import iglob


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
            if values and values[-1][0] == self._config._output_path:
                if default is not None and value == default and len(values) == 1:
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

        def get_key_file(self, key):
            values = self._items.get(key)
            return values[-1][0] if values else None

    def __init__(self, input_pathes, output_path):
        self._input_pathes = tuple(input_pathes)
        self._output_path = output_path
        self._groups = OrderedDict()

    def read(self):
        files = []
        for path in self._input_pathes:
            if os.path.isdir(path):
                files.extend(sorted(iglob(os.path.join(path, '*.conf'))))
            elif os.path.exists(path):
                files.append(path)
        if self._output_path not in files:
            files.append(self._output_path)

        self._groups.clear()
        for path in files:
            config_file = configparser.RawConfigParser(strict=False, allow_no_value=True)
            config_file.read(path)

            for groupname, values in config_file.items():
                if groupname == 'DEFAULT':
                    continue

                if groupname not in self._groups:
                    self._groups[groupname] = Config.ConfigGroup(self)
                group = self._groups[groupname]

                for key, value in values.items():
                    if key in group._items:
                        values = group._items[key]
                        if value is not None or values:
                            values.append((path, value))
                    elif value is not None:
                        group._items[key] = [(path, value)]

    def write(self):
        config_file = configparser.RawConfigParser(strict=False, allow_no_value=True)

        for groupname, group in self._groups.items():
            config_file.add_section(groupname)
            config_section = config_file[groupname]

            for key, values in group._items.items():
                if not values or values[-1][0] != self._output_path:
                    continue
                if values[-1][1] is not None or len(values) > 1:
                    config_section[key] = values[-1][1]

        with open(self._output_path, 'w') as file:
            config_file.write(file)

    def items(self):
        return self._groups.items()

    def allitems(self):
        return ((g, k, items[k]) for (g, items) in self._groups.items() for k in items._items)

    def add_group(self, name):
        if name in self._groups:
            return self._groups[name]
        else:
            return self._groups.setdefault(name, Config.ConfigGroup(self))

    def get_key_file(self, groupname, key):
        group = self._groups.get(groupname)
        return group.get_key_file(key) if group is not None else None

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
                self._groups = Config.ConfigGroup(self)
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
