# -*- coding: utf-8 -*-
import asyncio
import time
import random
import socketio
import numpy as np
from loguru import logger
from scipy.special import erfinv

loop = asyncio.get_event_loop()


clients = []
join_clients = []
leave_clients = []
disconnect_clients = []
reconnect_clients = []
fail_connect = 0
fail_join = 0
fail_leave = 0
fail_disconnect = 0
fail_reconnect = 0

# room_ids = ["100000", "100001", "100002", "100003", "100004", "100005"]
rooms = {
    "235947": 0,
    "548589": 0,
    "106779": 0,
    "325485": 0,
    "169226": 0,
    "844030": 0,
}
# room_ids = ["235947", "548589", "106779", "325485", "169226", "844030"]
room_ids = ["235947"]


def stat():
    logger.info(f"clients count {len(clients)}")
    logger.info(f"join clients count {len(join_clients)}")
    logger.info(f"leave clients count {len(leave_clients)}")
    logger.info(f"disconnect clients count {len(disconnect_clients)}")
    logger.info(f"reconnect clients count {len(reconnect_clients)}")

    logger.info(f"fail connect count {fail_connect}")
    logger.info(f"fail connect count {fail_join}")
    logger.info(f"fail leave count {fail_leave}")
    logger.info(f"fail connect count {fail_disconnect}")
    logger.info(f"fail reconnect count {fail_reconnect}")

    total = len(clients) + len(disconnect_clients) + fail_connect
    logger.debug(f"total connect count {total}")

    logger.info("----- current room count -----")
    logger.debug(f"{rooms}")


def boxmullersampling(mu=3, sigma=1, size=1):
    u = np.random.uniform(size=size)
    v = np.random.uniform(size=size)
    z = np.sqrt(-2 * np.log(u)) * np.cos(2 * np.pi * v)
    return mu + z * sigma


async def test_server(number):
    """
    ipython for test
    """

    # ulimit -n 4096 , 247
    tasks = []
    start = time.perf_counter()

    for uid in range(1, number+1):
        tasks.append(test(uid))

    await asyncio.gather(*tasks)

    # stat
    stat()

    elapsed = time.perf_counter() - start
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
    # await asyncio.sleep(3)


async def test(uid):
    client = socketio.AsyncClient()
    room_id = random.choice(room_ids)
    await test_user(client, uid, room_id)


async def test_user(client, uid, room_id):
    # wait time
    wait = abs(boxmullersampling()[0])
    await asyncio.sleep(wait)

    # join
    await test_join(client, uid, room_id)


async def test_join(client, uid, room_id):
    t1 = time.perf_counter()

    try:
        # await asyncio.sleep(random.randint(1, 5))
        # await client.connect("ws://beta.yingliboke.cn:2345/", namespaces=["/live_socket"])
        await client.connect("ws://127.0.0.1", namespaces=["/live_socket"], headers={'Host': 'socketio.yingliboke.cn'})
        await client.emit("join", {"room": room_id, "user_id": uid}, namespace="/live_socket")
        clients.append(client.sid)
        join_clients.append(client.sid)
        rooms[room_id] += 1
    except Exception as ex:
        global fail_join
        fail_join += 1
        logger.error(f"failed to join {client.sid}: {ex}")

    t2 = time.perf_counter() - t1
    logger.info(f"test_join executed in {t2:0.2f} seconds.")


if __name__ == "__main__":
    # task
    number = int(input('set the number of clients:'))
    loop.create_task(test_server(number))
    loop.run_forever()
    # loop.run_until_complete(test_server())
