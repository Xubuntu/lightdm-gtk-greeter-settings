#!/usr/bin/env python3


def main():
    from gi.repository import Gtk
    from lightdm_gtk_greeter_settings import GtkGreeterSettingsWindow

    import locale
    locale.textdomain('lightdm-gtk-greeter-settings')

    window = GtkGreeterSettingsWindow.GtkGreeterSettingsWindow()
    window.show()
    Gtk.main()


if __name__ == '__main__':
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    main()
