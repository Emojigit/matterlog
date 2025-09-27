from typing import Generator
from datetime import datetime, timezone
import os
from multiprocessing import Process

import configparser
import requests


def matterbridge_api_listener(base_url: str, token: str = None) -> Generator[dict, None, None]:
    header = {
        "User-Agent": "matterlog/1.0",
        "Accept": "application/json",
    }
    if token:
        header["Authorization"] = f"Bearer {token}"

    url = base_url + "api/messages"

    while True:
        with requests.get(url, headers=header, timeout=10) as responce:
            if responce.status_code != 200:
                print("ERROR: Failed to connect to Matterbridge API " +
                      f"{base_url}: {responce.status_code} {responce.text}")
                continue

            messages = responce.json()
            yield from messages


def process_chat(channel_name: str, messages_generator: Generator[dict, None, None], save_path: str):
    for message in messages_generator:
        username = message["username"]
        text = message["text"]
        timestamp = message["timestamp"]  # 2025-09-27T11:58:59.936761682-04:00
        timestamp = timestamp[0:26] + timestamp[-6:]  # trim nanoseconds
        time = datetime.strptime(
            timestamp, r'%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)
        year, month, day = time.year, time.month, time.day

        logfile_dir = f"{save_path}/{year:04d}/{month:02d}"
        logfile_path = f"{logfile_dir}/{day:02d}.txt"

        os.makedirs(logfile_dir, exist_ok=True)
        with open(logfile_path, "a", encoding="utf-8") as logfile:
            logfile.write(f"{time.isoformat()}\t{username}\t{text}\n")

        print(f"INFO: {time.isoformat()} #{channel_name} <{username}>: {text}")


def process(channel_name: str, base_url: str, save_path: str, token: str = None):
    print(f"INFO: Starting to process channel {channel_name}")
    gen = matterbridge_api_listener(base_url, token)
    try:
        process_chat(channel_name, gen, save_path)
    except KeyboardInterrupt:
        print(f"INFO: #{channel_name} interrupted by user")


def main() -> int:
    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'save_path' not in config['server']:
        config['server']['save_path'] = './logs'

    processes = []

    for section in config.sections():
        if section[0:8] == "channel.":
            channel_name = section[8:]
            base_url = config[section]['base_url']
            token = config[section].get('token', None)
            save_path = os.path.join(
                config['server']['save_path'], channel_name)

            p = Process(
                target=process,
                args=(channel_name, base_url, save_path, token))
            p.start()
            processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        for p in processes:
            p.terminate()
            p.join()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
