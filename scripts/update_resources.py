import click
import shutil
import os
# import robopom.constants as constants


# Project template.
# Files used in project template.
TEMPLATE_FILES = [
    ".gitignore",
    "_dot_project_sample",
    "argumentfile__template__",
    "README__template__.md",
    "red_sample.xml",
    "requirements__template__.txt",
    "robopom.resource",
    "robopom_pages.resource",
    "robopom_variables.yaml",
    "robopom_variables_update.robot",
    "doc/RobopomPageDoc.html",
    "doc/SeleniumRobopomPluginDoc.html",
    "node_modules/dictionary-es/index.aff",
    "node_modules/dictionary-es/index.dic",
    "node_modules/dictionary-es/index.js",
    "node_modules/dictionary-es/license",
    "node_modules/dictionary-es/package.json",
    "node_modules/dictionary-es/readme.md",
    "pages/mtp/mtp_home_page.resource",
    "pages/mtp/mtp_home_page.yaml",
    "pages/mtp/mtp_page.resource",
    "pages/mtp/mtp_page.yaml",
    "pages/mtp/mtp_search_results_page.resource",
    "pages/mtp/mtp_search_results_page.yaml",
    "pages/omnia/omnia_login_page.resource",
    "pages/omnia/omnia_login_page.yaml",
    "pages/omnia/omnia_main_page.resource",
    "pages/omnia/omnia_main_page.yaml",
    "pages/omnia/account/omnia_account_page.resource",
    "pages/omnia/account/omnia_account_page.yaml",
    "pages/omnia/search_results/omnia_search_results_page.resource",
    "pages/omnia/search_results/omnia_search_results_page.yaml",
    "pages/omnia/user/omnia_user_page.resource",
    "pages/omnia/user/omnia_user_page.yaml",
    "pages/other/test_component.yaml",
    "suites/mtp/__init__.robot",
    "suites/mtp/tc001_home_page_text.robot",
    "suites/mtp/tc002_search.robot",
    "suites/omnia/__init__.robot",
    "suites/omnia/tc001_basic_operations.robot",
    "variables_omnia.yaml",
]
# Folder where template files are stored.
TEMPLATE_TARGET = "robopom/resources/template_files"
# Resources package.
RESOURCES_PACKAGE = "robopom.resources"
# Template files folder name.
TEMPLATE_FILES_DIR_NAME = "template_files"


def update_files() -> None:
    """
    Files in ``robopom/resources`` are updated with content from *root level* files.
    These files are renamed because it is easier to use them this way in ``robopom template``.
    :return: None.
    """
    for file_path in TEMPLATE_FILES:
        new_basename = file_path.replace(".", "_-_").replace("/", "__--").replace("__template__", "")
        shutil.copyfile(file_path, os.path.join(TEMPLATE_TARGET, new_basename))


@click.command()
def update_resources() -> None:
    update_files()


if __name__ == '__main__':
    update_resources()
