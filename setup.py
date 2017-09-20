#!/usr/bin/env python3
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#   LightDM GTK Greeter Settings
#   Copyright (C) 2014 Andrew P. <pan.pav.7c5@gmail.com>
#
#   This program is free software: you can redistribute it and/or modify it
#   under the terms of the GNU General Public License version 3, as published
#   by the Free Software Foundation.
#
#   This program is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranties of
#   MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

try:
    import DistUtilsExtra.auto
except ImportError:
    print(
        'To build lightdm-gtk-greeter-settings you need '
        'https://launchpad.net/python-distutils-extra')
    sys.exit(1)
assert DistUtilsExtra.auto.__version__ >= '2.18', \
    'needs DistUtilsExtra.auto >= 2.18'


def write_config(libdir, values):
    filename = os.path.join(
        libdir, 'lightdm_gtk_greeter_settings/installation_config.py')
    try:
        f = open(filename, 'w')
        f.write('__all__ = [%s]\n' % ', '.join('"%s"' % k for k in sorted(values)))
        for k, v in sorted(values.items()):
            f.write('%s = %s\n' % (k, v))
    except OSError as e:
        print("ERROR: Can't write installation config: %s" % e)
        sys.exit(1)


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):

    user_options = DistUtilsExtra.auto.install_auto.user_options + \
        [('xfce-integration', None,
          'adds application icon to Xfce settings manager'),
         ('use-gtk-header', None,
          'use GtkHeaderBar instead of default DE window header')]

    def initialize_options(self):
        super().initialize_options()
        self.xfce_integration = None
        self.use_gtk_header = None

    def run(self):
        DistUtilsExtra.auto.install_auto.run(self)

        target_data = '/' + os.path.relpath(self.install_data, self.root) + '/'
        target_pkgdata = target_data + 'share/lightdm-gtk-greeter-settings/'

        values = {'__data_directory__': "'%s'" % (target_pkgdata),
                  '__version__': "'%s'" % self.distribution.get_version(),
                  '__config_path__': '"/etc/lightdm/lightdm-gtk-greeter.conf"'}
        write_config(self.install_lib, values)

        desktop_file_path = os.path.join(self.install_data, 'share', 'applications',
                                         'lightdm-gtk-greeter-settings.desktop')

        if self.xfce_integration:
            with open(desktop_file_path, 'a') as f:
                f.write('X-XfcePluggable=true\n')

        if self.use_gtk_header:
            with open(desktop_file_path, 'r+') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.startswith('Exec='):
                        lines[i] = line.strip() + ' --use-gtk-header\n'
                        break
                f.seek(0)
                f.truncate(0)
                f.writelines(lines)


DistUtilsExtra.auto.setup(
    name='lightdm-gtk-greeter-settings',
    version='1.2.2',
    license='GPL-3',
    author='Andrew P.',
    author_email='pan.pav.7c5@gmail.com',
    description='Settings editor for LightDM GTK+ Greeter',
    long_description='Settings editor for LightDM GTK+ Greeter',
    url='https://launchpad.net/lightdm-gtk-greeter-settings',
    cmdclass={'install': InstallAndUpdateDataDirectory},
)
