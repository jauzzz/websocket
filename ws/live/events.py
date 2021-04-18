import asyncio
import queue
import time

import aioredis
from loguru import logger
from simple_settings import settings
from socketio import AsyncNamespace


class LiveRoomNamespace(AsyncNamespace):

    # redis keyname pattern
    system_limit_keyname = "total_limit"
    room_limit_keyname = "%s_limit"

    normal_room_count_keyname = "%s_normal_count"
    watch_room_count_keyname = "%s_watch_count"
    lua_room_count_keyname = "%s_lua_count"
    asyncio_room_count_keyname = "%s_asyncio_count"
    queue_room_count_keyname = "%s_queue_count"

    locks = {}
    queues = {}

    _init_redis = False

    # ------------ init ------------
    async def init_redis(self):
        try:
            self.connect_user = await aioredis.create_redis_pool(
                (settings.REDIS_HOST, settings.REDIS_PORT),
                db=1,
                encoding="utf-8",
                maxsize=4,
            )
            self._init_redis = True
        except Exception as ex:
            logger.error(ex)

    # ------------ util ------------
    def get_room_max_people(self, room_id):
        return 1800

    # ------------ redis cas ------------
    async def asyncio_join(self, sid, uid, room_id):
        if room_id not in self.locks:
            self.locks[room_id] = asyncio.Lock()

        async with self.locks[room_id]:
            room_key = self.asyncio_room_count_keyname % room_id
            max_count = self.get_room_max_people(room_id)

            await self.connect_user.setnx(room_key, 0)
            count = int(await self.connect_user.get(room_key))

            if count < max_count:
                count = count + 1
                await self.connect_user.incr(room_key)
                logger.info(f"房间人数 {count}")

        return count

    async def normal_join(self, sid, uid, room_id):
        """ 最直观的 join """

        room_key = self.normal_room_count_keyname % room_id
        max_count = self.get_room_max_people(room_id)

        # test and set
        await self.connect_user.setnx(room_key, 0)
        count = int(await self.connect_user.get(room_key))

        if int(count) < max_count:
            count = count + 1
            await self.connect_user.incr(room_key)
            logger.info(f"房间人数 {count}")

        return count

    async def watch_join(self, sid, uid, room_id):
        room_key = self.watch_room_count_keyname % room_id
        max_count = self.get_room_max_people(room_id)

        await self.connect_user.setnx(room_key, 0)
        pipe = self.connect_user.pipeline()

        try:
            pipe.watch(room_key)
            count = await self.connect_user.get(room_key)
            if int(count) < max_count:
                current_count = await self.connect_user.get(room_key)
                logger.info(f"房间人数 {current_count}")
                pipe.multi_exec()
                count = pipe.incr(room_key)
                await pipe.execute()
        except aioredis.WatchVariableError:
            logger.error("需要重试")
        except Exception as ex:
            pipe.reset()
            logger.error(f"错误 {ex}")
        finally:
            return count

    async def lua_join(self, sid, uid, room_id):
        room_key = self.lua_room_count_keyname % room_id
        max_count = self.get_room_max_people(room_id)

        await self.connect_user.setnx(room_key, 0)

        script = """
            local room = ARGV[1]
            local limit = tonumber(ARGV[2])

            local count = tonumber(redis.call("GET", room) or "0")
            if (count < limit) then
                redis.call("INCRBY", room, 1)
                return count + 1
            else
                return 0
            end
        """

        return await self.connect_user.eval(
            script, keys=["room_key", "max_count"], args=[room_key, max_count]
        )

    async def queue_join(self, sid, uid, room_id):
        room_key = self.queue_room_count_keyname % room_id
        max_count = self.get_room_max_people(room_id)
        await self.connect_user.setnx(room_key, 0)

        if room_id not in self.queues:
            # NOTE: deque 是线程安全的，由 GIL 保证
            self.queues[room_id] = queue.Queue(maxsize=max_count)

        q = self.queues[room_id]

        try:
            q.put_nowait(uid)
            await self.connect_user.incr(room_key)
        except queue.Full:
            await self.emit("system", {"msg": "加入房间失败,参数不全"}, room=sid)
        except Exception as ex:
            logger.error(ex)

    async def zset_join(self, sid, uid, room_id):
        max_count = self.get_room_max_people(room_id)
        logger.info(f"{uid} 加入 zset")
        await self.connect_user.zadd(room_id, time.time(), uid)
        # 维持长度
        await self.connect_user.zremrangebyrank(room_id, max_count, -1)
        # return await self.connect_user.zrank(room_id, uid) < max_count - 1

    # ------------ events ------------
    async def on_connect(self, sid, environ):
        if self._init_redis is False:
            await self.init_redis()
        logger.debug(f"{sid} connected")

    async def on_disconnect(self, sid):
        logger.debug(f"{sid} disconnected")

    async def on_join(self, sid, data):
        room_id = data.get("room_id", None)
        uid = data.get("user_id", None)

        # count = await self.normal_join(sid, uid, room_id)
        # logger.debug(f"{sid} normal joined | 房间人数 {count}")

        # count = await self.watch_join(sid, uid, room_id)
        # logger.debug(f"{sid} watch joined | 房间人数 {count}")

        count = await self.lua_join(sid, uid, room_id)
        logger.debug(f"{sid} lua joined | 房间人数 {count}")

        # count = await self.asyncio_join(sid, uid, room_id)
        # logger.debug(f"{sid} lua joined | 房间人数 {count}")

        # await self.queue_join(sid, uid, room_id)
        # logger.debug(f"{sid} queue joined")

        # await self.zset_join(sid, uid, room_id)
        # logger.debug(f"{sid} zset joined")

    async def on_leave(self, sid, data):
        logger.debug(f"{sid} left")
