from typing import Generator
from datetime import datetime, timezone
import os

import configparser
import asyncio
import aiofiles
import aiohttp


async def matterbridge_api_listener(base_url: str, token: str = None) -> Generator[dict, None, None]:
    header = {
        "User-Agent": "matterlog/1.0",
        "Accept": "application/json",
    }
    if token:
        header["Authorization"] = f"Bearer {token}"

    url = base_url + "api/messages"

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=header, timeout=10) as responce:
                if responce.status != 200:
                    print("ERROR: Failed to connect to Matterbridge API " +
                          f"{base_url}: {responce.status} {responce.text}")
                    continue

                messages = await responce.json()
                for message in messages:
                    yield message


async def process_chat(channel_name: str, messages_generator: Generator[dict, None, None], save_path: str):
    async for message in messages_generator:
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
        async with aiofiles.open(logfile_path, "a", encoding="utf-8") as logfile:
            for line in text.splitlines():
                await logfile.write(f"{time.isoformat()}\t{username}\t{line}\n")

        print(f"INFO: {time.isoformat()} #{channel_name} <{username}>: {text}")


async def process(channel_name: str, base_url: str, save_path: str, token: str = None):
    print(f"INFO: Starting to process channel {channel_name}")
    gen = matterbridge_api_listener(base_url, token)
    await process_chat(channel_name, gen, save_path)


async def main() -> int:
    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'save_path' not in config['server']:
        config['server']['save_path'] = './logs'

    try:
        async with asyncio.TaskGroup() as tg:
            for section in config.sections():
                if section[0:8] != "channel.":
                    continue
                channel_name = section[8:]
                base_url = config[section]['base_url']
                token = config[section].get('token', None)
                save_path = os.path.join(
                    config['server']['save_path'], channel_name)
                tg.create_task(
                    process(channel_name, base_url, save_path, token))
    except asyncio.CancelledError:
        print("INFO: Interrupted by user")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
