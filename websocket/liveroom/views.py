from socketio import AsyncNamespace
from loguru import logger


class LiveNamespace(AsyncNamespace):
    clients = set()

    def on_connect(self, sid, environ):
        self.clients.add(sid)
        logger.info("connect ", sid)

    def on_disconnect(self, sid):
        self.clients.remove(sid)
        logger.info("disconnect ", sid)

    async def on_people_count(self, sid, data):
        logger.info(f"{len(self.clients)}")
        await self.emit("people_count", {len(self.clients)})
