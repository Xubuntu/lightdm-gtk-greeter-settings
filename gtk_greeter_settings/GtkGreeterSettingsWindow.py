
from collections import namedtuple
import configparser
from glob import iglob
from locale import gettext as _
import os
import sys

from gi.repository import Gtk

from gtk_greeter_settings import OptionEntry
from gtk_greeter_settings import helpers


__all__ = ['GtkGreeterSettingsWindow']


BindingValue = namedtuple('BindingValue', ('option', 'default'))


OPTIONS_BINDINGS = \
{
    'greeter':
    {
        # key: class, base widgets name, default value

        # Theme
        'theme-name': (OptionEntry.StringEntry, 'gtk_theme', None),
        'icon-theme-name': (OptionEntry.StringEntry, 'icons_theme', None),
        'font-name': (OptionEntry.FontEntry, 'font', 'Sans 10'),
        'xft-antialias': (OptionEntry.BooleanEntry, 'antialias', False),
        'xft-dpi': (OptionEntry.StringEntry, 'dpi', None),
        'background': (OptionEntry.BackgroundEntry, 'background', None),
        'default-user-image': (OptionEntry.IconEntry, 'user_image', '#avatar-default'),
        # Panel
        'show-clock': (OptionEntry.BooleanEntry, 'show_clock', False),
        'clock-format': (OptionEntry.ClockFormatEntry, 'clock_format', '%a, %H:%M'),
        'show-indicators': (OptionEntry.IndicatorsEntry, 'indicators', None),
        # Position
        'position': (OptionEntry.PositionEntry, 'position', '50%,center'),
    }
}


class BuilderWrapper:
    def __init__(self, builder, base):
        self._builder = builder
        self._base = base

    def __getitem__(self, key):
        return self._builder.get_object('%s_%s' % (self._base, key))


class GtkGreeterSettingsWindow(Gtk.Window):

    __gtype_name__ = 'GtkGreeterSettingsWindow'

    BUILDER_WIDGETS = ('dialog_buttons', 'apply_button',
                       'gtk_theme_values', 'icons_theme_values')

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object("settings_window")
        window._builder = builder
        window.__dict__.update(('_' + w, builder.get_object(w))
                               for w in cls.BUILDER_WIDGETS)
        builder.connect_signals(window)
        window._init_window()
        return window

    def _init_window(self):
        self._bindings = {section: {key: BindingValue(cls(BuilderWrapper(self._builder, base_name)), default)
                                    for key, (cls, base_name, default) in keys.items()}
                          for section, keys in OPTIONS_BINDINGS.items()}

        self._config_path = helpers.get_config_path()
        if not self._has_access_to_write(self._config_path):
            self._apply_button.props.sensitive = False

            helpers.show_message(text=_('No permissions to save configuration'),
                                 secondary_text=_(
'It seems that you don\'t have permissions to write to file:\n\
%s\n\nTry to run this program using "sudo" or "pkexec"') % self._config_path,
                                 message_type=Gtk.MessageType.WARNING)

        self._config = configparser.RawConfigParser(strict=False, allow_no_value=True)

        try:
            if not self._config.read(self._config_path):
                helpers.show_message(text=_('Failed to read configuration file: %s') % self._config_path,
                                     message_type=Gtk.MessageType.ERROR)
        except (configparser.DuplicateSectionError, configparser.MissingSectionHeaderError):
            pass

        for theme in iglob(os.path.join(sys.prefix, 'share', 'themes', '*', 'gtk-3.0')):
            self._gtk_theme_values.append_text(theme.split(os.path.sep)[-2])

        for theme in iglob(os.path.join(sys.prefix, 'share', 'icons', '*', 'index.theme')):
            self._icons_theme_values.append_text(theme.split(os.path.sep)[-2])

        self._read()

    def _has_access_to_write(self, path):
        if os.path.exists(path) and os.access(self._config_path, os.W_OK):
            return True
        return os.access(os.path.dirname(self._config_path), os.W_OK | os.X_OK)

    def _read(self):
        for section, keys in self._bindings.items():
            for key, binding in keys.items():
                binding.option.value = self._config.get(section, key, fallback=binding.default)

    def _write(self):
        for section, keys in self._bindings.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
            for key, binding in keys.items():
                value = binding.option.value
                if value is None:
                    self._config.remove_option(section, key)
                else:
                    self._config.set(section, key, value)

        try:
            with open(self._config_path + '_', 'w') as file:
                self._config.write(file)
        except OSError as e:
            helpers.show_message(e, Gtk.MessageType.ERROR)

    def on_destroy(self, *args):
        Gtk.main_quit()

    def on_apply_clicked(self, *args):
        self._write()

    def on_reset_clicked(self, *args):
        self._read()

    def on_close_clicked(self, *args):
        self.destroy()
