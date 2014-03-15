
from collections import namedtuple
from gi.repository import Gtk, GObject
from lightdm_gtk_greeter_settings.helpers import get_data_path, NC_, C_


__all__ = ['IconChooserDialog']


class IconChooserDialog(Gtk.Dialog):

    __gtype_name__ = 'IconChooserDialog'

    ContextsModelRow = namedtuple('ContextsModelRow',
                                  ('name', 'standard', 'title'))
    IconsModelRow = namedtuple('IconsModelRow',
                               ('name', 'standard', 'context'))
    IconsFilterArgs = namedtuple('IconsFilterArgs', ('standard', 'context'))

    BUILDER_WIDGETS = ('name', 'preview', 'standard_toggle', 'spinner',
                       'contexts_view', 'contexts_selection', 'contexts_model', 'contexts_filter',
                       'icons_view', 'icons_selection',
                       'icons_model', 'icons_sorted', 'icons_filter')

    def __new__(cls):
        builder = Gtk.Builder()
        builder.add_from_file(get_data_path('%s.ui' % cls.__name__))
        window = builder.get_object('icon_chooser_dialog')
        window._builder = builder
        window.__dict__.update(('_' + w, builder.get_object(w))
                               for w in cls.BUILDER_WIDGETS)

        builder.connect_signals(window)
        window._init_window()
        return window

    def _init_window(self):
        # Map ContextsModelRow fields to self._CONTEXT_{FIELD} = {field-index}
        for i, field in enumerate(IconChooserDialog.ContextsModelRow._fields):
            setattr(self, '_CONTEXT_' + field.upper(), i)
        # Map IconsModelRow fields to self._ICON_{FIELD} = {field-index}
        for i, field in enumerate(IconChooserDialog.IconsModelRow._fields):
            setattr(self, '_ICON_' + field.upper(), i)

        self._icons_loaded = False
        self._icon_to_select = None
        self._icons_filter_args = None

        self._contexts_view.set_row_separator_func(self._contexts_row_separator_callback, None)
        self._contexts_filter.set_visible_func(self._contexts_filter_visible_callback)

        self._icons_filter.set_visible_func(self._icons_filter_visible_callback)
        self._icons_sorted.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self._reload()

    def _read_icons(self):
        theme = Gtk.IconTheme.get_default()
        standard_contexts = set(name for name, title in STANDARD_CONTEXTS)

        self._contexts_model.clear()
        for name, title in STANDARD_CONTEXTS:
            translated_title = title and C_('icon-dialog', title)
            self._contexts_model.append(self.ContextsModelRow(name=name,
                                                              standard=True,
                                                              title=translated_title))

        for name in theme.list_contexts():
            if name not in standard_contexts:
                self._contexts_model.append(self.ContextsModelRow(name=name,
                                                                  standard=False,
                                                                  title=name))

        self._icons_model.clear()
        for context in theme.list_contexts():
            for icon in theme.list_icons(context):
                row = self.IconsModelRow(name=icon,
                                         standard=icon in STANDARD_ICON_NAMES,
                                         context=context)
                self._icons_model.append(row)

        self._icons_loaded = True
        if self._icon_to_select:
            self.select_icon(self._icon_to_select)
            self._icon_to_select = None
        return False

    def _reload(self):
        GObject.idle_add(self._read_icons)

    def _update_contexts_filter(self):
        selected_iter = self._contexts_selection.get_selected()[1]
        selected_path = self._contexts_filter.get_path(selected_iter) if selected_iter else None
        self._contexts_filter.refilter()
        if selected_path and self._contexts_selection.path_is_selected(selected_path):
            self._update_icons_filter()

    def _update_icons_filter(self):
        model, rowiter = self._contexts_selection.get_selected()
        if rowiter:
            self._icons_filter_args = self.IconsFilterArgs(self._standard_toggle.props.active,
                                                           model[rowiter][self._CONTEXT_NAME])
        else:
            self._icons_filter_args = None
        self._icons_view.props.model = None
        self._icons_filter.refilter()
        self._icons_view.props.model = self._icons_sorted

    def _contexts_filter_visible_callback(self, model, rowiter, data):
        if not self._standard_toggle.props.active:
            return True
        return model[rowiter][self._CONTEXT_STANDARD]

    def _contexts_row_separator_callback(self, model, rowiter, data):
        return not model[rowiter][self._CONTEXT_NAME] and \
               not model[rowiter][self._CONTEXT_TITLE]

    def _icons_filter_visible_callback(self, model, rowiter, data):
        if not self._icons_filter_args:
            return False
        if self._icons_filter_args.standard and not model[rowiter][self._ICON_STANDARD]:
            return False
        if not self._icons_filter_args.context:
            return True
        return model[rowiter][self._ICON_CONTEXT] == self._icons_filter_args.context

    def run(self):
        return super().run()

    def get_iconname(self):
        return self._name.props.text

    def select_icon(self, name):
        if not self._icons_loaded:
            self._icon_to_select = name
            return

        if not self._icons_filter_args or self._icons_filter_args.context is not None:
            if name not in STANDARD_ICON_NAMES:
                self._standard_toggle.props.active = False
            self._contexts_selection.select_path(0)
        for row in self._icons_sorted:
            if row[self._ICON_NAME] == name:
                self._icons_view.set_cursor(row.path)
                self._icons_selection.select_path(row.path)
                break
        else:
            self._name.props.text = name

    def on_icons_selection_changed(self, selection):
        model, rowiter = self._icons_selection.get_selected()
        if rowiter:
            name = model[rowiter][self._ICON_NAME]
            self._name.props.text = name

    def on_contexts_selection_changed(self, selection):
        self._icons_selection.unselect_all()
        self._update_icons_filter()

    def on_standard_toggled(self, toggle):
        self._update_contexts_filter()

    def on_name_changed(self, entry):
        name = entry.props.text
        if not Gtk.IconTheme.get_default().has_icon(name):
            name = ''
        self._preview.props.icon_name = name


# http://standards.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html

STANDARD_CONTEXTS =\
(
    (None, NC_('icon-dialog', 'All contexts')),
    (None, ''),  # separator
    ('Actions', NC_('icon-dialog', 'Actions')),
    ('Applications', NC_('icon-dialog', 'Applications')),
    ('Categories', NC_('icon-dialog', 'Categories')),
    ('Devices', NC_('icon-dialog', 'Devices')),
    ('Emblems', NC_('icon-dialog', 'Emblems')),
    ('Emotes', NC_('icon-dialog', 'Emoticons')),
    ('International', NC_('icon-dialog', 'International')),
    ('MimeTypes', NC_('icon-dialog', 'MIME Types')),
    ('Places', NC_('icon-dialog', 'Places')),
    ('Status', NC_('icon-dialog', 'Status'))
)

STANDARD_ICON_NAMES = \
{
# Actions
'address-book-new', 'application-exit', 'appointment-new', 'call-start', 'call-stop', 'contact-new',
'document-new', 'document-open', 'document-open-recent', 'document-page-setup', 'document-print',
'document-print-preview', 'document-properties', 'document-revert', 'document-save',
'document-save-as', 'document-send', 'edit-clear', 'edit-copy', 'edit-cut', 'edit-delete',
'edit-find', 'edit-find-replace', 'edit-paste', 'edit-redo', 'edit-select-all', 'edit-undo',
'folder-new', 'format-indent-less', 'format-indent-more', 'format-justify-center',
'format-justify-fill', 'format-justify-left', 'format-justify-right', 'format-text-direction-ltr',
'format-text-direction-rtl', 'format-text-bold', 'format-text-italic', 'format-text-underline',
'format-text-strikethrough', 'go-bottom', 'go-down', 'go-first', 'go-home', 'go-jump', 'go-last',
'go-next', 'go-previous', 'go-top', 'go-up', 'help-about', 'help-contents', 'help-faq',
'insert-image', 'insert-link', 'insert-object', 'insert-text', 'list-add', 'list-remove',
'mail-forward', 'mail-mark-important', 'mail-mark-junk', 'mail-mark-notjunk', 'mail-mark-read',
'mail-mark-unread', 'mail-message-new', 'mail-reply-all', 'mail-reply-sender', 'mail-send',
'mail-send-receive', 'media-eject', 'media-playback-pause', 'media-playback-start',
'media-playback-stop', 'media-record', 'media-seek-backward', 'media-seek-forward',
'media-skip-backward', 'media-skip-forward', 'object-flip-horizontal', 'object-flip-vertical',
'object-rotate-left', 'object-rotate-right', 'process-stop', 'system-lock-screen',
'system-log-out', 'system-run', 'system-search', 'system-reboot', 'system-shutdown',
'tools-check-spelling', 'view-fullscreen', 'view-refresh', 'view-restore', 'view-sort-ascending',
'view-sort-descending', 'window-close', 'window-new', 'zoom-fit-best', 'zoom-in', 'zoom-original',
'zoom-out',
# StandardApplicationIcons
'accessories-calculator', 'accessories-character-map', 'accessories-dictionary',
'accessories-text-editor', 'help-browser', 'multimedia-volume-control',
'preferences-desktop-accessibility', 'preferences-desktop-font', 'preferences-desktop-keyboard',
'preferences-desktop-locale', 'preferences-desktop-multimedia', 'preferences-desktop-screensaver',
'preferences-desktop-theme', 'preferences-desktop-wallpaper', 'system-file-manager',
'system-software-install', 'system-software-update', 'utilities-system-monitor',
'utilities-terminal',
# StandardCategoryIcons
'applications-accessories', 'applications-development', 'applications-engineering',
'applications-games', 'applications-graphics', 'applications-internet', 'applications-multimedia',
'applications-office', 'applications-other', 'applications-science', 'applications-system',
'applications-utilities', 'preferences-desktop', 'preferences-desktop-peripherals',
'preferences-desktop-personal', 'preferences-other', 'preferences-system',
'preferences-system-network', 'system-help',
# StandardDeviceIcons
'audio-card', 'audio-input-microphone', 'battery', 'camera-photo', 'camera-video', 'camera-web',
'computer', 'drive-harddisk', 'drive-optical', 'drive-removable-media', 'input-gaming',
'input-keyboard', 'input-mouse', 'input-tablet', 'media-flash', 'media-floppy', 'media-optical',
'media-tape', 'modem', 'multimedia-player', 'network-wired', 'network-wireless', 'pda', 'phone',
'printer', 'scanner', 'video-display',
# StandardEmblemIcons
'emblem-default', 'emblem-documents', 'emblem-downloads', 'emblem-favorite', 'emblem-important',
'emblem-mail', 'emblem-photos', 'emblem-readonly', 'emblem-shared', 'emblem-symbolic-link',
'emblem-synchronized', 'emblem-system', 'emblem-unreadable',
# StandardEmotionIcons
'face-angel', 'face-angry', 'face-cool', 'face-crying', 'face-devilish', 'face-embarrassed',
'face-kiss', 'face-laugh', 'face-monkey', 'face-plain', 'face-raspberry', 'face-sad',
'face-sick', 'face-smile', 'face-smile-big', 'face-smirk', 'face-surprise', 'face-tired',
'face-uncertain', 'face-wink', 'face-worried',
# StandardInternationalIcons
'flag-aa',
# StandardMIMETypeIcons
'application-x-executable', 'audio-x-generic', 'font-x-generic', 'image-x-generic',
'package-x-generic', 'text-html', 'text-x-generic', 'text-x-generic-template', 'text-x-script',
'video-x-generic', 'x-office-address-book', 'x-office-calendar', 'x-office-document',
'x-office-presentation', 'x-office-spreadsheet',
# StandardPlaceIcons
'folder', 'folder-remote', 'network-server', 'network-workgroup', 'start-here', 'user-bookmarks',
'user-desktop', 'user-home', 'user-trash',
# StandardStatusIcons
'appointment-missed', 'appointment-soon', 'audio-volume-high', 'audio-volume-low',
'audio-volume-medium', 'audio-volume-muted', 'battery-caution', 'battery-low', 'dialog-error',
'dialog-information', 'dialog-password', 'dialog-question', 'dialog-warning', 'folder-drag-accept',
'folder-open', 'folder-visiting', 'image-loading', 'image-missing', 'mail-attachment',
'mail-unread', 'mail-read', 'mail-replied', 'mail-signed', 'mail-signed-verified',
'media-playlist-repeat', 'media-playlist-shuffle', 'network-error', 'network-idle',
'network-offline', 'network-receive', 'network-transmit', 'network-transmit-receive',
'printer-error', 'printer-printing', 'security-high', 'security-medium', 'security-low',
'software-update-available', 'software-update-urgent', 'sync-error', 'sync-synchronizing',
'task-due', 'task-past-due', 'user-available', 'user-away', 'user-idle', 'user-offline',
'user-trash-full', 'weather-clear', 'weather-clear-night', 'weather-few-clouds',
'weather-few-clouds-night', 'weather-fog', 'weather-overcast', 'weather-severe-alert',
'weather-showers', 'weather-showers-scattered', 'weather-snow', 'weather-storm'
}
