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


import operator
import platform
import string
from copy import deepcopy

from gi.repository import (
    Gtk,
    Gdk)
from gi.repository.GObject import markup_escape_text as escape_markup

from lightdm_gtk_greeter_settings.helpers import (
    C_,
    get_greeter_version,
    get_markup_error,
    SimpleEnum,
    TreeStoreDataWrapper)
from lightdm_gtk_greeter_settings.OptionEntry import BaseEntry


__all__ = ['BuiltInIndicators',
           'EmptyIndicators',
           'Indicators',
           'IndicatorsEntry',
           'Option',
           'SingleIndicators']


class Indicators(SimpleEnum):
    External = '~external'
    Spacer = '~spacer'
    Separator = '~separator'
    Text = '~text'
    Host = '~host'
    Clock = '~clock'
    Layout = '~layout'
    Session = '~session'
    Language = '~language'
    A11y = '~a11y'
    Power = '~power'


# Valid builtin indicators
BuiltInIndicators = set(Indicators) - {Indicators.External}

# Special indicators
EmptyIndicators = {Indicators.Spacer, Indicators.Separator}

# These indicators can have only one instance
SingleIndicators = set(Indicators) - {Indicators.External, Indicators.Text,
                                      Indicators.Spacer, Indicators.Separator}

# Valid options names


class Option(SimpleEnum):
    # Common
    Name = 'name'
    Layout = 'layout'
    Text = 'text'
    Image = 'image'
    FallbackImage = 'fallback-image'
    Tooltip = 'tooltip'
    Markup = 'markup'
    Expand = 'expand'
    Align = 'align'
    # External
    Path = 'path'
    # Power
    HideDisabled = 'hide-disabled'


class Layout(SimpleEnum):
    Empty = ''
    Text = 'text'
    Image = 'image'
    ImageText = 'image-text'
    TextImage = 'text-image'

    @classmethod
    def _to_set(cls, value):
        return LayoutSet._str2set.get(value, set())


class LayoutSet(SimpleEnum):
    Text = 'text'
    Image = 'image'
    Reversed = 'reversed'

    _str2set = {
        Layout.Empty: set(),
        Layout.Text: {Text},
        Layout.Image: {Image},
        Layout.ImageText: {Text, Image},
        Layout.TextImage: {Text, Image, Reversed}}

    @classmethod
    def _to_string(cls, value):
        return next((k for k, v in cls._str2set.items() if v == value), '')


class Row(SimpleEnum):
    Name = ()
    Tooltip = ()
    HasState = ()
    State = ()
    Options = ()
    Icon = ()
    Markup = ()


class IndicatorsEntry(BaseEntry):
    # Readable names for indicators
    Names = {
        Indicators.External:    C_('option-entry|indicators|name', 'External library/service'),
        Indicators.Spacer:      C_('option-entry|indicators|name', 'Spacer'),
        Indicators.Separator:   C_('option-entry|indicators|name', 'Separator'),
        Indicators.Text:        C_('option-entry|indicators|name', 'Text'),
        Indicators.Clock:       C_('option-entry|indicators|name', 'Clock'),
        Indicators.Host:        C_('option-entry|indicators|name', 'Host name'),
        Indicators.Layout:      C_('option-entry|indicators|name', 'Keyboard layout'),
        Indicators.Session:     C_('option-entry|indicators|name', 'Sessions menu'),
        Indicators.Language:    C_('option-entry|indicators|name', 'Languages menu'),
        Indicators.A11y:        C_('option-entry|indicators|name', 'Accessibility menu'),
        Indicators.Power:       C_('option-entry|indicators|name', 'Power menu')}
    # Default icons for indicators to display in treeview
    Icons = {
        Indicators.A11y:        'preferences-desktop-accessibility',
        Indicators.Session:     'document-properties',
        Indicators.Power:       'system-shutdown'}
    Tooltips = {
        Indicators.Spacer:      C_('option-entry|indicators|tooltip', 'Spacer'),
        Indicators.Separator:   C_('option-entry|indicators|tooltip', 'Separator'),
        Indicators.Text:        C_('option-entry|indicators|tooltip', 'Custom text or/and image'),
        Indicators.Host:        C_('option-entry|indicators|tooltip', 'Host name'),
        Indicators.Clock:       C_('option-entry|indicators|tooltip', 'Clock'),
        Indicators.Layout:      C_('option-entry|indicators|tooltip', 'Layout indicator'),
        Indicators.Session:     C_('option-entry|indicators|tooltip',
                                   'Sessions menu (xfce, unity, gnome etc.)'),
        Indicators.Language:    C_('option-entry|indicators|tooltip', 'Languages menu'),
        Indicators.A11y:        C_('option-entry|indicators|tooltip', 'Accessibility menu'),
        Indicators.Power:       C_('option-entry|indicators|tooltip', 'Power menu')}
    # Default options for indicators
    DefaultOptions = {
        Indicators.External:    {Option.Text: None, Option.Image: None},
        Indicators.Spacer:      {Option.Layout: set()},
        Indicators.Separator:   {Option.Layout: set()},
        Indicators.Text:        {Option.Layout: {LayoutSet.Text}, Option.Text: None},
        Indicators.Host:        {Option.Layout: {LayoutSet.Text}, Option.Text: None},
        Indicators.Clock:       {Option.Layout: {LayoutSet.Text}, Option.Text: None},
        Indicators.Layout:      {Option.Layout: {LayoutSet.Text}, Option.Text: None},
        Indicators.Session:     {Option.Layout: {LayoutSet.Text, LayoutSet.Image},
                                 Option.Text: None, Option.Image: None},
        Indicators.Language:    {Option.Layout: {LayoutSet.Text}, Option.Text: None},
        Indicators.A11y:        {Option.Layout: {LayoutSet.Image}, Option.Image: None},
        Indicators.Power:       {Option.Layout: {LayoutSet.Image}, Option.Image: None}}

    def __init__(self, widgets):
        super().__init__(widgets)

        if get_greeter_version() < 0x020100:
            self._get_value = self._get_value_19
            self._on_button_release = self._on_button_release_19

        for k, v in self.DefaultOptions.items():
            v[Option.Name] = k

        self._treeview = widgets['treeview']
        self._selection = widgets['selection']
        self._state_renderer = widgets['state_renderer']
        self._state_column = widgets['state_column']
        self._add = widgets['add']
        self._remove = widgets['remove']
        self._up = widgets['up']
        self._down = widgets['down']
        self._tools = widgets['tools']
        self._model = widgets['model']
        self._widgets_to_disable = [self._treeview, widgets['toolbar']]
        self._properties_dialog = None
        self._row_menu = None
        self._tools_menu = None
        self._show_unused = False

        self._treeview.connect('key-press-event', self._on_key_press)
        self._treeview.connect('row-activated', self._on_row_activated)
        self._treeview.connect('button-release-event', self._on_button_release)
        self._selection.connect('changed', self._on_selection_changed)
        self._state_renderer.connect('toggled', self._on_state_toggled)

        self._add.connect('clicked', self._on_add_clicked)
        self._remove.connect('clicked', self._on_remove_clicked)
        self._up.connect('clicked', self._on_up_clicked)
        self._down.connect('clicked', self._on_down_clicked)
        self._tools.connect('clicked', self._on_tools_clicked)

        self._on_row_changed_id = self._model.connect('row-changed', self._on_model_changed)
        self._on_row_deleted_id = self._model.connect('row-deleted', self._on_model_changed)
        self._on_row_inserted_id = self._model.connect('row-inserted', self._on_model_row_inserted)
        self._on_rows_reordered_id = self._model.connect('rows-reordered', self._on_model_changed)

    def _on_model_changed(self, *unused):
        self._emit_changed()

    def _on_model_row_inserted(self, model, path, rowiter):
        # Do not emit 'changed' for uninitialized row (dragging rows)
        # It can cause calling get_value() for model with invalid values
        if model[rowiter][Row.Name] is not None:
            self._emit_changed()

    def _get_value(self):
        def fix_token(s):
            s = s.replace('"', r'\"')
            if any(c in s for c in string.whitespace):
                s = '"' + s + '"'
            return s

        items = []
        for row in self._model:
            if row[Row.HasState] and not row[Row.State]:
                continue

            options = deepcopy(row[Row.Options].data)
            name = options.pop(Option.Name)
            defaults = deepcopy(self.DefaultOptions[name])

            # text, image, layout=image-text -> text, image
            if options.get(Option.Layout) == {LayoutSet.Text, LayoutSet.Image}:
                del options[Option.Layout]

            for k in defaults.keys() & options.keys():
                if defaults[k] == options[k]:
                    del options[k]

            if Option.Layout in options:
                layout = options[Option.Layout]
                options[Option.Layout] = LayoutSet._to_string(layout)
                # text, layout=text -> layout=text
                if LayoutSet.Text in layout and options.get(Option.Text, self) is None:
                    del options[Option.Text]
                if LayoutSet.Image in layout and options.get(Option.Image, self) is None:
                    del options[Option.Image]

            # name=~text, text=value -> ~~value
            if name == Indicators.Text:
                name = '~~' + (options.pop(Option.Text, None) or '')
            elif name == Indicators.External:
                name = options.pop(Option.Path, None) or ''

            if not options:
                items.append(fix_token(name))
            else:
                values = (fix_token(k) + '=' + fix_token(v) if v else fix_token(k)
                          for k, v in sorted(options.items(), key=operator.itemgetter(0)))
                items.append(fix_token(name) + ': ' + ', '.join(values))
        return '; '.join(items)

    def _get_value_19(self):
        items = []
        for row in self._model:
            if row[Row.HasState] and not row[Row.State]:
                continue

            options = deepcopy(row[Row.Options].data)
            name = options.pop(Option.Name)

            # name=~text, text=value -> ~~value
            if name == Indicators.Text:
                name = '~~' + (options.pop(Option.Text, None) or '')
            elif name == Indicators.External:
                name = options.pop(Option.Path, None) or ''

            items.append(name)
        return ';'.join(items)

    def _set_value(self, value):
        with self._model.handler_block(self._on_row_deleted_id):
            self._model.clear()

        for options in self._read_options_string(value):
            name = options[Option.Name]

            if name.startswith('~~'):
                options.setdefault(Option.Text, name[2:])
                options[Option.Name] = Indicators.Text
                name = Indicators.Text
            elif name not in BuiltInIndicators:
                options.setdefault(Option.Path, name)
                options[Option.Name] = Indicators.External
                name = Indicators.External

            defaults = deepcopy(self.DefaultOptions[name])

            if Option.Markup in options:
                markup = options[Option.Markup]
                if markup is not None:
                    options[Option.Text] = markup
                options[Option.Markup] = None

            if Option.Layout in options:
                options[Option.Layout] = Layout._to_set(options[Option.Layout])
            else:
                options[Option.Layout] = defaults.get(Option.Layout) or set()

            if Option.Text in options:
                options[Option.Layout].add(LayoutSet.Text)
            elif LayoutSet.Text in options[Option.Layout]:
                options.setdefault(Option.Text, None)
            else:
                defaults.pop(Option.Text, None)

            if Option.Image in options:
                options[Option.Layout].add(LayoutSet.Image)
            elif LayoutSet.Image in options[Option.Layout]:
                options.setdefault(Option.Image, None)
            else:
                defaults.pop(Option.Image, None)

            options.update((k, defaults[k])
                           for k in defaults.keys() - options.keys())

            with self._model.handler_block(self._on_row_changed_id), \
                    self._model.handler_block(self._on_row_inserted_id):
                self._set_row(None, options, select=False)

        if self._show_unused:
            self._tools_show_unused_toggled()

        self._selection.select_path(0)
        self._on_model_changed()

    def _read_options_string(self, s):
        while s:
            name, s = self._next_string_token(s, ':;')
            options = {Option.Name: name}

            if s.startswith(':'):
                while s:
                    option, s = self._next_string_token(s[1:], '=,;')
                    if s.startswith('='):
                        value, s = self._next_string_token(s[1:], ',;')
                    else:
                        value = None
                    options[option] = value
                    if not s.startswith(','):
                        break

            yield options
            s = s[1:]

    def _next_string_token(self, s, delimiters):
        token = []
        quoted = False

        for last, c in enumerate(s):
            if not c.isspace():
                break

        # Parsing quotes
        for i, c in enumerate(s[last:], last):
            if c == '"':
                if i > last and s[i - 1] == '\\':
                    token.append(s[last:i - 1])
                    token.append('"')
                else:
                    token.append(s[last:i])
                    quoted = not quoted
                last = i + 1
            elif not quoted and c in delimiters:
                break

        if quoted:
            return '', ''

        if last != i or last == 0:
            token.append(s[last: i if c in delimiters else i + 1].rstrip())

        return ''.join(token) if token else None, s[i:]

    def _remove_selection(self):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            if self._show_unused and model[rowiter][Row.HasState]:
                model[rowiter][Row.State] = False
            else:
                model.remove(rowiter)
            self._on_selection_changed()

    def _move_selection(self, move_up):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            next_iter = model.iter_previous(
                rowiter) if move_up else model.iter_next(rowiter)
            if self._show_unused and \
               (model[rowiter][Row.HasState] and not model[rowiter][Row.State] or
                    model[next_iter][Row.HasState] and not model[next_iter][Row.State]):
                with self._model.handler_block(self._on_rows_reordered_id):
                    model.swap(rowiter, next_iter)
            else:
                model.swap(rowiter, next_iter)
            self._on_selection_changed()

    def _create_row_tuple(self, options):
        name = options[Option.Name]
        error = None

        text = options.get(Option.Text)
        if Option.Text in options:
            if text is not None:
                if Option.Markup in options:
                    error = get_markup_error(text)
                    if error:
                        text = '<i>{text}</i>'.format(text=escape_markup(text))
                else:
                    text = escape_markup(text)
                text = '"' + text + '"'
            elif name == Indicators.Host:
                text = escape_markup(platform.node())

        display_name = self.Names.get(name, name)
        if name == Indicators.External:
            if options.get(Option.Path):
                title = '{name} ({value})'.format(name=escape_markup(display_name),
                                                  value=escape_markup(options[Option.Path]))
            else:
                title = escape_markup(display_name)
        else:
            title = escape_markup(display_name)

        if text:
            markup = '{name}: {text}'.format(name=title, text=text)
        else:
            markup = title

        if Option.Image in options or get_greeter_version() < 0x020100:
            icon = options.get(Option.Image)
            if icon and icon.startswith('#'):
                icon = icon[1:]
            elif icon:
                icon = 'image-x-generic'
            else:
                if name in self.Icons:
                    icon = self.Icons[name]
                elif name in BuiltInIndicators:
                    icon = 'applications-system'
                else:
                    icon = 'application-x-executable'
        else:
            icon = ''

        has_state = name in SingleIndicators

        return Row._make(Name=name,
                         Tooltip=self.Tooltips.get(name),
                         Icon=icon,
                         Markup=markup,
                         HasState=has_state, State=has_state,
                         Options=TreeStoreDataWrapper(options))

    def _set_row(self, rowiter, options, select=True):
        old_name = self._model[rowiter][Row.Name] if rowiter else None
        new_name = options.get(
            Option.Name, '') if options is not None else None
        old_is_single = old_name in SingleIndicators
        new_is_single = new_name in SingleIndicators

        if new_name == old_name:
            # The same row - just update
            pass
        elif old_is_single and new_is_single:
            old_row = next(
                (row for row in self._model if row[Row.Name] == new_name), None)
            if old_row:
                if self._show_unused:
                    # Swap current row with new_row
                    with self._model.handler_block(self._on_rows_reordered_id):
                        self._model.move_before(old_row.iter, rowiter)
                    with self._model.handler_block(self._on_row_changed_id):
                        self._model[rowiter][Row.State] = False
                    rowiter = old_row.iter
                else:
                    # Replace current row with replace_row
                    with self._model.handler_block(self._on_row_deleted_id):
                        self._model.remove(old_row.iter)
        elif old_is_single:
            if self._show_unused:
                # Uncheck old row and use new instead of it
                with self._model.handler_block(self._on_row_changed_id):
                    self._model[rowiter][Row.State] = False
                with self._model.handler_block(self._on_row_inserted_id):
                    new_iter = self._model.insert_after(rowiter)
                rowiter = new_iter
        elif new_is_single:
            old_row = next(
                (row for row in self._model if row[Row.Name] == new_name), None)
            if old_row:
                with self._model.handler_block(self._on_row_deleted_id):
                    self._model.remove(old_row.iter)

        if rowiter and options:
            with self._model.handler_block(self._on_row_changed_id):
                self._model[rowiter] = self._create_row_tuple(options)
            self._model.row_changed(self._model.get_path(rowiter), rowiter)
        elif options:
            rowiter = self._model.append(self._create_row_tuple(options))

        if select and rowiter:
            self._selection.select_iter(rowiter)

        return rowiter

    def _edit_indicator(self, options, add_callback=None):
        if not self._properties_dialog:
            from lightdm_gtk_greeter_settings.IndicatorPropertiesDialog \
                import IndicatorPropertiesDialog as Dialog
            self._properties_dialog = Dialog(is_duplicate=self._is_duplicate,
                                             get_defaults=self.DefaultOptions.get,
                                             get_name=self.Names.get)
            self._properties_dialog.props.transient_for = self._treeview.get_toplevel()

        self._properties_dialog.add_callback = add_callback
        self._properties_dialog.set_indicator(options)
        if self._properties_dialog.run() == Gtk.ResponseType.OK:
            options = self._properties_dialog.get_indicator()
        else:
            options = None
        self._properties_dialog.hide()
        return options

    def _is_duplicate(self, name):
        return name in SingleIndicators and any(row[Row.Name] == name
                                                for row in self._model if row[Row.State])

    def _add_indicator(self, options):
        self._set_row(None, options)

    def _on_key_press(self, treeview, event):
        if Gdk.keyval_name(event.keyval) == 'Delete':
            self._remove_selection()
        elif Gdk.keyval_name(event.keyval) == 'F2':
            model, rowiter = self._selection.get_selected()
            treeview.row_activated(model.get_path(rowiter), None)
        else:
            return False
        return True

    def _on_row_activated(self, treeview, path, column):
        if column != self._state_column:
            options = self._edit_indicator(self._model[path][Row.Options].data)
            if options:
                self._set_row(self._model.get_iter(path), options)

    def _on_button_release(self, treeview, event):
        if event.button != 3:
            return False

        pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not pos:
            return False

        row = self._model[pos[0]]
        if row[Row.HasState] and not row[Row.State]:
            return False

        if not self._row_menu:
            self._row_menu = Gtk.Menu()
            self._row_menu_reset = Gtk.MenuItem(C_('option-entry|indicators',
                                                   'Reset to _defaults'))
            self._row_menu_text = Gtk.CheckMenuItem(C_('option-entry|indicators',
                                                       'Display _label'))
            self._row_menu_image = Gtk.CheckMenuItem(C_('option-entry|indicators',
                                                        'Display _image'))
            self._row_menu_remove = Gtk.MenuItem(
                C_('option-entry|indicators', '_Remove'))

            self._row_menu_text_id = self._row_menu_text.connect('toggled',
                                                                 self._on_row_menu_toggled,
                                                                 Option.Text)
            self._row_menu_image_id = self._row_menu_image.connect('toggled',
                                                                   self._on_row_menu_toggled,
                                                                   Option.Image)
            self._row_menu_reset.connect(
                'activate', self._on_row_menu_reset_clicked)
            self._row_menu_remove.connect('activate', self._on_remove_clicked)

            self._row_menu.append(self._row_menu_reset)
            self._row_menu.append(self._row_menu_text)
            self._row_menu.append(self._row_menu_image)
            self._row_menu.append(Gtk.SeparatorMenuItem())
            self._row_menu.append(self._row_menu_remove)

            for item in self._row_menu:
                if type(item) is not Gtk.SeparatorMenuItem:
                    item.props.use_underline = True
                item.props.visible = True

        options = row[Row.Options].data

        with self._row_menu_text.handler_block(self._row_menu_text_id):
            self._row_menu_text.props.active = Option.Text in options
        with self._row_menu_image.handler_block(self._row_menu_image_id):
            self._row_menu_image.props.active = Option.Image in options

        editable = options[Option.Name] not in {
            Indicators.Spacer, Indicators.Separator}
        self._row_menu_reset.props.sensitive = editable
        self._row_menu_text.props.sensitive = editable
        self._row_menu_image.props.sensitive = editable

        self._row_menu.popup(None, None, None, None, 0,
                             Gtk.get_current_event_time())

        return True

    def _on_button_release_19(self, treeview, event):
        pass

    def _on_row_menu_reset_clicked(self, item):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            name = model[rowiter][Row.Name]
            options = deepcopy(self.DefaultOptions[name])
            options[Option.Name] = name
            with model.handler_block(self._on_row_changed_id):
                model[rowiter] = self._create_row_tuple(options)
            model.row_changed(model.get_path(rowiter), rowiter)

    def _on_row_menu_toggled(self, item, option):
        model, rowiter = self._selection.get_selected()
        options = model[rowiter][Row.Options].data
        if item.props.active:
            options.setdefault(option, None)
        else:
            options.pop(option, None)
        model[rowiter] = self._create_row_tuple(options)

    def _on_state_toggled(self, renderer, path):
        self._model[path][Row.State] = not self._model[path][Row.State]

    def _on_selection_changed(self, selection=None):
        model, rowiter = self._selection.get_selected()
        if rowiter:
            row = model[rowiter]
            self._remove.props.sensitive = not row[
                Row.HasState] or row[Row.State]
            self._down.props.sensitive = model.iter_next(rowiter)
            self._up.props.sensitive = model.iter_previous(rowiter)
            self._treeview.scroll_to_cell(model.get_path(rowiter))
        else:
            self._remove.props.sensitive = False
            self._down.props.sensitive = False
            self._up.props.sensitive = False

    def _on_add_clicked(self, button=None):
        options = self._edit_indicator(self.DefaultOptions[Indicators.External],
                                       add_callback=self._add_indicator)
        if options:
            self._set_row(None, options, select=True)

    def _on_remove_clicked(self, button=None):
        self._remove_selection()

    def _on_up_clicked(self, button=None):
        self._move_selection(move_up=True)

    def _on_down_clicked(self, button=None):
        self._move_selection(move_up=False)

    def _on_tools_clicked(self, button=None):
        if not self._tools_menu:
            self._tools_menu = Gtk.Menu()
            self._tools_menu.attach_to_widget(self._tools)

            unused_item = Gtk.CheckMenuItem(C_('option-entry|indicators', 'Show unused items'))
            unused_item.connect('toggled', self._tools_show_unused_toggled)
            self._tools_menu.append(unused_item)

            header_item = Gtk.MenuItem(C_('option-entry|indicators', 'Predefined templates:'))
            header_item.props.sensitive = False
            self._tools_menu.append(Gtk.SeparatorMenuItem())
            self._tools_menu.append(header_item)

            templates = (
                ('host ~ clock, language, session, power',
                 '~host;~spacer;~language;~session;~power'),
                ('host ~ clock ~ language, session, a11y, power',
                 '~host;~spacer;~clock;~spacer;~language;~session;~a11y;~power'),
                ('host, layout, clock ~ language, session, power',
                 '~host;~layout;~clock;~spacer;~language;~session;~power'))

            for title, value in templates:
                item = Gtk.MenuItem(title)
                item.connect('activate', self._on_tools_template_clicked, value)
                self._tools_menu.append(item)

            self._tools_menu.show_all()
        self._tools_menu.popup(None, None, None, None, 0,
                               Gtk.get_current_event_time())

    def _on_tools_template_clicked(self, item, value):
        self._set_value(value)

    def _tools_show_unused_toggled(self, widget=None):
        if widget:
            self._show_unused = widget.props.active
        self._state_column.props.visible = self._show_unused

        used = {row[Row.Name]: row
                for row in self._model if row[Row.Name] in SingleIndicators}
        if self._show_unused:
            for name in SingleIndicators - used.keys():
                options = deepcopy(self.DefaultOptions[name])
                options[Option.Name] = name
                with self._model.handler_block(self._on_row_changed_id),\
                        self._model.handler_block(self._on_row_inserted_id):
                    rowiter = self._set_row(None, options, select=False)
                    self._model[rowiter][Row.State] = False
        else:
            for row in used.values():
                if row[Row.HasState] and not row[Row.State]:
                    with self._model.handler_block(self._on_row_deleted_id):
                        self._model.remove(row.iter)
