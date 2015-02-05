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


import configparser
import glob
import locale
import os
import pwd
import stat

from collections import (
    namedtuple,
    OrderedDict,
    defaultdict)
from itertools import (
    chain,
    accumulate)
from locale import gettext as _

from gi.repository import (
    GdkPixbuf,
    GLib,
    GObject,
    Gtk,
    Pango)


__license__ = 'GPL-3'
__version__ = 'dev'
__data_directory__ = '../data/'
__config_path__ = 'lightdm-gtk-greeter.conf'


try:
    from . installation_config import (
        __version__,
        __data_directory__,
        __config_path__)
except ImportError:
    pass


__all__ = [
    'bool2string',
    'C_',
    'clamp',
    'check_path_accessibility',
    'DefaultValueDict',
    'file_is_readable_by_greeter',
    'get_config_path',
    'get_data_path',
    'get_greeter_version'
    'get_markup_error',
    'get_version',
    'ModelRowEnum',
    'NC_',
    'pixbuf_from_file_scaled_down',
    'set_image_from_path',
    'show_message',
    'SimpleEnum',
    'string2bool',
    'TreeStoreDataWrapper',
    'WidgetsEnum',
    'WidgetsWrapper']


def C_(context, message):
    separator = '\x04'
    message_with_context = '{}{}{}'.format(context, separator, message)
    result = locale.gettext(message_with_context)
    if separator in result:
        result = message
    return result


def NC_(context, message):
    return message


def get_data_path(*parts):
    return os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        __data_directory__, *parts))


def get_config_path():
    return os.path.abspath(__config_path__)


def get_version():
    return __version__


def get_greeter_version():
    try:
        return get_greeter_version._version
    except AttributeError:
        try:
            get_greeter_version._version = int(os.getenv('GTK_GREETER_VERSION', '0x010900'), 16)
        except ValueError:
            get_greeter_version._version = 0x010900

    return get_greeter_version._version


def bool2string(value):
    return 'true' if value else 'false'


def string2bool(value, fallback=False):
    if isinstance(value, str):
        if value in ('true', 'yes', '1'):
            return True
        if value in ('false', 'no', '0'):
            return False
    return fallback


def show_message(**kwargs):
    dialog = Gtk.MessageDialog(parent=Gtk.Window.list_toplevels()[0],
                               buttons=Gtk.ButtonsType.CLOSE, **kwargs)
    dialog.run()
    dialog.destroy()


def pixbuf_from_file_scaled_down(path, width, height):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    scale = max(pixbuf.props.width / width, pixbuf.props.height / height)

    if scale > 1:
        return GdkPixbuf.Pixbuf.scale_simple(pixbuf,
                                             pixbuf.props.width / scale,
                                             pixbuf.props.height / scale,
                                             GdkPixbuf.InterpType.BILINEAR)
    return pixbuf


def set_image_from_path(image, path):
    if not path or not os.path.isfile(path):
        image.props.icon_name = 'unknown'
    else:
        try:
            width, height = image.get_size_request()
            if -1 in (width, height):
                width, height = 64, 64
            pixbuf = pixbuf_from_file_scaled_down(path, width, height)
            image.set_from_pixbuf(pixbuf)
            return True
        except GLib.Error:
            image.props.icon_name = 'file-broken'
    return False


def check_path_accessibility(path, file=True, executable=False):
    """Return None  if file is readable by greeter and error message otherwise"""

    if not os.path.exists(path):
        return _('File not found: {path}').format(path=path)

    try:
        uid, gids = check_path_accessibility.id_cached_data
    except AttributeError:
        files = glob.glob('/etc/lightdm/lightdm.d/*.conf')
        files += ['/etc/lightdm/lightdm.conf']
        config = configparser.RawConfigParser(strict=False)
        config.read(files)
        username = config.get('LightDM', 'greeter-user', fallback='lightdm')

        pw = pwd.getpwnam(username)
        uid = pw.pw_uid
        gids = set(os.getgrouplist(username, pw.pw_gid))
        check_path_accessibility.id_cached_data = uid, gids

    parts = os.path.normpath(path).split(os.path.sep)
    if not parts[0]:
        parts[0] = os.path.sep

    def check(p):
        try:
            st = os.stat(p)
        except OSError as e:
            return _('Failed to check permissions: {error}'.format(error=e.strerror))

        if stat.S_ISDIR(st.st_mode) and not stat.S_IREAD:
            return _('Directory is not readable: {path}'.format(path=p))
        if st.st_uid == uid:
            return not (st.st_mode & stat.S_IRUSR) and \
                _('LightDM do not have permissions to read path: {path}'.format(path=p))
        if st.st_gid in gids:
            return not (st.st_mode & stat.S_IRGRP) and \
                _('LightDM do not have permissions to read path: {path}'.format(path=p))
        return not (st.st_mode & stat.S_IROTH) and \
            _('LightDM do not have permissions to read path: {path}'.format(path=p))

    errors = (check(p) for p in accumulate(parts, os.path.join))
    error = next((error for error in errors if error), None)

    if not error and file and not os.path.isfile(path):
        return _('Path is not a regular file: {path}'.format(path=path))

    if not error and executable:
        st = os.stat(path)
        if st.st_uid == uid:
            if not st.st_mode & stat.S_IXUSR:
                return _('LightDM do not have permissions to execute file: {path}'
                         .format(path=path))
        elif st.st_gid in gids:
            if not st.st_mode & stat.S_IXGRP:
                return _('LightDM do not have permissions to execute file: {path}'
                         .format(path=path))
        elif not st.st_mode & stat.S_IXOTH:
            return _('LightDM do not have permissions to execute file: {path}'.format(path=path))

    return error


def get_markup_error(markup):
    try:
        Pango.parse_markup(markup, -1, '\0')
    except GLib.Error as e:
        return e.message
    return None


def clamp(v, a, b):
    if v < a:
        return a
    if v > b:
        return b
    return v


class DefaultValueDict(defaultdict):

    def __init__(self, *items, default=None, factory=None, source=None):
        super().__init__(None, source or items)
        self._value = default
        self._factory = factory

    def __missing__(self, key):
        return self._factory(key) if self._factory else self._value


class SimpleEnumMeta(type):

    @classmethod
    def __prepare__(mcs, *args, **kwargs):
        return OrderedDict()

    def __new__(self, cls, bases, classdict):
        obj = super().__new__(self, cls, bases, classdict)
        obj._dict = OrderedDict((k, v)
                                for k, v in classdict.items() if obj._accept_member_(k, v))
        obj._tuple_type = namedtuple(obj.__class__.__name__ + 'Tuple', obj._dict.keys())
        keys = list(obj._dict.keys())
        for i in range(len(keys)):
            if obj._dict[keys[i]] is ():
                v = 0 if i == 0 else obj._dict[keys[i - 1]] + 1
                setattr(obj, keys[i], v)
                obj._dict[keys[i]] = v
        return obj

    def __contains__(self, value):
        return value in self._dict.values()

    def __iter__(self):
        return iter(self._dict.values())

    def _make(self, *args, **kwargs):
        return self._tuple_type._make(self._imake(*args, **kwargs))

    def _imake(self, *args, **kwargs):
        if args:
            return args
        elif kwargs:
            return (kwargs.get(k, v) for k, v in self._dict.items())
        else:
            return self._dict.values()


class SimpleEnum(metaclass=SimpleEnumMeta):
    _dict = None

    def __init__(self, *args, **kwargs):
        if kwargs:
            self.__dict__.update(kwargs)
        else:
            self.__dict__.update((k, args[i]) for i, k in enumerate(self._dict))

    def __iter__(self):
        return (self.__dict__[k] for k in self._dict)

    def __repr__(self):
        return repr(tuple((k, self.__dict__[k]) for k in self._dict))

    @classmethod
    def _accept_member_(cls, name, value):
        return not name.startswith('_') and not name.endswith('_')


class WidgetsEnum(SimpleEnum):

    def __init__(self, wrapper=None, builder=None):
        getter = wrapper.__getitem__ if wrapper else builder.get_object
        for k, v in self._dict.items():
            if isinstance(v, type) and issubclass(v, WidgetsEnum):
                self.__dict__[k] = v(WidgetsWrapper(wrapper or builder, k))
            else:
                self.__dict__[k] = getter(v or k)


class WidgetsWrapper:
    _builder = None
    _prefixes = None

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


class TreeStoreDataWrapper(GObject.Object):

    def __init__(self, data):
        super().__init__()
        self.data = data
