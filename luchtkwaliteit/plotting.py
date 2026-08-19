from pathlib import Path

import json
import urllib
import urllib.request

import numpy as np
import pandas as pd

import plotly.express as px
import plotly.colors as pc

from luchtkwaliteit import geo


def utrecht_polys():
    """Return all implemented options for mapbox layers."""

    layouts_all = {
        'stad': {
            'polys': {
                'level': 'gemeente_Utrecht',
                'type': 'niet_gegeneraliseerd',
                'color': 'black',
                'width': 2,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
            },
        'wijk': {
            'polys': {
                'level': 'wijk',
                'type': 'niet_gegeneraliseerd',
                'color': 'black',
                'width': 1,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
            },
        'buurt': {
            'polys': {
                'level': 'buurt',
                'type': 'niet_gegeneraliseerd',
                'color': 'black',
                'width': 0.5,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
        },
        'pc4': {
            'polys': {
                'level': 'pc4',
                'type': '',
                'color': 'black',
                'width': 0.5,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
        },
        'pc6': {
            'polys': {
                'level': 'pc6',
                'type': '',
                'color': 'black',
                'width': 0.5,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
        },
        'umizo': {
            'polys': {
                'level': 'umizo',
                'type': '',
                'color': 'red',
                'width': 2,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
        },
        'filepath': {
            'polys': {
                'level': 'umizo',
                'type': '',
                'color': 'red',
                'width': 2,
                'fill': None, # None or 'toself'
                },
            'mapper': None,
        },
    }

    return layouts_all


def get_mapbox_token(fpath=[]):
    """Load the mapbox token."""

    fpath = fpath or [
        '~',
        'OneDrive - Gemeente Utrecht',
        'projects',
        'mapbox_token.txt',
        ]

    p = Path(*fpath).expanduser()

    try:
        token = open(p).read()
    except:
        token = False

    return token


def download_borders_utrecht(directory, year, level,
                             gentype='niet_gegeneraliseerd'):
    """Download borders from PDOK."""

    if level.startswith('gemeente'): level = 'gemeente'

    filename = f'{level}_{gentype}_{year:d}.geojson'
    filepath = Path(directory, filename)

    if not Path.exists(filepath):

        base_url = 'https://service.pdok.nl/cbs/gebiedsindelingen'
        service = 'GetFeature&service=WFS&version=2.0.0'
        typename = f'typeName={level}_{gentype}'
        outputformat = f'outputFormat=json'
        cosys = f'srsName=EPSG:4326'
        request_string = f'{service}&{typename}&{outputformat}&{cosys}'
        url = f'{base_url}/{year:d}/wfs/v1_0?request={request_string}'

        urllib.request.urlretrieve(url, filepath)

    return filepath


def download_borders_umizo(directory, filename='milieuzone_utrecht.geojson'):
    """Download UMIZO borders from own webpage."""

    filepath = Path(directory, filename)

    if not Path.exists(filepath):

        url = f'https://utrechtmilieu.nl/milieuzone/milieuzone_utrecht.geojson'

        urllib.request.urlretrieve(url, filepath)

    return filepath


def load_polygons_geojson(directory, filename):
    """Load borders from geojson file."""

    p = Path(directory, filename).expanduser()
    with open(p) as json_file:
        polygons = json.load(json_file)

    return polygons


def select_polygons(polygons_in, names, prop='statnaam'):
    """Get specific border items from a geojson object."""

    polygons = {}

    polygons['type'] = polygons_in['type']

    if type(names) is list:
        feats = [feat for feat in polygons_in['features']
                 if feat['properties'][prop] in names]

    elif type(names) is str:
        feats = [feat for feat in polygons_in['features']
                 if feat['properties'][prop].startswith(names)]

    polygons['features'] = feats

    return polygons


def get_names_Utrecht(level):
    """Return the names identifying items of mapbox layer levels."""

    names = {
        'buurt': 'BU0344',  # This doesnt work
        # [f'BU03440{}' for i in range(172, 182)],
        # BU03440172  BU03440182
        # BU03440211  BU03440224
        # BU03440325  BU03440333
        # BU03440434  BU03440443
        # BU03440454  
        # BU03440544  BU03440553
        # BU03440555  BU03440558
        # etc
        'wijk': 'WK0344',  # This works
        # [f'WK0344{i:02d}' for i in range(1, 11)],
        'gemeente': [
            'Amersfoort', 'Baarn', 'De Bilt', 'Bunnik', 'Bunschoten',
            'Eemnes', 'Houten','IJsselstein', 'Leusden', 'Lopik',
            'Montfoort', 'Nieuwegein', 'Oudewater', 'Renswoude', 'Rhenen',
            'De Ronde Venen', 'Soest', 'Stichtse Vecht', 'Utrecht',
            'Utrechtse Heuvelrug', 'Veenendaal', 'Vijfheerenlanden',
            'Wijk bij Duurstede', 'Woerden', 'Woudenberg', 'Zeist',
        ],
        'gemeente_Utrecht': ['Utrecht'],
        'stad': ['Utrecht'],
        'provincie': ['Utrecht'],
    }

    return names[level]


def get_mapbox_layers_utrecht(
        directory='.',
        year=2023,
        levels=['buurt', 'wijk', 'gemeente', 'provincie'],
        gentype='niet_gegeneraliseerd',
        ):
    """Put Utrecht borders in mapbox layers."""

    mb_layer = {
        "below": 'traces',
        "sourcetype": "geojson",
        "type": "line",
        "color": "gray",
        }

    mapbox_layers = []

    directory = Path(*[
        '~',
        'OneDrive - Gemeente Utrecht',
        'projects',
        ]).expanduser()  # FIXME: remove hardcoding

    for level in levels:

        if level == 'umizo':

            filename = 'milieuzone_utrecht.geojson'
            filepath = download_borders_umizo(directory, filename)
            polys = load_polygons_geojson(directory, filename)

        elif level == 'pc4':

            """
            import geopandas as gpd
            data = gpd.read_file("cbs_pc4_2023.gpkg")
            postcodes = [postcode for postcode in range(3450, 3587) if utrechtse_postcodes(postcode) == 'Utrecht']
            mask = data.postcode.isin(postcodes)
            data_U = data[mask]
            data_U.to_file("Utrecht_cbs_pc4_2023.geojson", driver='GeoJSON')
            """
            filename = 'Utrecht_cbs_pc4_2023.geojson'
            polys = load_polygons_geojson(directory, filename)

        elif level == 'pc6':

            """
            # Postcode6 geometry: extract Utrecht and save as geojson
            # # TODO fill here from buurten_op_kaart_tmp.py
            """
            filename = 'Utrecht_cbs_pc6_2023.geojson'
            polys = load_polygons_geojson(directory, filename)

        elif level == 'buurt':

            """
            import geopandas as gpd
            data = gpd.read_file("wijkenbuurten_2023_v1.gpkg")
            data = data[data.gemeentecode=='GM0344']
            data.to_file("GM0344_wijkenbuurten_2023_v1.geojson", driver='GeoJSON')
            """
            filename = 'GM0344_wijkenbuurten_2023_v1.geojson'
            polys = load_polygons_geojson(directory, filename)

        else:

            filepath = download_borders_utrecht(directory, year, level, gentype)
            polys = load_polygons_geojson(directory, filepath)

            names = get_names_Utrecht(level)
            levels_naam = ['stad', 'gemeente_Utrecht', 'gemeente', 'provincie']
            prop = 'statnaam' if level in levels_naam else 'statcode'
            polys = select_polygons(polys, names, prop)

        mb_layer['name'] = level
        mb_layer['source'] = polys

        mapbox_layers.append(mb_layer)

    return mapbox_layers


def layout_fig(fig, lo):
    """Ädd mapbox layer to figure."""

    mapbox_layers = get_mapbox_layers_utrecht(
        levels=[lo['polys']['level']],
        gentype=lo['polys']['type'],
        )

    level = mapbox_layers[0]['name']
    polys = mapbox_layers[0]['source']

    for i, poly in enumerate(polys['features']):

        name = pick_name(poly['properties'], level, lo['mapper'])
        if not name:  # in selector:
            continue
        col = assign_color(lo, i, name)
        co = pick_coords(poly, level)

        # print(name, lo['polys']['fill'], dict(width=lo['polys']['width'], color=col))

        fig = add_polys(
            fig,
            name,
            co,
            lo['polys']['fill'],
            dict(width=lo['polys']['width'], color=col),
            )

    return fig


def add_polys(fig, name, co, fill=None, line={}):
    """"""
    for i, coords in enumerate(co):
        fig.add_scattermap(
            below='',
            name=name if len(co) == 1 else f'{name}_p{i}',
            mode='lines+text',
            fill=fill,
            lon=coords[:, 0],
            lat=coords[:, 1],
            line=line,
            )
    return fig


def pick_name(polyprops, level, mapper=None):
    """Return the name for the polygon."""

    if level == 'umizo':

        name = 'umizo'

    elif level == 'pc4':

        name = str(polyprops['postcode'])

    elif level == 'pc6':

        name = str(polyprops['postcode6'])

    elif level == 'buurt':

        if mapper is not None:
            try:
                code = polyprops['buurtcode']  # NB
                name = mapper[code]
            except KeyError:
                name = ''
        else:
            name = polyprops['buurtnaam']

    else:

        name = polyprops['statnaam']

    if level != 'buurt':  # FIXME: integrate
        name = apply_mapper(name, mapper, level)

    return name


def apply_mapper(name, mapper=None, level=''):
    """"""

    # TODO: implement selector for specific list of postcodes
    if mapper is not None:

        if type(mapper) == str:
            df = pd.read_csv(mapper, header=None)
            postcode_list = list(df[0])
            if not ((name[:4] in postcode_list) or (name[:5] in postcode_list) or (name in postcode_list)):
                name = ''

        else:

            try:
                name = mapper[name]
            except KeyError:
                name = ''

    return name


def pick_coords(poly, level):
    """Return the name and coordinates for the polygon."""

    co  = poly['geometry']['coordinates'][0]

    if level == 'umizo':

        coords = [np.array(co)]

    elif (level == 'pc4') or (level == 'pc6'):
        # {"features": [ {"geometry": {"coordinates": [ [ [ [ lat, lon ] ] ] ] } ] }

        coords = [np.array(c) for co in poly['geometry']['coordinates'] for c in co]

        # if len(co) > 1:
        #     coords = [np.array(c) for c in co for co in poly['geometry']['coordinates']]
        #     print(poly['properties']['postcode'])
        # else:
        #     coords = np.array(co)
        #     coords = [coords[0, :, :]]

    elif level == 'buurt':

        coords = np.array(co)
        coords = [coords[0, :, :]]

    else:

        coords = [np.array(co[0])]

    if level in ['gemeente_Utrecht', 'Utrecht', 'stad', 'gemeente', 'wijk', 'buurt', 'pc4', 'pc6']:
        coords = [convert_coords(c) for c in coords]

    return coords


def convert_coords(coords):
    """Convert coordinates from RD to WGS84."""

    conv = geo.RDWGS84Converter()

    for i, co in enumerate(coords):
        co = conv.from_rd(co[0], co[1])
        coords[i, 0] = co[1]
        coords[i, 1] = co[0]

    return coords


def assign_color(layout, i, name):
    """Assign_color to polys according to chosen scheme."""

    col = layout['polys']['color']

    if col == 'fill':

        col = pc.DEFAULT_PLOTLY_COLORS[i%10]

    elif col == 'variable':

        try:
            col = layout['polys']['colormapping'].loc[name]
        except KeyError:
            print(f'KeyError on {name}')
            col = 'rgba(0, 0, 0, 0.5)'

    return col


def get_mapbox_styles(mapbox_token=False):
    """Return the set of available mapbox background styles."""

    mapbox_styles = [
        'carto-positron',
        'open-street-map',
        'carto-darkmatter',
        'white-bg',
        ]

    mapbox_token = mapbox_token or get_mapbox_token()
    if mapbox_token:
        mapbox_styles += [
            'basic',
            'streets',
            'outdoors',
            'light',
            'dark',
            'satellite',
            'satellite-streets',
            ]

    return mapbox_styles


import streamlit as st


def map_options(df, mapbox_token=False, indeling=['buurt', 'wijk', 'stad'], title='### Map options'):
    """Generate a widget to control map options."""

    mapbox_token = mapbox_token or get_mapbox_token()

    if title:
        st.title(title, width="stretch", text_alignment="center")

    background = st.selectbox(
        'Select background',
        options=get_mapbox_styles(mapbox_token),
        index=0,
        )

    selector = st.multiselect(
        'Draw boundaries',
        options=indeling,
        default=[indeling[0]],  # ['buurt'],
        )

    if not selector:
        return background, selector

    tabs = st.tabs(selector)

    layouts = [utrecht_polys()[grensnaam] for grensnaam in selector]

    for i, (tab, grensnaam) in enumerate(zip(tabs, selector)):
        with tab:
            layouts[i]['polys'] = augment_layout(layouts[i], df, grensnaam)

    return background, layouts


def augment_layout(layout, df, name=''):
    """Add mapbox layer styling."""

    polys = layout['polys']

    colortype = st.radio(
        f'Colortype {name}',
        options=['line', 'fill', 'variable'],
        index=0,
        horizontal=True,
        )

    if colortype == 'line':

        row = st.columns(2, gap='small')

        polys['color'] = row[0].color_picker(
            f'Color {name}',
            )

        polys['width'] = row[1].number_input(
            f'Width {name}',
            min_value=0.1,
            value=1.0,
            step=0.1,
            )

    else:

        polys['fill'] = 'toself'
        polys['color'] = colortype

    if colortype == 'variable':

        color = st.radio(
            f'Colormap {name}',
            options=['reds', 'greens', 'blues'],  # TODO: expand cmap options
            index=0,
            horizontal=True,
            )

        countcol = df.columns[0]

        polys['colormapping'] = create_colormapping(df, name, color, countcol)

    return polys


def create_colormapping(df, grens, color, countcol='adres'):
    """"""

    # Group dataframe
    # TODO: find better proxy for datasource
    if 'woonplaatsnaam' in df.columns:
        grensnaam = 'woonplaatsnaam' if grens == 'stad' else f'{grens}naam'
        options = {countcol: ['count']}
        df = df.groupby([grensnaam])[list(options.keys())].agg(options)

    # Normalize counts for rgba
    df = df.replace({np.nan: 0})
    df['rgba'] = (df[countcol] / df[countcol].abs().max() * 255).astype(int)

    df['rgba'] = map_rgba_to_string(df, color)

    return df['rgba']


def map_rgba_to_string(df, color, a=0.5):
    """Map uint8 dataframe column to rgba string."""

    if color == 'reds':
        lfunc = lambda x: f'rgba({x}, 0, 0, {a})'
    elif color == 'greens':
        lfunc = lambda x: f'rgba(0, {x}, 0, {a})'
    elif color == 'blues':
        lfunc = lambda x: f'rgba(0, 0, {x}, {a})'

    df['rgba'] = df['rgba'].apply(lfunc)

    return df['rgba']
