import luchtkwaliteit as lk
import luchtkwaliteit.lml
import luchtkwaliteit.plotting

import zipfile
import requests
from pathlib import Path

import numpy as np
import pandas as pd

import plotly.express as px


def download_data(directory):
    """Download data from utrechtmilieu.nl."""

    url = 'https://www.utrechtmilieu.nl/meetnet/opendata.php'
    r = requests.get(url, allow_redirects=True, verify=False)

    filename = 'luchtmeetnetdata.zip'
    filepath = Path(directory, filename)
    with open(filepath, 'wb') as file:
        file.write(r.content)

    with zipfile.ZipFile(filepath, 'r') as zf:
        zf.extractall(directory)

    return filepath


def import_data(directory):
    """Import data from Utrechts Meetnet Luchtkwaliteit to dataframe."""

    csv_params = dict(
        sep=',',
        quotechar='"',
        skipinitialspace=True,
        encoding="utf-8",
        )

    filename = 'metingen.csv'
    df = pd.read_csv(Path(directory, filename), **csv_params)

    filename = 'meetpunten.csv'
    df_meetpunten = pd.read_csv(Path(directory, filename), **csv_params)

    return df, df_meetpunten


def cleanup_data(df):
    """Clean Utrecht Palmes measurements."""

    # Delete entries with out a date set.
    mask = df['begin'] == '1900-01-00'
    mask |= df['eind'] == '1900-01-00'
    df = df[~mask]
    print(f'Deleted {np.sum(mask)} measurements where date was not set.')

    # Delete superfluous columns.
    cols = ['opmerkingen']
    for col in cols:
        del df[col]
    print(f'Deleted columns {cols}')

    return df


def convert_datatypes(df):
    """Set datatypes on columns."""

    df['puntid'] = df.puntid.astype('category')

    format = '%Y-%m-%d'
    for key in ['begin', 'eind']:
        df[key] = pd.to_datetime(df[key], format=format)

    return df


def calculate_mean(df):
    """Add column with mean for repeated/duplo measurements."""

    valcols = [f'waarde{i}' for i in range(1, 5)]
    df.replace(0, np.nan, inplace=True)
    df['waarde'] = df[valcols].mean(axis=1)

    return df


def get_corr_mapper(UML_dir, filename='correctiefactoren.csv'):
    """Get a dict that maps measurement dates to periods."""

    # TODO: get more accurate correctiefactoren
    df_corr = pd.read_csv(Path(UML_dir, filename), delimiter=';', decimal=',')
    df_corr.columns = ['JAAR'] + [f'P{i}' for i in range(1, 14)]
    df_corr = df_corr.melt(id_vars='JAAR')
    df_corr['periodY'] = df_corr['JAAR'].astype(int).astype(str) + df_corr['variable']
    corr_mapper = dict(zip(df_corr.periodY, df_corr.value))

    return corr_mapper


def apply_correction(df, directory, pick_date='eind'):
    """Apply a set of correction factors to the data."""

    filename = 'wisseldagen_UML.csv'
    df_dates = pd.read_csv(Path(directory, filename))
    mapper = dict(zip(df_dates.eind, df_dates.period))
    df['period'] = df[pick_date].map(mapper)
    # FIXME: this is incomplete. derive from data?

    # Find weeks that are associated with the periods and map missing period id's.
    mapper2 = {}
    for i, g in df.groupby('period'):
            for k in set(g['week']):
                mapper2[k] = i

    df['period'] = df['week'].map(mapper2)

    # df[df['period'].isna()]

    corr_mapper = get_corr_mapper(directory, 'correctiefactoren.csv')

    # print(df, df.dtypes)
    df['periodY'] = df['year'].astype(int).astype(str) + df['period'].astype(str)
    df['correctiefactor'] = df['periodY'].map(corr_mapper).fillna(1.)
    df['waarde_corr'] = df['waarde'] * df['correctiefactor']

    # FIXME: correct these in the measurements, manually corrected in the CSV for now
    # TODO: check on other NaNs after the first mapper??
    # 50,"2023-06-06","2023-04-07",16,0,0,0,""
    # 57,"2023-06-06","2023-04-07",11,0,0,0,"meetlocatie in gebruik m.i.v. 2014"

    return df


def add_station_info(df, df_meetpunten):
    """Add station metadata to each observation."""

    types = {
        'Straat': ['Straatmeetpunt', 'Straatmeetpunt/RIVM meetstation'],
        'Stad': ['Stadmeetpunt (achtergrond)', 'Stadmeetpunt/RIVM meetstation'],
        'Regio': ['Regiomeetpunt (achtergrond)'],
        }
    df['type'] = ''
    df['RIVM'] = False  # consider renaming to 'beheer', ivm met LML homogenisatie
    df['lat'] = np.nan
    df['lon'] = np.nan
    df['name'] = ''
    df['compound'] = ''

    for i, d in df_meetpunten.iterrows():
        mask = df['puntid'] == i + 1
        for meetpunttype in types.keys():
            if meetpunttype in d['type']:
                break
        df['type'][mask] = meetpunttype
        df['RIVM'] = 'RIVM' in d['type']
        df['lat'][mask] = d['lat']
        df['lon'][mask] = d['lng']
        df['name'][mask] = d['naam']
        df['compound'][mask] = d['wat']

    return df


def subselect_df(
        df,
        freq_key='YE',
        ref_station='Rijnenburg/IJsselstein',
        time_column='eind',
        value_column='waarde',
        color_column='type',
        group_column='name',
        station_cols = ['name', 'type', 'lat', 'lon'],
        ):
    """"""

    # select columns and set index to timestamps
    dft = df[[time_column]+[value_column]+station_cols]
    dfr = dft.set_index(time_column)

    # aggregate the value column by mean; the rest (categoricals) by count
    fun = lambda x: x.value_counts().index[0]
    cols = station_cols + [value_column]
    options = {c: fun for c in cols}
    options[value_column] = 'mean'

    # group and resample
    dfr = dfr.groupby(group_column).resample(freq_key, include_groups=False).agg(options)
    dfr = dfr.drop(group_column, axis=1)
    dfr = dfr.reset_index()

    # dfr = calculate_percentage(dfr, freq_key, ref_station, value_column, time_column, group_column)

    dfr = dfr[~dfr[value_column].isna()]
    # TODO: find out what the nans are

    return dfr


def calculate_percentage(
        df,
        freq_key='YE',
        ref_station='Rijnenburg/IJsselstein',
        value_column='waarde',
        time_column='eind',
        group_column='name',
        ):
    """"""

    freqs = {'QE': 'Kwartaal', 'YE': 'Jaar'}
    freq = freqs[freq_key]

    perc_column = f'{value_column}_perc'
    df[perc_column] = 0.

    df[freq] = pd.PeriodIndex(df.loc[:, time_column], freq=freq_key[0])
    for Q, df_Q in df.groupby(freqs[freq_key]):
        ref = df_Q[df_Q[group_column]==ref_station][value_column]
        df_Q[perc_column] = 0.
        df_Q[perc_column] = 100 * df_Q[value_column] / float(ref.iloc[0])
        columns = [perc_column]
        for col in columns:
            df.loc[df_Q.index, col] = df_Q[col]

    return df


def create_boxplot(
        df,
        freq_key='YE',
        time_column='eind',
        value_column='waarde',
        color_column='type',
        group_column='name',
        station_cols = ['name', 'type', 'lat', 'lon'],
        ):
    """Create a quarterly (QE) or yearly (YE) boxplot."""

    freqs = {'YE': 'Jaar', 'QE': 'Kwartaal', 'ME': 'Maand', 'P': 'Meetperiode'}
    freq = freqs[freq_key]

    fig = px.violin(df, x=time_column, y=value_column, color=color_column)
    # fig = px.box(df, x=time_column, y=value_column, color=color_column)
    fig.update_xaxes(
        title_text=freq,
        showgrid=True,
        ticks="outside",
        tickson="boundaries",
        ticklen=20,
        tick0="2011-03-31",
        # dtick=7*24*60*60*1000,
        # dtick='YE',
        minor=dict(ticks="inside", showgrid=True),
    )
    fig.update_yaxes(  # FIXME: make variable
        title_text=r'$NO_2 \mug / m^3$',  # FIXME: \mu not working
        range=[0, 70],
        )
    fig.update_xaxes(rangeslider_visible=True)

    return fig


def create_mapbox(
        df,
        freq_key='YE',
        mapbox_parset={},
        group_column='name',
        ):

    freqs = {'YE': 'Jaar', 'QE': 'Kwartaal', 'ME': 'Maand', 'P': 'Meetperiode'}
    freq = freqs[freq_key]

    # Set up layout
    background = 'carto-positron'
    lo1 = {
        'polys': {
            'level': 'gemeente_Utrecht',
            'type': 'niet_gegeneraliseerd',
            'color': 'black',
            'width': 2,
            'fill': None,  # None or 'toself'
        },
        'mapper': None,
    }
    lo2 = {
        'polys': {
            'level': 'wijk',
            'type': 'niet_gegeneraliseerd',
            'color': 'black',
            'width': 1,
            'fill': None, # None or 'toself'
        },
        'mapper': None,
    }

    fig = px.scatter_mapbox(
        df,
        animation_frame=freq,
        animation_group=group_column,
        lat="lat",
        lon="lon",
        hover_name=group_column,
        zoom=10.5,
        **mapbox_parset,
        )
    fig.update_layout(mapbox_style=background)
    fig.update_layout(coloraxis_colorbar_x=-0.1)
    fig = lk.plotting.layout_fig(fig, lo1)
    fig = lk.plotting.layout_fig(fig, lo2)  # FIXME: is printed in terminal

    return fig


def load_dataframe_uml(datadir, pick_date='eind', download=False):
    """Load and preprocess data and metadata from NO2 Meetnet Utrecht."""

    if download:
        datadir.mkdir(parents=True, exist_ok=True)
        download_data(datadir)

    df, df_mp = import_data(datadir)

    df = cleanup_data(df)
    df = convert_datatypes(df)
    df = lk.lml.add_time_breakdown(df, pick_date)
    df = calculate_mean(df)  # 'waarde{.}' -> 'waarde'

    df = apply_correction(df, datadir, pick_date)  # 'waarde' -> 'waarde_corr'

    df = add_station_info(df, df_mp)

    mapper = dict(zip(df_mp['id'], df_mp['code']))
    df['code'] = df['puntid'].astype(str).replace(mapper)

    # Calculate the measured yearly average concentration.
    df_jgc = calculate_jaargemiddelde_concentraties(df)  # 'waarde_corr' -> 'waarde_weighted'

    # geom  = gpd.points_from_xy(df_mp.lng, df_mp.lat)
    # df_mp = gpd.GeoDataFrame(df_mp, geometry=geom, crs="EPSG:4326")

    return df, df_mp, df_jgc


def calculate_jaargemiddelde_concentraties(df, waarden=['waarde', 'waarde_corr'], location_col='puntid'):
    """Calculate jaargemiddelde concentratie (jgc)."""

    groupcols = [location_col, 'year']
    cols = groupcols + ['begin', 'eind', 'name', 'type', 'lat', 'lon']

    jgc = time_weighted_yearly_average(df, groupcols, waarden)

    jgc = df[cols].set_index(groupcols).join(jgc, on=groupcols).reset_index()
    jgc = jgc.drop(['begin', 'eind'], axis=1).drop_duplicates()

    # The following is a quickfix to get all results to the cimlk tab
    # for y in range(2011, 2025):
    #     cols = ['puntid', 'name', 'type', 'lat', 'lon', 'waarde_weighted']
    #     dfr = jgc.loc[jgc['year'] ==  y, cols]
    #     dfr = dfr.drop_duplicates().set_index('puntid')
    #     st.session_state[f'no2Conc_gemeten_{y}'] = dfr

    return jgc


def time_weighted_yearly_average(df, groupcols, waarden=['waarde', 'waarde_corr']):
    """Calculate time-weighted jaargemiddelde concentratie."""

    df = df[groupcols + ['begin', 'eind'] + waarden + ['type', 'lat', 'lon']]

    # Calculate number of days for each measurement period.
    df['Ndays'] = (df['eind'] - df['begin']).dt.days
    for waarde in waarden:
        df.loc[df[waarde].isna(), 'Ndays'] = 0

    # Bereken tijdsgewogen jaargemiddelde.
    div = lambda x: x / x.sum()
    df['T_weight'] = df[groupcols+['Ndays']].groupby(groupcols).transform(div)
    d = {}
    for waarde in waarden:
        df[f'{waarde}_weighted'] = df['T_weight'] * df[waarde]
        d |= {waarde: np.mean, f'{waarde}_weighted': np.sum}

    df_tw = df[groupcols+waarden+[f'{waarde}_weighted' for waarde in waarden]].groupby(groupcols).agg(d)

    return df_tw


def get_jgc_for_year(jgc, myear):
    """Extract a measurement year from the jgc dataframe."""

    cols = ['puntid', 'name', 'type', 'lat', 'lon', 'waarde_weighted']
    df = jgc.loc[jgc['year'] ==  myear, cols]
    df = df.drop_duplicates().set_index('puntid')

    return df
