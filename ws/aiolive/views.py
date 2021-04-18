import json
from aiohttp import web, WSMsgType

from .conn import MyRedis


async def lua_join(data):
    room = data["room"]
    # uid = data["uid"]

    room_key = "{}_lua_count".format(room)
    max_count = 2000

    conn = await MyRedis.redis()
    await conn.setnx(room_key, 0)

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

    return await conn.eval(
        script, keys=["room_key", "max_count"], args=[room_key, max_count]
    )


async def websocket_handler(request):

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == "close":
                print("websocket connection closed")
                await ws.close()
            else:
                try:
                    data = json.loads(msg.data)
                    action = data["action"]

                    if action == "join":
                        await lua_join(data["data"])

                    await ws.send_str("echo:" + msg.data)
                except json.JSONDecodeError:
                    # invalid json
                    pass
                finally:
                    pass
        elif msg.type == WSMsgType.ERROR:
            print("ws connection closed with exception %s" % ws.exception())

    return ws
