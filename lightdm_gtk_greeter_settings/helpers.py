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

import locale
import os
from gi.repository import Gtk


__license__ = 'GPL-3'
__version__ = 'dev'
__data_directory__ = '../data/'
__config_path__ = 'lightdm-gtk-greeter.conf'


try:
    from . installation_config import *
except ImportError:
    pass


__all__ = ['C_', 'NC_',
           'get_data_path', 'get_config_path', 'show_message']


def C_(context, message):
    CONTEXT_SEPARATOR = '\x04'
    message_with_context = '{}{}{}'.format(context, CONTEXT_SEPARATOR, message)
    result = locale.gettext(message_with_context)
    if CONTEXT_SEPARATOR in result:
        result = message
    return result


def NC_(context, message):
    return message


def get_data_path(*parts):
    return os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        __data_directory__, *parts))


def get_config_path():
    return os.path.abspath(__config_path__)


def show_message(**kwargs):
    dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.CLOSE, **kwargs)
    dialog.run()
    dialog.destroy()


def get_version():
    return __version__
