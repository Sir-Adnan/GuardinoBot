import importlib
import inspect

from aiogram import Router

from app.logger import get_logger

router = Router(name="admin")
logger = get_logger("handlers/admin")


def generate_commands_help(module: str) -> list[str]:
    def sort_by_line(obj: callable):
        return obj.__code__.co_firstlineno

    cmd_functions: list[callable] = [
        obj
        for name, obj in inspect.getmembers(module)
        if (
            inspect.isfunction(obj)
            and name.endswith("_command")
            and obj.__doc__ is not None
        )
    ]
    cmd_functions.sort(key=sort_by_line)
    spacer = f"\n{'*' * 30}\n"
    output = list()
    index = 0
    for obj in cmd_functions:
        try:
            if len(output[index]) >= 3500:
                index += 1
                output.insert(index, "")
        except IndexError:
            output.insert(0, "")

        output[index] += spacer
        output[index] += obj.__doc__

    return output


handlers = [
    "admin",
    "user",
    "server",
    "service",
    "service_menu",
    "setting",
    "payment",
    "discount",
    "reports_group",
]


def init_handler() -> None:
    for name in handlers:
        importlib.import_module(f".{name}", "app.handlers.admin")
