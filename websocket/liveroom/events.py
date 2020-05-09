# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import socketio
import logging
import redis
import time
import random
import string
import hashlib
import requests
import json
from simple_settings import settings
from websocket import status_code as error_code

log = print
logger = logging.getLogger(__name__)

# 断开连接用户信息库
disconnect_user = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True, db=0)
# 连接用户信息库
connect_user = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True, db=1)
# sid直播用户信息库
sid_user_live = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True, db=2)


# 基于类的名称空间
class LiveBaseNamespace(socketio.AsyncNamespace):
    # 基于类的连接回调
    async def on_connect(self, sid, environ):
        await self.emit("system", {"code": error_code.SUCCESS, "msg": "服务器回调：连接服务器成功"}, room=sid)

    async def emit_msg(self, event, data, room):
        await self.emit(event, data, room)

    async def on_join(self, sid, data):
        # 加入房间异步化
        # 基于类的加入房间
        room = data.get("room", "")
        user_id = data.get("user_id", "")
        if room and user_id:
            ret = self.join_room_check(room, user_id, sid)
            print(ret)
            logger.info(ret)
            # 超出人数
            if ret["type"] == 0:
                # await self.emit(
                #     "system", {"code": error_code.OUT_OF_LIMITE_USER_COUNT, "msg": "加入房间失败,超出最大并发人数限制"}, room=sid
                # )
                # await self.disconnect(sid)
                data = {"code": error_code.OUT_OF_LIMITE_USER_COUNT, "msg": "加入房间失败,超出最大并发人数限制"}
                tasks = [self.emit_msg('system', data, room), self.disconnect(sid)]
                await asyncio.gather(*tasks)

            # 建立重复链接
            elif ret["type"] == 2:
                print("建立重复链接", int(time.time()))
                logger.info("建立重复链接")
                print("新连接", sid)
                logger.info(f"新连接 {sid}")
                sid2 = connect_user.hget(room, user_id)
                print("旧连接", sid2)
                logger.info(f"旧连接 {sid2}")
                if sid != sid2:
                    # 断开前置链接
                    await self.disconnect(sid2)
                open_time = int(time.time())
                # 将用户信息存入redis中
                sid_user_live.hset(sid, "user_id", user_id)
                sid_user_live.hset(sid, "room", room)
                sid_user_live.hset(sid, "leave_tag", 1)
                sid_user_live.hset(sid, "open_time", open_time)
                self.enter_room(sid, room)
                await self.emit(
                    "system",
                    {"code": error_code.SUCCESS, "msg": "服务器重复链接回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room)},
                    room=sid,
                )
                logger.info("服务器重复链接回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room))
            elif ret["type"] == 1:
                try:
                    print(ret["msg"])
                    logger.info(ret["msg"])
                    open_time = int(time.time())
                    # 将用户信息存入redis中
                    sid_user_live.hset(sid, "user_id", user_id)
                    sid_user_live.hset(sid, "room", room)
                    sid_user_live.hset(sid, "leave_tag", 1)
                    sid_user_live.hset(sid, "open_time", open_time)
                    self.enter_room(sid, room)
                    print("用户-<{}>加入房间".format(user_id))
                    logger.info("用户-<{}>加入房间".format(user_id))
                    if ret["status"] == 2:
                        print("断线重连")
                        logger.info("断线重连")
                        await self.emit(
                            "system",
                            {
                                "code": error_code.SUCCESS,
                                "msg": "服务器断线重连回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room),
                            },
                            room=sid,
                        )
                        logger.info("服务器断线重连回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room))
                    elif ret["status"] == 1:
                        print("正常连接")
                        logger.info("正常连接")
                        await self.emit(
                            "system",
                            {"code": error_code.SUCCESS, "msg": "服务器回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room)},
                            room=sid,
                        )
                        logger.info("服务器回调：用户-<{}>加入直播间-<{}>加入成功".format(user_id, room))
                except Exception as ex:
                    logger.exception(ex)
                    await self.disconnect(sid)
                # await self.emit('system', {
                #     'code': error_code.SUCCESS,
                #     'count': len(connect_user.hkeys(room))
                # }, room=sid)
        else:
            await self.emit("system", {"code": error_code.PARAMETER_IS_NOT_COMPLETE, "msg": "加入房间失败,参数不全"}, room=sid)
            logger.info("加入房间失败,参数不全")
            await self.disconnect(sid)

    async def on_leave(self, sid):
        # 基于类的离开房间
        # 获取用户信息
        user_id = sid_user_live.hget(sid, "user_id")
        room = sid_user_live.hget(sid, "room")
        # 标准离开房间
        if room and user_id:
            sid_user_live.hset(sid, "leave_tag", 2)
            logger.info("用户-<{}>-从直播间-<{}>离开".format(user_id, room))
            await self.emit(
                "system", {"code": error_code.SUCCESS, "msg": "用户-<{}>-从直播间-<{}>离开".format(user_id, room)}, room=sid
            )
        await self.disconnect(sid)

    async def on_disconnect(self, sid):
        # 基于类的断开连接回调
        user_id = sid_user_live.hget(sid, "user_id")
        room = sid_user_live.hget(sid, "room")
        leave_tag = sid_user_live.hget(sid, "leave_tag")
        if leave_tag:
            leave_tag = int(leave_tag)
        open_time = sid_user_live.hget(sid, "open_time")
        if open_time:
            open_time = int(open_time)
        if not (user_id and room and leave_tag and open_time):
            # 都没有进入房间，暂定不需要任何操作待日后其他需求
            pass
        if room and user_id and leave_tag:
            if leave_tag == 1:
                # 网络波动
                logger.info("网络波动")
                # key 变为user_id加room的拼接
                key = str(room) + "_" + str(user_id)
                logger.info(key)
                disconnect_user.set(key, user_id, ex=60)
            elif leave_tag == 2:
                # 主动退出
                logger.info("主动退出")
                print("主动退出")
                connect_user.hdel(room, user_id)
                li = connect_user.hkeys("live_pause_live")
                # li = ["548589", ]
                all_sum = 0
                li2 = [len(connect_user.hkeys(room_id)) for room_id in li]
                for i in li2:
                    all_sum += i
                print(all_sum)
                keyname1 = "total_limit_number"  # redis key name
                keyname2 = "%s_limit_number" % room
                print("3", keyname1, all_sum)
                print(keyname2, len(connect_user.hkeys(room)))
                logger.info(f"3 {keyname1} {all_sum}")
                logger.info(keyname2, len(connect_user.hkeys(room)))

            # 从sid库中删除
            sid_user_live.delete(sid)
            self.leave_room(sid, room)
            signature_dict = self.get_callback_signature()
            end_time = int(time.time())
            # 确切有观看时长才统计
            if end_time - open_time > 0:
                print("更新数据", int(time.time()))
                data = {
                    "user_id": user_id,
                    "room_id": room,
                    "start_time": open_time,
                    "end_time": end_time,
                    "nonce": signature_dict["nonce"],
                    "timestamp": signature_dict["timestamp"],
                    "signature": signature_dict["signature"],
                }
                await self.update_data(data)
            log("用户-<{}>-从直播间-<{}>断开".format(user_id, room))
            logger.info("用户-<{}>-从直播间-<{}>断开".format(user_id, room))

        else:
            logger.info("异常退出")
            self.leave_room(sid, room)

    async def update_data(self, data):
        # 异步发送数据更新请求
        # 本地测试
        # url = 'http://0.0.0.0:8800/livesocket/create_user_live_duration/'
        # 测试服务器端
        url = "http://beta.yingliboke.cn/api/livesocket/create_user_live_duration/"
        # 生产服务器端
        # url = 'https://www.yingliboke.cn/api/livesocket/create_user_live_duration/'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    print(resp.status)
                    res = await resp.json()
                    if res["code"] == 20000:
                        print("更新直播在线数据成功")
                        logger.info("更新直播在线数据成功")
                    else:
                        print(res["msg"])
                        logger.info(res["msg"])
        except Exception as ex:
            logger.exception(ex)

    def join_room_check(self, room, user_id, sid):
        # 是否可以进入房间
        ret = {"type": 0, "msg": ""}
        """
        0:拒绝进入，
        1:可以进入，
        2:建立重复链接，断开旧连接，进入新连接
        """
        # 判断指定房间是否包含指定的用户
        if connect_user.hexists(room, user_id):
            # 判断断开连接db中是否包含指定用户，不包含则判断为重复建立连接
            keyname = str(room) + "_" + str(user_id)
            if not disconnect_user.exists(keyname):
                # 五次重连内的建立重复链接
                ret["type"] = 2
                ret["msg"] = "重复链接，结束前置链接"
                return ret
            connect_user.hset(room, user_id, sid)
            # 断线再次连接
            ret["type"] = 1
            ret["msg"] = "断线重连"
            ret["status"] = 2
            return ret
        keyname1 = "total_limit"  # 总限制人数
        keyname3 = "%s_limit" % room  # 单场总限制人数

        # 获取全局最大人数字段是否存在
        if not connect_user.exists(keyname1):
            # 本地测试
            # url = 'http://192.168.0.100:8000/livesocket/get_systemsettings_max_limit/'
            # 测试服务器
            url = "http://beta.yingliboke.cn/api/livesocket/get_systemsettings_max_limit/"
            # 服务器端
            # url = 'https://www.yingliboke.cn/api/livesocket/get_systemsettings_max_limit/'
            signature_dict = self.get_callback_signature()
            headers = {"content-type": "application/json"}
            data = json.dumps(
                {
                    "nonce": signature_dict["nonce"],
                    "timestamp": signature_dict["timestamp"],
                    "signature": signature_dict["signature"],
                }
            )
            res = requests.post(url=url, headers=headers, data=data).json()
            if res["code"] == 20000:
                nu1 = res["total_limit"]
                connect_user.set(keyname1, nu1)
                log("获取全局最大人数成功")
            else:
                log(res["msg"])

        # 判断单场直播最大人数是否存在
        if not connect_user.exists(keyname3):
            # 本地测试
            # url = 'http://192.168.0.100:8000/livesocket/get_liveroom_package_max_limit/'
            # 测试服务器端
            url = "http://beta.yingliboke.cn/api/livesocket/get_liveroom_package_max_limit/"
            # 服务器端
            # url = 'https://www.yingliboke.cn/api/livesocket/get_liveroom_package_max_limit/'
            signature_dict = self.get_callback_signature()
            headers = {"content-type": "application/json"}
            data = json.dumps(
                {
                    "nonce": signature_dict["nonce"],
                    "timestamp": signature_dict["timestamp"],
                    "signature": signature_dict["signature"],
                    "room": room,
                }
            )
            res = requests.post(url=url, headers=headers, data=data).json()
            nu2 = 0
            if res["code"] == 20000:
                nu2 = res["liveroom_limit_number"]
                log("获取单场直播间人数限制成功")

            # 测试环境
            connect_user.set(keyname3, nu2)
            # 判断总接入数字段是否存在

        total_limit = connect_user.get(keyname1)
        room_limit = connect_user.get(keyname3)
        li = connect_user.hkeys("live_pause_live")
        # li = ["548589", ]
        all_sum = 0
        li2 = [len(connect_user.hkeys(room_id)) for room_id in li]
        for i in li2:
            all_sum += i
        print(all_sum)

        if (all_sum + 1 <= int(total_limit)) and (len(connect_user.hkeys(room)) + 1 <= int(room_limit)):
            # 将可以进入队列的数据放入redis的连接用户库中
            connect_user.hset(room, user_id, sid)
            connect_length = len(connect_user.hkeys(room))

            logger.info(f"1 total_limit_number {all_sum + 1}")
            logger.info(f"{room}_limit_number {connect_length}")

            print(f"1 total_limit_number {all_sum + 1}")
            print(f"{room}_limit_number {connect_length}")

            print(f"{room} 当前人数 {connect_length}")
            logger.info(f"{room} 当前人数 {connect_length}")
            ret["type"] = 1
            ret["msg"] = "建立链接"
            ret["status"] = 1
            return ret
        else:
            ret["type"] = 0
            ret["msg"] = "超出人数"
            return ret

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
