from __future__ import annotations
import typing
import os
import yaml
import anytree.importer
import robopom.model as model
import robopom.constants as constants

T = typing.TypeVar('T', bound='model.PageComponent')


class ComponentLoader:
    """
    Class that compiles several static methods (functions) used to load Components from a file.
    """

    @staticmethod
    def load_component_from_file(file: os.PathLike = None,
                                 component_path: str = None, ) -> typing.Optional[model.PageComponent]:
        """
        Loads a ``Component`` from a file (and returns it).

        If ``file`` is ``None``, it returns ``None``. If ``file`` is provided but ``component_path`` is ``None``,
        it returns the ``root component`` defined in ``file``.

        :param file: The file to read the component definition from. If file is None, it returns None.
        :param component_path: The (optional) path inside the file of the component to import. If component_path
                               is None, it return the root component in file.
        :return: The component obtained, or None if file was None.
        """
        if file is None or not os.path.isfile(file):
            return None

        generic_component = ComponentLoader.load_generic_component_from_file(file, component_path)

        return generic_component.get_component_type_instance()

    @staticmethod
    def load_generic_component_from_file(file: os.PathLike = None,
                                         component_path: str = None, ) -> typing.Optional[model.GenericComponent]:
        """
        Loads a ``GenericComponent`` from a file (and returns it).

        If ``file`` is ``None``, it returns ``None``. If ``file`` is provided but ``component_path`` is ``None``,
        it returns the ``root generic component`` defined in ``file``.

        :param file: The file to read the generic component definition from. If file is None, it returns None.
        :param component_path: The (optional) path inside the file of the generic component to import.
                               If component_path is None, it return the root generic component in file.
        :return: The generic component obtained, or None if file was None.
        """

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
        """
        It returns the list of ``path parts`` in ``component_path``.

        Removes possible ``separator`` at the beginning or ending of ``component_path``.

        :param component_path: The component path.
        :return: List of path parts.
        """
        path_parts = []
        if component_path is not None:
            sep = constants.SEPARATOR
            while component_path.startswith(sep):
                component_path = component_path[len(sep):]
            while component_path.endswith(sep):
                component_path = component_path[:-len(sep)]
            path_parts = component_path.split(sep)
        return path_parts

    @staticmethod
    def _get_data_from_file(file: os.PathLike = None,
                            component_path: str = None, ) -> typing.Optional[dict]:
        """
        Reads data (as a ``dictionary``) from ``file`` (a ``yaml`` file) and returns it.

        If ``file`` is ``None``, it returns ``None``. If ``file`` is provided but ``component_path`` is ``None``,
        it returns the ``root dictionary`` defined in ``file``.

        :param file: The file to read the dictionary from. If file is None, it returns None.
        :param component_path: The (optional) path inside the file of the dictionary to import.
                               If component_path is None, it return the root dictionary in file.
        :return: The dictionary obtained, or None if file was None.
        """
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
