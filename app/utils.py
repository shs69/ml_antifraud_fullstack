from io import StringIO
from fastapi import UploadFile
import requests
import asyncio
from typing import Tuple
from geopy.distance import geodesic
import pandas as pd

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


def dict_insert_line(line: str, hash_map: dict) -> None:
    keys = list(hash_map.keys())
    for i, elem in enumerate(line.split(",")):
        hash_map[keys[i]].append(elem)


def csv_to_dict(file: UploadFile) -> dict:
    contents = file.file.read().decode("utf-8")
    f = StringIO(contents)
    column_names = f.readline().rstrip().split(",")
    parsed_file = {x: [] for x in column_names}
    for line in f:
        dict_insert_line(line, parsed_file)

    return parsed_file


def dict_to_transactions(data: dict):
    transactions = []
    for i in range(len(data["shop_name"])):
        transaction_data = {
            "shop_name": data["shop_name"][i].strip('"'),
            "shop_adress": data["shop_address"][i].strip('"'),
            "is_refill": int(data["is_refill"][i]),
            "size": int(data["size"][i]),
            "used_chip": str_to_bool(data["used_chip"][i]),
            "used_pin_number": str_to_bool(data["used_pin_number"][i]),
            "online_order": str_to_bool(data["online_order"][i])
        }
        transaction = Transaction(**transaction_data)
        transactions.append(transaction)
    return transactions


def str_to_bool(s: str) -> bool:
    s = s.strip()
    return s in ("1", "1.0", "true", "True")
