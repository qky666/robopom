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
