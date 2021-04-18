# -*- coding: utf-8 -*-
import argparse
import asyncio
import os
import time

from aiohttp import ClientSession
from loguru import logger


"""
Parser
"""

parser = argparse.ArgumentParser(description="Benchmark a WebSocket server")
parser.add_argument(
    "--h",
    dest="host",
    help="Host address of WebSocket server",
    default="127.0.0.1:8200",
)
parser.add_argument(
    "--n", dest="clients", help="Number of clients to create", default=1000, type=int
)
parser.add_argument(
    "--c", dest="concurrency", help="Number of concurrent clients", default=64, type=int
)
parser.add_argument(
    "--r", dest="roundtrips", help="Roundtrips per client", default=5, type=int
)
parser.add_argument(
    "--s", dest="msg_size", help="Message size in characters", default=30, type=int
)
parser.add_argument(
    "--l",
    dest="log_path",
    help="Path to create or append to a log file",
    default=os.path.join(".", "log.txt"),
)
args = parser.parse_args()

# get benchmark parameters
host = args.host
clients = args.clients
concurrency = args.concurrency
roundtrips = args.roundtrips
message = "a" * args.msg_size


async def test_server(number):
    """
    ipython for test
    """

    tasks = []

    for uid in range(1, number + 1):
        tasks.append(test(uid))

    await asyncio.gather(*tasks)


async def test(uid):
    client = ClientSession()
    await test_join(client, uid)


async def test_join(client, uid):

    try:
        async with client.ws_connect("http://127.0.0.1:8200/ws") as ws:
            await ws.send_json(
                {"action": "join", "data": {"room": "235947", "uid": uid}}
            )
            data = await ws.receive()
            print(data)

        await client.close()
    except Exception as ex:
        logger.error(f"{uid} failed to join, reason: {ex}")


if __name__ == "__main__":
    # task
    number = int(input("set the number of clients:"))
    loop = asyncio.get_event_loop()
    # loop.create_task(test_server(number))
    # loop.run_forever()
    loop.run_until_complete(test_server(number))
