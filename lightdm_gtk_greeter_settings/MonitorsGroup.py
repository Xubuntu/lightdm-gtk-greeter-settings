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


from lightdm_gtk_greeter_settings.MultiheadSetupDialog import MultiheadSetupDialog
from lightdm_gtk_greeter_settings import (
    helpers,
    OptionEntry,
    OptionGroup)
from lightdm_gtk_greeter_settings.helpers import (
    WidgetsWrapper)


__all__ = ['MonitorsGroup']


class MonitorsGroup(OptionGroup.BaseGroup):

    GroupPrefix = 'monitor:'
    EntriesSetup = (('name', OptionEntry.StringEntry),
                    ('background', OptionEntry.BackgroundEntry),
                    ('user-background', OptionEntry.BooleanEntry),
                    ('laptop', OptionEntry.BooleanEntry))

    def __init__(self, widgets):
        super().__init__(widgets)
        self._widgets = helpers.WidgetsWrapper(widgets)
        self._groups = []
        self._adapters = {key: OptionGroup.OneToManyEntryAdapter()
                          for key, __ in self.EntriesSetup}
        self._dialog = None

        self._groups_wrapper = helpers.SimpleDictWrapper(
            deleter=self._remove_group,
            add=self._add_group,
            itergetter=lambda: iter(self._groups))

        self._widgets['multihead_label'].connect('activate-link', self._on_label_link_activate)

    def read(self, config):
        for group in self._groups:
            group.clear()
        self._groups.clear()

        for groupname in config:
            if not groupname.startswith(MonitorsGroup.GroupPrefix):
                continue

            monitor = groupname[len(MonitorsGroup.GroupPrefix):].strip()
            self._add_group(monitor, groupname, config)

    def write(self, config, is_changed=None):
        groups = set(group.entries['name'].value for group in self._groups)
        groups_to_remove = tuple(name for name in config
                                 if (name.startswith(self.GroupPrefix) and
                                     name[len(self.GroupPrefix):].strip() not in groups))

        for group in self._groups:
            name = group.entries['name']
            new_name = self.GroupPrefix + ' ' + name.value

            if group.name == new_name:
                def changed_(entry):
                    if entry == name:
                        return False
                    return not is_changed or is_changed(entry)
            else:
                def changed_(entry):
                    return entry != name

            group.name = new_name
            group.write(config, is_changed=changed_)

        for name in groups_to_remove:
            config_group = config[name]
            for key, *__ in self.EntriesSetup:
                del config_group[key]

    def clear(self):
        if not self._groups and not self._adapters:
            return
        for group in self._groups:
            group.clear()
        self._groups.clear()

    def activate(self, key, entry):
        self._adapters[key].activate(entry)

    @property
    def groups(self):
        return self._groups_wrapper

    def _add_group(self, monitor='', groupname='', config=None):
        group = OptionGroup.SimpleGroup(groupname, self._widgets)

        group.entry_added.connect(lambda g, s, e, k: self.entry_added.emit(s, e, k))
        group.entry_removed.connect(lambda g, s, e, k: self.entry_removed.emit(s, e, k))

        group.options = {key: (adapter.new_entry, None)
                         for key, adapter in self._adapters.items()}

        if config:
            group.read(config)

        name = group.entries['name']
        name.enabled = True
        name.value = monitor

        self._groups.append(group)
        return group

    def _remove_group(self, group):
        group.clear()
        self._groups.remove(group)

    def _on_label_link_activate(self, label, uri):
        if not self._dialog:
            self._dialog = MultiheadSetupDialog(self)
            self._dialog.props.transient_for = self._widgets['multihead_label'].get_toplevel()

            for key, klass in self.EntriesSetup:
                self._adapters[key].base_entry = klass(WidgetsWrapper(self._dialog.builder, key))

        self._dialog.run()
        self._dialog.hide()
        return True
