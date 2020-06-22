# General
# CORE_PREFIX = "Core"  # This constant is "implicitly used" only. Leave it here as a reminder.

# Conversions
TRUE = [value.casefold() for value in ["True", "Yes"]],
FALSE = [value.casefold() for value in ["False", "No"]]
ALMOST_NONE = [None, {}, []]

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

# Roles
ROLE_TEXT = "text"
ROLE_PASSWORD = "password"
ROLE_SELECT = "select"
ROLE_CHECKBOX = "checkbox"

# Get/Set
GET_SET_SEPARATOR = ":"
SET_TEXT_PREFIX = "set_text"
GET_TEXT_PREFIX = "get_text"
SET_PASSWORD_PREFIX = "set_password"
GET_PASSWORD_PREFIX = "get_password"
SET_SELECT_PREFIX = "set_select"
GET_SELECT_PREFIX = "get_select"
SET_CHECKBOX_PREFIX = "set_checkbox"
GET_CHECKBOX_PREFIX = "get_checkbox"
SET_PREFIX = "set"
GET_PREFIX = "get"
ACTION_PREFIX = "action"
ACTION_CLICK = "click"
ACTION_DOUBLE_CLICK = "double_click"
ACTION_CONTEXT_CLICK = "context_click"
ASSERT_EQUALS_PREFIX = "assert_equals"
ASSERT_NOT_EQUALS_PREFIX = "assert_not_equals"
ASSERT_EQUALS_IGNORE_CASE_PREFIX = "assert_equals_ignore_case"
ASSERT_NOT_EQUALS_IGNORE_CASE_PREFIX = "assert_not_equals_ignore_case"
ASSERT_VALUE_GREATER_THAN_EXPECTED_PREFIX = "assert_value_greater_than_expected"
ASSERT_VALUE_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX = "assert_value_greater_or_equal_than_expected"
ASSERT_VALUE_LOWER_THAN_EXPECTED_PREFIX = "assert_value_lower_than_expected"
ASSERT_VALUE_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX = "assert_value_lower_or_equal_than_expected"
ASSERT_VALUE_IN_EXPECTED_PREFIX = "assert_value_in_expected"
ASSERT_VALUE_NOT_IN_EXPECTED_PREFIX = "assert_value_not_in_expected"
ASSERT_EXPECTED_IN_VALUE_PREFIX = "assert_expected_in_value"
ASSERT_EXPECTED_NOT_IN_VALUE_PREFIX = "assert_expected_not_in_value"
ASSERT_VALUE_LEN_EQUALS_PREFIX = "assert_value_len_equals"
ASSERT_VALUE_LEN_NOT_EQUALS_PREFIX = "assert_value_len_not_equals"
ASSERT_VALUE_LEN_GREATER_THAN_EXPECTED_PREFIX = "assert_value_len_greater_than_expected"
ASSERT_VALUE_LEN_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX = "assert_value_len_greater_or_equal_than_expected"
ASSERT_VALUE_LEN_LOWER_THAN_EXPECTED_PREFIX = "assert_value_len_lower_than_expected"
ASSERT_VALUE_LEN_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX = "assert_value_len_lower_or_equal_than_expected"
ASSERT_VALUE_MATCHES_REGULAR_EXPRESSION_PREFIX = "assert_value_matches_regular_expression"
ASSERT_VALUE_NOT_MATCHES_REGULAR_EXPRESSION_PREFIX = "assert_value_not_matches_regular_expression"

GET_ACTIONS_PREFIXES = (GET_TEXT_PREFIX, GET_PASSWORD_PREFIX, GET_SELECT_PREFIX, GET_CHECKBOX_PREFIX, GET_PREFIX)

