import requests
from typing import Tuple
from geopy.distance import geodesic
import asyncio

from app.models import Transaction, Transactions


async def _get_coordinates(*, adress: str) -> Tuple[float, float]:
    url: str = "https://geocode-maps.yandex.ru/v1/"
    params: dict[str, str] = {
        "apikey": "86b267e6-434c-4d80-a44f-ee8bf21fba8f",
        "geocode": adress,
        "format": "json"
    }
    r: requests.models.Response = requests.get(url=url, params=params)
    r_json: dict = r.json()
    received_objects: dict = r_json['response']["GeoObjectCollection"]["featureMember"]
    coord: Tuple[float, float]

    for elem in received_objects:
        geo_object = elem["GeoObject"]
        precision = geo_object["metaDataProperty"]["GeocoderMetaData"]["precision"]
        if precision != "exact":
            continue
        coord = (float(geo_object["Point"]["pos"].split(" ")[0]), float(
            geo_object["Point"]["pos"].split(" ")[1]))
        break
    return coord


def get_coordinates(*, adress: str) -> Tuple[float, float]:
    url: str = "https://geocode-maps.yandex.ru/v1/"
    params: dict[str, str] = {
        "apikey": "86b267e6-434c-4d80-a44f-ee8bf21fba8f",
        "geocode": adress,
        "format": "json"
    }
    r: requests.models.Response = requests.get(url=url, params=params)
    r_json: dict = r.json()
    received_objects: dict = r_json['response']["GeoObjectCollection"]["featureMember"]
    coord: Tuple[float, float]

    for elem in received_objects:
        geo_object = elem["GeoObject"]
        precision = geo_object["metaDataProperty"]["GeocoderMetaData"]["precision"]
        if precision != "exact":
            continue
        coord = (float(geo_object["Point"]["pos"].split(" ")[0]), float(
            geo_object["Point"]["pos"].split(" ")[1]))
        break
    return coord


def get_distance_coords_adress(*, adress: str, coords: Tuple[float, float]):
    return geodesic(coords, _get_coordinates(adress=adress)).kilometers


def get_distance_coords(coords1: Tuple[float, float], coords2: Tuple[float, float]):
    return geodesic(coords1, coords2).kilometers


async def calculate_transaction_distances(*, transaction_in: Transaction, home_coords: Tuple[float, float], last_transaction: Transactions | None):
    shop_coords_task = asyncio.create_task(
        _get_coordinates(adress=transaction_in.shop_adress))

    current_shop_coords = await shop_coords_task

    distance_from_home = get_distance_coords(home_coords, current_shop_coords)

    last_shop_coords: Tuple[float, float]

    if last_transaction:
        last_shop_coords = str_coord_to_tuple(
            coord_string=last_transaction.shop_coords)
    else:
        return current_shop_coords, distance_from_home, 0

    distance_from_last_transaction = (
        get_distance_coords(current_shop_coords, last_shop_coords))

    return current_shop_coords, distance_from_home, distance_from_last_transaction


def str_coord_to_tuple(*, coord_string: str):
    return float(coord_string[1:-1].split(", ")[0]), float(coord_string[1:-1].split(", ")[1])
