import asyncio
import time
import random
import socketio
from loguru import logger

loop = asyncio.get_event_loop()

clients = []
disconnect_clients = []


async def test_server():
    """
    ipython for test
    """

    # ulimit -n 4096 , 247
    tasks = []
    start = time.perf_counter()
    # semaphore = asyncio.Semaphore(50)
    for _ in range(1000):
        tasks.append(test())
        # tasks.append(test(semaphore))

    await asyncio.gather(*tasks)
    logger.debug(f"clients count {len(clients)}")

    elapsed = time.perf_counter() - start
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
    # await asyncio.sleep(3)


async def test():
    client = socketio.AsyncClient()
    await test_connect(client)
    await test_leave(client)
    await test_reconnect()


async def test_with_semaphore(semaphore):
    client = socketio.AsyncClient()
    async with semaphore:
        await test_connect(client)
        await test_leave(client)
        await test_reconnect()


async def test_connect(client):
    # await asyncio.sleep(1 / 500)
    try:
        await client.connect("http://localhost:8110")
        clients.append(client)
    except Exception:
        logger.error(f"failed to connect {id(client)}")


async def test_leave(client):
    number = random.randint(0, 9)
    if number < 3:
        try:
            await client.disconnect()
            clients.remove(client)
            disconnect_clients.append(client)
        except Exception:
            logger.error(f"failed to leave {id(client)}")


async def test_reconnect():
    number = random.randint(0, 50)
    total = len(disconnect_clients)
    if number <= 2 and total > 0:
        try:
            client = random.choice(disconnect_clients)
            await client.connect("http://localhost:8110")
            disconnect_clients.remove(client)
            clients.append(client)
        except Exception:
            logger.error(f"failed to reconnect {id(client)}")


if __name__ == "__main__":
    # task
    # loop.create_task(test_server())
    # loop.run_forever()
    loop.run_until_complete(test_server())
