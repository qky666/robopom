import pkg_resources
import shutil
import os
import robopom.constants as constants


def template() -> None:
    """
    Generates a project skeleton in current directory.

    :return: None.
    """
    template_dir = pkg_resources.resource_filename(constants.RESOURCES_PACKAGE, constants.TEMPLATE_FILES_DIR_NAME)
    for item in os.scandir(template_dir):
        if item.is_file() is True and item.name != "__init__.py" and item.name != "__pycache__":
            target = item.name.replace("_-_", ".").replace("__--", "/")
            dir_name = os.path.dirname(target)
            if len(dir_name) > 0:
                os.makedirs(dir_name, exist_ok=True)
            shutil.copyfile(item.path, target)
