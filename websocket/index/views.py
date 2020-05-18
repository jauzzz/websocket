import aioredis
import aiohttp_jinja2
from aiohttp import web
from loguru import logger
from simple_settings import settings

routes = web.RouteTableDef()

# 连接用户信息库
redis_address = (settings.REDIS_HOST, settings.REDIS_PORT)


class Index(web.View):
    """a view handler for home page"""

    async def get(self):
        # response.headers['Content-Language'] = 'utf-8'
        return aiohttp_jinja2.render_template("index.html", self.request, locals())


class Enter(web.View):
    """a view handler for chat """

    async def get(self):
        data = self.request.query
        room = data["room"]
        user_id = data["user_id"]

        if room and user_id:
            context2 = {"user_id": user_id, "room": room}
            return aiohttp_jinja2.render_template("chat.html", self.request, context=context2)
        else:
            return aiohttp_jinja2.render_template("index.html", self.request, locals())


class EnterPlayback(web.View):
    """a view handler for playback """

    async def get(self):
        data = self.request.query
        user_id = data["use_id"]
        room_id = data["room_id"]
        playback_data_id = data["playback_data_id"]
        if user_id == "":
            return aiohttp_jinja2.render_template("index.html", self.request, locals())
        if user_id and room_id and playback_data_id:
            context1 = {"room_id": room_id, "user_id": user_id, "playback_data_id": playback_data_id}
            return aiohttp_jinja2.render_template("playback.html", self.request, context=context1)
        else:
            return aiohttp_jinja2.render_template("index.html", self.request, locals())


@routes.get("/room_number/")
async def room_number(request):
    """
    获取直播间人数
    :return:
    """
    connect_user = await aioredis.create_redis_pool(redis_address, db=1, encoding="utf-8")
    data = request.query
    room_id = data.get("room_id", None)
    if room_id is None:
        msg = {"code": 19999, "msg": "获取失败"}
    else:
        count = len(await connect_user.hkeys(room_id))
        msg = {"code": 20000, "room_id": room_id, "count": count, "msg": "获取成功"}
        logger.info("直播间{}人数获取成功，数量{}".format(room_id, count))
    return web.json_response(msg)


@routes.post("/write_live_room/")
async def write_live_room(request):
    """
    将房间号写入直播列表中
    :param request:
    :return:
    """
    connect_user = await aioredis.create_redis_pool(redis_address, db=1, encoding="utf-8")
    data = await request.post()
    room_id = data.get("room_id")
    keyname = "live_pause_live"
    if room_id is None:
        msg = {"code": 19999, "msg": "参数错误"}
    else:
        await connect_user.hset(keyname, room_id, "")
        msg = {"code": 20000, "room_id": room_id, "msg": "操作成功"}
        logger.info("%s写入直播列表成功" % room_id)
    return web.json_response(msg)


@routes.post("/update_live_date/")
async def update_live_date(request):
    """
    直播结束后操作redis数据
    :param request:
    :return:
    """
    connect_user = await aioredis.create_redis_pool(redis_address, db=1, encoding="utf-8")
    data = await request.post()
    keyname = "live_pause_live"
    room_id = data.get("room_id", None)
    if room_id is None:
        msg = {"code": 19999, "msg": "参数错误"}
    else:
        await connect_user.hdel(keyname, room_id)
        await connect_user.delete(room_id)
        msg = {"code": 20000, "room_id": room_id, "msg": "操作成功"}
        logger.info("%s操作数据成功" % room_id)
    return web.json_response(msg)
