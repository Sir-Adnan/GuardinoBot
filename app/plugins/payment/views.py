import importlib.util
from glob import glob
from os.path import basename, dirname, join
from types import ModuleType

from aiohttp import web

routes = web.RouteTableDef()

# # Handlers defined here


# # End Handler definitions
# Do not edit after this line if you don't know what you are doing


def discover_sub_views() -> list[ModuleType]:
    views = list()
    for d in glob(join(dirname(__file__), "*/views.py"), recursive=False):
        spec = importlib.util.spec_from_file_location(basename(d).replace(".py", ""), d)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        views.append(module)
    return views


def discover_sub_routes() -> list[web.RouteTableDef]:
    return [
        views.get_routes()
        for views in discover_sub_views()
        if hasattr(views, "get_views")
    ]


def get_routes() -> list[web.RouteTableDef]:
    return [routes] + discover_sub_routes()
