from aiohttp import web
import socketio
from loguru import logger

# ulimit -n 4096

sio = socketio.AsyncServer(async_mode="aiohttp")
# sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

clients = set()

connect_count = 0
disconnect_count = 0


@sio.event
async def connect(sid, environ):
    clients.add(sid)
    global connect_count
    connect_count += 1
    logger.debug("connect ", sid)
    logger.debug(f"已连接 {len(clients)}")


@sio.event
async def disconnect(sid):
    clients.remove(sid)
    global disconnect_count
    disconnect_count += 1
    print("disconnect ", sid)
    logger.debug(f"剩余 clients 数量: {len(clients)}")


@sio.event
async def stat():
    logger.info(f"connect count {connect_count}")
    logger.info(f"disconnect count {disconnect_count}")
    logger.debug(f"exit: 剩余 clients 数量: {len(clients)}")


if __name__ == "__main__":
    try:
        web.run_app(app, port=8110)
    finally:
        logger.info(f"connect count {connect_count}")
        logger.info(f"disconnect count {disconnect_count}")
        logger.debug(f"exit: 剩余 clients 数量: {len(clients)}")
