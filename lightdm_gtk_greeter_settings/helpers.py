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

from collections import namedtuple
from itertools import chain
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
           'get_data_path', 'get_config_path', 'show_message',
           'bool2string', 'string2bool',
           'ModelRowEnum', 'WidgetsWrapper']


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
    dialog = Gtk.MessageDialog(parent=Gtk.Window.list_toplevels()[0], buttons=Gtk.ButtonsType.CLOSE, **kwargs)
    dialog.run()
    dialog.destroy()

def get_version():
    return __version__


def bool2string(value):
    return 'true' if value else 'false'


def string2bool(value):
    return value and value.lower() in ('true', 'yes', '1')


class ModelRowEnum:

    def __init__(self, *names):
        self.__keys = tuple(names)
        self.__values = {name: i for i, name in enumerate(names)}
        self.__dict__.update(self.__values)
        self.__RowTuple = namedtuple('ModelRowEnumTuple', names)

    def __call__(self, *args, **kwargs):
        if args:
            return self.__RowTuple._make(chain.from_iterable(args))
        else:
            return self.__RowTuple._make(kwargs.get(name, i) for i, name in enumerate(self.__keys))


class WidgetsWrapper:

    def __init__(self, source, *prefixes):
        if isinstance(source, Gtk.Builder):
            self._builder = source
            self._prefixes = tuple(prefixes)
        elif isinstance(source, WidgetsWrapper):
            self._builder = source._builder
            self._prefixes = source._prefixes + tuple(prefixes)
        else:
            raise TypeError(source)

    def __getitem__(self, args):
        if not isinstance(args, tuple):
            args = (args,)
        return self._builder.get_object('_'.join(chain(self._prefixes, args)))
