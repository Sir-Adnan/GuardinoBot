import re


def normalize_module_name(name: str) -> str:
    return re.sub(r"^([A-Za-z]_)?", "", name)


def prefix_from_module_path(path: str) -> str:
    return normalize_module_name(path.split("/")[-2])
