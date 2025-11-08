import pandas as pd

path = '../small.csv'

def dict_insert_line(line: str, hash_map: dict) -> None:
    keys = list(hash_map.keys())
    for i, elem in enumerate(line.split(",")):
        hash_map[keys[i]].append(elem)


with open(path, 'r', encoding='utf-8') as f:
    column_names = f.readline().rstrip().split(",")
    parsed_file = {x: [] for x in column_names}
    for line in f:
        dict_insert_line(line, parsed_file)


df = pd.DataFrame.from_dict(parsed_file)