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


from collections import defaultdict

from gi.repository import (
    Gdk,
    Gtk)

import lightdm_gtk_greeter_settings.helpers
from lightdm_gtk_greeter_settings.helpers import (
    check_path_accessibility,
    get_data_path,
    WidgetsEnum)

from gi.overrides import GLib


__all__ = ['MultiheadSetupDialog']

C_ = lambda t: lightdm_gtk_greeter_settings.helpers.C_('option|multihead', t)


class MultiheadSetupDialog(Gtk.Dialog):
    __gtype_name__ = 'MultiheadSetupDialog'

    def __new__(cls, monitors):
        builder = Gtk.Builder()
        builder.add_from_file(get_data_path('%s.ui' % cls.__gtype_name__))
        window = builder.get_object('multihead_setup_dialog')
        window.builder = builder
        window.monitors = monitors
        builder.connect_signals(window)
        window.init_window()
        return window

    class Widgets(WidgetsEnum):
        notebook = 'monitors_notebook'
        available_menu = 'available_menu'
        name = 'name_value'
        name_combo = 'name_combo'

        editor = 'editor_page'
        editor_add_button = 'editor_add_button'
        editor_add_menu_button = 'editor_add_menu_button'
        empty = 'empty_page'
        empty_add_button = 'empty_add_button'
        empty_add_menu_button = 'empty_add_menu_button'

    class PageData:
        group = None
        holder = None
        label = None
        ids = None
        # Entries
        name = None
        background = None

    builder = None
    monitors = None

    def init_window(self):
        self._widgets = self.Widgets(builder=self.builder)

        # To set size of widgets.notebook to size of widgets.editor
        self.realize()

        self._widgets.notebook.remove_page(self._widgets.notebook.page_num(self._widgets.editor))

        self._current_page = None
        self._defaults = {}
        self._page_to_data = {}

        screen = Gdk.Screen.get_default()
        self._available_monitors = [(screen.get_monitor_plug_name(i),
                                     Gtk.MenuItem(screen.get_monitor_plug_name(i)))
                                    for i in range(screen.get_n_monitors())]

        menu_header = Gtk.MenuItem(C_('Detected monitors:'))
        menu_header.set_sensitive(False)
        self._widgets.available_menu.append(menu_header)
        self._widgets.available_menu.append(Gtk.SeparatorMenuItem())
        self._widgets.available_menu.show_all()
        for name, item in self._available_monitors:
            self._widgets.available_menu.append(item)
            item.connect('activate', self.on_add_button_clicked, name)

    def run(self):
        editor_parent = self._widgets.editor.get_parent()
        if editor_parent:
            editor_parent.remove(self._widgets.editor)

        self._widgets.notebook.handler_block_by_func(self.on_switch_page)
        for page in self._widgets.notebook.get_children():
            if page != self._widgets.empty:
                self._widgets.notebook.remove_page(self._widgets.notebook.page_num(page))
        self._widgets.notebook.handler_unblock_by_func(self.on_switch_page)

        for data in self._page_to_data.values():
            for entry, ids in data.ids.items():
                for id_ in ids:
                    entry.disconnect(id_)

        self._page_to_data.clear()

        for group in self.monitors.groups:
            self._add_page(group)

        self._widgets.empty.props.visible = not self._page_to_data
        self._update_monitors_list()

        super().run()

    def _add_page(self, group):
        data = self.PageData()
        data.group = group

        data.holder = Gtk.Box()
        data.holder.show()
        data.label = Gtk.Label(group.entries['name'].value)

        close_button = Gtk.Button()
        close_button.set_focus_on_click(False)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect('clicked', lambda w, p: self._remove_page(p), data.holder)
        close_image = Gtk.Image.new_from_icon_name('stock_close', Gtk.IconSize.INVALID)
        close_image.set_pixel_size(16)
        close_button.add(close_image)

        label_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        label_box.pack_start(data.label, False, False, 3)
        label_box.pack_start(close_button, False, False, 0)

        label_eventbox = Gtk.EventBox()
        label_eventbox.add(label_box)
        label_eventbox.show_all()

        data.name = group.entries['name']
        data.background = group.entries['background']

        data.ids = defaultdict(list)
        data.ids[data.name].append(data.name.changed.connect(self._on_name_changed, data))
        data.ids[data.background].append(
            data.background.changed.connect(self._on_background_changed, data))

        self._on_name_changed(data.name, data)
        self._on_background_changed(data.background, data)

        self._page_to_data[data.holder] = data

        if self._widgets.empty.get_parent():
            self._widgets.empty.hide()

        current_idx = self._widgets.notebook.get_current_page()
        current_idx = self._widgets.notebook.insert_page(data.holder, label_eventbox,
                                                         current_idx + 1)

        return current_idx

    def _remove_page(self, page):
        if page == self._widgets.editor.props.parent:
            page.remove(self._widgets.editor)

        self._widgets.notebook.remove_page(self._widgets.notebook.page_num(page))

        del self.monitors.groups[self._page_to_data[page].group]
        del self._page_to_data[page]

        self._update_monitors_list()
        if not self._page_to_data:
            self._widgets.empty.show()

    def _update_monitors_list(self):
        configs = set(group.entries['name'].value for group in self.monitors.groups)
        used_count = 0
        self._widgets.name_combo.get_model().clear()
        for name, item in self._available_monitors:
            used = name in configs
            if used:
                used_count += 1
            item.props.visible = not used
            if not used:
                self._widgets.name_combo.append_text(name)

        show_button = used_count < len(self._available_monitors)
        self._widgets.name_combo.props.button_sensitivity = (Gtk.SensitivityType.ON if show_button
                                                             else Gtk.SensitivityType.OFF)
        self._widgets.editor_add_menu_button.props.visible = show_button
        self._widgets.empty_add_menu_button.props.visible = show_button

    def _on_name_changed(self, entry, data):
        value = entry.value
        markup = None
        error = None

        if not value:
            markup = C_('<i>No name</i>')
            error = C_('The name can\'t be empty. Configuration will not be saved.')
        elif any(data.name != entry and data.name.value == value
                 for data in self._page_to_data.values()):
            error = (C_('"{name}" is already defined. Only last configuration will be saved.')
                     .format(name=value))

        if markup:
            data.label.set_markup(markup)
        else:
            data.label.set_label(value)

        data.name.error = error
        self._update_monitors_list()

    def _on_background_changed(self, entry, data):
        value = entry.value
        if not value or Gdk.RGBA().parse(value):
            entry.error = None
        else:
            entry.error = check_path_accessibility(value)

    def _focus_name_entry(self):
        self._widgets.name.grab_focus()
        self._widgets.name.set_position(0)

    def on_add_button_clicked(self, widget, name=''):
        group = self.monitors.groups.add(name)
        page_idx = self._add_page(group)

        self._widgets.empty.props.visible = not self._page_to_data
        self._widgets.notebook.set_current_page(page_idx)
        if name:
            self._update_monitors_list()

    def on_switch_page(self, notebook, page, page_idx):
        if page == self._widgets.empty:
            buttons = self._widgets.editor_add_menu_button, self._widgets.empty_add_menu_button
        else:
            buttons = self._widgets.empty_add_menu_button, self._widgets.editor_add_menu_button

            old_parent = self._widgets.editor.get_parent()
            if old_parent:
                old_parent.remove(self._widgets.editor)
            page.add(self._widgets.editor)

            data = self._page_to_data[page]
            for key, *__ in self.monitors.EntriesSetup:
                self.monitors.activate(key, data.group.entries[key])

            GLib.idle_add(self._focus_name_entry)

        buttons[0].props.popup = None
        buttons[1].props.popup = self._widgets.available_menu
