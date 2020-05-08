import asyncio
import json
import requests
import time
import random
import string
import hashlib
import aioredis
from socketio import AsyncNamespace
from simple_settings import settings
from websocket import status_code as error_code
from loguru import logger


class LiveRoomNamespace(AsyncNamespace):

    # stat count
    connect_count = 0
    disconnect_count = 0
    join_count = 0
    leave_count = 0
    success_join_count = 0
    success_leave_count = 0

    # redis keyname
    system_limit_keyname = "total_limit"
    room_limit_keyname = "%s_limit"

    # init flag
    _init_redis = False

    async def init_redis(self):
        try:
            self.disconnect_user = await aioredis.create_redis_pool(
                (settings.REDIS_HOST, settings.REDIS_PORT), db=0, encoding="utf-8"
            )
            self.connect_user = await aioredis.create_redis_pool(
                (settings.REDIS_HOST, settings.REDIS_PORT), db=1, encoding="utf-8", minsize=1, maxsize=1
            )
            self.sid_user_live = await aioredis.create_redis_pool(
                (settings.REDIS_HOST, settings.REDIS_PORT), db=2, encoding="utf-8"
            )
            self._init_redis = True
        except Exception as ex:
            logger.error(ex)

    # ------------ stat --------------
    def stat_connect(self, sid):
        # logger.info(f"connecting {sid}")
        self.connect_count += 1

    def stat_disconnect(self, sid):
        # logger.info(f"disconnecting {sid}")
        self.disconnect_count += 1

    def stat_join(self, sid):
        # logger.info(f"joining {sid}")
        self.join_count += 1

    def stat_leave(self, sid):
        # logger.info(f"leaving {sid}")
        self.leave_count += 1
        self.disconnect_count += 1

    def stat_success_join(self, sid, uid, room_id):
        logger.info(f"用户 {uid} 加入房间 {room_id}")
        self.success_join_count += 1

    def stat_success_leave(self, sid, uid, room_id):
        logger.info(f"用户 {uid} 退出房间 {room_id}")
        self.success_leave_count += 1

    # ------------ utils ---------------
    def get_callback_signature(self):
        timestamp = int(time.time())
        nonce = "".join(random.SystemRandom().choice(string.digits) for _ in range(6))
        secret = "71347c514224cf29c78abb39090e32be"
        # secret = 'secret'
        tmpli = [secret, str(timestamp), str(nonce)]
        tmpli.sort()
        tmpstr = "".join(tmpli)
        tmpstr = hashlib.sha1(tmpstr.encode("utf-8"))
        tmpsign = tmpstr.hexdigest()
        return {"nonce": nonce, "timestamp": timestamp, "signature": tmpsign}

    def request_system_limit(self) -> int:
        url = "http://beta.yingliboke.cn/api/livesocket/get_systemsettings_max_limit/"
        headers = {"content-type": "application/json"}
        signature_dict = self.get_callback_signature()
        data = json.dumps(signature_dict)

        res = requests.post(url=url, headers=headers, data=data).json()

        assert res["code"] == 20000
        return res["total_limit"]

    def request_room_limit(self, room_id: str) -> int:
        url = "http://beta.yingliboke.cn/api/livesocket/get_liveroom_package_max_limit/"
        headers = {"content-type": "application/json"}

        signature_dict = self.get_callback_signature()
        signature_dict.update({"room": room_id})
        data = json.dumps(signature_dict)
        res = requests.post(url=url, headers=headers, data=data).json()

        assert res["code"] == 20000
        return res["liveroom_limit_number"]

    async def get_system_limit(self) -> int:
        keyname = self.system_limit_keyname
        if not await self.connect_user.exists(keyname):
            result = self.request_system_limit()
            await self.connect_user.set(keyname, result)
        return await self.connect_user.get(keyname)

    async def get_room_limit(self, room_id: str) -> int:
        pattern = self.room_limit_keyname
        keyname = pattern % room_id
        if not await self.connect_user.exists(keyname):
            result = self.request_room_limit(room_id)
            await self.connect_user.set(keyname, result)
        return await self.connect_user.get(keyname)

    async def get_room_max_user(self, room_id: str) -> int:
        max_user = int(await self.get_system_limit())
        room_max_user = int(await self.get_room_limit(room_id))
        return max(max_user, room_max_user)

    async def get_room_exists_user(self, room_id: str, connect_db) -> int:
        return len(await connect_db.hkeys(room_id))

    async def exceed_max_user_check(self, uid, room_id, connect_db) -> bool:
        """ 超过最大房间人数检测 """
        max_user = await self.get_room_max_user(room_id)
        room_user = await self.get_room_exists_user(room_id, connect_db)

        # for test
        # return False

        logger.info(f"房间 {room_id}: {room_user} 人 | 最大 {max_user}")
        return room_user >= max_user

    async def duplicate_join_check(self, uid, room_id, connect_db) -> bool:
        """ 重复加入房间检测 """
        user_exists = await connect_db.hexists(room_id, uid)
        if user_exists:
            logger.error(f"duplicate join {room_id} {uid}")
        return user_exists

    async def reconnect_join_check(self, uid, room_id) -> bool:
        """ 断线重连检测 """
        keyname = str(room_id) + "_" + str(uid)
        disconnect_exists = await self.disconnect_user.exists(keyname)
        return disconnect_exists

    async def update_user_join_info(self, sid, uid, room_id, leave_tag, connect_db):
        """ 加入房间后，更新用户连接信息 """
        logger.info(f"更新redis信息, 客户端 {sid} 用户 {uid} 加入房间 {room_id}，离开类型 {leave_tag}")
        open_time = int(time.time())
        await connect_db.hset(room_id, uid, sid)
        await self.sid_user_live.hset(sid, "user_id", uid)
        await self.sid_user_live.hset(sid, "room_id", room_id)
        await self.sid_user_live.hset(sid, "leave_tag", leave_tag)
        await self.sid_user_live.hset(sid, "open_time", open_time)

    async def update_user_disconnect_info(self, sid):
        # TODO: 搞清楚 disconnect 是否会自动退出房间
        self.stat_disconnect(sid)
        uid = await self.sid_user_live.hget(sid, "user_id")
        room_id = await self.sid_user_live.hget(sid, "room_id")
        leave_tag = await self.sid_user_live.hget(sid, "leave_tag")
        open_time = await self.sid_user_live.hget(sid, "open_time")

        # 参数校验
        if uid and room_id and leave_tag and open_time:
            leave_tag = int(leave_tag)
            open_time = int(open_time)
        else:
            logger.info(f"异常退出 {sid}")
            logger.info(f"values: {uid} {room_id} {leave_tag} {open_time}")
            self.leave_room(sid, room_id)

        # 判断 leave_tag
        if leave_tag == 1:
            keyname = room_id + "_" + uid
            logger.info(f"网络波动 {sid} 设置keyname {keyname}")
            await self.disconnect_user.set(keyname, uid, expire=60)

        # 正常 disconnect
        if room_id and uid:
            await self.connect_user.hdel(room_id, uid)
            await self.sid_user_live.delete(sid)
            self.leave_room(sid, room_id)

    # ------------ events --------------
    async def on_connect(self, sid, environ):
        if self._init_redis is False:
            await self.init_redis()

        self.stat_connect(sid)
        await self.emit("system", {"code": error_code.SUCCESS, "msg": "服务器回调：连接服务器成功"}, room=sid)

    async def on_disconnect(self, sid):
        # TODO: Check later

        # Important
        # Raise concurrent.futures._base.CancelledError when redis get value
        #
        # See Issue: https://github.com/aio-libs/aiohttp/issues/2168
        # See Issue: https://github.com/aio-libs/aiohttp/issues/2098

        # ----- 方案 1: aiojobs -------
        # Doc: https://github.com/aio-libs/aiojobs
        #
        # scheduler = await aiojobs.create_scheduler()
        # await scheduler.spawn(self.update_user_disconnect_info(sid))
        # await asyncio.sleep(5.0)
        # await scheduler.close()

        # ----- 方案 2: shield -------
        # Doc: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
        await asyncio.shield(self.update_user_disconnect_info(sid))

        # ----- 方案 3: async_armor -------
        # Doc: https://github.com/hellysmile/async_armor
        # from async_armor import armor
        # await armor(self.update_user_disconnect_info(sid))

        # ----------- Explanation ---------
        # 三个方案效果等同，用自带的 shield，没有依赖库

    async def on_join(self, sid, data):
        self.stat_join(sid)

        room_id = data.get("room_id", None)
        uid = data.get("user_id", None)

        # 参数检测
        if room_id is None or uid is None:
            await self.emit("system", {"code": error_code.PARAMETER_IS_NOT_COMPLETE, "msg": "加入房间失败,参数不全"}, room=sid)
            await self.disconnect(sid)

        with await self.connect_user as connect_db:

            # 重复加入检测
            duplicate_flag = await self.duplicate_join_check(uid, room_id, connect_db)
            if duplicate_flag is True:
                await self.emit("system", {"code": error_code.SUCCESS, "msg": "加入房间失败,建立重复链接"}, room=sid)
                await self.disconnect(sid)

            # 最大人数检测
            max_flag = await self.exceed_max_user_check(uid, room_id, connect_db)
            if max_flag is True:
                await self.emit(
                    "system", {"code": error_code.OUT_OF_LIMITE_USER_COUNT, "msg": "加入房间失败,超出最大并发人数限制"}, room=sid
                )
                await self.disconnect(sid)

            # 进入房间（重连、未超过人数正常进入）
            reconnect_flag = await self.reconnect_join_check(uid, room_id)
            if reconnect_flag is True or max_flag is False:
                leave_tag = 1
                self.enter_room(sid, room_id)
                await self.update_user_join_info(sid, uid, room_id, leave_tag, connect_db)
                self.stat_success_join(sid, uid, room_id)
            else:
                logger.error(f"{sid} {uid} {room_id} join failed")

    async def on_leave(self, sid, data):
        self.stat_leave(sid)

        # 获取用户信息
        uid = await self.sid_user_live.hget(sid, "user_id")
        room_id = await self.sid_user_live.hget(sid, "room_id")

        # 标准离开房间
        if room_id and uid:
            await self.sid_user_live.hset(sid, "leave_tag", 2)
            # logger.info(f"用户-<{uid}>-从直播间-<{room_id}>离开")
            await self.emit("system", {"code": error_code.SUCCESS, "msg": f"用户-<{uid}>-从直播间-<{room_id}>离开"}, room=sid)
            await self.disconnect(sid)
            self.stat_success_leave(sid, uid, room_id)
        else:
            logger.error(f"leave error: {sid} room[{room_id}] uid[{uid}]")
            await self.emit("system", {"code": error_code.PARAMETER_IS_NOT_COMPLETE, "msg": "加入房间失败,参数不全"}, room=sid)
