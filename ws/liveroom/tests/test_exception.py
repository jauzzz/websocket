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
exception_count = 0
reconnect_join_count = 0

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

    logger.info(f"exception_count is {exception_count}")
    logger.info(f"reconnect_join_count is {reconnect_join_count}")

    logger.info(f"fail connect count {fail_connect}")
    logger.info(f"fail join count {fail_join}")
    logger.info(f"fail leave count {fail_leave}")
    logger.info(f"fail disconnect count {fail_disconnect}")
    logger.info(f"fail reconnect count {fail_reconnect}")

    total = len(clients) + len(disconnect_clients) + fail_connect
    logger.debug(f"total connect count {total}")
    logger.debug(f"total exception count {exception_count / 5}")
    logger.debug(f"total exception and reconnect count {reconnect_join_count / 5}")

    logger.info("----- current room count -----")
    logger.debug(f"{rooms}")


def boxmullersampling(mu=0.5, sigma=0.1, size=1):
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

    for uid in range(number):
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
    wait = boxmullersampling()[0]
    await asyncio.sleep(wait)

    # join
    await test_join(client, uid, room_id)

    if uid % 3 == 0:
        await test_exception(client, uid, room_id, exception_time=5)


async def test_join(client, uid, room_id):
    try:
        await asyncio.sleep(0.01)
        # await client.connect("ws://beta.yingliboke.cn:2345/", namespaces=["/live_socket"])
        await client.connect("ws://127.0.0.1:2345/", namespaces=["/live_socket"])
        await client.emit("join", {"room_id": room_id, "user_id": uid}, namespace="/live_socket")
        logger.info(f"sid({client.sid}), uid({uid}), room_id({room_id})")
        clients.append(client.sid)
        join_clients.append(client.sid)
        rooms[room_id] += 1
    except Exception as ex:
        global fail_join
        fail_join += 1
        logger.error(f"failed to join {client.sid}: {ex}")


async def test_disconnect(client, room_id):
    try:
        await asyncio.sleep(9)
        clients.remove(client.sid)
        disconnect_clients.append(client.sid)
        await client.disconnect()
        rooms[room_id] -= 1
    except Exception as ex:
        global fail_disconnect
        fail_disconnect += 1
        logger.error(f"failed to disconnect {client.sid}: {ex}")


async def test_exception(client, uid, room_id, exception_time):
    reconnect_clients.append(client)
    new_client = socketio.AsyncClient()

    try:
        # 断开
        if client.sid in clients:
            await test_disconnect(client, room_id)

        await asyncio.sleep(0.01)

        # 重连
        # 偶重连
        if uid % 2 == 0:
            await asyncio.sleep(9)
            global reconnect_join_count
            reconnect_join_count += 1
            await test_join(new_client, uid, room_id)

    except Exception as ex:
        global fail_reconnect
        fail_reconnect += 1
        logger.error(f"failed to reconnect {client.sid}: {ex}")

    finally:
        # exception loop
        global exception_count
        exception_count += 1

        exception_time -= 1
        if exception_time > 0:
            await test_exception(new_client, uid, room_id, exception_time)


if __name__ == "__main__":
    # task
    number = int(input("set the number of clients:"))
    loop.create_task(test_server(number))
    loop.run_forever()
    # loop.run_until_complete(test_server())
