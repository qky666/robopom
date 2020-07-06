from __future__ import annotations
import typing
import os
import pathlib
import re
import inspect
import robot.api.deco as robot_deco
import SeleniumLibrary
from . import Plugin, model


class Page:
    """
    Robot Framework Library to use in conjunction with SeleniumLibrary and RobopomSeleniumPlugin.

    It is designed to be used in a special kind of Robot resource file where a specific `page` is defined.
    Usually, the import can be done like this:

    | Library | robopom.RobopomPage | page_file_path=path/page | parent_page_name=my_parent_page | WITH NAME | my_page |

    If `my_page` has no parent page, we should remove that parameter:

    | Library | robopom.RobopomPage | page_file_path=path/to/my_page | WITH NAME | my_page |

    Here `my_page` is the name of the page.
    This name has to be unique in the model tree (or an error will be generated).
    """
    OVERRIDE_PREFIX = "Override"
    CORE_PREFIX = "Core"
    SUPER_PREFIX = "Super"
    YAML_EXTENSIONS = [".yaml", ".yml"]

    @classmethod
    def get_yaml_file(cls, file: os.PathLike = None) -> typing.Optional[os.PathLike]:
        """
        Return a existing file with the same name as the provided file (ignoring extension)
        that has a `yaml` extension (`.yaml`, `.yml`).
        If no such a file exists, or the provided file is `None`, then `None` is returned.

        :param file: The file.
        :return: Existing yaml file with the same name (ignoring extension) as the provided file, or None.
        """
        if file is None:
            return None

        file = pathlib.Path(os.path.abspath(file))
        base, ext = os.path.splitext(file)
        if ext in cls.YAML_EXTENSIONS:
            return file

        for yaml_ext in cls.YAML_EXTENSIONS:
            yaml_file = pathlib.Path(f"{base}{yaml_ext}")
            if os.path.exists(yaml_file):
                return yaml_file

        return None

    def __init__(self,
                 parent_page_name: str = None,
                 selenium_library_name: str = None) -> None:
        """
        Creates a new `RobopomPage`.

        :param page_file_path: Path to the page file (without extension).
        :param parent_page_name: Optional. Name of the parent page (if it has a parent page).
        :param selenium_library_name: Optional. Name given to the SeleniumLibrary when imported.
        """
        self.parent_page_name = parent_page_name

        if selenium_library_name is None:
            # Try to guess selenium_library_name
            all_libs: typing.Dict[str] = Plugin.Plugin.built_in.get_library_instance(all=True)
            candidates = {name: lib for name, lib in all_libs.items()
                          if isinstance(lib, SeleniumLibrary.SeleniumLibrary)}
            assert len(candidates) == 1, \
                f"Error in Page.__init__. The should be one candidate, but candidates are: {candidates}"
            selenium_library_name = list(candidates.keys())[0]
        self.selenium_library_name = selenium_library_name

        # Provided by Listener. Listener also adds page to model
        self.page_resource_file_path: typing.Optional[os.PathLike] = None

    @property
    def name(self) -> str:
        if self.page_resource_file_path is None:
            return ""
        return os.path.splitext(os.path.basename(self.page_resource_file_path))[0]

    @property
    def model_file(self) -> typing.Optional[os.PathLike]:
        return self.get_yaml_file(self.page_resource_file_path)

    def local_keyword_names(self) -> typing.List[str]:
        return [name for name in dir(self) if hasattr(getattr(self, name), 'robot_name')]

    def parent_keyword_names(self) -> typing.List[str]:
        if self.parent_page_library() is None:
            return []
        return self.parent_page_library().local_and_parent_keyword_names()

    def local_and_parent_keyword_names(self) -> typing.List[str]:
        return list(set(self.local_keyword_names() + self.parent_keyword_names()))

    def super_keyword_names(self) -> typing.List[str]:
        return [f"{self.SUPER_PREFIX.lower()}_{parent_kw}" for parent_kw in self.parent_keyword_names()]

    def get_keyword_names(self) -> typing.List[str]:
        """
        Returns the list if keyword names (used by `Robot Framework`).

        :return: List of keyword names.
        """
        return list(set(self.local_and_parent_keyword_names() + self.super_keyword_names()))

    def run_keyword(self, name: str, args: list, kwargs: dict) -> typing.Any:
        """
        Runs the `name` keyword, with `args` as positional arguments, and `kwargs` as named arguments.
        Returns the keyword returned value. It is used by the `Robot Framework`.

        :param name: The keyword.
        :param args: Positional arguments.
        :param kwargs: Named arguments.
        :return: Keyword returned value.
        """
        if hasattr(self, name):
            return getattr(self, name)(*args, **kwargs)
        else:
            if name.casefold().startswith(self.SUPER_PREFIX.casefold()):
                no_super_name = name[len(self.SUPER_PREFIX) + 1:]
                if no_super_name in self.parent_page_library().get_keyword_names():
                    name = no_super_name
            return self.parent_page_library().run_keyword(name, args, kwargs)

    def get_keyword_documentation(self, name: str) -> str:
        """
        Returns the documentation string of the `name` keyword. It is used by the `Robot Framework`.

        :param name: The keyword.
        :return: Documentation string of the keyword.
        """
        if name == "__intro__":
            return inspect.getdoc(self.__class__)
        elif hasattr(self, name):
            return inspect.getdoc(getattr(self, name))
        else:
            if name.casefold().startswith(self.SUPER_PREFIX.casefold()):
                no_super_name = name[len(self.SUPER_PREFIX) + 1:]
                if no_super_name in self.parent_page_library().get_keyword_names():
                    name = no_super_name
            return self.parent_page_library().get_keyword_documentation(name)

    def get_keyword_arguments(self, name: str) -> list:
        """
        Returns the arguments list of the `name` keyword. It is used by the `Robot Framework`.

        :param name: The keyword.
        :return: The arguments list.
        """
        if hasattr(self, name):
            value = []
            method = getattr(self, name)
            spec = inspect.getfullargspec(method)
            args = spec.args[1:] if inspect.ismethod(method) else spec.args  # drop self
            defaults = spec.defaults or ()
            num_args_without_default = len(args) - len(defaults)
            args_without_default = args[:num_args_without_default]
            value += [arg for arg in args_without_default]

            args_with_default = zip(args[num_args_without_default:], defaults)
            value += [f"{name}={value}" for name, value in args_with_default]

            kwonlyargs = spec.kwonlyargs or []
            kwonlydefaults = spec.kwonlydefaults or {}

            if spec.varargs:
                value.append(f"*{spec.varargs}")
            elif len(kwonlyargs) > 0:
                value.append("*")

            if len(kwonlyargs) > 0:
                num_kwonlyargs_without_default = len(kwonlyargs) - len(kwonlydefaults)
                kwonlyargs_without_default = kwonlyargs[:num_kwonlyargs_without_default]
                value += [kwonlyarg for kwonlyarg in kwonlyargs_without_default]
                value += [f"{name}={value}" for name, value in kwonlydefaults.items()]

            if spec.varkw:
                value.append(f"**{spec.varkw}")
            return value
        else:
            if name.casefold().startswith(self.SUPER_PREFIX.casefold()):
                no_super_name = name[len(self.SUPER_PREFIX) + 1:]
                if no_super_name in self.parent_page_library().get_keyword_names():
                    name = no_super_name
            return self.parent_page_library().get_keyword_arguments(name)

    @staticmethod
    def _get_arg_spec(func_or_method: typing.Callable) -> \
            typing.Tuple[
                typing.List[str],
                typing.Iterator[typing.Tuple],
                typing.Optional[str],
                typing.Optional[str],
            ]:
        """
        Returns a tuple with arguments info of a function or method.

        :param func_or_method: Function or method to inspect.
        :return: Tuple: Mandatory arguments, default values, name of * parameter (or None),
                 name of ** parameter (or None).
        """
        spec = inspect.getfullargspec(func_or_method)
        kwargs_name = spec.varkw
        args = spec.args[1:] if inspect.ismethod(func_or_method) else spec.args  # drop self
        defaults = spec.defaults or ()
        nargs = len(args) - len(defaults)
        mandatory = args[:nargs]
        defaults = zip(args[nargs:], defaults)
        return mandatory, defaults, spec.varargs, kwargs_name

    def get_keyword_types(self, name: str) -> list:
        """
        Types of the `name` keyword arguments. Used by the `Robot Framework`.

        :param name: The keyword.
        :return: List of the keyword arguments types.
        """
        if hasattr(self, name):
            return getattr(getattr(self, name), 'robot_types')
        else:
            if name.casefold().startswith(self.SUPER_PREFIX.casefold()):
                no_super_name = name[len(self.SUPER_PREFIX) + 1:]
                if no_super_name in self.parent_page_library().get_keyword_names():
                    name = no_super_name
            return self.parent_page_library().get_keyword_types(name)

    def get_selenium_library(self) -> SeleniumLibrary.SeleniumLibrary:
        """
        Returns the `SeleniumLibrary` instance been used.

        :return: The SeleniumLibrary instance.
        """
        return Plugin.Plugin.built_in.get_library_instance(self.selenium_library_name)

    def get_robopom_plugin(self) -> Plugin.Plugin:
        """
        Returns the `RobopomSeleniumPlugin` been used.

        :return: The RobopomSeleniumPlugin.
        """
        return getattr(self.get_selenium_library(), "robopom_plugin")

    def parent_page_library(self) -> typing.Optional[Page]:
        """
        Returns the parent page library object (`RobopomPage` instance) that represents the parent of this page.

        :return: The parent page library object.
        """
        return Plugin.Plugin.built_in.get_library_instance(self.parent_page_name) \
            if self.parent_page_name is not None else None

    def parent_page_node(self) -> typing.Optional[model.Node]:
        """
        The page object (`PageObject` instance) associated to the `parent` this page.

        :return: The page object associated to the parent this page.
        """
        if self.parent_page_name is None:
            return None
        return self.get_robopom_plugin().get_node(self.parent_page_name)

    def ancestor_pages_names(self) -> typing.List[str]:
        """
        Returns the list of names of all the `ancestors` pages (starting from `root`).

        :return: List of names of all the ancestors pages.
        """
        if self.parent_page_name is None:
            return []
        else:
            value = self.parent_page_library().ancestor_pages_names()
            value.append(self.parent_page_name)
            return value

    def ancestor_pages_libs(self) -> typing.List[Page]:
        """
        Returns the list of names of all the `ancestors` pages (starting from `root`).

        :return: List of names of all the ancestors pages.
        """
        return [Plugin.Plugin.built_in.get_library_instance(name) for name in self.ancestor_pages_names()]

    @robot_deco.keyword
    def get_page_name(self) -> str:
        """
        Returns the name of the page.
        """
        return self.name

    @robot_deco.keyword
    def get_page_node(self) -> model.Node:
        """
        Returns the `page object` of this page.
        """
        return self.get_robopom_plugin().get_node(self.name)

    @robot_deco.keyword
    def get_model_file(self) -> typing.Optional[os.PathLike]:
        """
        Returns the file path of the YAML model file. If page has no model file associated, it returns 'None'.
        """
        return self.model_file

    @robot_deco.keyword(types=[str])
    def get_node(self, name: str) -> model.Node:
        """
        Returns the `page component` defined by `path`. If `path` is `None`, it returns the `page object`.

        Parameter `path` can be a real path, or a `short`.
        """
        return self.get_page_node().find_node(name)

    @robot_deco.keyword(types=[str])
    def get_multiple_node_names(self, name: str) -> typing.List[str]:
        """
        Returns a list with the `path` of every `page element` obtained from the `page elements` (multiple)
        where `path` points to.

        `path` (string): This path should point to a `page elements` (multiple) object.
        Otherwise, this keyword generates an error.
        """
        multiple_node = self.get_node(name)
        assert multiple_node.is_multiple, \
            f"'is_multiple' should be True, but it is {multiple_node.is_multiple}"
        return [node.full_name for node in multiple_node.get_multiple_nodes()]

    def _override_run(self,
                      keyword: str,
                      method: typing.Callable,
                      *args,
                      **kwargs, ) -> typing.Any:
        """
        Runs the `Override [keyword]` keyword if it exists. If not, it runs the provided `method`.
        In both cases, it uses provided `args` as positional arguments and `kwargs` as named arguments,
        and returns the value obtained from the run.

        :param keyword: The keyword.
        :param method: The method.
        :param args: Positional arguments.
        :param kwargs: Named arguments.
        :return: Returned value from the run.
        """
        over_keyword = f"{self.name}.{self.OVERRIDE_PREFIX} {keyword}"

        if self.get_robopom_plugin().keyword_exists(over_keyword):
            run_args = list(args[:])
            run_args += [f"{key}={value}" for key, value in kwargs.items()]
            return Plugin.Plugin.built_in.run_keyword(over_keyword, *run_args)
        else:
            return method(*args, **kwargs)

    @robot_deco.keyword(types=[None, typing.Union[bool, str]])
    def wait_until_loaded(self, timeout=None) -> None:
        """
        Default implementation: Test execution waits until al elements that should be visible in page
        (the ones that have `always_visible` = `True`) are indeed visible.

        Also, if `set_library_search_order` is `True`, sets library search order so that subsequent keywords
        are searched first in this page. Default value: True.

        It can be overridden defining a 'Override Wait Until Loaded' keyword in the `page resource file`.
        Calling `Core Wait Until Loaded` from that keyword, you can run the default implementation.
        This override can be used (for example) to perform additional validations in the page.

        `timeout` (Robot Framework Time): The maximum waiting time. If any element with `always_visible` = `True`
        is not visible after this time, an error is generated.
        Default value: The timeout defined when SeleniumLibrary was imported.

        `set_library_search_order` (boolean or True-False-like-string): Optional.
        If `True`, sets library search order so that subsequent keywords are searched first in this page.
        Default value: True.

        Tags: flatten
        """
        self._override_run(
            "Wait Until Loaded",
            self.super_wait_until_loaded,
            timeout,
        )

    @robot_deco.keyword
    def super_wait_until_loaded(self, timeout=None) -> None:
        """
        Test execution waits until al elements that should be visible in page
        (the ones that have `always_visible` = `True`) are indeed visible.

        Also, if `set_library_search_order` is `True`, sets library search order so that subsequent keywords
        are searched first in this page. Default value: True.

        This keyword should only be called from a `Override Wait Until Loaded` custom keyword
        in the `page resource file`. Otherwise you should call `Wait Until Loaded`.

        `timeout` (Robot Framework Time): The maximum waiting time. If any element with `always_visible` = `True`
        is not visible after this time, an error is generated.
        Default value: The timeout defined when SeleniumLibrary was imported.

        `set_library_search_order` (boolean or True-False-like-string): Optional.
        If `True`, sets library search order so that subsequent keywords are searched first in this page.
        Default value: True.
        """
        set_search_order = self.get_robopom_plugin().set_library_search_order_in_wait_until_loaded
        built_in = Plugin.Plugin.built_in
        if set_search_order:
            built_in.set_library_search_order(self.name)

        if self.parent_page_library() is not None:
            self.parent_page_library().wait_until_loaded(timeout)
        self.get_page_node().wait_until_loaded(timeout)

        if set_search_order:
            built_in.set_library_search_order(self.name)

    def get_node_from_file(self) -> model.Node:
        ancestor_node: typing.Optional[model.Node] = None
        for ancestor_page_lib in self.ancestor_pages_libs():
            if ancestor_page_lib.model_file is not None:
                current_node = Plugin.Plugin.get_node_from_file(ancestor_page_lib.model_file)
            else:
                current_node = model.Node(name=ancestor_page_lib.name)
            current_node.update_with_defaults_from(ancestor_node)
            ancestor_node = current_node

        if self.model_file is not None:
            page_node = Plugin.Plugin.get_node_from_file(self.model_file)
        else:
            page_node = model.Node(name=self.name)

        page_node.update_with_defaults_from(ancestor_node)
        return page_node

    # @robot_deco.keyword
    def attach_page_node(self) -> None:
        self.get_robopom_plugin().attach_node(self.get_node_from_file())

    # @robot_deco.keyword
    def init_page_nodes(self) -> None:
        """
        Default implementation: Initializes the page components defined in the page model file.

        This keyword should not be called directly (you usually call `Ẁait Until Loaded`).
        It can be overridden defining a 'Override Init Page Elements' keyword in the `page resource file`.
        Calling `Core Init Page Elements` from that keyword, you can run the default implementation.
        This override can be used to create additional `page components` that can not be added
        to the YAML `page model file` for some reason.
        """
        self._override_run("Init Page Nodes", self.super_init_page_nodes)

    @robot_deco.keyword
    def super_init_page_nodes(self) -> None:
        """
        Initializes the page components defined in the page model file.

        This keyword should only be called from a `Override Init Page Elements` custom keyword
        in the `page resource file`.
        """
        self.attach_page_node()

        for ancestor_page_name in self.ancestor_pages_names():
            ancestor_kw = f"{ancestor_page_name}.{self.OVERRIDE_PREFIX} Init Page Nodes"
            if self.get_robopom_plugin().keyword_exists(ancestor_kw):
                Plugin.Plugin.built_in.run_keyword(ancestor_kw)

    def get_custom_get_set_keyword(self,
                                   element: typing.Union[model.Node, str],
                                   get_set: str = "Get",
                                   ) -> typing.Optional[str]:
        get_set = get_set.capitalize()
        assert get_set in ["Get", "Set"], f"'get_set' must be 'Get' or 'Set', but it is: {get_set}"

        if isinstance(element, str):
            element = self.get_node(element)
        aliases = element.aliases()
        possible_keywords = [f"{self.name}.{get_set} {alias}" for alias in aliases]
        keywords = [keyword for keyword in possible_keywords if self.get_robopom_plugin().keyword_exists(keyword)]
        assert len(keywords) <= 1, f"Found more than one {get_set} keyword for '{element.full_name}': {keywords}"
        if len(keywords) == 1:
            return keywords[0]
        else:
            return None

    @robot_deco.keyword(types=[typing.Union[str, model.Node], str])
    def get_field_value(self,
                        element: typing.Union[str, model.Node, str],
                        pseudo_type: str = None,
                        **kwargs,
                        ) -> typing.Any:
        custom_keyword = self.get_custom_get_set_keyword(element, get_set="Get")
        if custom_keyword is not None:
            return self.get_robopom_plugin().built_in.run_keyword(custom_keyword, pseudo_type, **kwargs)
        else:
            if isinstance(element, str):
                element = self.get_node(element)
            if element.is_multiple:
                nodes = element.get_multiple_nodes()
                return [self.get_robopom_plugin().default_get_field_value(node.pom_locator, pseudo_type, **kwargs)
                        for node in nodes]
            else:
                return self.get_robopom_plugin().default_get_field_value(element.pom_locator, pseudo_type, **kwargs)

    @robot_deco.keyword(types=[typing.Union[str, model.Node], None])
    def set_field_value(self,
                        element: typing.Union[str, model.Node],
                        value: typing.Any = None,
                        force: bool = False,
                        **kwargs, ) -> None:
        custom_keyword = self.get_custom_get_set_keyword(element, get_set="Set")
        if custom_keyword is not None:
            self.get_robopom_plugin().built_in.run_keyword(custom_keyword, value, force, **kwargs)
            return
        else:
            if isinstance(element, str):
                element = self.get_node(element)
            if element.is_multiple:
                nodes = element.get_multiple_nodes()
                if not isinstance(value, list):
                    value = [value]
                for i, v in enumerate(value):
                    self.get_robopom_plugin().default_set_field_value(nodes[i].pom_locator, v, force, **kwargs)
                return
            else:
                self.get_robopom_plugin().default_set_field_value(element.pom_locator, value, force, **kwargs)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_equals(self,
                       element: typing.Union[model.PageElement, str],
                       expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) equals `expected_value`. Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value == expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_equals(self,
                      element: typing.Union[model.PageElement, str],
                      expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) equals `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} == expected: {expected_value}], should be: {expected_result}"
        assert self.compare_equals(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_not_equals(self,
                          element: typing.Union[model.PageElement, str],
                          expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) not equals `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = False
        should = f"Element: {element}. [value: {value} == expected: {expected_value}], should be: {expected_result}"
        assert self.compare_equals(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_equals_ignore_case(self,
                                   element: typing.Union[model.PageElement, str],
                                   expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) equals `expected_value` ignoring case.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return str(value).casefold() == expected_value.casefold()

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_equals_ignore_case(self,
                                  element: typing.Union[model.PageElement, str],
                                  expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) equals `expected_value` ignoring case.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} ==(ignore case) expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_equals_ignore_case(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_not_equals_ignore_case(self,
                                      element: typing.Union[model.PageElement, str],
                                      expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) not equals `expected_value` ignoring case.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = False
        should = f"Element: {element}. [value: {value} ==(ignore case) expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_equals_ignore_case(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_greater_than_expected(self,
                                            element: typing.Union[model.PageElement, str],
                                            expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is greater than `expected_value`. Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value > expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_greater_than_expected(self,
                                           element: typing.Union[model.PageElement, str],
                                           expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is greater than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} > expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_greater_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_greater_or_equal_than_expected(self,
                                                     element: typing.Union[model.PageElement, str],
                                                     expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is greater or equal than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value >= expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_greater_or_equal_than_expected(self,
                                                    element: typing.Union[model.PageElement, str],
                                                    expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is greater or equal than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} >= expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_greater_or_equal_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_lower_than_expected(self,
                                          element: typing.Union[model.PageElement, str],
                                          expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is lower than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value < expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_lower_than_expected(self,
                                         element: typing.Union[model.PageElement, str],
                                         expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is lower than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} < expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_lower_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_lower_or_equal_than_expected(self,
                                                   element: typing.Union[model.PageElement, str],
                                                   expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is lower or equal than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value <= expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_lower_or_equal_than_expected(self,
                                                  element: typing.Union[model.PageElement, str],
                                                  expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is lower or equal than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} <= expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_lower_or_equal_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_in_expected(self,
                                  element: typing.Union[model.PageElement, str],
                                  expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is in `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value in expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_in_expected(self,
                                 element: typing.Union[model.PageElement, str],
                                 expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is in `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} in expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_in_expected(element, expected_value), f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_not_in_expected(self,
                                      element: typing.Union[model.PageElement, str],
                                      expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) is not in `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return value not in expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_not_in_expected(self,
                                     element: typing.Union[model.PageElement, str],
                                     expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) is not in `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [value: {value} not in expected: {expected_value}], should be: {expected_result}"
        assert self.compare_value_not_in_expected(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_expected_in_value(self,
                                  element: typing.Union[model.PageElement, str],
                                  expected_value: typing.Any = None, ) -> bool:
        """
        Checks if `expected_value` is in value of `element` (obtained with `get:` command).
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return expected_value in value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_expected_in_value(self,
                                 element: typing.Union[model.PageElement, str],
                                 expected_value: typing.Any = None, ) -> None:
        """
        Asserts `expected_value` is in value of `element` (obtained with `get:` command).

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [expected: {expected_value} in value: {value}], should be: {expected_result}"
        assert self.compare_expected_in_value(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_expected_not_in_value(self,
                                      element: typing.Union[model.PageElement, str],
                                      expected_value: typing.Any = None, ) -> bool:
        """
        Checks if `expected_value` is not in value of `element` (obtained with `get:` command).
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return expected_value not in value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_expected_not_in_value(self,
                                     element: typing.Union[model.PageElement, str],
                                     expected_value: typing.Any = None, ) -> None:
        """
        Asserts `expected_value` is not in value of `element` (obtained with `get:` command).

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [expected: {expected_value} not in value: {value}], should be: {expected_result}"
        assert self.compare_expected_not_in_value(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_len_equals(self,
                                 element: typing.Union[model.PageElement, str],
                                 expected_value: typing.Any = None, ) -> bool:
        """
        Checks if length of value of `element` (obtained with `get:` command) is `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return len(value) == expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_equals(self,
                                element: typing.Union[model.PageElement, str],
                                expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [len(value): {len(value)} == expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_equals(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_not_equals(self,
                                    element: typing.Union[model.PageElement, str],
                                    expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is not `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = False
        should = f"Element: {element}. [len(value): {len(value)} == expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_equals(element, expected_value) is expected_result, f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_len_greater_than_expected(self,
                                                element: typing.Union[model.PageElement, str],
                                                expected_value: typing.Any = None, ) -> bool:
        """
        Checks if length of value of `element` (obtained with `get:` command) is greater than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return len(value) > expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_greater_than_expected(self,
                                               element: typing.Union[model.PageElement, str],
                                               expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is greater than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [len(value): {len(value)} > expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_greater_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_len_greater_or_equal_than_expected(self,
                                                         element: typing.Union[model.PageElement, str],
                                                         expected_value: typing.Any = None, ) -> bool:
        """
        Checks if length of value of `element` (obtained with `get:` command) is greater or equal than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return len(value) >= expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_greater_or_equal_than_expected(self,
                                                        element: typing.Union[model.PageElement, str],
                                                        expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is greater or equal than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [len(value): {len(value)} >= expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_greater_or_equal_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_len_lower_than_expected(self,
                                              element: typing.Union[model.PageElement, str],
                                              expected_value: typing.Any = None, ) -> bool:
        """
        Checks if length of value of `element` (obtained with `get:` command) is lower than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return len(value) < expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_lower_than_expected(self,
                                             element: typing.Union[model.PageElement, str],
                                             expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is lower than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [len(value): {len(value)} < expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_lower_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_len_lower_or_equal_than_expected(self,
                                                       element: typing.Union[model.PageElement, str],
                                                       expected_value: typing.Any = None, ) -> bool:
        """
        Checks if length of value of `element` (obtained with `get:` command) is lower or equal than `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return len(value) <= expected_value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_len_lower_or_equal_than_expected(self,
                                                      element: typing.Union[model.PageElement, str],
                                                      expected_value: typing.Any = None, ) -> None:
        """
        Asserts length of value of `element` (obtained with `get:` command) is lower or equal than `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: Value used in the comparison.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [len(value): {len(value)} <= expected: {expected_value}], " \
                 f"should be: {expected_result}"
        assert self.compare_value_len_lower_or_equal_than_expected(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def compare_value_matches_regular_expression(self,
                                                 element: typing.Union[model.PageElement, str],
                                                 expected_value: typing.Any = None, ) -> bool:
        """
        Checks if value of `element` (obtained with `get:` command) matches the regular expression `expected_value`.
        Returns a boolean.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: The regular expression.
        If `expected_value` is `None`, no comparison is made, and `True` is returned.
        """
        if expected_value is None:
            return True
        value = self.get_element_value(element)
        return re.search(expected_value, value) is not None

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_matches_regular_expression(self,
                                                element: typing.Union[model.PageElement, str],
                                                expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) matches regular expression `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: The regular expression.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = True
        should = f"Element: {element}. [re.search(expected: {expected_value}, value {value}) is not None], " \
                 f"should be: {expected_result}"
        assert self.compare_value_matches_regular_expression(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def assert_value_not_matches_regular_expression(self,
                                                    element: typing.Union[model.PageElement, str],
                                                    expected_value: typing.Any = None, ) -> None:
        """
        Asserts value of `element` (obtained with `get:` command) does not match regular expression `expected_value`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `expected_value`: The regular expression.
        If `expected_value` is `None`, no assertion is made.
        """
        value = self.get_element_value(element)
        expected_result = False
        should = f"Element: {element}. [re.search(expected: {expected_value}, value {value}) is not None], " \
                 f"should be: {expected_result}"
        assert self.compare_value_matches_regular_expression(element, expected_value) is expected_result, \
            f"Checked KO. {should}"
        self.built_in.log(f"Checked OK. {should}")
