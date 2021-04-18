from .views import Enter, EnterPlayback, Index, routes


def register_routes(app):
    app.router.add_get("", Index, name="index")
    app.router.add_get("/chat", Enter, name="Enter")
    app.router.add_get("/playback", EnterPlayback, name="EnterPlayback")
    app.router.add_routes(routes)
