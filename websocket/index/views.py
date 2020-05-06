# -*- coding: utf-8 -*-
import aioredis
import json
import aiohttp_jinja2
from aiohttp import web


class IndexView(web.View):
    """a view handler for home page"""

    async def get(self):
        # response.headers['Content-Language'] = 'utf-8'
        return aiohttp_jinja2.render_template("index.html", self.request, locals())


class EnterView(web.View):
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


class EnterPlaybackView(web.View):
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


async def get_room_number(request):
    connect_user = await aioredis.create_redis_pool("redis://localhost", db=1)
    data = request.query
    room_id = data["room_id"]
    if room_id == "":
        msg = {"code": 19999, "error_msg": "获取失败"}
    else:
        count = len(connect_user.hkeys(room_id))
        msg = {"code": 20000, "room": room_id, "count": count}
    return web.Response(text=json.dumps(msg))
