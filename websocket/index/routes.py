from .views import IndexView, EnterView, EnterPlaybackView, get_room_number


def register_routes(app):
    app.router.add_get("", IndexView, name="index")
    app.router.add_get("/chat", EnterView, name="Enter")
    app.router.add_get("/playback", EnterPlaybackView, name="EnterPlayback")
    app.router.add_get("/number/", get_room_number, name="number")
