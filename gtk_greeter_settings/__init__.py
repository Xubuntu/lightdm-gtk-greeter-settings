#!/usr/bin/env python3

from gi.repository import Gtk


def main():
    from gtk_greeter_settings import GtkGreeterSettingsWindow
    window = GtkGreeterSettingsWindow.GtkGreeterSettingsWindow()
    window.show()
    Gtk.main()


if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    window = __import__('GtkGreeterSettingsWindow').GtkGreeterSettingsWindow()
    window.show()
    Gtk.main()
