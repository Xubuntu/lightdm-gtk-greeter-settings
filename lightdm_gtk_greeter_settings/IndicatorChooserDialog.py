
from glob import iglob
import os
import sys

from gi.repository import Gtk
from lightdm_gtk_greeter_settings import helpers


__all__ = ['IndicatorChooserDialog']


class IndicatorChooserDialog(Gtk.Dialog):

    __gtype_name__ = 'IndicatorChooserDialog'

    BUILDER_WIDGETS = ('short_choice', 'short_value', 'short_model',
                       'path_choice', 'path_value',
                       'add_button', 'ok_button', 'infobar', 'message')

    def __new__(cls, check_callback=None, add_callback=None):
        builder = Gtk.Builder()
        builder.add_from_file(helpers.get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('indicator_chooser_dialog')
        window._builder = builder
        window.__dict__.update(('_' + w, builder.get_object(w))
                               for w in cls.BUILDER_WIDGETS)

        builder.connect_signals(window)
        window._init_window(check_callback, add_callback)
        return window

    def _init_window(self, check_callback, add_callback):
        self._check_callback = check_callback
        self._add_callback = add_callback
        self._add_button.props.visible = add_callback is not None

        for path in sorted(iglob(os.path.join(sys.prefix, 'share', 'unity', 'indicators', '*'))):
            name = os.path.basename(path)
            parts = name.rsplit('.', maxsplit=1)
            if len(parts) == 2 and parts[0] == 'com.canonical.indicator':
                name = parts[1]
            self._short_model.append((name,))

        for path in sorted(iglob(os.path.join(sys.prefix, 'lib', 'indicators3', '7', '*.so'))):
            self._short_model.append((os.path.basename(path),))

    def _get_current_value(self):
        if self._short_choice.props.active:
            return self._short_value.props.text
        else:
            return self._path_value.get_filename()

    def _update_state(self, force_state=None):
        message = None
        if force_state is None:
            valid = False
            if self._check_callback is not None:
                check = self._check_callback(self._get_current_value())
                if isinstance(check, str):
                    message = check
                else:
                    valid = bool(check)
            else:
                valid = True
        else:
            valid = force_state

        self._infobar.props.visible = message is not None
        if message is not None:
            self._message.props.label = message

        self._ok_button.props.sensitive = valid
        self._add_button.props.sensitive = valid

    def on_short_value_changed(self, widget):
        if not self._short_choice.props.active:
            self._short_choice.props.active = True
        else:
            self._update_state()

    def on_path_value_changed(self, widget):
        self._path_choice.props.active = True
        self._update_state()

    def on_short_choice_toggled(self, widget):
        self._update_state()

    def on_add_clicked(self, widget):
        value = self._get_current_value()
        if value:
            self._add_callback(value)
            self._update_state(False)

    def on_short_value_activate(self, entry):
        if self._short_choice.props.active and self._ok_button.props.sensitive:
            self._ok_button.clicked()

    def get_indicator(self):
        self._short_choice.props.active = True
        self._update_state()
        self._short_value.grab_focus()
        response = self.run()
        self.hide()
        if response == Gtk.ResponseType.OK:
            return self._get_current_value()
        return None
