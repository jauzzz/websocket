import socketio

import aiohttp_jinja2
import jinja2
from aiocache import caches
from aiohttp import web
from aiohttp_swagger import setup_swagger
from simple_settings import settings

from .healthcheck.routes import register_routes as register_heathcheck_routes
from .index.routes import register_routes as register_index_routes
from .contrib.middlewares import exception_handler_middleware, version_middleware
from .settings.base import TEMPLATE_DIR


def build_app(loop=None):
    app = web.Application(loop=loop, middlewares=get_middlewares())

    app.on_startup.append(start_plugins)
    app.on_cleanup.append(stop_plugins)

    setup_swagger(app, swagger_url="/docs", swagger_from_file="docs/swagger.yaml")
    setup_template_routes(app)

    register_routes(app)

    init_websocket(app)

    return app


def setup_template_routes(app):
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(TEMPLATE_DIR))


def register_routes(app):
    register_heathcheck_routes(app)
    register_index_routes(app)


def get_middlewares():
    return [version_middleware, exception_handler_middleware]


def init_websocket(app):
    from websocket.liveroom.views import LiveRoomNamespace

    sio = socketio.AsyncServer(async_mode="aiohttp")
    sio.attach(app)
    sio.register_namespace(LiveRoomNamespace("/liveroom"))


async def start_plugins(app):
    caches.set_config(settings.CACHE)


async def stop_plugins(app):
    cache_config = caches.get_config()
    for cache_name in cache_config:
        await caches.get(cache_name).close()
