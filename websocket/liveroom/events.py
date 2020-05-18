# -*- coding: utf-8 -*-
import socketio
import aiohttp
import time
import random
import string
import hashlib
import requests
import json
import aioredis
import asyncio
from loguru import logger
from simple_settings import settings
from websocket import status_code as error_code


# 基于类的名称空间
class LiveBaseNamespace(socketio.AsyncNamespace):
    # redis keyname
    system_limit_keyname = "total_limit"
    room_limit_keyname = "%s_limit"
    redis_address = (settings.REDIS_HOST, settings.REDIS_PORT)

    # init flag
    _init_redis = False

    async def init_redis(self):
        # 断开连接链接池
        self.disconnect_user = await aioredis.create_redis_pool(self.redis_address, db=0, encoding="utf-8")
        # 接入连接连接池
        self.connect_user = await aioredis.create_redis_pool(
            self.redis_address, db=1, encoding="utf-8", minsize=1, maxsize=1
        )
        # 用户信息连接池
        self.sid_user_live = await aioredis.create_redis_pool(self.redis_address, db=2, encoding="utf-8")
        self._init_redis = True

    # ------------ utils ---------------
    def get_callback_signature(self):
        """
        请求后端回调秘钥
        :return: 加密后字典
        """
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
        """
        请求系统最大限制人数
        :return: 系统最大限制人数
        """
        # 本地测试
        # url = 'http://192.168.0.100:8000/livesocket/get_systemsettings_max_limit/'
        # 测试服务器
        url = "http://beta.yingliboke.cn/api/livesocket/get_systemsettings_max_limit/"
        # 生产服务器端
        # url = 'https://www.yingliboke.cn/api/livesocket/get_systemsettings_max_limit/'
        headers = {"content-type": "application/json"}
        signature_dict = self.get_callback_signature()
        data = json.dumps(signature_dict)

        res = requests.post(url=url, headers=headers, data=data).json()

        if res["code"] == 20000:
            return res["total_limit"]
        else:
            logger.info("获取系统最大并发失败，原因%s" % res["msg"])
            return 0

    def request_room_limit(self, room_id: str) -> int:
        """
        请求指定直播间限制人数
        :param room_id: 房间号
        :return: 指定直播间限制人数
        """
        # 本地测试
        # url = 'http://192.168.0.100:8000/livesocket/get_liveroom_package_max_limit/'
        # 测试服务器端
        url = "http://beta.yingliboke.cn/api/livesocket/get_liveroom_package_max_limit/"
        # 服务器端
        # url = 'https://www.yingliboke.cn/api/livesocket/get_liveroom_package_max_limit/'
        headers = {"content-type": "application/json"}
        signature_dict = self.get_callback_signature()
        signature_dict.update({"room": room_id})
        data = json.dumps(signature_dict)

        res = requests.post(url=url, headers=headers, data=data).json()
        if res["code"] == 20000:
            return res["liveroom_limit_number"]
        else:
            logger.info("获取指定房间最大并发失败，原因%s" % res["msg"])
            return 0

    async def get_system_limit(self, connect_db) -> int:
        """
        获取系统最大限制人数
        :return: 系统最大限制人数
        """
        logger.info("开始获取系统最大人数限制")
        keyname = self.system_limit_keyname
        if not await connect_db.exists(keyname):
            result = self.request_system_limit()
            await connect_db.set(keyname, result)
        logger.info("获取系统最大限制人数 %s " % await connect_db.get(keyname))
        return await connect_db.get(keyname)

    async def get_room_limit(self, room_id: str, connect_db) -> int:
        """
        获取指定房间最大限制人数
        :param room_id: 房间号
        :return: 指定房间最大限制人数
        """
        logger.info("开始获取指定房间最大人数限制")
        pattern = self.room_limit_keyname
        keyname = pattern % room_id
        if not await connect_db.exists(keyname):
            result = self.request_room_limit(room_id)
            await connect_db.set(keyname, result)
        logger.info("获取指定房间最大限制人数 %s " % await connect_db.get(keyname))
        return await connect_db.get(keyname)

    async def get_system_exists_user(self, connect_db) -> int:
        """
        获取系统全局在线人数
        :return:
        """
        all_sum = 0
        li = await connect_db.hkeys("live_pause_live")
        li2 = [len(await connect_db.hkeys(room_id)) for room_id in li]
        for i in li2:
            all_sum += i
        return all_sum

    async def get_room_exists_user(self, room_id: str, connect_db) -> int:
        """
        获取指定房间在线人数
        :param room_id:
        :param connect_db:
        :return:
        """
        return len(await connect_db.hkeys(room_id))

    async def exceed_max_user_check(self, room_id: str, connect_db) -> bool:
        """
        超过最大房间人数检测
        :param room_id:房间号
        :param connect_db:
        :return:
        """
        logger.info("开始进行人数限制检测")
        total_limit = await self.get_system_limit(connect_db)
        room_limit = await self.get_room_limit(room_id, connect_db)
        all_sum = await self.get_system_exists_user(connect_db)
        room_user = await self.get_room_exists_user(room_id, connect_db)
        logger.info("当前系统总人数{},房间{}人数为{}".format(all_sum, room_id, room_user))
        if (all_sum + 1 <= int(total_limit)) and (room_user + 1 <= int(room_limit)):
            logger.info("判定人数通过")
            return True
        else:
            logger.info("判定人数不通过")
            return False

    async def reconnect_join_check(self, user_id: str, room_id: str, connect_db) -> bool:
        """
        重连检测
        :param user_id: 用户id
        :param room_id: 房间号
        :param connect_db: 连接库
        :return:
        """
        user_exists = await connect_db.hexists(room_id, user_id)
        logger.info("用户{}{}存在房间{}".format(user_id, user_exists, room_id))
        return user_exists

    async def duplicate_join_check(self, user_id: str, room_id: str) -> bool:
        """
        重复连接检测
        :param user_id: 用户id
        :param room_id: 房间号
        :return:
        """
        keyname = str(room_id) + "_" + str(user_id)
        disconnect_exists = await self.disconnect_user.exists(keyname)
        logger.info("用户{}在断开连接db{}存在".format(user_id, disconnect_exists))
        return disconnect_exists

    async def update_user_join_info(self, sid, user_id, room_id, leave_tag, connect_db):
        """
        更新用户连接数据信息
        :param sid:
        :param user_id:
        :param room_id:
        :param leave_tag:
        :param connect_db:
        :return:
        """
        open_time = int(time.time())
        await connect_db.hset(room_id, user_id, sid)
        await self.sid_user_live.hset(sid, "user_id", user_id)
        await self.sid_user_live.hset(sid, "room_id", room_id)
        await self.sid_user_live.hset(sid, "leave_tag", leave_tag)
        await self.sid_user_live.hset(sid, "open_time", open_time)

    async def update_user_disconnect_info(self, sid):
        """
        更新用户断开连接数据信息
        :param sid:
        :return:
        """
        user_id = await self.sid_user_live.hget(sid, "user_id")
        room_id = await self.sid_user_live.hget(sid, "room_id")
        leave_tag = await self.sid_user_live.hget(sid, "leave_tag")
        open_time = await self.sid_user_live.hget(sid, "open_time")

        # 参数校验
        if user_id and room_id and leave_tag and open_time:
            leave_tag = int(leave_tag)
            open_time = int(open_time)
        else:
            logger.info(f"异常退出 {sid}")
            logger.info(f"values: {user_id} {room_id} {leave_tag} {open_time}")
            self.leave_room(sid, room_id)

        # 判断 leave_tag
        if leave_tag == 1:
            keyname = room_id + "_" + user_id
            logger.info("网络波动")
            await self.disconnect_user.set(keyname, user_id, expire=5)
            await self.sid_user_live.delete(sid)
            logger.info("用户{}网络波动从直播间{}退出".format(user_id, room_id))
        elif leave_tag == 2:
            logger.info("主动退出")
            await self.connect_user.hdel(room_id, user_id)
            await self.sid_user_live.delete(sid)
            signature_dict = self.get_callback_signature()
            end_time = int(time.time())
            if end_time - open_time > 0:
                signature_dict.update(
                    {"user_id": user_id, "room_id": room_id, "start_time": open_time, "end_time": end_time}
                )
                await self.update_data(signature_dict)
        self.leave_room(sid, room_id)

    async def update_data(self, data):
        """
        异步发送数据更新请求
        :param data: 更新数据包
        :return:
        """
        # 本地测试
        # url = 'http://0.0.0.0:8800/livesocket/create_user_live_duration/'
        # 测试服务器端
        url = "http://beta.yingliboke.cn/api/livesocket/create_user_live_duration/"
        # 生产服务器端
        # url = 'https://www.yingliboke.cn/api/livesocket/create_user_live_duration/'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    res = await resp.json()
                    if res["code"] == 20000:
                        logger.info("更新直播在线数据成功")
                    else:
                        logger.info(res["msg"])
        except Exception as ex:
            logger.exception(ex)

    # ------------ events --------------
    async def on_connect(self, sid, environ):
        if self._init_redis is False:
            await self.init_redis()
        await self.emit("system", {"code": error_code.SUCCESS, "msg": "服务器回调：连接服务器成功", "type": 1000}, room=sid)
        logger.info("%s 接入服务器成功" % sid)

    async def on_join(self, sid, data):
        room_id = data.get("room", None)
        user_id = data.get("user_id", None)
        # 参数检测
        if room_id is None or user_id is None:
            await self.emit("system", {"code": error_code.PARAMETER_IS_NOT_COMPLETE, "msg": "加入房间失败,参数不全"}, room=sid)
            logger.info("%s 参数不全，断开连接" % sid)
            await self.disconnect(sid)

        with await self.connect_user as connect_db:
            # 重连检测
            user_exists = await self.reconnect_join_check(user_id, room_id, connect_db)
            logger.info("判定重连 %s 通过" % user_exists)
            if user_exists:
                # 重复链接检测
                disconnect_exists = await self.duplicate_join_check(user_id, room_id)
                logger.info("判定重复连接 %s 通过" % user_exists)
                if not disconnect_exists:
                    sid2 = await connect_db.hget(room_id, user_id)
                    if sid != sid2:
                        await self.disconnect(sid2)
                    leave_tag = 1
                    self.enter_room(sid, room_id)
                    await self.update_user_join_info(sid, user_id, room_id, leave_tag, connect_db)
                    await self.emit(
                        "system",
                        {
                            "code": error_code.SUCCESS,
                            "msg": "服务器重复链接回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room_id),
                            "type": 1001,
                        },
                        room=sid,
                    )
                    logger.info("服务器重复链接回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room_id))
                else:
                    leave_tag = 1
                    self.enter_room(sid, room_id)
                    await self.update_user_join_info(sid, user_id, room_id, leave_tag, connect_db)
                    await self.emit(
                        "system",
                        {
                            "code": error_code.SUCCESS,
                            "msg": "服务器断线重连回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room_id),
                            "type": 1001,
                        },
                        room=sid,
                    )
                    logger.info("服务器断线重连回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room_id))
            elif not user_exists:
                # 最大人数检测
                max_flag = await self.exceed_max_user_check(room_id, connect_db)
                logger.info("判定人数 %s 通过" % max_flag)
                if max_flag:
                    leave_tag = 1
                    self.enter_room(sid, room_id)
                    logger.info("{}进入直播房间{}成功".format(user_id, room_id))
                    await self.update_user_join_info(sid, user_id, room_id, leave_tag, connect_db)
                    await self.emit(
                        "system",
                        {
                            "code": error_code.SUCCESS,
                            "msg": "服务器回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room_id),
                            "type": 1001,
                        },
                        room=sid,
                    )
                elif not max_flag:
                    await self.emit(
                        "system", {"code": error_code.OUT_OF_LIMITE_USER_COUNT, "msg": "加入房间失败,超出最大并发人数限制"}, room=sid
                    )
                    await asyncio.sleep(2)
                    await self.disconnect(sid)

    async def on_leave(self, sid):
        # 基于类的离开房间
        # 获取用户信息
        user_id = await self.sid_user_live.hget(sid, "user_id")
        room_id = await self.sid_user_live.hget(sid, "room_id")
        # 标准离开房间
        if room_id and user_id:
            await self.sid_user_live.hset(sid, "leave_tag", 2)
            await self.emit(
                "system", {"code": error_code.SUCCESS, "msg": "用户-<{}>-从直播间-<{}>离开".format(user_id, room_id)}, room=sid
            )
            logger.info("用户-<{}>-从直播间-<{}>离开".format(user_id, room_id))
            await self.disconnect(sid)
        else:
            await self.disconnect(sid)

    async def on_disconnect(self, sid):
        # 基于类的断开连接回调
        await asyncio.shield(self.update_user_disconnect_info(sid))
