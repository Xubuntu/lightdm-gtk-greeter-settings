#!/usr/bin/env python3


def main():
    from gi.repository import Gtk
    from lightdm_gtk_greeter_settings import GtkGreeterSettingsWindow
    window = GtkGreeterSettingsWindow.GtkGreeterSettingsWindow()
    window.show()
    Gtk.main()


if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    main()
