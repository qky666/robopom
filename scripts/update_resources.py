import click
import shutil
import os
import robopom.constants as constants


def update_files() -> None:
    """
    Files in ``robopom/resources`` are updated with content from *root level* files.
    These files are renamed because it is easier to use them this way in ``robopom template``.
    :return: None.
    """
    for file_path in constants.TEMPLATE_FILES:
        new_basename = file_path.replace(".", "_-_").replace("/", "__--").replace("__template__", "")
        shutil.copyfile(file_path, os.path.join(constants.TEMPLATE_TARGET, new_basename))


@click.command()
def update_resources() -> None:
    update_files()


if __name__ == '__main__':
    update_resources()
