
from _functools import partial
from builtins import isinstance
from collections import namedtuple, OrderedDict
from itertools import product
from locale import gettext as _
import time

from gi.repository import Gtk, Gdk, GObject

from gtk_greeter_settings import IndicatorChooserDialog


__all__ = ['BaseEntry', 'BooleanEntry', 'StringEntry', 'ClockFormatEntry',
           'BackgroundEntry', 'IconEntry', 'IndicatorsEntry', 'PositionEntry']


class SignalBlocker:
    def __init__(self, widget, handler):
        if hasattr(handler, '__call__'):
            self._block = partial(widget.handler_block_by_func, handler)
            self._unblock = partial(widget.handler_unblock_by_func, handler)
        elif isinstance(handler, int):
            self._block = partial(widget.handler_block, handler)
            self._unblock = partial(widget.handler_unblock, handler)
        else:
            self._block = None
            self._unblock = None

    def __enter__(self):
        if self._block:
            self._block()
        return self

    def __exit__(self, *args):
        if self._unblock:
            self._unblock()
        return False


class BaseEntry:

    @property
    def value(self):
        return self._get_value()

    @value.setter
    def value(self, value):
        return self._set_value(value)

    def __repr__(self):
        try:
            value = self._get_value()
        except NotImplemented:
            value = '<Undefined>'
        return '%s(%s)' % (self.__class__.__name__, value)

    def _get_value(self):
        raise NotImplementedError(self.__class__)

    def _set_value(self, value):
        raise NotImplementedError(self.__class__)


class BooleanEntry(BaseEntry):

    def __init__(self, widgets):
        self._widget = widgets['value']

    def _get_value(self):
        return 'true' if self._widget.props.active else 'false'

    def _set_value(self, value):
        self._widget.props.active = value and value.lower() not in ('false', 'no', '0')


class StringEntry(BaseEntry):

    def __init__(self, widgets):
        self._widget = widgets['value']
        if isinstance(self._widget, Gtk.ComboBoxText):
            self._widget = self._widget.get_child()

    def _get_value(self):
        return self._widget.props.text

    def _set_value(self, value):
        self._widget.props.text = value or ''


class ClockFormatEntry(StringEntry):

    def __init__(self, widgets):
        super().__init__(widgets)
        self._preview = widgets['preview']
        self._widget.connect('changed', self._on_changed)
        GObject.timeout_add_seconds(1, self._on_changed, self._widget)

    def _on_changed(self, entry):
        self._preview.props.label = time.strftime(self._widget.props.text)
        return True


class BackgroundEntry(BaseEntry):

    def __init__(self, widgets):
        self._image_choice = widgets['image_choice']
        self._color_choice = widgets['color_choice']
        self._image_value = widgets['image_value']
        self._color_value = widgets['color_value']

    def _get_value(self):
        if self._image_choice.props.active:
            return self._image_value.get_filename()
        else:
            return self._color_value.props.color.to_string()

    def _set_value(self, value):
        if value is None:
            value = ''

        color = Gdk.color_parse(value)

        self._color_choice.props.active = color is not None
        self._image_choice.props.active = color is None

        if color is not  None:
            self._color_value.props.color = color
            self._image_value.unselect_all()
        else:
            if value:
                self._image_value.select_filename(value)
            else:
                self._image_value.unselect_all()


class FontEntry(BaseEntry):

    def __init__(self, widgets):
        self._widget = widgets['value']

    def _get_value(self):
        return self._widget.get_font_name()

    def _set_value(self, value):
        self._widget.props.font_name = value or ''


class IconEntry(BaseEntry):

    def __init__(self, widgets):
        self._image = widgets['image']
        self._button = widgets['button']

    def _get_value(self):
        pass

    def _set_value(self, value):
        pass


class IndicatorsEntry(BaseEntry):
    NAMES_DELIMITER = ';'
    # It's the only one place where model columns order defined
    ModelRow = namedtuple('ModelRow', ('enabled', 'name', 'builtin', 'external'))

    def __init__(self, widgets):
        self._use = widgets['use']
        self._toolbar = widgets['toolbar']
        self._treeview = widgets['treeview']
        self._treeview_render_state = widgets['render_state']
        self._treeview_selection = self._treeview.get_selection()
        self._add = widgets['add']
        self._remove = widgets['remove']
        self._up = widgets['up']
        self._down = widgets['down']
        self._model = widgets['model']

        self._initial_items = OrderedDict((item.name, item)
                                          for item in map(self.ModelRow._make, self._model))
        self._indicators_dialog = None

        self._treeview.connect("key-press-event", self._on_key_press)
        self._treeview_render_state.connect("toggled", self._on_state_toggled)
        self._treeview_selection.connect("changed", self._on_selection_changed)
        self._add.connect("clicked", self._on_add)
        self._remove.connect("clicked", self._on_remove)
        self._up.connect("clicked", self._on_up)
        self._down.connect("clicked", self._on_down)
        self._use.connect("notify::active", self._on_use_toggled)

    def _get_value(self):
        if self._use.props.active:
            return self.NAMES_DELIMITER.join(item.name for item in map(self.ModelRow._make, self._model)
                                             if (item.builtin and item.enabled) or item.external)
        else:
            return None

    def _set_value(self, value):
        with SignalBlocker(self._use, self._on_use_toggled):
            self._use.set_active(value is not None)

        self._model.clear()
        last_options = self._initial_items.copy()
        if value:
            for name in value.split(self.NAMES_DELIMITER):
                try:
                    self._model.append(last_options.pop(name)._replace(enabled=True))
                except KeyError:
                    self._model.append(self.ModelRow(name=name, external=True,
                                                     builtin=False, enabled=False))
        for i in last_options.values():
            self._model.append(i)

        self._toolbar.props.sensitive = value is not None
        self._treeview.props.sensitive = value is not None

        self._treeview_selection.select_path(0)

    def _remove_selection(self):
        model, rowiter = self._treeview_selection.get_selected()
        if rowiter:
            previter = model.iter_previous(rowiter)
            model.remove(rowiter)
            if previter:
                self._treeview_selection.select_iter(previter)

    def _move_selection(self, move_up):
        model, rowiter = self._treeview_selection.get_selected()
        if rowiter:
            if move_up:
                model.swap(rowiter, model.iter_previous(rowiter))
            else:
                model.swap(rowiter, model.iter_next(rowiter))
            self._on_selection_changed(self._treeview_selection)

    def _add_indicator(self, name):
        if name:
            rowiter = self._model.append(self.ModelRow(name=name, external=True,
                                                       builtin=False, enabled=False))
            self._treeview_selection.select_iter(rowiter)

    def _on_key_press(self, treeview, event):
        if Gdk.keyval_name(event.keyval) == 'Delete':
            self._remove_selection()
            return True
        return False

    def _on_state_toggled(self, toggle, path):
        item = self.ModelRow._make(self._model[path])
        self._model[path] = item._replace(enabled=not item.enabled)

    def _on_use_toggled(self, *args):
        if self._use.props.active:
            self._set_value([])
        else:
            self._set_value(None)

    def _on_selection_changed(self, selection):
        model, rowiter = selection.get_selected()
        self._remove.props.sensitive = (rowiter is not None) and self.ModelRow._make(model[rowiter]).external
        self._down.props.sensitive = (rowiter is not None) and model.iter_next(rowiter) is not None
        self._up.props.sensitive = (rowiter is not None) and model.iter_previous(rowiter) is not None
        if rowiter is not None:
            self._treeview.scroll_to_cell(model.get_path(rowiter))

    def _on_add(self, *args):
        if not self._indicators_dialog:
            self._indicators_dialog = IndicatorChooserDialog.IndicatorChooserDialog()
        name = self._indicators_dialog.get_indicator(self._add_indicator)
        if name:
            self._add_indicator(name)

    def _on_remove(self, *args):
        self._remove_selection()

    def _on_up(self, *args):
        self._move_selection(move_up=True)

    def _on_down(self, *args):
        self._move_selection(move_up=False)


class PositionEntry(BaseEntry):

    class Dimension:
        def __init__(self, name, widgets, anchors, on_changed):
            self.__dict__.update(('_%s' % w, widgets['%s_%s' % (name, w)])
                                  for w in ('value', 'percents', 'mirror', 'adjustment'))
            self._name = name
            self._on_changed = on_changed
            self._anchor = ''

            self._percents.connect('toggled', self._on_percents_toggled)
            self._mirror.connect('toggled', self._on_mirror_toggled)
            self._adjustment.connect('value-changed', self._on_value_changed)

            for (x, y), widget  in anchors.items():
                widget.connect('toggled', self._on_anchor_toggled, self,
                               x if self._name == 'x' else y)

        @property
        def value(self):
            return '%s%d%s,%s' % ('-' if self._mirror.props.active else '',
                                  int(self._value.props.value),
                                  '%' if self._percents.props.active else '',
                                  'start' if self._name == 'x' else 'end')

        @value.setter
        def value(self, dim_value):
            value, _, anchor = dim_value.partition(',')

            percents = value and value[-1] == '%'
            if percents:
                value = value[:-1]

            try:
                p = int(value)
            except ValueError:
                p = 0

            negative = (p < 0) or (p == 0 and value and value[0] == '-')

            if not anchor or anchor not in ('start', 'center', 'end'):
                if negative:
                    anchor = 'end'
                else:
                    anchor = 'start'
            self._anchor = anchor

            with SignalBlocker(self._percents, self._on_percents_toggled):
                self._percents.props.active = percents
                self._adjustment.props.upper = 100 if self._percents.props.active else 10000
            with SignalBlocker(self._mirror, self._on_mirror_toggled):
                self._mirror.props.active = negative
            with SignalBlocker(self._adjustment, self._on_value_changed):
                self._adjustment.props.value = -p if negative else p

        @property
        def anchor(self):
            return self._anchor

        def get_scaled_position(self, screen, window, scale):
            screen_size = screen[0] if self._name == 'x' else screen[1]
            window_size = window[0] if self._name == 'x' else window[1]

            p = int(self._adjustment.props.value)
            if self._percents.props.active:
                p = screen_size * p / 100
            else:
                p *= scale

            if self._mirror.props.active:
                p = screen_size - p

            if self._anchor == 'center':
                p -= window_size / 2
            elif self._anchor == 'end':
                p -= window_size

            p = int(p)

            if p + window_size > screen_size:
                p = screen_size - window_size
            if p < 0:
                p = 0

            return p

        def _on_value_changed(self, widget):
            self._on_changed(self)

        def _on_percents_toggled(self, toggle):
            self._adjustment.props.upper = 100 if toggle.props.active else 10000
            self._on_changed(self)

        def _on_mirror_toggled(self, toggle):
            self._on_changed(self)

        def _on_anchor_toggled(self, toggle, dimension, anchor):
            if dimension == self and toggle.props.active and anchor != self._anchor:
                self._anchor = anchor
                self._on_changed(self)

    REAL_WINDOW_SIZE = 430, 210

    def __init__(self, widgets):
        self._screen = widgets['screen']
        self._window = widgets['window']
        self._screen_pos = (0, 0)
        self._screen_size = (0, 0)

        self._anchors = {(x, y): widgets['base_%s_%s' % (x, y)]
                         for x, y in product(('start', 'center', 'end'), repeat=2)}

        self._screen.connect('realize', self._on_realize)
        self._screen.connect('size-allocate', self._on_resize)
        self._screen.connect('draw', self._on_draw_screen_border)

        self._x = PositionEntry.Dimension('x', widgets, self._anchors, self._on_dimension_changed)
        self._y = PositionEntry.Dimension('y', widgets, self._anchors, self._on_dimension_changed)

    def _on_draw_screen_border(self, widget, cr):
        width, height = self._screen_size
        x, y = self._screen_pos
        line_width = 2
        width -= line_width
        height -= line_width
        x += line_width / 2
        y += line_width / 2
        cr.set_source_rgba(0.2, 0.1, 0.2, 0.8)
        cr.set_line_width(line_width)

        cr.move_to(x, y)
        cr.line_to(x + width, y)
        cr.line_to(x + width, y + height)
        cr.line_to(x, y + height)
        cr.line_to(x, y - line_width / 2)
        cr.stroke_preserve()

        return False

    def _get_value(self):
        return self._x.value + ' ' + self._y.value

    def _set_value(self, value):
        if value:
            x, _, y = value.partition(' ')
            self._x.value = x
            self._y.value = y or x
            self._anchors[self._x.anchor, self._y.anchor].props.active = True
            self._update_layout()

    def _update_layout(self):
        screen = self._screen.get_toplevel().get_screen()
        geometry = screen.get_monitor_geometry(screen.get_primary_monitor())
        window_allocation = self._window.get_allocation()
        window_size = window_allocation.width, window_allocation.height
        scale = self._screen_size[0] / geometry.width

        x = self._screen_pos[0] + self._x.get_scaled_position(self._screen_size, window_size, scale)
        y = self._screen_pos[1] + self._y.get_scaled_position(self._screen_size, window_size, scale)

        self._screen.move(self._window, x, y)
        self._screen.check_resize()

    def _on_resize(self, widget, allocation):
        screen = self._screen.get_toplevel().get_screen()
        geometry = screen.get_monitor_geometry(screen.get_primary_monitor())
        screen_scale = geometry.height / geometry.width

        width = allocation.width
        height = int(width * screen_scale)

        if height > allocation.height:
            height = allocation.height
            width = min(width, int(height / screen_scale))
        self._screen_pos = int((allocation.width - width) / 2), 0
        self._screen_size = (width, height)
        with SignalBlocker(self._screen, self._on_resize):
            scale = width / geometry.width
            if 1:  # scale > 0.01:
                self._window.set_size_request(PositionEntry.REAL_WINDOW_SIZE[0] * scale,
                                              PositionEntry.REAL_WINDOW_SIZE[1] * scale)
                self._update_layout()

    def _on_realize(self, *args):
        self._update_layout()

    def _on_dimension_changed(self, dimension):
        self._update_layout()
