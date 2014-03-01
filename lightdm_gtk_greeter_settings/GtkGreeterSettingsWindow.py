
from collections import namedtuple
import configparser
from glob import iglob
from locale import gettext as _
import os
import sys

from gi.repository import Gtk

from lightdm_gtk_greeter_settings import OptionEntry
from lightdm_gtk_greeter_settings import helpers


__all__ = ['GtkGreeterSettingsWindow']


BindingValue = namedtuple('BindingValue', ('option', 'default', 'changed_handler'))
InitialValue = namedtuple('InitialValue', ('value', 'state'))


GREETER_SECTION = 'greeter'

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
        'xft-rgba': (OptionEntry.ChoiceEntry, 'rgba', None),
        'xft-hintstyle': (OptionEntry.ChoiceEntry, 'hintstyle', None),
        'background': (OptionEntry.BackgroundEntry, 'background', '#000000'),
        'default-user-image': (OptionEntry.IconEntry, 'userimage', '#avatar-default'),
        # Panel
        'show-clock': (OptionEntry.BooleanEntry, 'show_clock', False),
        'clock-format': (OptionEntry.ClockFormatEntry, 'clock_format', '%a, %H:%M'),
        'indicators': (OptionEntry.IndicatorsEntry, 'indicators', None),
        # Position
        'position': (OptionEntry.PositionEntry, 'position', '50%,center'),
        # Misc
        'screensaver-timeout': (OptionEntry.AdjustmentIntEntry, 'timeout', 60),
        'keyboard': (OptionEntry.StringEntry, 'keyboard', None),
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

    BUILDER_WIDGETS = ('apply_button', 'no_access_infobar',
                       'gtk_theme_values', 'icons_theme_values',
                       'timeout_view', 'timeout_adjustment', 'timeout_end_label')

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
        self._bindings = {section: {key: self._new_binding(*args) for key, args in keys.items()}
                          for section, keys in OPTIONS_BINDINGS.items()}
        self._initial_values = {}
        self._changed_values = None

        self._config_path = helpers.get_config_path()
        self._allow_edit = self._has_access_to_write(self._config_path)
        self._no_access_infobar.props.visible = not self._allow_edit
        self._apply_button.props.visible = self._allow_edit
        if not self._allow_edit:
            helpers.show_message(text=_('No permissions to save configuration'),
                                 secondary_text=_(
'It seems that you don\'t have permissions to write to file:\n\
{path}\n\nTry to run this program using "sudo" or "pkexec"').format(path=self._config_path),
                                 message_type=Gtk.MessageType.WARNING)

        self._configure_special_entries()
        self._config = configparser.RawConfigParser(strict=False)
        self._read()

    def _configure_special_entries(self):
        # theme-name
        for theme in iglob(os.path.join(sys.prefix, 'share', 'themes', '*', 'gtk-3.0')):
            self._gtk_theme_values.append_text(theme.split(os.path.sep)[-2])
        # icon-theme-name
        for theme in iglob(os.path.join(sys.prefix, 'share', 'icons', '*', 'index.theme')):
            self._icons_theme_values.append_text(theme.split(os.path.sep)[-2])
        # screensaver-timeout
        step = 60
        lower = int(self._timeout_adjustment.props.lower) // step
        upper = int(self._timeout_adjustment.props.upper) // step
        for value in range(lower * step, (upper + 1) * step, step):
            self._timeout_view.add_mark(value, Gtk.PositionType.BOTTOM, None)
        self._timeout_end_label.props.label = _('{count} min').format(count=upper)

    def _has_access_to_write(self, path):
        if os.path.exists(path) and os.access(self._config_path, os.W_OK):
            return True
        return os.access(os.path.dirname(self._config_path), os.W_OK | os.X_OK)

    def _new_binding(self, cls, basename, default):
        option = cls(BuilderWrapper(self._builder, basename))
        changed_id = option.connect('changed', self.on_option_changed)
        return BindingValue(option, default, changed_id)

    def _read(self):
        self._config.clear()
        try:
            if not self._config.read(self._config_path):
                helpers.show_message(text=_('Failed to read configuration file: {path}')
                                            .format(path=self._config_path),
                                     message_type=Gtk.MessageType.ERROR)
        except (configparser.DuplicateSectionError, configparser.MissingSectionHeaderError):
            pass

        if not self._config.has_option(GREETER_SECTION, 'indicators'):
            try:
                value = self._config.get(GREETER_SECTION, 'show-indicators')
            except (configparser.NoOptionError, configparser.NoSectionError):
                pass
            else:
                if value:
                    self._config.set(GREETER_SECTION, 'indicators', value)
                self._config.remove_option(GREETER_SECTION, 'show-indicators')

        for section, keys in self._bindings.items():
            for key, binding in keys.items():
                with binding.option.handler_block(binding.changed_handler):
                    try:
                        binding.option.value = self._config.get(section, key)
                        binding.option.enabled = True
                    except (configparser.NoOptionError, configparser.NoSectionError):
                        binding.option.value = binding.default
                        binding.option.enabled = False
                self._initial_values[binding.option] = InitialValue(binding.option.value,
                                                                    binding.option.enabled)
        self._changed_values = set()
        self._apply_button.props.sensitive = False

    def _write(self):
        for section, keys in self._bindings.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
            for key, binding in keys.items():
                if binding.option.enabled:
                    self._config.set(section, key, binding.option.value)
                else:
                    self._config.remove_option(section, key)
                self._initial_values[binding.option] = InitialValue(binding.option.value,
                                                                    binding.option.enabled)
        self._changed_values = set()
        self._apply_button.props.sensitive = False
        try:
            with open(self._config_path, 'w') as file:
                self._config.write(file)
        except OSError as e:
            helpers.show_message(e, Gtk.MessageType.ERROR)

    def on_option_changed(self, option):
        if option.enabled != self._initial_values[option].state or \
           (option.enabled and option.value != self._initial_values[option].value):
            self._changed_values.add(option)
        else:
            self._changed_values.discard(option)
        self._apply_button.props.sensitive = self._allow_edit and self._changed_values

    def on_format_timeout_scale(self, scale, value):
        if value != self._timeout_adjustment.props.lower and \
           value != self._timeout_adjustment.props.upper:
            value = int(value)
            return '%02d:%02d' % (value // 60, value % 60)
        else:
            return ''

    def on_destroy(self, *args):
        Gtk.main_quit()

    def on_apply_clicked(self, *args):
        self._write()

    def on_reset_clicked(self, *args):
        self._read()

    def on_close_clicked(self, *args):
        self.destroy()
