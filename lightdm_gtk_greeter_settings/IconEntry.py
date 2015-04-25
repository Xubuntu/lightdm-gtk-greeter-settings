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


import os

from gi.repository import Gtk

from lightdm_gtk_greeter_settings.IconChooserDialog import IconChooserDialog
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry
from lightdm_gtk_greeter_settings.helpers import (
    C_,
    get_data_path,
    set_image_from_path,
    SimpleEnum)


__all__ = ['IconEntry']


class IconEntry(BaseEntry):

    class Item(SimpleEnum):
        priority = 0
        # (value, just_label) => (label, tooltip)
        update = None
        # (old_value) => str or None
        ask = None
        # Associated menu item
        menuitem = None

    def __init__(self, widgets):
        super().__init__(widgets)
        self._value = None
        self._image = widgets['image']
        self._button = widgets['button']
        self._button.props.popup = Gtk.Menu()
        self._icon_dialog = None
        self._path_dialog = None
        self._current_item = None

        self._add_controlled_by_state_widget(self._button)

        self._items = []
        for priority, (update, ask) in self._get_items():
            item = self.Item(priority=priority, update=update, ask=ask)
            item.menuitem = Gtk.MenuItem()
            item.menuitem.props.visible = True
            item.menuitem.props.label = item.update(None, True)[0]
            item.menuitem.connect('activate', self._on_item_clicked, item)
            self._button.props.popup.append(item.menuitem)
            self._items.append(item)

        self._items.sort(key=lambda i: i.priority)

    def _get_value(self):
        return self._value

    def _set_value(self, value):
        applied_item = None
        tooltip = None
        for item in self._items:
            if applied_item:
                label, __ = item.update(None, True)
            else:
                label, tooltip = item.update(value, False)
                if tooltip:
                    applied_item = item
            item.menuitem.get_child().set_markup(label)

        if not applied_item:
            tooltip = C_('option-entry|icon', 'Unrecognized value: {value}').format(value=value)
        self._button.set_tooltip_markup(tooltip)

        self._value = value
        self._current_item = applied_item

        self._emit_changed()

    def _get_items(self):
        return ((0, (self._update_icon, self._ask_icon)),
                (100, (self._update_image, self._ask_image)))

    def _on_item_clicked(self, menuitem, item):
        value = item.ask(self._value if item == self._current_item else None)
        if value is not None:
            self._set_value(value)

    def _update_icon(self, value, just_label=False):
        if just_label or value is None or not value.startswith('#'):
            return C_('option-entry|icon', 'Select icon name...'), None
        name = value[1:]
        label = C_('option-entry|icon', '<b>Icon: {icon}</b>').format(icon=name)
        tooltip = label
        self._image.set_from_icon_name(name, Gtk.IconSize.DIALOG)
        return label, tooltip

    def _ask_icon(self, oldvalue):
        if not self._icon_dialog:
            self._icon_dialog = IconChooserDialog()
            self._icon_dialog.props.transient_for = self._image.get_toplevel()
        if oldvalue:
            self._icon_dialog.select_icon(oldvalue[1:])

        value = None
        if self._icon_dialog.run() == Gtk.ResponseType.OK:
            value = '#' + self._icon_dialog.get_selected_icon()
        self._icon_dialog.hide()
        return value

    def _update_image(self, value, just_label=False):
        if just_label or value is None:
            return C_('option-entry|icon', 'Select file...'), None

        if set_image_from_path(self._image, value):
            label = C_('option-entry|icon', '<b>File: {path}</b>')
        else:
            label = C_('option-entry|icon', '<b>File: {path}</b> (failed to load)')

        return (label.format(path=os.path.basename(value)),
                label.format(path=value))

    def _ask_image(self, oldvalue):
        if not self._path_dialog:
            builder = Gtk.Builder()
            builder.add_from_file(get_data_path('ImageChooserDialog.ui'))

            self._path_dialog = builder.get_object('dialog')
            self._path_dialog.props.transient_for = self._image.get_toplevel()
            self._path_dialog.connect('update-preview', self._on_update_path_preview)

            preview_size = self._image.props.pixel_size
            preview = self._path_dialog.props.preview_widget
            preview.props.pixel_size = preview_size
            preview.set_size_request(preview_size, preview_size)

        if oldvalue is not None:
            self._path_dialog.select_filename(self._value)

        value = None
        if self._path_dialog.run() == Gtk.ResponseType.OK:
            value = self._path_dialog.get_filename()
        self._path_dialog.hide()
        return value

    def _on_update_path_preview(self, chooser):
        set_image_from_path(chooser.props.preview_widget, chooser.get_filename())
