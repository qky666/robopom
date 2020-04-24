from __future__ import annotations
import typing
import robopom.component_loader as pom_loader
import os
import pathlib
import robopom.RobopomPage as robopom_page
import robopom.constants as constants
import robot.parsing.model as robot_model
import robot.parsing.settings as robot_settings


class ComponentVariables:
    @staticmethod
    def get_variables(pages_files: typing.Union[os.PathLike, typing.List[os.PathLike]] = constants.PAGES_FILE,
                      model_files: typing.Union[os.PathLike, typing.List[os.PathLike]] = None) -> dict:
        """
        Returns a ``dictionary`` obtained from the ``pages_files`` and ``model_files`` provided.

        Dictionary key-value format is one of:

        - Key: ``[PAGE_NAME]__[PAGE_COMPONENT__PATH]``. Value: ``path:[page_name]__[page_component__path]``.
          It can have ``separators`` (``__``) in ``page_component__path``.
          The ``page_component__path`` is formed with the names (``name`` property) of the components
          in the page component path joined with a ``separator`` (``__``).
          If any of the page component ancestors (or the page component itself) has no explicit ``name`` attribute,
          it does not generate a key-value pair.

        - ``[PAGE_NAME]__[PAGE_COMPONENT_SHORT]``.  Value: ``path:[page_name]__[page_component_short]``.
          It can not have ``separators`` (``__``) in ``page_component_short``.
          If the page component has no explicit ``short`` attribute, it does not generate a key-value pair.

        *Note*: ``Key`` is upper-cased because it is usually used to define global Robot Framework variables.

        All ``pages_files`` and ``model_files`` provided are used to generate the dictionary.

        :param pages_files: List of pages files (Robot Framework resources files) used to generate the dictionary.
                            If a single object is given, it is used as a list with that single object.
                            Default value: 'robopom_pages.resource'
        :param model_files: List of model files (yaml files) used to generate the dictionary.
                            If a single object is given, it is used as a list with that single object.
                            Default value: None.
        :return: The dictionary obtained.
        """
        if model_files is None:
            model_files = []
        if isinstance(model_files, str):
            model_files = [model_files]
        if isinstance(pages_files, str):
            pages_files = [pages_files]

        working_dir = os.path.abspath(".")
        real_files = []
        for pages_file in pages_files:
            if os.path.isabs(pages_file):
                real_files.append(pages_file)
            else:
                for found in pathlib.Path(working_dir).rglob(str(pages_file)):
                    real_files.append(str(found))

        for pages_file in real_files:
            if os.path.isfile(pages_file):
                res = robot_model.ResourceFile(pages_file).populate()
                for page_res in res.imports.data:
                    page_res: robot_settings.Resource
                    page_res_name = os.path.splitext(page_res.name)[0]
                    if os.path.isabs(page_res_name):
                        model_files.append(page_res_name)
                    else:
                        pages_file_dir = os.path.dirname(pages_file)
                        model_files.append(os.path.join(pages_file_dir, page_res_name))

        model_files = [robopom_page.RobopomPage.get_yaml_file(model_file) for model_file in model_files]
        d = {}
        for model_file in model_files:
            component = pom_loader.ComponentLoader.load_component_from_file(model_file)
            if component is not None:
                d.update(component.variables_dictionary())
        return d
