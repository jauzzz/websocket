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
from aiohttp.log import ws_logger


def build_app(loop=None):
    app = web.Application(loop=loop, middlewares=get_middlewares(), logger=ws_logger)

    app.on_startup.append(start_plugins)
    app.on_cleanup.append(stop_plugins)

    setup_swagger(app, swagger_url="/docs", swagger_from_file="docs/swagger.yaml")
    setup_template_routes(app)

    register_routes(app)

    init_websocket(app)

    return app


def setup_template_routes(app):
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(settings.TEMPLATE_DIR))


def register_routes(app):
    register_heathcheck_routes(app)
    register_index_routes(app)


def get_middlewares():
    return [version_middleware, exception_handler_middleware]


def init_websocket(app):
    from websocket.liveroom.views import LiveRoomNamespace
    from websocket.liveroom.events import LiveBaseNamespace
    from websocket.playback.events import PlayBackNamespace

    mgr = socketio.AsyncRedisManager(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/4")
    sio = socketio.AsyncServer(async_mode="aiohttp", ping_timeout=62, client_manager=mgr, cors_allowed_origins="*")
    sio.attach(app)
    sio.register_namespace(LiveRoomNamespace("/liveroom"))
    sio.register_namespace(LiveBaseNamespace("/live_socket"))
    sio.register_namespace(PlayBackNamespace("/play_back_socket"))


async def start_plugins(app):
    caches.set_config(settings.CACHE)


async def stop_plugins(app):
    cache_config = caches.get_config()
    for cache_name in cache_config:
        await caches.get(cache_name).close()
