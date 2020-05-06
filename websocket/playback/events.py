import socketio
import aiohttp
import time
import json
import requests
import random
import string
import hashlib
import logging
import redis
from websocket import status_code as error_code

logger = logging.getLogger(__name__)

log = print
# sid回放用户信息库
sid_user_playback = redis.Redis(host="localhost", port=6379, decode_responses=True, db=3)


# 基于类的名称空间


class PlayBackNamespace(socketio.AsyncNamespace):
    async def on_connect(self, sid, environ):
        # 回放类的连接回调
        await self.emit("system", {"msg": "服务器回调：连接回放空间成功"}, room=sid)

    async def on_join(self, sid, data):
        # 加入房间异步化
        # 基于类的加入房间
        room_id = data.get("room_id", "")
        user_id = data.get("user_id", "")
        playback_data_id = data.get("playback_data_id", "")
        if room_id and user_id and playback_data_id:
            ret = self.join_room_check(room_id, user_id, sid)
            logger.info(ret)
            # 异常情况
            if ret["type"] == 0:
                await self.emit("system", {"code": error_code.JPIN_PLAYBACK_ROOM_ERROR, "msg": "加入房间失败"}, room=sid)
                logger.info("加入房间失败")
                await self.disconnect(sid)
            # 正常建立链接
            elif ret["type"] == 1:
                try:
                    open_time = int(time.time())
                    # 将用户信息存入redis中
                    sid_user_playback.hset(sid, "user_id", user_id)
                    sid_user_playback.hset(sid, "room_id", room_id)
                    sid_user_playback.hset(sid, "playback_data_id", playback_data_id)
                    sid_user_playback.hset(sid, "open_time", open_time)

                    # 进入指定的房间
                    self.enter_room(sid, room_id)
                    log("用户-<{}>加入回放房间".format(user_id))
                    await self.emit(
                        "system",
                        {"code": 20000, "msg": "服务器回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id)},
                        room=sid,
                    )
                    logger.info("用户-<{}>加入回放房间".format(user_id))
                except Exception as ex:
                    logger.exception(ex)
                    await self.disconnect(sid)
            # 建立重复链接
            elif ret["type"] == 2:
                print("建立重复链接", int(time.time()))
                logger.info("建立重复链接", int(time.time()))
                print("新连接", sid)
                logger.info("新连接", sid)
                sid2 = sid_user_playback.hget(room_id, user_id)
                print("旧连接", sid2)
                logger.info("旧连接", sid2)
                if sid != sid2:
                    # 断开前置链接
                    await self.disconnect(sid2)
                open_time = int(time.time())
                # 将用户信息存入redis中
                sid_user_playback.hset(sid, "user_id", user_id)
                sid_user_playback.hset(sid, "room_id", room_id)
                sid_user_playback.hset(sid, "playback_data_id", playback_data_id)
                sid_user_playback.hset(sid, "open_time", open_time)
                # 进入指定的房间
                self.enter_room(sid, room_id)
                await self.emit(
                    "system",
                    {"code": 20000, "msg": "服务器重复链接回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id)},
                    room=sid,
                )
                logger.info("服务器重复链接回调：用户-<{}>进入回放房间-<{}>成功".format(user_id, room_id))

        else:
            await self.emit("system", {"msg": "加入房间失败"})
            logger.info("加入房间失败")
            await self.disconnect(sid)

    async def on_disconnect(self, sid):
        # 基于类的断开连接回调,获取存储的上下文消息
        user_id = sid_user_playback.hget(sid, "user_id")
        room_id = sid_user_playback.hget(sid, "room_id")
        playback_data_id = sid_user_playback.hget(sid, "playback_data_id")
        open_time = sid_user_playback.hget(sid, "open_time")
        if open_time:
            open_time = int(open_time)
        if room_id and user_id and playback_data_id and open_time:
            self.leave_room(sid, room_id)
            # 向后端进行请求
            signature_dict = self.get_callback_signature()
            close_time = int(time.time())
            print("更新数据", int(time.time()))
            logger.info("更新数据", int(time.time()))
            # 本地测试
            # url = 'http://0.0.0.0:8800/appplayback/user_playback_update/'
            # 测试服务器端
            url = "http://beta.yingliboke.cn/api/appplayback/user_playback_update/"
            # 服务器端
            # url = 'https://www.yingliboke.cn/api/appplayback/user_playback_update/'
            # 确切有观看时长才统计
            if close_time - open_time > 0:
                data = {
                    "user_id": user_id,
                    "room_id": room_id,
                    "playback_data_id": playback_data_id,
                    "open_time": open_time,
                    "close_time": close_time,
                    "duration": close_time - open_time,
                    "nonce": signature_dict["nonce"],
                    "timestamp": signature_dict["timestamp"],
                    "signature": signature_dict["signature"],
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=data) as resp:
                        print(resp.status)
                        res = await resp.json()
                        if res["code"] == 20000:
                            log("更新回放数据成功")
                        else:
                            log(res["msg"])
            print(room_id, user_id)
            logger.info(room_id, user_id)
            sid_user_playback.hdel(room_id, user_id)
            log("用户-<{}>-从回放房间-<{}>断开".format(user_id, room_id))
        else:
            log("sid-<{}>-断开".format(sid))
        # 从sid库中删除
        sid_user_playback.delete(sid)

    async def on_leave(self, sid):
        # 基于类的离开房间
        user_id = sid_user_playback.hget(sid, "user_id")
        room_id = sid_user_playback.hget(sid, "room_id")
        await self.emit("system", {"msg": "用户-<{}>-从回放房间-<{}>离开".format(user_id, room_id)}, room=sid)
        logger.info("用户-<{}>-从回放房间-<{}>离开".format(user_id, room_id))
        await self.disconnect(sid)

    def join_room_check(self, room_id, user_id, sid):
        # 是否可以进入房间
        ret = {"type": 0, "msg": ""}
        """
        0:拒绝进入，
        1:可以进入，
        2:建立重复链接，断开旧连接，进入新连接
        """
        if sid_user_playback.hexists(room_id, user_id):
            ret["type"] = 2
            ret["msg"] = "重复链接，结束前置链接"
            return ret
        else:
            sid_user_playback.hset(room_id, user_id, sid)
            ret["type"] = 1
            ret["msg"] = "建立连接"
            return ret

    def get_callback_signature(self):
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
