from __future__ import annotations
import typing
import os
import yaml
import anytree.importer
import robopom.model as model

T = typing.TypeVar('T', bound='model.PageComponent')


class ComponentLoader:

    @staticmethod
    def load_component_from_file(file: os.PathLike = None,
                                 component_path: str = None, ) -> typing.Optional[model.PageComponent]:
        if file is None or not os.path.isfile(file):
            return None

        generic_component = ComponentLoader.load_generic_component_from_file(file, component_path)

        return generic_component.get_component_type_instance()

    @staticmethod
    def load_generic_component_from_file(file: os.PathLike = None,
                                         component_path: str = None, ) -> typing.Optional[model.GenericComponent]:
        data_dict = ComponentLoader._get_data_from_file(file, component_path)
        if data_dict is None:
            return None

        if component_path is None:
            is_root = True
        else:
            is_root = False

        component_importer = anytree.importer.DictImporter(model.GenericComponent)

        # Name of the component.
        if is_root:
            assert "name" not in data_dict, f"Root node in a file (PageObject) should not define 'name'"
            # Use file name
            data_dict["name"] = os.path.splitext(os.path.basename(file))[0]

        return component_importer.import_(data_dict)

    @staticmethod
    def _get_path_parts(component_path: str = None) -> typing.List[str]:
        # Determine path parts.
        path_parts = []
        if component_path is not None:
            while component_path.startswith(model.Component.separator):
                component_path = component_path[len(model.Component.separator):]
            while component_path.endswith(model.Component.separator):
                component_path = component_path[:-len(model.Component.separator)]
            path_parts = component_path.split(model.Component.separator)
        return path_parts

    @staticmethod
    def _get_data_from_file(file: os.PathLike = None,
                            component_path: str = None, ) -> typing.Optional[dict]:
        if file is None:
            return None

        path_parts = ComponentLoader._get_path_parts(component_path)

        # Load data.
        with open(file, encoding="utf-8") as src_file:
            yaml_data = src_file.read()
        file_data = yaml.safe_load(yaml_data)
        data = file_data
        for part in path_parts:
            for child in data["children"]:
                if child["name"] == part:
                    data = child
                    break
            else:
                assert False, f"Component path '{component_path}' not found in file {file}. Part not found: {part}"
        return data
