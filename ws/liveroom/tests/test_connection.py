# -*- coding: utf-8 -*-
import asyncio
import time
import random
import socketio
from loguru import logger

loop = asyncio.get_event_loop()


times = []
room_ids = ["235947"]


def stat():
    logger.info("----- current room count -----")
    logger.debug(f"{len(times)}")

    logger.info("----- fastest time -----")
    logger.debug(f"{min(times):0.5f}")
    logger.info("----- slowest time -----")
    logger.debug(f"{max(times):0.5f}")
    logger.info("----- average time -----")
    logger.debug(f"{(sum(times) / len(times)):0.5f}")


async def test_server(number):
    """
    ipython for test
    """

    # ulimit -n 4096 , 247
    tasks = []

    for uid in range(1, number + 1):
        tasks.append(test(uid))

    start = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    # stat
    stat()

    print(f"{__file__} executed in {elapsed:0.2f} seconds.")


async def test(uid):
    client = socketio.AsyncClient(request_timeout=60)
    # room_id = random.choice(room_ids)
    room_id = "235947"
    await test_join(client, uid, room_id)


async def test_join(client, uid, room_id):

    wait = int(uid / 1000)
    await asyncio.sleep(wait)

    try:
        t1 = time.perf_counter()
        # await client.connect(
        #     "ws://127.0.0.1:8200", namespaces=["/liveroom"], headers={"Host": "socketio.yingliboke.cn"}
        # )
        await client.connect("ws://127.0.0.1:8200")
        t2 = time.perf_counter() - t1
        times.append(t2)
        logger.info(f"test_join executed in {t2:0.2f} seconds.")
    except Exception as ex:
        logger.error(f"failed to join {client.sid}: {ex}")


if __name__ == "__main__":
    # task
    number = int(input("set the number of clients:"))
    # loop.create_task(test_server(number))
    # loop.run_forever()
    loop.run_until_complete(test_server(number))
