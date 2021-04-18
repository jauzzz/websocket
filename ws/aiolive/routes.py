from aiohttp import web

from .views import websocket_handler


def register_routes(app):
    app.add_routes([web.get("/ws", websocket_handler)])
