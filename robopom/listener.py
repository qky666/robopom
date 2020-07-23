from __future__ import annotations
import typing
import os
import logging
import robopom.Plugin
# import robopom.Page as Page


class Listener:

    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self):
        self.imported_library_to_path: typing.Dict[str, os.PathLike] = {}
        # self.known_plugins: typing.Set[robopom.Plugin.Plugin] = set()

    def library_import(self, name: str, attributes: dict) -> None:
        # logging.debug(f"Starting Listener 'library_import' with name={name}, attributes={attributes} ")
        original_name: str = attributes["originalname"]
        if "robopom.Page" in original_name:
            path = attributes["importer"]
            assert name == os.path.splitext(os.path.basename(path))[0], \
                f"Invalid name or path. Library imported with name '{name}' has resource file '{path}'"
            self.imported_library_to_path[name] = attributes["importer"]

    # def start_keyword(self, name: str, attributes: dict):
    #     logging.debug(f"Starting Listener 'start_keyword' with name={name}, attributes={attributes} ")
    #     lib_to_path = self.imported_library_to_path.copy()
    #     self.imported_library_to_path = {}
    #     for lib, path in lib_to_path.items():
    #         page_lib: robopom.Plugin.Page = robopom.Plugin.Plugin.built_in.get_library_instance(lib)
    #         page_lib.page_resource_file_path = path
    #
    #         plugin = page_lib.get_robopom_plugin()
    #         self.known_plugins.add(plugin)
    #         if plugin.pom_root.find_node(page_lib.name) is None:
    #             page_lib.init_page_nodes()
    #             plugin.pom_root.resolve(recursive=True)
    #         # logging.debug(f"Pom tree: {plugin.pom_root.pom_tree}")
    #
    # def end_test(self, name: str, attributes: dict):
    #     logging.debug(f"Starting Listener 'end_test' with name={name}, attributes={attributes} ")
    #     for plugin in self.known_plugins:
    #         plugin.reset_pom_tree()
    #     self.known_plugins = set()
