from aiohttp import web

from app.main import raw_redis

routes = web.RouteTableDef()


@routes.get("/")
async def guardino_bot_healthcheck_endpoint(request: web.Request):
    return web.json_response({"status": "ok"})


@routes.get("/qr/{username}")
async def get_qr_image(request: web.Request):
    username = request.match_info.get("username")
    if not username:
        return web.json_response({"detail": "Bad request"}, status=400)
    _data = await raw_redis.get(f"qr:generated:{username}")
    if not _data:
        return web.json_response({"detail": "Not found"}, status=404)

    return web.Response(body=_data, content_type="image/png")
