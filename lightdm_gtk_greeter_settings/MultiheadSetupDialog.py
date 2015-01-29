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


from builtins import max
from locale import gettext as _

from gi.repository import (
    Gdk,
    GdkPixbuf,
    Gtk)

from lightdm_gtk_greeter_settings.helpers import (
    C_,
    check_path_accessibility,
    get_data_path,
    SimpleEnum,
    WidgetsEnum)


__all__ = ['MultiheadSetupDialog']


class Row(SimpleEnum):
    Name = ()
    Background = ()
    UserBg = ()
    UserBgDisabled = ()
    Laptop = ()
    LaptopDisabled = ()
    BackgroundPixbuf = ()
    BackgroundIsColor = ()
    ErrorVisible = ()
    ErrorText = ()


class BackgroundRow(SimpleEnum):
    Text = ()
    Type = ()


class MultiheadSetupDialog(Gtk.Dialog):
    __gtype_name__ = 'MultiheadSetupDialog'

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('multihead_setup_dialog')
        window.builder = builder
        builder.connect_signals(window)
        window.init_window()
        return window

    class Widgets(WidgetsEnum):
        treeview = 'monitors_treeview'
        model = 'monitors_model'
        selection = 'monitors_selection'
        bg_model = 'background_model'
        bg_renderer = 'bg_renderer'
        bg_column = 'background_column'
        name_column = 'name_column'
        remove = 'remove_button'
        available = 'monitors_label'

    builder = None

    def init_window(self):
        self._widgets = self.Widgets(builder=self.builder)
        self._group = None
        self._available_monitors = None

        self._file_dialog = None
        self._color_dialog = None
        self._invalid_name_dialog = None
        self._name_exists_dialog = None

        self._widgets.treeview.props.tooltip_column = Row.ErrorText
        self._widgets.bg_renderer.set_property('placeholder-text',
                                               C_('option|multihead', 'Use default value'))

    def _update_monitors_label(self):
        if not self._available_monitors:
            self._widgets.available.props.visible = False
            return

        used = set(row[Row.Name] for row in self._widgets.model)
        monitors = []
        for name in self._available_monitors:
            if name in used:
                monitors.append(name)
            else:
                monitors.append('<i><a href="{name}">{name}</a></i>'.format(name=name))

        label = C_('option|multihead',
                   'Available monitors: {monitors}').format(monitors=', '.join(monitors))
        self._widgets.available.props.label = label
        self._widgets.available.props.visible = True

    def set_model(self, values):
        self._widgets.model.clear()
        for name, entry in values.items():
            row = Row._make(Name=name,
                            Background=entry['background'],
                            UserBg=entry['user-background'],
                            UserBgDisabled=entry['user-background'] is None,
                            Laptop=entry['laptop'],
                            LaptopDisabled=entry['laptop'] is None,
                            BackgroundPixbuf=None,
                            BackgroundIsColor=False,
                            ErrorVisible=False,
                            ErrorText=None)
            self._update_row_appearance(self._widgets.model.append(row))
        screen = Gdk.Screen.get_default()
        self._available_monitors = [screen.get_monitor_plug_name(i)
                                    for i in range(screen.get_n_monitors())]
        self._update_monitors_label()

    def get_model(self):
        return {
            row[Row.Name]:
            {
                'background': row[Row.Background],
                'user-background': self._get_toggle_state(row, Row.UserBg, Row.UserBgDisabled),
                'laptop': self._get_toggle_state(row, Row.Laptop, Row.LaptopDisabled)
            }
            for row in self._widgets.model}

    def _update_row_appearance(self, rowiter):
        row = self._widgets.model[rowiter]
        bg = row[Row.Background]

        error = None
        color = Gdk.RGBA()
        if color.parse(bg):
            pixbuf = row[Row.BackgroundPixbuf]
            if not pixbuf:
                pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 16, 16)
                row[Row.BackgroundPixbuf] = pixbuf
            value = (int(0xFF * color.red) << 24) + \
                    (int(0xFF * color.green) << 16) + \
                    (int(0xFF * color.blue) << 8)
            pixbuf.fill(value)
            row[Row.BackgroundIsColor] = True
        else:
            row[Row.BackgroundIsColor] = False
            if bg:
                error = check_path_accessibility(bg)

        row[Row.ErrorVisible] = error is not None
        row[Row.ErrorText] = error

    ToggleStatesSeq = {None: True, False: None, True: False}

    def _get_toggle_state(self, row, active_column, inconsistent_column):
        return None if row[inconsistent_column] else row[active_column]

    def _toggle_state(self, row, active_column, inconsistent_column):
        state = self._get_toggle_state(row, active_column, inconsistent_column)
        row[active_column] = self.ToggleStatesSeq[state]
        row[inconsistent_column] = self.ToggleStatesSeq[state] is None

    def on_monitors_add_clicked(self, button):
        prefix = 'monitor'
        numbers = (row[Row.Name][len(prefix):]
                   for row in self._widgets.model if row[Row.Name].startswith(prefix))
        try:
            max_number = max(int(v) for v in numbers if v.isdigit())
        except ValueError:
            max_number = 0

        row = Row._make(Name='%s%d' % (prefix, max_number + 1),
                        UserBg=False,
                        UserBgDisabled=False,
                        Laptop=True,
                        LaptopDisabled=False,
                        Background='',
                        BackgroundPixbuf=None,
                        BackgroundIsColor=False,
                        ErrorVisible=False,
                        ErrorText=None)
        rowiter = self._widgets.model.append(row)
        self._widgets.treeview.set_cursor(self._widgets.model.get_path(rowiter),
                                          self._widgets.name_column, True)

    def on_monitors_remove_clicked(self, button):
        model, rowiter = self._widgets.selection.get_selected()
        model.remove(rowiter)
        self._update_monitors_label()

    def on_selection_changed(self, selection):
        self._widgets.remove.props.sensitive = all(selection.get_selected())

    def on_monitors_label_activate_link(self, label, name):
        row = Row._make(Name=name,
                        UserBg=False,
                        UserBgDisabled=False,
                        Laptop=True,
                        LaptopDisabled=False,
                        Background='',
                        BackgroundPixbuf=None,
                        BackgroundIsColor=True,
                        ErrorVisible=False,
                        ErrorText=None)

        rowiter = self._widgets.model.append(row)
        self._update_row_appearance(rowiter)
        self._widgets.selection.select_iter(rowiter)
        self._update_monitors_label()
        return True

    def on_bg_renderer_editing_started(self, renderer, combobox, path):
        combobox.connect('format-entry-text', self.on_bg_combobox_format)

    def on_bg_combobox_format(self, combobox, path):
        model, rowiter = self._widgets.selection.get_selected()
        item_type = combobox.props.model[path][BackgroundRow.Type]
        value = model[rowiter][Row.Background]

        if item_type == 'path':
            if not self._file_dialog:
                self._file_dialog = Gtk.FileChooserDialog(
                    parent=self,
                    buttons=(_('_OK'), Gtk.ResponseType.OK,
                             _('_Cancel'), Gtk.ResponseType.CANCEL),
                    title=C_('option|multihead', 'Select background file'))
                self._file_dialog.props.filter = Gtk.FileFilter()
                self._file_dialog.props.filter.add_mime_type('image/*')
            if self._file_dialog.run() == Gtk.ResponseType.OK:
                value = self._file_dialog.get_filename()
            self._file_dialog.hide()
        elif item_type == 'color':
            if not self._color_dialog:
                self._color_dialog = Gtk.ColorChooserDialog(parent=self)
            if self._color_dialog.run() == Gtk.ResponseType.OK:
                value = self._color_dialog.get_rgba().to_color().to_string()
            self._color_dialog.hide()
        else:
            value = ''

        combobox.set_active(-1)
        return value

    def on_bg_renderer_edited(self, renderer, path, new_text):
        self._widgets.model[path][Row.Background] = new_text
        self._update_row_appearance(self._widgets.model.get_iter(path))

    def on_name_renderer_edited(self, renderer, path, new_name):
        old_name = self._widgets.model[path][Row.Name]
        invalid_name = not new_name.strip()
        name_in_use = new_name != old_name and any(new_name == row[Row.Name]
                                                   for row in self._widgets.model)
        if invalid_name or name_in_use:
            if not self._invalid_name_dialog:
                self._invalid_name_dialog = Gtk.MessageDialog(parent=self,
                                                              buttons=Gtk.ButtonsType.OK)
            self._invalid_name_dialog.set_property('text',
                                                   C_('option|multihead',
                                                      'Invalid name: "{name}"')
                                                   .format(name=new_name))
            if name_in_use:
                message = C_('option|multihead', 'This name already in use.')
            else:
                message = C_('option|multihead', 'This name is not valid.')
            self._invalid_name_dialog.set_property('secondary-text', message)
            self._invalid_name_dialog.run()
            self._invalid_name_dialog.hide()
        else:
            self._widgets.model[path][Row.Name] = new_name
        self._update_monitors_label()

    def on_user_bg_renderer_toggled(self, renderer, path):
        self._toggle_state(self._widgets.model[path], Row.UserBg, Row.UserBgDisabled)

    def on_laptop_renderer_toggled(self, renderer, path):
        self._toggle_state(self._widgets.model[path], Row.Laptop, Row.LaptopDisabled)
