from __future__ import annotations
import os

ROBOT_LISTENER_API_VERSION = 2


def library_import(name: str, attributes: dict) -> None:
    original_name: str = attributes["originalname"]
    if "robopom.Page" in original_name:
        path = attributes["importer"]
        assert name == os.path.splitext(os.path.basename(path))[0], \
            f"Invalid name or path. Library imported with name '{name}' has resource file '{path}'"
