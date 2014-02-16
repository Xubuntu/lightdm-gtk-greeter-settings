
from glob import iglob
import os
import sys

from gi.repository import Gtk
from gtk_greeter_settings import helpers


class IndicatorChooserDialog(Gtk.Dialog):

    __gtype_name__ = 'IndicatorChooserDialog'

    BUILDER_WIDGETS = ('short_choice', 'short_value', 'short_model',
                       'path_value', 'add_button')

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('indicator_chooser_dialog')
        window._builder = builder
        window.__dict__.update(('_' + w, builder.get_object(w))
                               for w in cls.BUILDER_WIDGETS)
        builder.connect_signals(window)
        window._init_window()
        return window

    def _init_window(self):
        self._add_callback = None

        for path in iglob(os.path.join(sys.prefix, 'share', 'unity', 'indicators', '*')):
            name = os.path.basename(path)
            parts = name.rsplit('.', maxsplit=1)
            if len(parts) == 2 and parts[0] == 'com.canonical.indicator':
                name = parts[1]
            self._short_model.append((name,))

        for path in iglob(os.path.join(sys.prefix, 'lib', 'indicators3', '7', '*.so')):
            self._short_model.append((os.path.basename(path),))

    def _get_current_value(self):
        if self._short_choice.props.active:
            return self._short_value.props.text
        else:
            return self._path_value.get_filename()

    def on_add_clicked(self, *args):
        value = self._get_current_value()
        if value:
            self._add_callback(value)

    def get_indicator(self, add_callback=None):
        self._add_callback = add_callback
        self._add_button.props.visible = add_callback and hasattr(add_callback, '__call__')
        response = self.run()
        self.hide()
        if response == Gtk.ResponseType.OK:
            return self._get_current_value()
        return None
