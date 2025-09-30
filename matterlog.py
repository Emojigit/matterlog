from typing import Generator
from datetime import datetime, timezone, timedelta
import os
import re
import signal

import configparser
import asyncio
import aiofiles
import aiohttp

time_regex = re.compile(
    r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)([+-])(\d{2}):(\d{2})')


async def matterbridge_api_listener(base_url: str, sleep_time: int, token: str = None) -> Generator[dict, None, None]:
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
            await asyncio.sleep(sleep_time)


async def process_chat(channel_name: str, messages_generator: Generator[dict, None, None], save_path: str):
    async for message in messages_generator:
        username = message["username"]
        text = message["text"]
        # 2025-09-27T11:58:59.936761682-04:00
        timestamp_raw = message["timestamp"]
        timestamp_matches = time_regex.match(timestamp_raw)
        if not timestamp_matches:
            print(f"WARNING: Invalid timestamp format: {timestamp_raw}")
            continue
        tz = timezone((-1 if timestamp_matches[8] == '-' else 1) * timedelta(
            hours=int(timestamp_matches[9]),
            minutes=int(timestamp_matches[10])))
        time = datetime(
            year=int(timestamp_matches[1]),
            month=int(timestamp_matches[2]),
            day=int(timestamp_matches[3]),
            hour=int(timestamp_matches[4]),
            minute=int(timestamp_matches[5]),
            second=int(timestamp_matches[6]),
            microsecond=int(timestamp_matches[7][0:6]),
            tzinfo=tz
        ).astimezone(timezone.utc)
        year, month, day = time.year, time.month, time.day

        logfile_dir = f"{save_path}/{year:04d}/{month:02d}"
        logfile_path = f"{logfile_dir}/{day:02d}.txt"

        os.makedirs(logfile_dir, exist_ok=True)
        async with aiofiles.open(logfile_path, "a", encoding="utf-8") as logfile:
            for line in text.splitlines():
                await logfile.write(f"{time.isoformat()}\t{username}\t{line}\n")

        print(f"INFO: {time.isoformat()} #{channel_name} <{username}>: {text}")


async def process(channel_name: str, base_url: str, save_path: str, sleep_time: int, token: str = None):
    print(f"INFO: Starting to process channel {channel_name}")
    gen = matterbridge_api_listener(base_url, sleep_time, token)
    try:
        await process_chat(channel_name, gen, save_path)
    except asyncio.exceptions.CancelledError:
        print(f"INFO: Stopping processing channel {channel_name}")


async def shutdown(sig, tasks):  # https://stackoverflow.com/a/79612074/12805899
    print(f"Caught signal: {sig.name}")
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    print("Shutdown complete.")


async def main() -> int:
    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'save_path' not in config['server']:
        config['server']['save_path'] = './logs'

    sleep_time = int(config['server'].get('sleep_time', '5'))

    loop = asyncio.get_running_loop()
    tasks = []
    for section in config.sections():
        if section[0:8] != "channel.":
            continue
        channel_name = section[8:]
        base_url = config[section]['base_url']
        token = config[section].get('token', None)
        save_path = os.path.join(
            config['server']['save_path'], channel_name)
        tasks.append(loop.create_task(
            process(channel_name, base_url, save_path, sleep_time, token)))

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s,
                                lambda s=s: asyncio.create_task(shutdown(s, tasks)))
    await asyncio.gather(*tasks)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
