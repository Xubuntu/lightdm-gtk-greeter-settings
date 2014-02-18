
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


__all__ = ['get_data_path', 'get_config_path', 'show_message']


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
