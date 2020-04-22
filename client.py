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
    start = time.perf_counter()
    for i in range(1000):
        # logger.info(f"client {i} initial...")
        client = socketio.AsyncClient()
        await test_connect(client)
        await test_leave(client)
        await test_reconnect()

    logger.debug(f"clients count {len(clients)}")

    elapsed = time.perf_counter() - start
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
    # await asyncio.sleep(3)


async def test_connect(client):
    # await asyncio.sleep(1 / 500)
    await client.connect("http://localhost:8110")
    clients.append(client)


async def test_leave(client):
    number = random.randint(0, 9)
    if number < 3:
        await client.disconnect()
        clients.remove(client)
        disconnect_clients.append(client)


async def test_reconnect():
    number = random.randint(0, 50)
    total = len(disconnect_clients)
    if number <= 2 and total > 0:
        client = random.choice(disconnect_clients)
        await client.connect("http://localhost:8110")
        disconnect_clients.remove(client)
        clients.append(client)


if __name__ == "__main__":
    # task
    loop.create_task(test_server())
    loop.run_forever()
