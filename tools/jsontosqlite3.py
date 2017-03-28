import os
import sys
import pathlib
import gzip
import json
import argparse
import time

import sqlite3


VALID_REGIONS = ("BR", "EUNE", "EUW", "JP", "KR", "LAN", "LAS", "NA", "OCE", "RU", "TR")
folder_data = pathlib.Path('.', 'data')
BATCH_SIZE = 1000

def init_db(filename):
    if not os.path.isfile(filename):
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE "MatchJSON"
            (
                id INTEGER PRIMARY KEY,
                region CHAR(4) NOT NULL,
                matchId BIGINT NOT NULL,
                timestampRetrieved BIGINT,
                matchJSON BLOB NOT NULL,
                UNIQUE(region, matchId) ON CONFLICT IGNORE
            )
            """
        )
        conn.commit()
        conn.close()


def flush_matches(conn, json_list):
    tuples_list = [(region, k, gzip.compress(v.encode(encoding="UTF-8"))) for k, v in json_list.items()]
    try:
        c = conn.cursor()
        c.executemany('INSERT INTO "MatchJSON" ("region", "matchId", "matchJSON") VALUES (?, ?, ?)', tuples_list)
        conn.commit()
        for match_id in json_list:
            filename = "match-" + str(match_id) + ".json.gz"
            os.rename(pathlib.Path(folder_json_match, filename), pathlib.Path(folder_json_match_processed, filename))
    except:
        raise

# Parse arguments
try:
    parser = argparse.ArgumentParser(description="Combines single-match json files into one larger text file.")
    parser.add_argument("-r", "--region", help="server region", choices=VALID_REGIONS, required=True, nargs=1, type=str.upper)

except argparse.ArgumentError as e:
    print("Invalid argument: {0}.".format(e.message))
    sys.exit(2)
args = parser.parse_args()

if args.region is None:
    print("Region not set. Set region with -r argument.")
    sys.exit(2)
else:
    print("Region set to {0}.".format(args.region[0].upper()))
    region = args.region[0]

# Set directories
folder_region = pathlib.Path(folder_data, region.lower())
folder_json_match = pathlib.Path(folder_region, 'json-match')
folder_json_match_processed = pathlib.Path(folder_region, 'json-match-processed')
folder_db = pathlib.Path(folder_region, 'database')

filename_db = "db-match-json-" + region.lower() + ".sqlite"
path_db = str(pathlib.Path(folder_db, filename_db))

init_db(path_db)

# Count files in json folder
count = 0
for file in folder_json_match.iterdir():
    if file.match('*.json.gz') and file.is_file():
        count += 1

print("Processing {count} matches".format(count=count))

start_time = time.monotonic()

# Main loop
current = 1
json_list = {}
for file in folder_json_match.iterdir():
    if file.match('*.json.gz') and file.is_file():
        print("Processing match {current}/{count} ({perc:.0f}%)".format(current=current, count=count, perc=(current*100/count)), end="\r")
        match_json = {}
        with gzip.open(file, 'rt') as f:
            file_prefix = str(file).split(".")[0]
            matchId = int(file_prefix.split("-")[-1])
            match_json = f.readline()
            json_list[matchId] = match_json

        if len(json_list) >= BATCH_SIZE:
            with sqlite3.connect(path_db) as conn:
                flush_matches(conn, json_list)
            json_list = {}

        current += 1

if len(json_list):
    with sqlite3.connect(path_db) as conn:
        flush_matches(conn, json_list)

end_time = time.monotonic()
total_time = end_time - start_time
if count == 0:
    count = 1
print("\nFinished inserting {count} matches in {t}s, avg {avg:.2f}s / 1000 matches".format(count=count, t=total_time, avg=(total_time / (count / 1000))))
conn.close()

