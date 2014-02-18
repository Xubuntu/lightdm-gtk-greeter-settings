#!/usr/bin/env python3

import os
import sys
import configparser

try:
    import DistUtilsExtra.auto
except ImportError:
    print('To build lightdm-gtk-greeter-settings you need https://launchpad.net/python-distutils-extra')
    sys.exit(1)
assert DistUtilsExtra.auto.__version__ >= '2.18', 'needs DistUtilsExtra.auto >= 2.18'

def write_config(libdir, values):
    filename = os.path.join(libdir, 'lightdm_gtk_greeter_settings/installation_config.py')
    try:
        f = open(filename, 'w')
        f.write('__all__ = [%s]\n' % ', '.join('"%s"' % k for k in values))
        for k, v in values.items():
            f.write('%s = %s\n' % (k, v))
    except OSError as e:
            print ("ERROR: Can't write installation_config: %s" % e)
            sys.exit(1)


def move_desktop_file(root, target_data, prefix):
    old_desktop_path = os.path.normpath(root + target_data +
                                        '/share/applications')
    old_desktop_file = old_desktop_path + '/lightdm-gtk-greeter-settings.desktop'
    desktop_path = os.path.normpath(root + prefix + '/share/applications')
    desktop_file = desktop_path + '/lightdm-gtk-greeter-settings.desktop'

    if not os.path.exists(old_desktop_file):
        print("ERROR: Can't find", old_desktop_file)
        sys.exit(1)
    elif target_data != prefix + '/':
        # This is an /opt install, so rename desktop file to use extras-
        desktop_file = desktop_path + '/extras-lightdm-gtk-greeter-settings.desktop'
        try:
            os.makedirs(desktop_path)
            os.rename(old_desktop_file, desktop_file)
            os.rmdir(old_desktop_path)
        except OSError as e:
            print ("ERROR: Can't rename", old_desktop_file, ":", e)
            sys.exit(1)

    return desktop_file


def update_desktop_file(filename, target_pkgdata, target_scripts):

    config = configparser.RawConfigParser(strict=False, allow_no_value=True)
    try:
        config.read(filename)
    except configparser.Error as e:
        print("Cann't parse desktop file: %s" % e)
        sys.exit(1)

    if not config.has_section('Desktop Entry'):
        config.add_section('Desktop Entry')
    
    old_command = config.get('Desktop Entry', 'Exec', fallback='').split(None, 1)
    new_command = target_scripts + 'lightdm-gtk-greeter-settings'
    if len(old_command) > 1:
        new_command += ' ' + new_command[1]
    config.set('Desktop Entry', 'Exec', new_command)
    
    with open(filename, 'w') as f:
        config.write(f)


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):
    def run(self):
        DistUtilsExtra.auto.install_auto.run(self)

        target_data = '/' + os.path.relpath(self.install_data, self.root) + '/'
        target_pkgdata = target_data + 'share/lightdm-gtk-greeter-settings/'
        target_scripts = '/' + os.path.relpath(self.install_scripts, self.root) + '/'

        values = {'__data_directory__': "'%s'" % (target_pkgdata),
                  '__version__': "%s" % self.distribution.get_version(),
                  '__config_path__': '"/etc/lightdm/lightdm-gtk-greeter.conf"'}
        write_config(self.install_lib, values)

        desktop_file = move_desktop_file(self.root, target_data, self.prefix)
        update_desktop_file(desktop_file, target_pkgdata, target_scripts)


DistUtilsExtra.auto.setup(
    name='lightdm-gtk-greeter-settings',
    version='0.1',
    license='GPL-3',
    author='Andrew P.',
    author_email='pan.pav.7c5@gmail.com',
    description='Settings editor for LightDM GTK+ Greeter',
    long_description='Settings editor for LightDM GTK+ Greeter',
    url='https://launchpad.net/lightdm-gtk-greeter-settings',
    cmdclass={'install': InstallAndUpdateDataDirectory}
    )

