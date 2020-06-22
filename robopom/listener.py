from __future__ import annotations
from . import Plugin, Page


class Listener:

    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self):
        self.ROBOT_LIBRARY_LISTENER = self

    @staticmethod
    def _library_import(name: str, attributes: dict) -> None:
        original_name: str = attributes["original_name"]
        if "robopom.Page" in original_name:
            page_lib: Page.Page = Plugin.Plugin.built_in.get_library_instance(name)
            page_lib.page_resource_file_path = attributes["source"]

            plugin = page_lib.get_robopom_plugin()
            if plugin.get_node(page_lib.name) is None:
                page_lib.init_page_nodes()
                plugin.pom_root.resolve(recursive=True)
