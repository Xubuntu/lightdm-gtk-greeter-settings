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


from gi.repository import (
    Gdk,
    Gtk)

import lightdm_gtk_greeter_settings.helpers

from lightdm_gtk_greeter_settings.helpers import (
    check_path_accessibility,
    get_data_path,
    WidgetsEnum,
    WidgetsWrapper)
from lightdm_gtk_greeter_settings import OptionEntry

from gi.overrides import GLib


__all__ = ['MultiheadSetupDialog']

C_ = lambda t: lightdm_gtk_greeter_settings.helpers.C_('option|multihead', t)


class PageOptions:
    name = None
    background = None
    background_disabled = None
    user_background = None
    user_background_disabled = None
    laptop = None
    laptop_disabled = None
    label = None


class MultiheadSetupDialog(Gtk.Dialog):
    __gtype_name__ = 'MultiheadSetupDialog'

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(get_data_path('%s.ui' % cls.__gtype_name__))
        window = builder.get_object('multihead_setup_dialog')
        window.builder = builder
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

    builder = None

    def init_window(self):
        self._widgets = self.Widgets(builder=self.builder)

        self._widgets.notebook.remove_page(self._widgets.notebook.page_num(self._widgets.editor))

        self._current_page = None
        self._defaults = {}
        self._options = {}

        self._option_name = OptionEntry.StringEntry(WidgetsWrapper(self.builder, 'name'))
        self._option_bg = OptionEntry.BackgroundEntry(WidgetsWrapper(self.builder, 'background'))
        self._option_user_bg = OptionEntry.BooleanEntry(WidgetsWrapper(self.builder,
                                                                       'user-background'))
        self._option_laptop = OptionEntry.BooleanEntry(WidgetsWrapper(self.builder, 'laptop'))

        self._option_name.changed.connect(self._on_name_changed)
        for entry in (self._option_bg, self._option_user_bg, self._option_laptop):
            entry.changed.connect(self._on_option_changed)

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

    def set_model(self, values):
        self._widgets.notebook.handler_block_by_func(self.on_monitors_notebook_switch_page)
        for page in self._widgets.notebook.get_children():
            self._remove_monitor(page, update=False)
        self._widgets.notebook.handler_unblock_by_func(self.on_monitors_notebook_switch_page)

        self._options.clear()
        for name, entry in values.items():
            options = PageOptions()
            options.name = name
            options.background = entry['background']
            options.user_background = entry['user-background']
            options.laptop = entry['laptop']

            options.background_disabled = self._get_first_not_none(
                options.background, self._defaults.get('background'), '')
            options.user_background_disabled = self._get_first_not_none(
                options.user_background, self._defaults.get('user-background'), 'true')
            options.laptop_disabled = self._get_first_not_none(
                options.laptop, self._defaults.get('laptop'), 'false')

            self._add_monitor(options)

        self._widgets.empty.props.visible = not self._options

        self._update_monitors_list()

    def get_model(self):
        sections = []
        for page in self._widgets.notebook.get_children():
            options = self._options.get(page)
            if not options or not options.name:
                continue
            sections.append((options.name,
                             {'background': options.background,
                              'user-background': options.user_background,
                              'laptop': options.laptop}))
        return sections

    def set_defaults(self, values):
        self._defaults = values.copy()

    def _get_first_not_none(self, *values, fallback=None):
        return next((v for v in values if v is not None), fallback)

    def _add_monitor(self, options):
        holder = Gtk.Box()
        holder.show()

        options.label = Gtk.Label(options.name)
        options.error_image = Gtk.Image.new_from_icon_name('dialog-warning', Gtk.IconSize.INVALID)
        options.error_image.set_pixel_size(16)
        options.error_image.set_no_show_all(True)

        close_button = Gtk.Button()
        close_button.set_focus_on_click(False)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect('clicked', lambda w, p: self._remove_monitor(p), holder)
        close_image = Gtk.Image.new_from_icon_name('stock_close', Gtk.IconSize.INVALID)
        close_image.set_pixel_size(16)
        close_button.add(close_image)

        label_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        label_box.pack_start(options.error_image, False, False, 1)
        label_box.pack_start(options.label, False, False, 3)
        label_box.pack_start(close_button, False, False, 0)

        label_eventbox = Gtk.EventBox()
        label_eventbox.add(label_box)
        label_eventbox.show_all()

        self._options[holder] = options

        if self._widgets.empty.get_parent():
            self._widgets.empty.hide()

        current_idx = self._widgets.notebook.get_current_page()
        current_idx = self._widgets.notebook.insert_page(holder, label_eventbox, current_idx + 1)

        # self._widgets.notebook.set_tab_reorderable(holder, True)

        return current_idx

    def _remove_monitor(self, page, update=True):
        if page not in self._options:
            return

        self._options.pop(page)

        if page == self._widgets.editor.props.parent:
            page.remove(self._widgets.editor)

        if update:
            self._update_monitors_list()
            if not self._options:
                self._widgets.empty.show()

        self._widgets.notebook.remove_page(self._widgets.notebook.page_num(page))

    def _apply_monitor_options(self, options):
        for entry, value, fallback in \
            ((self._option_bg, options.background, options.background_disabled),
             (self._option_user_bg, options.user_background, options.user_background_disabled),
             (self._option_laptop, options.laptop, options.laptop_disabled)):
            entry.handler_block_by_func(self._on_option_changed)
            entry.value = fallback if value is None else value
            entry.enabled = value is not None
            entry.handler_unblock_by_func(self._on_option_changed)

        self._option_name.value = options.name or ''
        self._on_option_changed()
        self._on_name_changed()

    def _on_option_changed(self, entry=None):
        options = self._options.get(self._current_page)
        options.background_disabled = self._option_bg.value
        options.background = options.background_disabled if self._option_bg.enabled else None
        options.user_background_disabled = self._option_user_bg.value
        options.user_background = (options.user_background_disabled
                                   if self._option_user_bg.enabled else None)
        options.laptop_disabled = self._option_laptop.value
        options.laptop = options.laptop_disabled if self._option_laptop.enabled else None

        if not options.background or Gdk.RGBA().parse(options.background):
            self._option_bg.error = None
        else:
            self._option_bg.error = check_path_accessibility(options.background)

    def _on_name_changed(self, entry=None):
        options = self._options[self._current_page]
        options.name = self._option_name.value.strip()
        self._update_monitors_list()

        markup = None
        error = None

        if not options.name:
            markup = C_('<i>No name</i>')
            error = C_('The name can\'t be empty. Configuration will not be saved.')
        elif any(options.name == o.name and p != self._current_page
                 for p, o in self._options.items()):
            error = (C_('"{name}" is already defined. Only last configuration will be saved.')
                     .format(name=options.name))

        if markup:
            options.label.set_markup(markup)
        else:
            options.label.set_label(options.name)

        self._option_name.error = error

    def _focus_name_entry(self):
        self._widgets.name.grab_focus()
        self._widgets.name.set_position(0)

    def on_add_button_clicked(self, widget, name=""):
        options = PageOptions()
        options.name = name

        options.background_disabled = self._get_first_not_none(
            self._defaults.get('background'), '')
        options.user_background_disabled = self._get_first_not_none(
            self._defaults.get('user-background'), 'true')
        options.laptop = self._get_first_not_none(self._defaults.get('laptop'), 'false')

        self._widgets.notebook.set_current_page(self._add_monitor(options))
        if name:
            self._update_monitors_list()

    def on_monitors_notebook_switch_page(self, notebook, page, page_idx):
        if page == self._widgets.empty:
            self._current_page = None
            buttons = self._widgets.editor_add_menu_button, self._widgets.empty_add_menu_button
        else:
            self._current_page = page
            buttons = self._widgets.empty_add_menu_button, self._widgets.editor_add_menu_button

            old_parent = self._widgets.editor.get_parent()
            if old_parent:
                old_parent.remove(self._widgets.editor)
            page.add(self._widgets.editor)
            self._apply_monitor_options(self._options[page])

            GLib.idle_add(self._focus_name_entry)

        buttons[0].props.popup = None
        buttons[1].props.popup = self._widgets.available_menu

    def _update_monitors_list(self):
        used_monitors = set(options.name for options in self._options.values())
        used_count = 0
        self._widgets.name_combo.get_model().clear()
        for name, item in self._available_monitors:
            used = name in used_monitors
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
