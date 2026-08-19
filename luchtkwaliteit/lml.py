import zipfile
import urllib.request
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd


def retrieve_and_unzip(url, zipfilepath, directory='.'):
    """Download and unzip files."""

    try:
        urllib.request.urlretrieve(url, zipfilepath)
    except:
        print(f'{url} not found')
    else:
        with zipfile.ZipFile(zipfilepath, 'r') as zf:
            zf.extractall(directory)


def download_data_meta(directory):
    """Download the yearly luchtmeetnet.nl data."""

    base_url = 'https://data.rivm.nl/data/luchtmeetnet'

    csv_metadata = [
        'brongegevens', 'componenten', 'componentgroepen',
        'meetlocaties', 'meetopstellingen', 'meetreeksen', 'opst_meetreeksen',
        ]
    for c in csv_metadata:
        filename = f"luchtmeetnet_{c}.csv"
        filepath = Path(directory, filename)
        url = f"{base_url}/Metadata/{filename}"
        urllib.request.urlretrieve(url, filepath)

    pdf_readme = ['', '_HC_ZM']
    for c in pdf_readme:
        filename = f"readme{c}.pdf"
        filepath = Path(directory, filename)
        url = f"{base_url}/{filename}"
        urllib.request.urlretrieve(url, filepath)


def download_data_years(directory, year_range=[1976, 2024]):
    """Download the yearly luchtmeetnet.nl data."""

    for year in range(year_range[0], year_range[1]):

        base_url = 'https://data.rivm.nl/data/luchtmeetnet'
        url = f'{base_url}/Vastgesteld-jaar/{year}/{year}.zip'

        zipfilepath = Path(directory, f'{year}.zip')
        retrieve_and_unzip(url, zipfilepath, directory)


def download_data_months(directory, year=2026, month_range=[1,13], monthdir='Actueel-jaar'):
    """Download the recent monthly luchtmeetnet.nl data."""

    for month in range(month_range[0], month_range[1]):

        filestem = f'{year}_{month:02d}'

        base_url = 'https://data.rivm.nl/data/luchtmeetnet'
        url = f'{base_url}/{monthdir}/{filestem}.zip'

        zipfilepath = Path(directory, f'{filestem}.zip')
        retrieve_and_unzip(url, zipfilepath, directory)


def download_data(directory, year_start=1976, year_stop=None):
    """Download the data available on luchtmeetnet.nl."""

    lk.lml.download_data_meta(LML_dir)

    if year_stop is None:
        today = datetime.today()
        year_stop = today.year

    def get_data(filestem, remotedir):
        base_url = 'https://data.rivm.nl/data/luchtmeetnet'
        url = f'{base_url}/{remotedir}/{filestem}.zip'
        zipfilepath = Path(directory, f'{filestem}.zip')
        lk.lml.retrieve_and_unzip(url, zipfilepath, directory)

    # Download years in 'Vastgesteld-jaar'
    for year in range(year_start, year_stop+1):
        get_data(f'{year}', f'Vastgesteld-jaar/{year}')
    # Download months from last year ('Voorlopig-jaar')
    for month in range(1, 13):
        get_data(f'{year_stop - 1}_{month:02d}', 'Voorlopig-jaar')
    # Download months from this year ('Actueel-jaar')
    for month in range(1, 13):
        get_data(f'{year_stop}_{month:02d}', 'Actueel-jaar')


def _sort(df, sortcols={'date_time': True}):
    """Default sorting of the dataframe."""

    df = df.sort_values(
        list(sortcols.keys()),
        ascending=list(sortcols.values()),
        ).reset_index(drop=True)
    
    return df


def add_time_breakdown(df, col='date_time'):
    """Add columns for various time periods."""

    df['day'] = df[col].dt.dayofyear
    df['week'] = df[col].dt.isocalendar().week
    df['month'] = df[col].dt.month
    df['quarter'] = df[col].dt.quarter
    df['year'] = df[col].dt.year
    df['leap'] = df[col].dt.is_leap_year

    return df


def read_csv(
        filepath,
        read_csv_kwargs={
            'header': list(range(10)),
            'delimiter': ';',
            'encoding': 'iso8859_15',
            },
        ):
    """Read luchtmeetnet data from a single csv file."""

    df = pd.read_csv(filepath, **read_csv_kwargs)

    df_hdr = df.columns.to_frame().transpose()

    df.columns = df.columns.get_level_values(-1)
    df_hdr.columns = df_hdr.columns.get_level_values(-1)

    # handle duplicate columns (these are caused by eg Meetopstelling changes)
    # Replace the values by nanmean and drop the duplicate columns
    # from both df and df_hdr->(assuming we dont need these details)
    for col in df.columns:
        if np.sum(df.columns == col) > 1:
            df[col] = np.nanmean(df[col], axis=1)

    dupes = ~df.columns.duplicated()
    df = df.loc[:, dupes].copy()
    df_hdr = df_hdr.loc[:, dupes].copy()

    # Create homogenized datetime objects.
    df['begin'] = pd.to_datetime(df[' Begindatumtijd'], utc=True)
    df['eind'] = pd.to_datetime(df['Einddatumtijd'], utc=True)

    return df, df_hdr


def import_data(
        metric,
        year_range,
        month_range,
        directory='.',
        read_csv_kwargs={
            'header': list(range(10)),  # [9, 4],
            'delimiter': ';',
            'encoding': 'iso8859_15',
            },
        ):
    """"Concatenate luchtmeetnet data from a series of csv files."""

    dfs, dfs_hdr = [], []

    for year in range(year_range[0], year_range[1]):

        try:

            filename = f'{year}_{metric}.csv'

            filepath = Path(directory, filename)
            df, df_hdr = read_csv(filepath, read_csv_kwargs)
            dfs.append(df)
            dfs_hdr.append(df_hdr)

        except FileNotFoundError:

            try:

                for month in range(month_range[0], month_range[1]):
                    filename = f'{year}_{month:02d}_{metric}.csv'

                    filepath = Path(directory, filename)
                    df, df_hdr = read_csv(filepath, read_csv_kwargs)
                    dfs.append(df)
                    dfs_hdr.append(df_hdr)

            except FileNotFoundError:

                print(f'no file for {year}_{month:02d}')

            print(f'no file for {year}')

    df = pd.concat(dfs, ignore_index=True)
    df = _sort(df, sortcols={'eind': True})
    df = add_time_breakdown(df, 'eind')


    # Process station info
    # NB. this is only approximate and does not preserve all detail correctly
    df_hdr = dfs_hdr[0]
    for df_hdr_next in dfs_hdr[1:]:
        df_hdr = df_hdr.combine_first(df_hdr_next)

    df_hdr = df_hdr.iloc[:, 4:].transpose()
    df_hdr.columns = df_hdr.iloc[0, :]
    df_hdr = df_hdr.drop(df_hdr.index[0])
    df_hdr = split_latlon(df_hdr, old_key='Latitude,Longitude')
    df_hdr['compound'] = metric

    return df, df_hdr


def import_station_info(
        metric, year_range, month_range, directory='.',
        read_csv_kwargs={'header': [9, 4]},
        ):
    """Importeer meetstation info vanuit header rows."""

    # FIXME: not getting this more elegant and generic implementation to work
    # df = import_data(metric, year_range, month_range, LML_dir, {'header': list(range(9))})
    # df_meetpunten = df.columns.to_frame().transpose()

    # FIXME: some nan issues with reading the full header
    # kwargs = {'header': [9, 5, 3, 1, 2, 6, 7, 8], 'nrows': 9}
    # mapping = {
    #     0: 'StationsCode',  # name
    #     1: 'StationsType',  # type
    #     2: 'Latitude,Longitude',  # latlon   l[2][4]
    #     3: 'BeheerderMeetStation',  # beheerder
    #     4: 'StationsNaam',  # locatie
    #     5: 'Meetprincipe',
    #     6: 'Meetopstelling',
    #     7: 'Accreditatienummer',
    #     }

    kwargs = {'header': [9, 5, 3], 'nrows': 4}
    mapping = {
        0: 'StationsCode',  # name
        1: 'StationsType',  # type
        2: 'Latitude,Longitude',  # latlon   l[2][4]
        }

    df = import_data(metric, year_range, month_range, directory, kwargs)
    l = [df.columns.get_level_values(k) for k in mapping.keys()]
    df = pd.DataFrame(l).transpose()
    df = df.rename(columns=mapping)
    df = df[df['StationsCode'].str.startswith('NL')]
    df = split_latlon(df, old_key='Latitude,Longitude')
    df['compound'] = metric

    return df


def split_latlon(df, old_key='latlon', new_keys=['lat', 'lon']):

    df[old_key] = df[old_key].str[1:]
    df[[old_key, f'{old_key}_tmp']] = df[old_key].str.split(')', n=1, expand=True)
    df[new_keys] = df[old_key].str.split(',', n=1, expand=True)
    df = df.drop([old_key, f'{old_key}_tmp'], axis=1)

    return df


def add_station_info(df, df_meetpunten):
    """Add station metadata to each observation."""

    # Create columns.
    for c in df_meetpunten.columns:
        if c in ['lat', 'lon']:
            df[c] = np.nan
        else:
            df[c] = ''

    # Fill columns.
    for i, d in df_meetpunten.iterrows():
        mask = df['StationsCode'] == i
        for c in df_meetpunten.columns:
            df[c][mask] = d[c]

    return df


def import_data_long(
        metric,
        year_range,
        month_range,
        directory='.',
        read_csv_kwargs={'delimiter': ';'},
        ):
    """"Concatenate luchtmeetnet data from a series of csv files."""

    dfs = []

    for year in range(year_range[0], year_range[1]):
        print(year)

        try:

            read_csv_kwargs['skiprows'] = 5
            filename = f'{year}_{metric}.csv'

            filepath = Path(directory, filename)
            df = pd.read_csv(filepath, **read_csv_kwargs)
            dfs.append(df)

        except FileNotFoundError:

            try:

                for month in range(month_range[0], month_range[1]):

                    read_csv_kwargs['skiprows'] = 6
                    filename = f'{year}_{month:02d}_{metric}.csv'

                    filepath = Path(directory, filename)
                    df = pd.read_csv(filepath, **read_csv_kwargs)
                    dfs.append(df)

            except FileNotFoundError:

                print(f'no file for {year}_{month:02d}')

            print(f'no file for {year}')

    df = pd.concat(dfs, ignore_index=True)
    df['begin'] = pd.to_datetime(df['begindatumtijd'], utc=True)
    df['eind'] = pd.to_datetime(df['einddatumtijd'], utc=True)
    df = _sort(df, sortcols={'eind': True})
    df = add_time_breakdown(df, 'eind')

    return df


def import_metadata(
        directory='.',
        read_csv_kwargs={'delimiter': ';'},
        metadata_name='meetlocaties',
        ):
    """"."""

    read_csv_kwargs['skiprows'] = 5
    filename = f'luchtmeetnet_{metadata_name}.csv'

    filepath = Path(directory, filename)
    df = pd.read_csv(filepath, **read_csv_kwargs)

    return df



# API

import requests
import json


def build_uri(base_url, property_name, odata={}):
    uri = f'{base_url}/{property_name}'
    if odata:
        uri += '?'
        for k, v in odata.items():
            uri += f'{k}={v}&'
        uri = uri[:-1]
    return uri


def get_all(base_url, property_name, odata={}):
    """Get list of various entities."""

    uri = build_uri(base_url, property_name, odata)
    records = get_records(uri)

    return records


def get_records_page(base_url, property_name, odata={}):
    uri = build_uri(base_url, property_name, odata)
    response = requests.get(uri)
    jfile = json.loads(response.text)
    return jfile


def get_records(base_url, property_name, odata={}, data_field='data'):
    """Get all records from a stream."""

    jfile = get_records_page(base_url, property_name, odata)
    records = jfile[data_field]

    while jfile['pagination']['current_page'] < jfile['pagination']['last_page']:
        odata['page'] = jfile['pagination']['next_page']
        jfile = get_records_page(base_url, property_name, odata)
        records += jfile[data_field]

    return records


def get_stations():
    ### Stations  https://api.luchtmeetnet.nl/open_api/stations?order_by=&organisation_id=&page=
    base_url = 'https://api.luchtmeetnet.nl/open_api'
    property_name = 'stations'
    odata = {
        'page': '',
        'orderby': 'organisation_id',
    }
    stations = get_records(base_url, property_name, odata)
    return stations


def get_station(station_number):
    ### Station  https://api.luchtmeetnet.nl/open_api/stations/NL10301
    base_url = 'https://api.luchtmeetnet.nl/open_api'
    property_name = f'stations/{station_number}'
    station = get_records_page(base_url, property_name)['data']
    return station


def load_dataframe(thing_ids, base_url, obsprop, start, end):

    time_col = 'timestamp_measured'
    value_col = 'value'

    # postfix = f"on {obsprop} for period {start} to {end}"
    dfs = []
    for thing_id in thing_ids:

        odata = {
            'page': '1',
            'station_number': thing_id,
            'formula': obsprop,
            'orderby': time_col,
            'start': start,
            'end': end,
        }
        observations = get_records(base_url, 'measurements', odata)

        if observations != []:
            df = pd.DataFrame.from_records(observations)
            df['date_time'] = pd.to_datetime(df[time_col])
            df = df.drop(time_col, axis=1)
            df = df.rename({value_col: obsprop}, axis=1)
            df['thing_id'] = f'LML_{thing_id}'
            dfs.append(df)

        #     prefix = f"has {len(observations)} observations"
        # else:
        #     prefix = f"*does NOT seem to have observations*"

        # st.write(f"{thing_id} {prefix} {postfix}.")

    df = pd.concat(dfs, axis=0)

    return df
