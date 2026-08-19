from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

import streamlit as st  # TODO: remove st dependency

import requests
import json

import warnings
warnings.filterwarnings("ignore")


def get_location_coordinates(base_url, id):
    """Get the location of a Thing by id."""
    uri = f'{base_url}/Things({id})/Locations'
    response = requests.get(uri)
    jfile = json.loads(response.text)
    try:
        coords = jfile['value'][0]['location']['coordinates'] 
    except IndexError:
        coords = []
    return coords


def get_records(uri, data_field='value', nextlink_field='@iot.nextLink'):
    """Get all records from a stream."""
    response = requests.get(uri)
    jfile = json.loads(response.text)
    try:
        records = jfile[data_field]
    except KeyError:
        return jfile
    else:
        while nextlink_field in jfile.keys():
            uri = jfile[nextlink_field]
            response = requests.get(uri)
            jfile = json.loads(response.text)
            records += jfile[data_field]
        return records


def get_thing_by_id(base_url, id):
    """Get a Thing calling it by its id."""
    uri = f'{base_url}/Things({id})'
    record = get_records(uri)
    return record


def get_thing_by_name(base_url, name):
    """Get a Thing calling it by its name."""
    uri = f'{base_url}/Things?$filter=name%20eq%20%27{name}%27'
    records = get_records(uri)
    return records[0]


def select_datastream_from_thing(base_url, id, obsprop='no2'):
    """Get a specific named Datastream from a Thing."""
    uri = f'{base_url}/Things({id})/Datastreams'  # &$select=id,ObservedProperty@iot.navigationLink
    datastreams = get_records(uri)
    for datastream in datastreams:
        uri = datastream['ObservedProperty@iot.navigationLink']
        response = requests.get(uri)
        jfile = json.loads(response.text)
        if jfile['name'] == obsprop:
            return datastream['@iot.id']
    return None


def get_datastreams_of_thing(base_url, id):
    """Get all Datastreams of a Thing."""
    uri = f'{base_url}/Things({id})/Datastreams'
    datastreams = get_records(uri)
    # for datastream in datastreams:
    #     uri = datastream['ObservedProperty@iot.navigationLink']
    #     records = get_records(uri)
    #     if datastream['name'] == obsprop:
    #         return datastream['@iot.id']
    return datastreams


def get_period_from_datastream(base_url, id, date_start, date_stop):
    """Get an interval of records from a Datastream."""
    timecol  = 'phenomenonTime'
    filter = f'$filter={timecol}+ge+%27{date_start}%27+and+{timecol}+lt+%27{date_stop}%27'
    ordering = f'$orderby={timecol}'
    selection = f'$select={timecol},result'  # id
    uri = f'{base_url}/Datastreams({id})/Observations?{filter}&{ordering}&{selection}'
    records = get_records(uri)
    return records


def get_all(base_url, property_name, odata={'orderby': 'id'}):
    """Get list of various entities."""
    uri = f'{base_url}/{property_name}'
    if odata:
        uri += '?'
        for k, v in odata.items():
            uri += f'${k}={v}&'
        uri = uri[:-1]
    records = get_records(uri)
    return records


def geolocate(df, base_url='https://api-samenmeten.rivm.nl/v1.0'):
    for thing in things_utrecht:
        id = thing["@iot.id"]
        c = get_location_coordinates(base_url, id)
    return c
        # st.write((f'Thing {id} is at coordinates {c}'))


def get_coordinates(id, base_url='https://api-samenmeten.rivm.nl/v1.0'):
    """Get the location of a Thing by id."""
    uri = f'{base_url}/Things({id})/Locations'
    response = requests.get(uri)
    jfile = json.loads(response.text)
    try:
        coords = jfile['value'][0]['location']['coordinates'] 
    except IndexError:
        coords = [None, None]
    # return {'latitude': coords[0], "longitude": coords[1]}
    return pd.Series(coords, index=["latitude", "longitude"])


@st.cache_data
def get_all_things_in_gemeente(base_url='https://api-samenmeten.rivm.nl/v1.0', gemeentecode='344'):
    # Get all Things in the Gemeente Utrecht
    odata = {
        'orderby': 'id',
        'filter': f'(properties/codegemeente%20eq%20%27{gemeentecode}%27)',
    }
    things = get_all(base_url, 'Things', odata)
    df = pd.DataFrame.from_records(things)
    df[['longitude', 'latitude']] = df["@iot.id"].apply(lambda x: get_coordinates(x))
    cols = ["@iot.id", 'name', 'description', 'properties', 'latitude', 'longitude']
    df = df[cols].set_index("@iot.id")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["longitude"],
            df["latitude"],
        ),
        crs="EPSG:4326",
    )

    return gdf


@st.cache_data
def get_all_things_in_box(base_url='https://api-samenmeten.rivm.nl/v1.0', center={"lat": 5.121314, "lon": 52.090654}, degrees=0.005):
    # https://api-samenmeten.rivm.nl/v1.0/locations?$filter=
    # 
    # Get all Things in the Gemeente Utrecht
    odata = {
        'orderby': 'id',
        'filter': f'geo.distance(location%2C+geography%27SRID%3D4326%3BPOINT({center["lat"]}+{center["lon"]})%27)+le+{degrees}',
    }
    locations = get_all(base_url, 'Locations', odata)
    things = []
    for location in locations:
        things += get_records(location["Things@iot.navigationLink"])


    df = pd.DataFrame.from_records(things)
    df[['longitude', 'latitude']] = df["@iot.id"].apply(lambda x: get_coordinates(x))
    cols = ["@iot.id", 'name', 'description', 'properties', 'latitude', 'longitude']
    df = df[cols].set_index("@iot.id")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["longitude"],
            df["latitude"],
        ),
        crs="EPSG:4326",
    )

    return gdf


def get_things_from_location(base_url, id):
    """Get a the Things at a location."""
    things = get_records(uri)
    for datastream in datastreams:
        uri = datastream['ObservedProperty@iot.navigationLink']
        response = requests.get(uri)
        jfile = json.loads(response.text)
        if jfile['name'] == obsprop:
            return datastream['@iot.id']
    return None


def load_dataframe(thing_ids, base_url, obsprop, start, end):

    time_col = 'phenomenonTime'
    value_col = 'result'

    postfix = f"on {obsprop} for period {start} to {end}"
    dfs = []
    for thing_id in thing_ids:

        datastream_id = select_datastream_from_thing(base_url, thing_id, obsprop)
        observations = get_period_from_datastream(base_url, datastream_id, start, end)
        # st.write(thing_id, observations)

        if observations != []:
            df = pd.DataFrame.from_records(observations)
            st.dataframe(df)
            df['date_time'] = pd.to_datetime(df[time_col])
            df = df.drop(time_col, axis=1)
            df = df.rename({value_col: obsprop}, axis=1)
            df['thing_id'] = f'SMD_{thing_id}'
            dfs.append(df)

            prefix = f"has {len(observations)} observations"
        else:
            prefix = f"*does NOT seem to have observations*"

        st.write(f"{thing_id} {prefix} {postfix}.")

    df = pd.concat(dfs, axis=0)

    return df
