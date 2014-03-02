
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


# Have I again missed something obvious or there is no pgettext(context, id) in python?
def C_(context, message):
    CONTEXT_SEPARATOR = "\x04"
    message_with_context = "{}{}{}".format(context, CONTEXT_SEPARATOR, message)
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
