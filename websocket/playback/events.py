import socketio
import aiohttp
import time
import random
import string
import hashlib
import aioredis
import asyncio
from loguru import logger
from simple_settings import settings
from websocket import status_code as error_code


# 基于类的名称空间
class PlayBackNamespace(socketio.AsyncNamespace):
    # init flag
    _init_redis = False
    redis_address = (settings.REDIS_HOST, settings.REDIS_PORT)

    async def init_redis(self):
        self.sid_user_playback = await aioredis.create_redis_pool(self.redis_address, db=3, encoding="utf-8")

    # ------------ utils ---------------
    def get_callback_signature(self):
        """
        请求后端回调秘钥
        :return: 加密后字典
        """
        timestamp = int(time.time())
        nonce = "".join(random.SystemRandom().choice(string.digits) for _ in range(6))
        secret = "71347c514224cf29c78abb39090e32be"
        # secret = callback_key
        tmpli = [secret, str(timestamp), str(nonce)]
        tmpli.sort()
        tmpstr = "".join(tmpli)
        tmpstr = hashlib.sha1(tmpstr.encode("utf-8"))
        tmpsign = tmpstr.hexdigest()
        return {"nonce": nonce, "timestamp": timestamp, "signature": tmpsign}

    async def duplicate_join_check(self, room_id: str, user_id: str) -> bool:
        """
        重复连接检测
        :param room_id: 用户id
        :param user_id: 房间号
        :return:
        """
        user_exists = await self.sid_user_playback.hexists(room_id, user_id)
        return user_exists

    async def update_user_join_info(self, sid, user_id, room_id, playback_data_id):
        """
        更新用户连接数据信息
        :param sid:
        :param user_id:
        :param room_id:
        :param playback_data_id:
        :return:
        """
        open_time = int(time.time())
        await self.sid_user_playback.hset(room_id, user_id, sid)
        await self.sid_user_playback.hset(sid, "user_id", user_id)
        await self.sid_user_playback.hset(sid, "room_id", room_id)
        await self.sid_user_playback.hset(sid, "playback_data_id", playback_data_id)
        await self.sid_user_playback.hset(sid, "open_time", open_time)

    async def update_user_disconnect_info(self, sid):
        """
        更新用户断开连接数据信息
        :param sid:
        :return:
        """
        user_id = await self.sid_user_playback.hget(sid, "user_id")
        room_id = await self.sid_user_playback.hget(sid, "room_id")
        playback_data_id = await self.sid_user_playback.hget(sid, "playback_data_id")
        open_time = await self.sid_user_playback.hget(sid, "open_time")
        logger.info(f"values: {user_id} {room_id} {playback_data_id} {open_time}")
        # 参数校验
        if user_id and room_id and playback_data_id and open_time:
            open_time = int(open_time)
        else:
            logger.info(f"异常退出 {sid}")
            logger.info(f"values: {user_id} {room_id} {playback_data_id} {open_time}")
        self.leave_room(sid, room_id)
        signature_dict = self.get_callback_signature()
        close_time = int(time.time())
        if close_time - open_time > 0:
            signature_dict.update(
                {
                    "user_id": user_id,
                    "room_id": room_id,
                    "playback_data_id": playback_data_id,
                    "open_time": open_time,
                    "close_time": close_time,
                    "duration": close_time - open_time,
                }
            )
            await self.update_data(signature_dict)
            await self.sid_user_playback.delete(sid)
            await self.sid_user_playback.hdel(room_id, user_id)

    async def update_data(self, data):
        """
        异步发送数据更新请求
        :param data: 更新数据包
        :return:
        """
        # 本地测试
        # url = 'http://0.0.0.0:8800/appplayback/user_playback_update/'
        # 测试服务器端
        url = "http://beta.yingliboke.cn/api/appplayback/user_playback_update/"
        # 服务器端
        # url = 'https://www.yingliboke.cn/api/appplayback/user_playback_update/'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    print(resp.status)
                    res = await resp.json()
                    assert res["code"] == 20000
                    logger.info("更新回放数据成功")
        except Exception as ex:
            logger.exception(ex)

    # ------------ events --------------
    async def on_connect(self, sid, environ):
        # 回放类的连接回调
        if self._init_redis is False:
            await self.init_redis()
        await self.emit("system", {"msg": "服务器回调：连接回放服务器成功"}, room=sid)
        logger.info("%s 接入回放服务器成功" % sid)

    async def on_join(self, sid, data):
        # 加入房间异步化
        room_id = data.get("room_id", None)
        user_id = data.get("user_id", None)
        playback_data_id = data.get("playback_data_id", None)
        # 参数检测
        if room_id is None or user_id is None or playback_data_id is None:
            await self.emit("system", {"code": error_code.PARAMETER_IS_NOT_COMPLETE, "msg": "加入房间失败,参数错误"})
            logger.info("加入房间失败,参数错误")
            await self.disconnect(sid)

        # 重连检测
        user_exists = await self.duplicate_join_check(room_id, user_id)
        logger.info("判定重连 %s 通过" % user_exists)
        if user_exists:
            sid2 = await self.sid_user_playback.hget(room_id, user_id)
            if sid != sid2:
                await self.disconnect(sid2)
                logger.info("判定重连，结束前置连接{}".format(sid2))
            await self.update_user_join_info(sid, user_id, room_id, playback_data_id)
            self.enter_room(sid, room_id)
            await self.emit(
                "system", {"code": 20000, "msg": "服务器重复链接回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id)}, room=sid
            )
            logger.info("服务器重复链接回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id))
        else:
            await self.update_user_join_info(sid, user_id, room_id, playback_data_id)
            self.enter_room(sid, room_id)
            await self.emit(
                "system", {"code": 20000, "msg": "服务器回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id)}, room=sid
            )
            logger.info("服务器回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id))

    async def on_leave(self, sid):
        # 基于类的离开房间
        user_id = await self.sid_user_playback.hget(sid, "user_id")
        room_id = await self.sid_user_playback.hget(sid, "room_id")
        if user_id and room_id:
            await self.emit("system", {"msg": "用户-<{}>-从回放房间-<{}>离开".format(user_id, room_id)}, room=sid)
            logger.info("用户-<{}>-从回放房间-<{}>离开".format(user_id, room_id))
            await self.disconnect(sid)
        else:
            await self.disconnect(sid)

    async def on_disconnect(self, sid):
        # 基于类的断开连接回调
        await asyncio.shield(self.update_user_disconnect_info(sid))
