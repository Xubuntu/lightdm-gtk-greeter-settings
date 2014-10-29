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
from gi.repository import Gtk, Gdk, GdkPixbuf

from lightdm_gtk_greeter_settings import helpers
from lightdm_gtk_greeter_settings.helpers import WidgetsWrapper, C_, ModelRowEnum


__all__ = ['MultiheadSetupDialog']


ROW = ModelRowEnum('NAME', 'BACKGROUND',
                   'USER_BG', 'USER_BG_DISABLED',
                   'LAPTOP', 'LAPTOP_DISABLED',
                   'BACKGROUND_PIXBUF', 'BACKGROUND_IS_COLOR')

BG_ROW = ModelRowEnum('TEXT', 'TYPE')


class MultiheadSetupDialog(Gtk.Dialog):

    __gtype_name__ = 'MultiheadSetupDialog'

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('multihead_setup_dialog')
        window._widgets = WidgetsWrapper(builder)
        builder.connect_signals(window)
        window._init_window()
        return window

    def _init_window(self):
        self._group = None
        self._available_monitors = None

        self._remove_button = self._widgets['remove_button']
        self._treeview = self._widgets['monitors_treeview']
        self._model = self._widgets['monitors_model']
        self._bg_model = self._widgets['background_model']
        self._selection = self._treeview.get_selection()
        self._bg_renderer = self._widgets['bg_renderer']
        self._bg_column = self._widgets['background_column']
        self._name_column = self._widgets['name_column']
        self._file_dialog = None
        self._color_dialog = None
        self._invalid_name_dialog = None
        self._name_exists_dialog = None

        self._bg_renderer.set_property('placeholder-text',
                                       C_('option|multihead', 'Use default value'))

    def _update_monitors_label(self):
        used = set(row[ROW.NAME] for row in self._model)
        monitors = ['<a href="{name}">{name}</a>'.format(name=name)
                    for name in self._available_monitors if name not in used]
        label = C_('option|multihead', 'Available monitors: <i>{monitors}</i>')\
                   .format(monitors=', '.join(monitors or ('none',)))
        self._widgets['monitors_label'].props.label = label


    def set_model(self, values):
        self._model.clear()
        for name, entry in values.items():
            rowiter = self._model.append(ROW(NAME=name,
                                             BACKGROUND=entry['background'],
                                             USER_BG=entry['user-background'],
                                             USER_BG_DISABLED=entry['user-background'] is None,
                                             LAPTOP=entry['laptop'],
                                             LAPTOP_DISABLED=entry['laptop'] is None,
                                             BACKGROUND_PIXBUF=None,
                                             BACKGROUND_IS_COLOR=False))
            self._update_row_appearance(rowiter)
        screen = Gdk.Screen.get_default()
        self._available_monitors = [screen.get_monitor_plug_name(i)
                                    for i in range(screen.get_n_monitors())]
        self._update_monitors_label()

    def get_model(self):
        return {row[ROW.NAME]:
                {
                    'background': row[ROW.BACKGROUND],
                    'user-background': self._get_toggle_state(row, ROW.USER_BG, ROW.USER_BG_DISABLED),
                    'laptop': self._get_toggle_state(row, ROW.LAPTOP, ROW.LAPTOP_DISABLED)
                }
                for row in self._model}

    def _update_row_appearance(self, rowiter):
        row = self._model[rowiter]
        bg = row[ROW.BACKGROUND]

        color = Gdk.color_parse(bg)
        if color:
            pixbuf = row[ROW.BACKGROUND_PIXBUF]
            if not pixbuf:
                pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,
                                              False, 8, 16, 16)
                row[ROW.BACKGROUND_PIXBUF] = pixbuf
            value = (int(0xFF / Gdk.Color.MAX_VALUE * color.red) << 24) + \
                    (int(0xFF / Gdk.Color.MAX_VALUE * color.green) << 16) + \
                    (int(0xFF / Gdk.Color.MAX_VALUE * color.blue) << 8)
            pixbuf.fill(value)
            row[ROW.BACKGROUND_IS_COLOR] = True
        else:
            row[ROW.BACKGROUND_IS_COLOR] = False

    _TOGGLE_STATES = {None: True, False: None, True: False}

    def _get_toggle_state(self, row, active_column, inconsistent_column):
        return None if row[inconsistent_column] else row[active_column]

    def _toggle_state(self, row, active_column, inconsistent_column):
        state = self._get_toggle_state(row, active_column, inconsistent_column)
        row[active_column] = self._TOGGLE_STATES[state]
        row[inconsistent_column] = self._TOGGLE_STATES[state] is None

    def on_monitors_add_clicked(self, button):
        prefix = 'monitor'
        numbers = (row[ROW.NAME][len(prefix):]
                   for row in self._model if row[ROW.NAME].startswith(prefix))
        try:
            max_number = max(int(v) for v in numbers if v.isdigit())
        except ValueError:
            max_number = 0
        rowiter = self._model.append(ROW(NAME='%s%d' % (prefix, max_number + 1),
                                         USER_BG=False,
                                         USER_BG_ENABLED=False,
                                         LAPTOP=True,
                                         LAPTOP_ENABLED=False,
                                         BACKGROUND='',
                                         BACKGROUND_PIXBUF=None,
                                         BACKGROUND_IS_COLOR=False))
        self._treeview.set_cursor(self._model.get_path(rowiter), self._name_column, True)

    def on_monitors_remove_clicked(self, button):
        model, rowiter = self._treeview.get_selection().get_selected()
        model.remove(rowiter)

    def on_selection_changed(self, selection):
        self._remove_button.props.sensitive = selection.get_selected()[1] is not None

    def on_monitors_label_activate_link(self, label, name):
        rowiter = self._model.append(ROW(NAME=name,
                                         USER_BG=False,
                                         USER_BG_ENABLED=False,
                                         LAPTOP=True,
                                         LAPTOP_ENABLED=False,
                                         BACKGROUND='',
                                         BACKGROUND_PIXBUF=None,
                                         BACKGROUND_IS_COLOR=False))
        self._update_row_appearance(rowiter)
        self._treeview.get_selection().select_iter(rowiter)
        self._update_monitors_label()
        return True

    def on_bg_renderer_editing_started(self, renderer, combobox, path):
        combobox.connect('format-entry-text', self.on_bg_combobox_format)

    def on_bg_combobox_format(self, combobox, path):
        model, rowiter = self._selection.get_selected()
        item_type = combobox.props.model[path][BG_ROW.TYPE]
        value = model[rowiter][ROW.BACKGROUND]
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
        elif item_type == 'icon':
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
        self._model[path][ROW.BACKGROUND] = new_text
        self._update_row_appearance(self._model.get_iter(path))

    def on_name_renderer_edited(self, renderer, path, new_name):
        old_name = self._model[path][ROW.NAME]
        invalid_name = not new_name.strip()
        name_in_use = new_name != old_name and any(new_name == row[ROW.NAME] for row in self._model)
        if invalid_name or name_in_use:
            if not self._invalid_name_dialog:
                self._invalid_name_dialog = Gtk.MessageDialog(parent=self,
                                                              buttons=Gtk.ButtonsType.OK)
            self._invalid_name_dialog.set_property('text',
                                                   C_('option|multihead', 'Invalid name: "{name}"')
                                                        .format(name=new_name))
            if name_in_use:
                message = C_('option|multihead', 'This name already in use.')
            else:
                message = C_('option|multihead', 'This name is not valid.')
            self._invalid_name_dialog.set_property('secondary-text', message)
            self._invalid_name_dialog.run()
            self._invalid_name_dialog.hide()
        else:
            self._model[path][ROW.NAME] = new_name
        self._update_monitors_label()

    def on_user_bg_renderer_toggled(self, renderer, path):
        self._toggle_state(self._model[path],
                           ROW.USER_BG, ROW.USER_BG_DISABLED)

    def on_laptop_renderer_toggled(self, renderer, path):
        self._toggle_state(self._model[path],
                           ROW.LAPTOP, ROW.LAPTOP_DISABLED)

