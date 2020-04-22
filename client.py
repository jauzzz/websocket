import asyncio
import time
import random
import socketio
from loguru import logger

loop = asyncio.get_event_loop()

# TODO: 信号量限制并发数
sem = asyncio.Semaphore(1000)

clients = []
disconnect_clients = []
reconnect_clients = []
fail_connect = 0
fail_leave = 0
fail_reconnect = 0


def stat():
    logger.info(f"clients count {len(clients)}")
    logger.info(f"disconnect clients count {len(disconnect_clients)}")
    logger.info(f"reconnect clients count {len(reconnect_clients)}")

    logger.info(f"fail connect count {fail_connect}")
    logger.info(f"fail leave count {fail_leave}")
    logger.info(f"fail reconnect count {fail_reconnect}")

    total = len(clients) + len(disconnect_clients) + fail_connect
    logger.debug(f"total connect count {total}")


async def test_server():
    """
    ipython for test
    """

    # ulimit -n 4096 , 247
    tasks = []
    start = time.perf_counter()

    for _ in range(3000):
        tasks.append(test())

    await asyncio.gather(*tasks)

    # stat
    stat()

    elapsed = time.perf_counter() - start
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
    # await asyncio.sleep(3)


async def test():
    client = socketio.AsyncClient()
    await test_connect(client)
    await test_leave(client)
    await test_reconnect()


async def test_with_sem():
    with (await sem):
        client = socketio.AsyncClient()
        await test_connect(client)
        await test_leave(client)
        await test_reconnect()


async def test_connect(client):
    try:
        await client.connect("http://localhost:8110")
        clients.append(client)
    except Exception:
        global fail_connect
        fail_connect += 1
        logger.error(f"failed to connect {id(client)}")


async def test_leave(client):
    number = random.randint(0, 9)
    if number < 3:
        try:
            await client.disconnect()
            clients.remove(client)
            disconnect_clients.append(client)
        except Exception:
            global fail_leave
            fail_leave += 1
            logger.error(f"failed to leave {id(client)}")


async def test_reconnect():
    number = random.randint(0, 50)
    if number <= 2:
        try:
            client = socketio.AsyncClient()
            await client.connect("http://localhost:8110")
            reconnect_clients.append(client)
        except Exception:
            global fail_reconnect
            fail_reconnect += 1
            logger.error(f"failed to reconnect {id(client)}")


if __name__ == "__main__":
    # task
    # loop.create_task(test_server())
    # loop.run_forever()
    loop.run_until_complete(test_server())
