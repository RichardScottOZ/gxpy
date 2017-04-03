import os
import atexit
from math import ceil

import geosoft
import geosoft.gxapi as gxapi
from . import gx as gx
from . import utility as gxu
from . import dataframe as gxdf
from . import view as gxvw
from . import mapplot as mapl

__version__ = geosoft.__version__

def _t(s):
    return s

class MapException(Exception):
    """
    Exceptions from this module.

    .. versionadded:: 9.2
    """
    pass

WRITE_NEW = 1
WRITE_OLD = 2

LIST_ALL = gxapi.MAP_LIST_MODE_ALL
LIST_3D = gxapi.MAP_LIST_MODE_3D
LIST_2D = gxapi.MAP_LIST_MODE_NOT3D

VIEW_NAME_SIZE = 2080

# 2D map reference points
REF_BOTTOM_LEFT = 1
REF_BOTTOM_CENTER = 2
REF_BOTTOM_RIGHT = 3
REF_CENTER_LEFT = 4
REF_MAP_CENTER = 5
REF_CENTER_RIGHT = 6
REF_TOP_LEFT = 7
REF_TOP_CENTER = 8
REF_TOP_RIGHT = 9
REF_DATA_ORIGIN = 10
REF_DATA_BOTTOM_LEFT = 11
REF_DATA_BOTTOM_CENTER = 12
REF_DATA_BOTTOM_RIGHT = 13
REF_DATA_CENTER_LEFT = 14
REF_DATA_MAP_CENTER = 15
REF_DATA_CENTER_RIGHT = 16
REF_DATA_TOP_LEFT = 17
REF_DATA_TOP_CENTER = 18
REF_DATA_TOP_RIGHT = 19

TEXT_BOTTOM_LEFT = -1
TEXT_BOTTOM_CENTER = 0
TEXT_BOTTOM_RIGHT = 1
TEXT_ALL_CENTER = 2
TEXT_BASE_LEFT= 3
TEXT_BASE_CENTER = 4
TEXT_BASE_RIGHT = 5
TEXT_BASE_ALL_CENTER = 6
TEXT_BASE_FIT_BY_CHARACTER_WIDTH = 7
TEXT_BASE_FIT_BY_CHARACTER_SIZE = 8

MAP_LANDSCAPE = 0
MAP_PORTRAIT = 1

def map_file_name(filename):
    """
    Return a fully resolved map file path using the filename, with .map extyension

    :param filename:    file name, with ot without path and/or extension
    :return:            file name path with extension .map

    .. versionadded:: 9.2
    """
    if os.path.splitext(filename)[1].lower() != '.map':
        filename += '.map'
    return os.path.abspath(filename)

def delete_files(filename):
    """
    Delete all files associates with this map name.
    :param filename:

    .. versionadded:: 9.2
    """

    def remove(fn):
        try:
            os.remove(fn)
        except FileNotFoundError:
            pass

    filename = map_file_name(filename)
    remove(filename + '.xml')
    remove(os.path.splitext(filename)[0] + '.mdf')
    remove(filename)

def save_as_image(mapfile, imagefile, type="PNG", pix_width=1000, pix_height=0):
    """
    Save a map to an image file
    :param mapfile:     mapfile name
    :param imagefile:   name of the output raster file
    :param type:        one of type list below
    :param pix_width:   image pixel width, if 0 use pix_height only
    :param pix_height:  image pixel height, if 0 use pix_width only
    :return:

    .. versionadded:: 9.2
    """

    with GXmap.open(mapfile) as g:
        g.gxmap.export_all_raster(imagefile, '',
                                  pix_width, pix_height, gxapi.rDUMMY,
                                  gxapi.MAP_EXPORT_BITS_24,
                                  gxapi.MAP_EXPORT_METHOD_NONE,
                                  type, '')

def crc_map(mapfile, pix_width=1000):
    """
    Return the CRC of a map based on the output bitmap image.
    :param mapfile:     name of the map file
    :param pix_width:   image pixel width - use a higher resolution to test more detail
    :return:            CRC as an int

    .. versionadded:: 9.2
    """
    crc_image = os.path.join(gx.GXpy().temp_folder(), "__crc_image__.bmp")
    save_as_image(mapfile, crc_image, type='BMP', pix_width=pix_width)
    crc = gxu.crc32_file(crc_image)
    os.remove(crc_image)
    try:
        os.remove(crc_image + '.gi')
        os.remove(crc_image + '.xml')
    except FileNotFoundError:
        pass
    return crc

class GXmap:
    """
    Geosoft map files.

    A Geosoft map is a container for views.  A view has a defined coordinate system (2D or 3D) and
    contains graphical elements defined relative to the coordinate system of the view.  The
    ``geosoft.gxpy.view`` module provides classes and methods for working with individual 2D or
     3D views.

    Geosoft maps will always have a 2D 'base' view, which uses map cm as the coordinate system and is
    intended for drawing map annotations, such as titles, a scale bar, North arrow and legends.  The
    lower-left corner of the base view at location (0, 0) and the upper-right corner is defined by the
    media size and may be adjusted to fit the data view.

    Geosoft maps will also have one or more data views, each with it's own defined coordinate system
    and graphical content.  Creating a new map will create one data view, which will become the map's 
    ``current_data_view``, within which any spatial data drawn by Geosoft 2D drawing applications
    will be placed.  Maps may have more than one data view, including 3D data views, and the 
    ``current_data_view`` can be changed to any 2D or 3D view, and subsequent drawing will be placed
    in that view.

    3D views define a 3D spatial volume and accept both 2D and 3D drawing elements.  A 3D view will always
    contain a plane or surface on which 2D elements are drawn, and when a 3D view is the
    `default data view`, 2D elements will be drawn to the identified plane or surface.  When a 3D view is
    rendered on a map, which is a flat surface, the view is rendered from the last use point of view.  Geosoft
    map viewing applications allow a user to open a 3D view in a 3D viewer, which provides for 3D viewing,
    3D navigation and 3D drawing capabilities.

    Map constructors:

        ======== =============================
        `open()` open an existing map
        `new()`  create a new map
        ======== =============================

    .. versionadded:: 9.2
    """

    def __enter__(self):
        return self

    def __exit__(self, xtype, xvalue, xtraceback):
        self._close()

    def __repr__(self):
        return "{}({})".format(self.__class__, self.__dict__)

    def __str__(self):
        return self._filename

    def __init__(self, filename, mode=WRITE_NEW):

        self.gxmap = None
        self._remove = False
        self._filename = map_file_name(filename)
        self.gxmap = gxapi.GXMAP.create(self.filename, mode)

        atexit.register(self._close, pop=False)
        self._open = gx.track_resource(self.__class__.__name__, self._filename)

    def _close(self, pop=True):
        if self._open:
            if self.gxmap:

                if not self._remove:
                    pass
                    #self.gxmap.clean()

                self.gxmap = None

                if self._remove:
                    try:
                        delete_files(self._filename)
                    except OSError:  # remove if we can
                        pass
            if pop:
                gx.pop_resource(self._open)
            self._open = None

    @classmethod
    def open(cls, filename):
        """
        Open an existing map file.

        :param filename:    name of the map file

        .. versionadded:: 9.2
        """

        gmap = cls(filename, mode=WRITE_OLD)

        return gmap

    @classmethod
    def new(cls, filename=None, data_area=(0.,0.,100.,100.), scale=None,
            cs=None, media=None, layout=None, fixed_size=None, map_style='figure',
            margins=None, inside_margin=1.0, overwrite=False):

        """
        Create and open a new Geosoft map.

        :parameters:
            :filename:      Map file name.  If not specified a temporary file is created in the instance
                            temporary folder.  Use ``filename()`` to get the file name if needed.  The 
                            temporary map file will be unique and will exist through the life of the
                            Python GX instance, but will be deleted along with all temporary files
                            when the GX loses context.
            :data_area:     (min_x, min_y, max_x, max_y) data area for a 2D data view on the map
            :scale:         required scale, default will fit data to the map media
            :cs:            coordinate system, default is an unknown coordinate system.  You may pass
                            a ``coordinate_system.GXcs`` instance, a string descriptor, such as
                            `WGS 84 / UTM zone 15N`, or another valid constructor supported by
                            ``coordinate_system.GXcs``.
            :media:         media size as a tuple(x_cm, y_cm), or as a standard media name string.
                            If the media name contains 'portrait', the media is media aspect will be portrait.
                            Named media sizes are read from media.csv, which includes A4, A3, A2, A1, A0, 
                            letter, legal, ledger, A, B, C, D, E. For example `media='A4 portrait'`.
            :layout:        MAP_PORTRAIT or MAP_LANDSCAPE, overrides media setting.  If the layout is not 
                            defined by media or this parameter, the layout is determined by the aspect
                            ratio of the data area.
            :map_style:     'map' or 'figure' (default).  A 'map' style is intended for A3 or larger
                            media with a larger right or left margin for map annotations.  A 'figure'
                            style is intended for smaller media with a larger bottom margin for a
                            title and limited annotations.
            :fixed_size:    True for fixed media size, if, and only if, a media size is defined.
                            The default is True for 'figure' map_style, and False for 'map' map_style. 
                            If False, the base view boundary will be reduced to the data view plus margins.  
                            Tf True, the base view boundary is fixed to the media size and margins are 
                            adjusted to locate the data view proportionally relative to the requested margins.
            :margins:       (left, right, bottom, top) map margins in map cm.  The default for 'map'
                            style is (3, 14, 6, 3), and for figure (1, 4, 1, 1).
            :inside_margin: additional margin (cm) inside the base view.  This margin effectively
                            expands the data_area to allow room for graphical elements related to
                            spatial data near the edge of the defined data area.
            :overwrite:     True to overwrite an existing map.  If False and map exists, raises
                            ``MapException``.

        .. versionadded:: 9.2
        """

        def data_window_on_map():
            mx = media[0] - m_left - m_right
            my = media[1] - m_bottom - m_top
            im = inside_margin * 2
            return mx - im, my - im  # data window on map cm

        def set_coordinate_system(gmap, cs):
            with gxvw.GXview(gmap=gmap, viewname='data', mode=gxvw.WRITE_OLD) as view:
                view.set_cs(cs)

        def set_registry(gmap, style, inside_margin):
            rd = {'MAP.STYLE': style,
                  'MAP.MARGIN_INSIDE': str(inside_margin),
                  'MAP.UP_DIRECTION': 'right',
                  'MAP.UP_ANGLE': '67.5'}
            gmap.gxmap.set_reg(gxu.reg_from_dict(rd))

        if ((data_area[2] - data_area[0]) <= 0.0) or ((data_area[3] - data_area[1]) <= 0.0):
            raise MapException(_t('Invalid data area {}'.format(data_area)))

        if layout is None:
            if (data_area[2] - data_area[0]) < (data_area[3] - data_area[1]):
                layout = MAP_PORTRAIT
            else:
                layout = MAP_LANDSCAPE

        if filename is None:

            # get a new temporary map file name
            tempname = "temp_map"
            i = 0
            while True:
                filename = map_file_name(os.path.join(gx.GXpy().temp_folder(), tempname + str(i) + '.map'))
                if not os.path.isfile(filename):
                    break
                i += 1

        else:
            if not overwrite:
                filename = map_file_name(filename)
                if os.path.isfile(filename):
                    raise MapException(_t('Cannot overwrite existing file: "{}"').format(filename))

        gmap = cls(filename, WRITE_NEW)

        if type(media) is str:
            try:
                spec = gxdf.table_record('media', media.upper())
                media = (float(spec['SIZE_X']), float(spec['SIZE_Y']))
            except:
                media = None
                fixed_size = False

        if media is None:
            fixed_size = False
            if scale:
                media = (5000., 4000.)  # crazy large, will be trimmed to scale
                if margins is None:
                    if map_style == 'map':
                        margins = (1.5, 14.0, 5.0, 1.5)
                    else:
                        margins = (1.0, 1.0, 4.0, 1.0)
            else:
                media = (50., 40.)

        if (layout == MAP_PORTRAIT) and (media[0] > media[1]):
            media = (media[1], media[0])

        if margins:
            m_left, m_right, m_bottom, m_top = margins

        else:
            mx, my = media
            if map_style == 'map':
                if mx <= 30.0:
                    raise MapException('\'map\' style requires minimum 30cm media. Yours is {}cm'.format(mx))
                m_left = max(1.5, mx * 0.025)
                m_right = max(14.0, mx * 0.15)
                m_bottom = max(5.0, my * 0.1)
                m_top = max(1.5, my * 0.025)
            else:
                m_left = max(1.0, mx * 0.04)
                m_right = max(1.0, mx * 0.04)
                m_bottom = max(4.0, my * 0.15)
                m_top = max(1.0, my * 0.04)

        if scale is None:
            # determine largest scale to fit the media
            mx, my = data_window_on_map()
            sx = (data_area[2] - data_area[0]) * 100.0 / mx
            sy = (data_area[3] - data_area[1]) * 100.0 / my
            scale = max(sx, sy)

            # TODO - add a round_to_precision() function with option to round up or down.
            if scale > 100:
                scale = float(ceil(scale))

        if fixed_size is None:
            if map_style == 'figure':
                fixed_size = True
            else:
                fixed_size = False

        if fixed_size:
            mx, my = data_window_on_map()
            x_adjust = max(0., (mx - ((data_area[2] - data_area[0]) * 100.0 / scale)) * 0.5)
            y_adjust = max(0., (my - ((data_area[3] - data_area[1]) * 100.0 / scale)) * 0.5)
            m_left += x_adjust
            m_right += x_adjust
            m_bottom += y_adjust
            m_top += y_adjust

        # ensure the data fits on this media
        mx, my = data_window_on_map()
        dmx = (data_area[2] - data_area[0]) * 100.0 / scale
        dmy = (data_area[3] - data_area[1]) * 100.0 / scale
        if (mx - dmx) < -0.01 or (my - dmy) < -0.01:
            raise MapException(_t('The data does not fit media ({},{})cm at a scale of 1:{}')
                               .format(media[0], media[1], scale))

        gxapi.GXMVU.mapset(gmap.gxmap,
                           'base', 'data',
                           data_area[0], data_area[2],
                           data_area[1], data_area[3],
                           '{},{}'.format(media[0] + 50.0, media[1] + 50.0), layout,
                           0, scale, gxapi.rDUMMY,
                           m_left, m_right, m_bottom, m_top,
                           float(inside_margin))

        set_coordinate_system(gmap, cs)
        set_registry(gmap, map_style, inside_margin)

        return gmap

    @property
    def filename(self):
        """
        Full map file path name.
        """
        return self._filename

    @property
    def current_data_view(self):
        """ The current default data view which accepts drawing commands from Geosoft methods."""
        return self.get_class_view_name('data')

    @current_data_view.setter
    def current_data_view(self, s):
        if not self.has_view(s):
            raise MapException(_t('Map does not contain a view named "{}"').format(s))
        self.gxmap.set_class_name('data', s)

    @property
    def current_base_view(self):
        """ The current default base view which accepts drawing commands from Geosoft methods."""
        return self.get_class_view_name('base')

    @current_base_view.setter
    def current_base_view(self, s):
        if not self.has_view(s):
            raise MapException(_t('Map does not contain a view named "{}"').format(s))
        self.gxmap.set_class_name('base', s)

    @property
    def current_section_view(self):
        """ The current default base view which accepts drawing commands from Geosoft methods."""
        return self.get_class_view_name('section')

    @current_section_view.setter
    def current_section_view(self, s):
        if not self.has_view(s):
            raise MapException(_t('Map does not contain a view named "{}"').format(s))
        self.gxmap.set_class_name('section', s)

    def close(self):
        """ Close the map and release resources. """
        self._close()

    def remove_on_close(self, remove=True):
        """
        :param remove:  if True (the default), remove the map file when finished.
        """
        self._remove = remove

    def commit_changes(self):
        """Commit changes to the map."""
        self.gxmap.commit()

    def _classview(self, name):
        if name[0] != '*':
            return name
        return self.get_class_view_name(name[1:])

    def view_list(self, view_type=LIST_ALL):
        """
        Return dictionary of view names.
        :param view_type: `gxmap.LIST_ALL`, `gxapi.LIST_2D` or `gxapi.LIST_3D`
        :return: list of views
        """
        gxlst = gxapi.GXLST.create(VIEW_NAME_SIZE)
        self.gxmap.view_list_ex(gxlst, view_type)
        return list(gxu.dict_from_lst(gxlst))

    def has_view(self, view):
        """ Returns True if the map contains this view."""
        return self.gxmap.exist_view(self._classview(view))

    def copy_view(self, old, new, overwrite=False, copy_all=True):
        """
        Copy an existing view into a new view.
        
        :param old:         name of the existing view
        :param new:         name for the new view
        :param overwrite:   True to overwrite an existing view if it exists
        :param copy_all:    True to copy content of old to new, false to create an empty new view
                            with the same coordinate system, scale and clipping as the old view.
        """

        old = self._classview(old)
        new = self._classview(new)

        if not self.has_view(old):
            raise MapException(_t('"{}" view does not exist.').format(old))
        if self.has_view(new):
            if overwrite:
                self.gxmap.delete_view(new)
            else:
                raise MapException(_t('Cannot overwtite existing view "{}"').format(new))

        s = gxapi.str_ref()
        s.value = new

        self.gxmap.duplicate_view(old, s, copy_all)

        if s.value != new:
            self.gxmap.delete_view(new)
            raise MapException(_t('Invalud view name "{}", suggest "{}"').format(new, s.value ))

    def delete_view(self, viewname):
        """
        Delete a view from a map. You cannot delete the last view in a mep.
        
        :param viewname: name of the view to delete
        
        .. versionadded:: 9.2
        """
        self.gxmap.delete_view(self._classview(viewname))

    def mdf(self):
        """
        Returns the Map Description File specification for maps that contain
        both a base view and a data view.

        ((x_size, y_size, margin_bottom, margin_right, margin_top, margin_left),
         (scale, units_per_metre, x_origin, y_origin))\

        .. versionadded: 9.2
        """

        views = self.view_list()

        if not(self.has_view(self.current_data_view) and self.has_view(self.current_base_view)):
            raise MapException('The map must have both a base view and a data view.')

        xmn = gxapi.float_ref()
        ymn = gxapi.float_ref()
        xmx = gxapi.float_ref()
        ymx = gxapi.float_ref()

        with gxvw.GXview(self, self.current_base_view, gxvw.READ_ONLY) as v:
            v.gxview.extent(gxapi.MVIEW_EXTENT_CLIP, gxapi.MVIEW_EXTENT_UNIT_MM,
                            xmn, ymn, xmx, ymx)
            mapx = (xmx.value - xmn.value) * 0.1
            mapy = (ymx.value - ymn.value) * 0.1

        with gxvw.GXview(self, self.current_data_view, gxvw.READ_ONLY) as v:
            v.gxview.extent(gxapi.MVIEW_EXTENT_CLIP, gxapi.MVIEW_EXTENT_UNIT_MM,
                            xmn, ymn, xmx, ymx)
            view_map = (xmn.value * 0.1,
                        ymn.value * 0.1,
                        xmx.value * 0.1,
                        ymx.value * 0.1)

            v.gxview.extent(gxapi.MVIEW_EXTENT_CLIP, gxapi.MVIEW_EXTENT_UNIT_VIEW,
                            xmn, ymn, xmx, ymx)
            view_view = (xmn.value, ymn.value, xmx.value, ymx.value)

        m1 = (mapx, mapy, view_map[1], mapx - view_map[2], mapy - view_map[3], view_map[0])
        sc = (view_view[2] - view_view[0]) / ((view_map[2] - view_map[0]) / 100.0)
        ufac = 1.0
        x0 = view_view[0]
        y0 = view_view[1]
        m2 = (sc, ufac, x0, y0)

        return m1, m2

    def get_class_view_name(self, view_class):
        """
        Get the view name associated with a class.

        :param view_class:  desired class

        Common view class names are::

            'Base'      the base map/figure view, uses map cm
            'Data'      the default data view for drawing spatial data.
            'Section'   the default section view for things drawn in section

        Other class names may be defined, though they are not used by Geosoft.

        :return: view name associated with the class, '' if not defined.

        .. versionadded:: 9.2
        """
        sr = gxapi.str_ref()
        self.gxmap.get_class_name(view_class, sr)
        return sr.value.lower()

    def set_class_view_name(self, view_class, view_name):
        """
        Set the view name associated with a class.

        :param view_class:  class name
        :param view_name:   name of the view associated with this class.

        Common view class names are::

            'Base'      the base map/figure view, uses map cm
            'Data'      the default data view for drawing spatial data.
            'Section'   the default section view for things drawn in section

        .. versionadded:: 9.2
        """
        self.gxmap.set_class_name(view_class, view_name)

    def map_reference_location(self, refp, viewname='base'):
        """
        Return the location of a reference point relative to the current clipping window
        extent of a view on the map.
        
        :param refp: One of:
        
            ::
            
                REF_BOTTOM_LEFT = 1
                REF_BOTTOM_CENTER = 2
                REF_BOTTOM_RIGHT = 3
                REF_CENTER_LEFT = 4
                REF_VIEW_CENTER = 5
                REF_CENTER_RIGHT = 6
                REF_TOP_LEFT = 7
                REF_TOP_CENTER = 8
                REF_TOP_RIGHT = 9
                
        :param viewname:    the name of the view, default is the base view which returns the
                            extent in map cm.

        :return:    (x, y) in view units
        
        .. versionadded:: 9.2
        """

        viewname = self._classview(viewname)

        if not viewname:
            with gxvw.GXview(self, self.current_base_view) as v:
                extent = v.extent_map_cm
        else:
            with gxvw.GXview(self, viewname) as v:
                extent = v.extent

        xc = extent[0] + (extent[2] - extent[0]) * 0.5
        yc = extent[1] + (extent[3] - extent[1]) * 0.5
        rpoints = ((extent[0], extent[1]),
                   (xc, extent[1]),
                   (extent[2], extent[1]),
                   (extent[0], yc),
                   (xc, yc),
                   (extent[2], yc),
                   (extent[0], extent[3]),
                   (xc, extent[3]),
                   (extent[2], extent[3]))

        return rpoints[refp - 1]

    def surround(self, outer_pen='kt250', inner_pen='kt1', gap=0):
        """
        Draw a map surround.  This will draw a single or a double neat-line around the base view of the
        map.
        
        :param outer_pen:   outer-line pen attributes
        :param inner_pen:   inner-line pen attributes
        :param gap:         gap between the outer and inner line in cm.  If 0, only the outer line is drawn.
         
        .. versionadded:: 9.2
        """

        with mapl.GXmapplot(self) as mpl:

            mpl.start_group('north_arrow', view=mapl.VIEW_BASE, mode=mapl.GROUP_APPEND)

            mpl.define_named_attribute('outer', pen_def=outer_pen)
            if gap <= 0:
                inner = ''
                gap = ''
            else:
                inner = 'inner'
                mpl.define_named_attribute(inner, pen_def=inner_pen)

            mpl.command('SURR "{}",{},"{}"'.format('outer', gap, inner))

    def north_arrow(self,
                    location=(1, 2., 2.7),
                    direction=None,
                    length=3,
                    inclination=None,
                    declination=None,
                    text=(0.25, 15),
                    pen='kt200'):
        """
        Add a North arrow to the base view of the map.

        :param location:    (reference, x_offset, y_offset) reference is a reference point relative to the
                            base map extents (1 through 9) nd the offsets are the offset from that reference
                            point in cm.
        :param direction:   North direction in degrees azimuth (clockwise from map Y axis).  The efault is 
                            calculated direction of North at the center of the data view.
        :param length:      arrow length in cm
        :param inclination: magnetic inclination, not shown if not specified
        :param declination: magnetic declination, not shown if not specified
        :param text:        (height_cm, slant_deg) text height and slant.
        :param pen:         pen descriptor string, eg. 'kt200'.

        .. versionadded:: 9.2
        """

        #TODO add IGRF calculation from a date, igrfdate=

        if direction is None:
            with gxvw.GXview(self, '*data', mode=gxvw.WRITE_OLD) as v:
                direction = round(v.gxview.north(), 1)
                if direction == gxapi.rDUMMY:
                    direction = ''

        if inclination is None:
            inclination = ''

        if declination is None:
            declination = ''

        with mapl.GXmapplot(self) as mpl:
            mpl.start_group('north_arrow', view=mapl.VIEW_BASE, mode=mapl.GROUP_APPEND)
            mpl.define_named_attribute('arrow', pen_def=pen)
            mpl.define_named_attribute('annot', text_def=text, pen_def='kt50')
            mpl.command("NARR {},{},{},{},{},{},{},{}".format(location[0], location[1], location[2],
                                                              direction,
                                                              length,
                                                              'arrow',
                                                              inclination,
                                                              declination))
            mpl.command('     annot')

    def scale_bar(self,
                  length=5,
                  sections=None,
                  post_scale=False,
                  ref_point=(1, 5, 2),
                  text=(0.25, 15),
                  pen='kt50'):
        """

        :param length:      maximum scale bar length, default is 5 cm. scale=0.0 will suppress drawing of the bar.
        :param sections:    number of major sections in the bar, default is determined automatically.
        :param post_scale:  True to post the actual scale as a string, e.g. '1:50,000'.  Note that a posted
                            scale is only relevant for printed maps.  The default does not post the scale.
        :param text:        (height_cm, slant_deg) text height and slant.
        :param pen:         pen descriptor string, eg. 'kt200'.


        .. versionadded:: 9.2
        """

        if sections is None:
            sections = ''

        if post_scale:
            option = 2
        else:
            option = 1

        with mapl.GXmapplot(self) as mpl:
            mpl.start_group('scale_bar', view=mapl.VIEW_BASE, mode=mapl.GROUP_APPEND)
            att = 'scale_bar'
            mpl.define_named_attribute(att, ref_point=ref_point, pen_def=pen, text_def=text)
            mpl.command("SCAL {},{},{},,,{},{},,{},".format(ref_point[0], ref_point[1], ref_point[2],
                                                            length, sections, option))
            mpl.command('     {}'.format(att))
