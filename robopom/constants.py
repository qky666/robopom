import datetime

# General
# CORE_PREFIX = "Core"  # This constant is "implicitly used" only. Leave it here as a reminder.

DEFAULT_SELENIUM_LIBRARY_NAME = "SeleniumLibrary"

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

# Pom prefix
POM_PREFIX = "pom"
POM_LOCATOR_PREFIXES = [f"{POM_PREFIX}:", f"{POM_PREFIX}="]

# Page keywords
OVERRIDE_PREFIX = "Override"
CORE_PREFIX = "Core"
SUPER_PREFIX = "Super"
YAML_EXTENSIONS = [".yaml", ".yml"]
FROM_KEYWORD = ("from", "keyword")

# Types and conversions
TYPES = {
    str: str,
    "str".casefold(): str,
    "string".casefold(): str,

    bool: bool,
    "bool".casefold(): bool,
    "boolean".casefold(): bool,

    int: int,
    "int".casefold(): int,
    "integer".casefold(): int,

    float: float,
    "float".casefold(): float,

    datetime.date: datetime.date,
    "date".casefold(): datetime.date,

    datetime.datetime: datetime.datetime,
    "datetime".casefold(): datetime.datetime,
}

PSEUDO_BOOLEAN = {
    True: True,
    "True".casefold(): True,
    "Yes".casefold(): True,
    1: True,
    False: False,
    "False".casefold(): False,
    "No".casefold(): False,
    0: False,
}
