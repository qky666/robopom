from __future__ import annotations
import typing
import os
import pathlib
import re
import inspect
import robot.api.deco as robot_deco
import robot.libraries.BuiltIn as robot_built_in
import SeleniumLibrary
import robopom.RobopomSeleniumPlugin as robopom_selenium_plugin
import robopom.model as model
import robopom.constants as constants
import robopom.component_loader as component_loader


class RobopomPage:
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
    added_to_model_page_file_paths = []

    def __init__(self,
                 page_file_path: os.PathLike = None,
                 parent_page_name: str = None,
                 selenium_library_name: str = "SeleniumLibrary") -> None:
        """
        Creates a new `RobopomPage`.

        :param page_file_path: Path to the page file (without extension).
        :param parent_page_name: Optional. Name of the parent page (if it has a parent page).
        :param selenium_library_name: Optional. Name given to the SeleniumLibrary when imported.
        """
        self.page_file_path = page_file_path
        self.parent_page_name = parent_page_name
        self.selenium_library_name = selenium_library_name

        if self.page_file_path is None:
            assert robopom_selenium_plugin.is_robot_running() is False, \
                f"RobopomPage created without page_file_path"
            return

        self.page_name = os.path.splitext(os.path.basename(self.page_file_path))[0]
        self.model_file = self.get_yaml_file(self.page_file_path)
        self.page_path = \
            f"{model.Component.separator}{constants.ROOT_NAME}{model.Component.separator}{self.page_name}"
        self.parent_page_path = f"{model.Component.separator}{constants.ROOT_NAME}{model.Component.separator}" \
                                f"{self.parent_page_name}" if self.parent_page_name is not None else None
        self.built_in = robot_built_in.BuiltIn()

        self.add_to_model_if_needed()

    @staticmethod
    def get_yaml_file(file: os.PathLike = None) -> typing.Optional[os.PathLike]:
        """
        Return a existing file with the same name as the provided file (ignoring extension)
        that has a `yaml` extension (`.yaml`, `.yml`).
        If no such a file exists, or the provided file is `None`, then `None` is returned.

        :param file: The file.
        :return: Existing yaml file with the same name (ignoring extension) as the provided file, or None.
        """
        if file is None:
            return None

        base, ext = os.path.splitext(file)
        if ext in constants.YAML_EXTENSIONS:
            return file

        for yaml_ext in constants.YAML_EXTENSIONS:
            yaml_file = pathlib.Path(f"{base}{yaml_ext}")
            if os.path.exists(yaml_file):
                return yaml_file

        return None

    def get_keyword_names(self) -> typing.List[str]:
        """
        Returns the list if keyword names (used by `Robot Framework`).

        :return: List of keyword names.
        """
        return [name for name in dir(self) if hasattr(getattr(self, name), 'robot_name')]

    def run_keyword(self, name: str, args: list, kwargs: dict) -> typing.Any:
        """
        Runs the `name` keyword, with `args` as positional arguments, and `kwargs` as named arguments.
        Returns the keyword returned value. It is used by the `Robot Framework`.

        :param name: The keyword.
        :param args: Positional arguments.
        :param kwargs: Named arguments.
        :return: Keyword returned value.
        """
        return getattr(self, name)(*args, **kwargs)

    def get_keyword_documentation(self, name: str) -> str:
        """
        Returns the documentation string of the `name` keyword. It is used by the `Robot Framework`.

        :param name: The keyword.
        :return: Documentation string of the keyword.
        """
        if name == "__intro__":
            return inspect.getdoc(RobopomPage)
        return inspect.getdoc(getattr(self, name))

    # def get_keyword_arguments(self, name):
    #     value = []
    #     signature = inspect.signature(getattr(self, name))
    #     for p in signature.parameters.values():
    #         p: inspect.Parameter
    #         s = p.name
    #         if p.kind == inspect.Parameter.VAR_POSITIONAL:
    #             s = f"*{s}"
    #         elif p.kind == inspect.Parameter.VAR_KEYWORD:
    #             s = f"**{s}"
    #         default = p.default
    #         if default is not inspect.Parameter.empty:
    #             s = f"{s} = {default}"
    #         value.append(s)
    #     return value

    def get_keyword_arguments(self, name: str) -> list:
        """
        Returns the arguments list of the `name` keyword. It is used by the `Robot Framework`.

        :param name: The keyword.
        :return: The arguments list.
        """
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

    @staticmethod
    def _get_arg_spec(func_or_method: typing.Callable) -> typing.Tuple[typing.List[str],
                                                                       typing.Iterator[typing.Tuple],
                                                                       typing.Optional[str],
                                                                       typing.Optional[str]]:
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
        return getattr(getattr(self, name), 'robot_types')

    def add_to_model_if_needed(self) -> None:
        """
        Add this `RobopomPage` to the model tree (if it has no been added before).

        :return: None.
        """
        if (self.page_file_path in RobopomPage.added_to_model_page_file_paths) is False:
            self.init_page_elements()
            RobopomPage.added_to_model_page_file_paths.append(self.page_file_path)

    def selenium_library(self) -> SeleniumLibrary.SeleniumLibrary:
        """
        Returns the `SeleniumLibrary` instance been used.

        :return: The SeleniumLibrary instance.
        """
        return self.built_in.get_library_instance(self.selenium_library_name)

    def robopom_plugin(self) -> robopom_selenium_plugin.RobopomSeleniumPlugin:
        """
        Returns the `RobopomSeleniumPlugin` been used.

        :return: The RobopomSeleniumPlugin.
        """
        return getattr(self.selenium_library(), "robopom_plugin")

    def parent_page_library(self) -> RobopomPage:
        """
        Returns the parent page library object (`RobopomPage` instance) that represents the parent of this page.

        :return: The parent page library object.
        """
        return self.built_in.get_library_instance(self.parent_page_name) if self.parent_page_name is not None else None

    def page_object(self) -> model.PageObject:
        """
        Returns the page object (`PageObject` instance) associated to this page.

        :return: The page object associated to this page.
        """
        self.add_to_model_if_needed()
        po = self.robopom_plugin().get_component(self.page_path)
        assert isinstance(po, model.PageObject), f"page_object should be a PageObject, but it is a {type(po)}"
        return po

    def parent_page_object(self) -> typing.Optional[model.PageObject]:
        """
        The page object (`PageObject` instance) associated to the `parent` this page.

        :return: The page object associated to the parent this page.
        """
        if self.parent_page_path is None:
            return None
        po = self.robopom_plugin().get_component(self.parent_page_path)
        assert isinstance(po, model.PageObject), \
            f"parent_page_object should be a PageObject, but it is a {type(po)}"
        return po

    def parent_pages_names(self) -> typing.List[str]:
        """
        Returns the list of names of all the `ancestors` pages (starting from `root`).

        :return: List of names of all the ancestors pages.
        """
        if self.parent_page_name is None:
            return []
        else:
            value = self.parent_page_library().parent_pages_names()
            value.append(self.parent_page_name)
            return value

    @robot_deco.keyword
    def get_page_name(self) -> str:
        """
        Returns the name of the page.
        """
        return self.page_name

    @robot_deco.keyword
    def get_page(self) -> typing.Optional[model.PageObject]:
        """
        Returns the `page object` of this page.
        """
        return self.page_object()

    @robot_deco.keyword
    def get_model_file(self) -> typing.Optional[os.PathLike]:
        """
        Returns the file path of the YAML model file. If page has no model file associated, it returns 'None'.
        """
        return self.model_file

    @robot_deco.keyword(types=[str])
    def get_page_element(self, path: str) -> model.PageComponent:
        """
        Returns the `page component` defined by `path`. If `path` is `None`, it returns the `page object`.

        Parameter `path` can be a real path, or a `short`.
        """
        if path is None:
            return self.page_object()

        sep = constants.SEPARATOR

        # Try to find component by short
        if sep not in path and self.robopom_plugin().exists_component_with_short(self.page_name, path):
            return self.robopom_plugin().get_component_with_short(self.page_name, path)

        path = self.robopom_plugin().remove_path_prefix(path)
        path = self.robopom_plugin().remove_separator_prefix(path)
        path = self.robopom_plugin().remove_root_prefix(path)
        path = self.robopom_plugin().remove_separator_prefix(path)

        for parent_name in self.parent_pages_names():
            prefix = f"{parent_name}{sep}"
            if path.startswith(prefix):
                path = path[len(parent_name):]
                path = f"{self.page_name}{path}"
                break

        if not path.startswith(f"{self.page_name}{sep}"):
            path = f"{self.page_name}{sep}{path}"

        element = self.robopom_plugin().get_component(path)
        assert isinstance(element, model.PageComponent), \
            f"Element should be a PageComponent, but it is a {type(element)}"
        return element

    @robot_deco.keyword(types=[str])
    def get_page_elements_paths(self, path: str) -> typing.List[str]:
        """
        Returns a list with the `path` of every `page element` obtained from the `page elements` (multiple)
        where `path` points to.

        `path` (string): This path should point to a `page elements` (multiple) object.
        Otherwise, this keyword generates an error.
        """
        plural_element = self.get_page_element(path)
        assert isinstance(plural_element, model.PageElements), \
            f"plural_element should be a PageElements instance, bu it is a {type(plural_element)}"
        return [page_element.absolute_path for page_element in plural_element.page_elements]

    @robot_deco.keyword(types=[str,
                               str,
                               typing.Union[list, str],
                               dict,
                               typing.Union[bool, str],
                               typing.Union[str, model.PageElement],
                               typing.Union[int, str],
                               str,
                               typing.Union[int, str], ])
    def add_page_element_generator_instance(self,
                                            generator_path: str,
                                            name: str = None,
                                            format_args: typing.Union[typing.List[str], str] = None,
                                            format_kwargs: typing.Dict[str, str] = None,
                                            # *,
                                            always_visible: typing.Union[bool, str] = None,
                                            html_parent: typing.Union[str, model.PageElement] = None,
                                            order: typing.Union[int, str] = None,
                                            default_role: str = None,
                                            prefer_visible: typing.Union[bool, str] = None,
                                            ) -> str:
        """
        Adds a `page element generator instance` from the page element generator defined by `generator_path`
        to the model tree, and returns the `path` of the generated `page element`.

        `generator_path` (string): Path that should point to a `page element generator`.
        Otherwise, it generates an error.

        `name` (string): Optional. Name of the new generated page element.
        If not provided, a pseudo random numeric string (string with only numeric characters) is used.

        `format_args` (list or string): Optional. The `Python format arguments` (list) used in the `locator_generator`
        of the page element generator to determine the final `locator` of the new page element.
        It can be a list of strings (or just a single string, if the list has just one element).

        `format_kwargs` (dictionary): Optional. The` Python format keyword arguments` (dictionary)
        used in the `locator_generator` of the page element generator to determine the final `locator`
        of the new page element.

        `always_visible` (boolean or True-False-like-string): Optional. Establishes if the generated page element
        should always be visible in the page. Default value: Value of the `always_visible` property of the generator
        in `generator_path`.

        `html_parent` (object or string): Optional. If the generator `parent` is not the `real html parent`
        in the page, can be set here. Can be a page element (object) or a SeleniumLibrary locator (string).
        Default value: Value of the `html_parent` property of the generator in `generator_path`.

        `order` (integer or integer-like-string): Optional. If the generated `locator` returns more than one element,
        you can determine which to use (zero-based).
        Default value: Value of the `order` property of the generator in `generator_path`.

        `default_role` (string): Optional. Establishes the default role of the generated page element that is used
        in get/set operations.
        Default value: Value of the `default_role` property of the generator in `generator_path`.
        If not provided here nor in the generator in `generator_path`, Robopom tries to guess it
        ('text' is used as default if can not guess).
        Possible values: `text`, `select`, `checkbox`, `password`.

        `prefer_visible` (boolean or True-False-string): Optional. If `prefer_visible` is `True`
        and `locator` returns more than one element, the first 'visible' element is used.
        If `False`, the first element is used (visible or not). Default value: Value of the `prefer_visible`
        property of the generator in `generator_path`.
        """
        if isinstance(format_args, str):
            format_args = [format_args]
        if isinstance(always_visible, str):
            if always_visible.casefold() == "True".casefold():
                always_visible = True
            elif always_visible.casefold() == "False".casefold():
                always_visible = False
            else:
                assert False, \
                    f"'always_visible' should be a boolean or 'True-False-like-string', but it is {always_visible}"
        if isinstance(order, str):
            order = int(order)
        if isinstance(prefer_visible, str):
            if prefer_visible.casefold() == "True".casefold():
                prefer_visible = True
            elif prefer_visible.casefold() == "False".casefold():
                prefer_visible = False
            else:
                assert False, \
                    f"'prefer_visible' should be a boolean or 'True-False-like-string', but it is {prefer_visible}"

        generator_element = self.get_page_element(generator_path)
        assert isinstance(generator_element, model.PageElementGenerator), \
            f"generator_element should be a PageElementGenerator instance, bu it is a {type(generator_element)}"
        instance = generator_element.page_element_with(
            name=name,
            format_args=format_args,
            format_kwargs=format_kwargs,
            always_visible=always_visible,
            html_parent=html_parent,
            order=order,
            default_role=default_role,
            prefer_visible=prefer_visible,
        )
        return instance.absolute_path

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
        over_keyword = f"{self.page_name}.{constants.OVERRIDE_PREFIX} {keyword}"

        if self.robopom_plugin().keyword_exists(over_keyword):
            run_args = list(args[:])
            run_args += [f"{key}={value}" for key, value in kwargs.items()]
            return self.built_in.run_keyword(over_keyword, *run_args)
        else:
            return method(*args, **kwargs)

    @robot_deco.keyword(types=[typing.Union[str, model.AnyConcretePageElement]])
    def wait_until_visible(self,
                           element: typing.Union[model.AnyConcretePageElement, str],
                           timeout=None, ) -> None:
        """
        Test execution waits until `element` is visible.

        `element` (object or string): The page element that needs to be visible in page to continue execution.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `timeout` (Robot Framework Time): The maximum waiting time. If `element` is not visible after this time,
        an error is generated. Default value: The timeout defined when SeleniumLibrary was imported.

        Tags: flatten
        """
        if isinstance(element, str):
            element = self.get_page_element(element)
        self.robopom_plugin().wait_until_page_element_is_visible(element, timeout)

    @robot_deco.keyword(types=[None, typing.Union[bool, str]])
    def wait_until_loaded(self,
                          timeout=None,
                          # *,
                          set_library_search_order: typing.Union[bool, str] = True) -> None:
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
            self.core_wait_until_loaded,
            timeout,
            set_library_search_order=set_library_search_order,
        )

    @robot_deco.keyword
    def core_wait_until_loaded(self,
                               timeout=None,
                               # *,
                               set_library_search_order: typing.Union[bool, str] = True, ) -> None:
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
        if isinstance(set_library_search_order, str):
            if set_library_search_order.casefold() == "True".casefold():
                set_library_search_order = True
            elif set_library_search_order.casefold() == "False".casefold():
                set_library_search_order = False
            else:
                assert False, \
                    f"'set_library_search_order' should be a boolean or 'True-False-like-string', " \
                    f"but it is {set_library_search_order}"
        if set_library_search_order:
            self.built_in.set_library_search_order(self.page_name)

        if self.parent_page_library() is not None:
            self.parent_page_library().wait_until_loaded(timeout)
        self.page_object().wait_until_loaded(timeout)

        if set_library_search_order:
            self.built_in.set_library_search_order(self.page_name)

    @robot_deco.keyword
    def init_page_elements(self) -> None:
        """
        Default implementation: Initializes the page components defined in the page model file.

        This keyword should not be called directly (you usually call `Ẁait Until Loaded`).
        It can be overridden defining a 'Override Init Page Elements' keyword in the `page resource file`.
        Calling `Core Init Page Elements` from that keyword, you can run the default implementation.
        This override can be used to create additional `page components` that can not be added
        to the YAML `page model file` for some reason.
        """
        self._override_run("Init Page Elements", self.core_init_page_elements)

    @robot_deco.keyword
    def core_init_page_elements(self) -> None:
        """
        Initializes the page components defined in the page model file.

        This keyword should only be called from a `Override Init Page Elements` custom keyword
        in the `page resource file`.
        """

        if self.model_file is not None:
            generic_page = component_loader.ComponentLoader.load_generic_component_from_file(self.model_file)
        else:
            generic_page = model.GenericComponent(name=self.page_name, component_type="PageObject")

        parent_generic_page = None
        if self.parent_page_name is not None and self.parent_page_library().model_file is not None:
            parent_generic_page = component_loader.ComponentLoader.load_generic_component_from_file(
                self.parent_page_library().model_file,
            )
        if parent_generic_page is not None:
            generic_page.update_with_imported(parent_generic_page)

        page = generic_page.get_component_type_instance()
        self.robopom_plugin().add_page_component(page)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], str])
    def perform_set_text(self,
                         element: typing.Union[model.PageElement, str],
                         value: typing.Optional[str] = None) -> None:
        """
        Sets the text of an `element`. If it can not be done (because `element` is not an `input`, for example),
        it generates an error.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `value` (string or None): The text value. If `None`, no action is performed.

        Tags: flatten
        """
        if value is None:
            return
        element = self.get_page_element(element) if isinstance(element, str) else element
        # SeleniumLibrary.FormElementKeywords(self.selenium_library()).input_text(element.path_locator, value)
        self.robopom_plugin().input_text(element.path_locator, value)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement]])
    def perform_get_text(self, element: typing.Union[model.PageElement, str]) -> typing.Optional[str]:
        """
        Returns the text of an `element`. If it is an `input`, it returns the text written in it.
        If not, it returns the text that the element contains.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        Tags: flatten
        """
        element = self.get_page_element(element) if isinstance(element, str) else element
        if not element.is_present():
            return None
        text = SeleniumLibrary.ElementKeywords(self.selenium_library()).get_text(element.path_locator)
        if text in [None, ""] and element.tag_name.casefold() == "input".casefold():
            text = SeleniumLibrary.ElementKeywords(self.selenium_library()).get_value(element.path_locator)
        return text

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], str])
    def perform_set_password(self,
                             element: typing.Union[model.PageElement, str],
                             value: typing.Optional[str] = None) -> None:
        """
        Sets the text of an `element`. If it can not be done (because `element` is not an `input`, for example),
        it generates an error.

        It is the same as Perform Text Set, but `value` is not written in logs.
        NOTE: Mind that, if log level is `trace`, `value` is written because all parameters values are always written.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `value` (string or None): The text value. If `None`, no action is performed.

        Tags: flatten
        """
        if value is None:
            return
        element = self.get_page_element(element) if isinstance(element, str) else element
        # SeleniumLibrary.FormElementKeywords(self.selenium_library()).input_password(element.path_locator, value)
        self.robopom_plugin().input_password(element.path_locator, value)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement]])
    def perform_get_select(
            self,
            element: typing.Union[model.PageElement, str],
    ) -> typing.Union[None, typing.List[str]]:
        """
        Returns the list of selected labels in `element` (it should be a html `select`).

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        Tags: flatten
        """
        element = self.get_page_element(element) if isinstance(element, str) else element
        if not element.is_present():
            return None
        value = SeleniumLibrary.SelectElementKeywords(self.selenium_library()) \
            .get_selected_list_labels(element.path_locator)
        # if len(value) == 1:
        #     value = value[0]
        return value

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], typing.Union[None, str, int, list]])
    def perform_set_select(self,
                           element: typing.Union[model.PageElement, str],
                           value: typing.Union[None, str, int, typing.List[str, int]] = None) -> None:
        """
        Sets the selected item of an `element` (it should be a html `select`).

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `value` (string or integer or list or None): The value to set. If `None`, no action is performed.
        If it is a string, the item with that label is selected.
        It it is an integer, the item with that index (zero based) is selected.
        If it is a list (with string or integers in it), that items are selected.

        Tags: flatten
        """
        if value is None:
            return

        element = self.get_page_element(element) if isinstance(element, str) else element
        if isinstance(value, list) and len(value) == 0:
            # SeleniumLibrary.SelectElementKeywords(self.selenium_library()) \
            #     .select_from_list_by_label(element.path_locator)
            self.robopom_plugin().select_from_list_by_label(element.path_locator)
            return

        if isinstance(value, str) or isinstance(value, int):
            value = [value]

        value_str = []
        value_int = []
        assert isinstance(value, list), f"value should be a list, but is a {type(value)}"
        for v in value:
            if isinstance(v, str):
                value_str.append(v)
            elif isinstance(v, int):
                value_int.append(v)
            else:
                assert False, f"v should be a str or an int, but it is a {type(v)}"
        if len(value_str) > 0:
            # SeleniumLibrary.SelectElementKeywords(self.selenium_library()).select_from_list_by_label(
            #     element.path_locator,
            #     *value_str,
            # )
            self.robopom_plugin().select_from_list_by_label(element.path_locator, *value_str)
        if len(value_int) > 0:
            # SeleniumLibrary.SelectElementKeywords(self.selenium_library()).select_from_list_by_index(
            #     element.path_locator,
            #     *value_int,
            # )
            self.robopom_plugin().select_from_list_by_index(element.path_locator, *value_int)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement]])
    def perform_get_checkbox(self, element: typing.Union[model.PageElement, str]) -> typing.Optional[bool]:
        """
        Returns if checkbox `element` is selected (boolean).

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        Tags: flatten
        """
        element = self.get_page_element(element) if isinstance(element, str) else element
        if not element.is_present():
            return None
        return element.is_selected()

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], bool])
    def perform_set_checkbox(self,
                             element: typing.Union[model.PageElement, str],
                             value: typing.Optional[bool, str] = None) -> None:
        """
        Sets the selected status of the checkbox `element`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `value` (boolean or True-False-string or None): The value to set (`True` -> selected, `False` -> Not selected).
        If `None`, no action is performed.

        Tags: flatten
        """
        if value is None:
            return
        if isinstance(value, str):
            if value.casefold() == "True".casefold():
                value = True
            elif value.casefold() == "False".casefold():
                value = False
            else:
                assert False, \
                    f"'value' should be a boolean or 'True-False-like-string', but it is {value}"

        element = self.get_page_element(element) if isinstance(element, str) else element
        if value:
            # SeleniumLibrary.FormElementKeywords(self.selenium_library()).select_checkbox(element.path_locator)
            self.robopom_plugin().select_checkbox(element.path_locator)
        else:
            # SeleniumLibrary.FormElementKeywords(self.selenium_library()).unselect_checkbox(element.path_locator)
            self.robopom_plugin().unselect_checkbox(element.path_locator)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], str])
    def perform_action(self,
                       element: typing.Union[model.PageElement, str],
                       action: typing.Optional[str] = None) -> None:
        """
        Performs an action in `element`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `value` (string or None): The action to perform. Possible values: `click`, `double_click`, `context_click`.
        If `None`, no action is performed.

        Tags: flatten
        """
        if action is None:
            return
        element = self.get_page_element(element) if isinstance(element, str) else element
        if action.casefold() == constants.ACTION_CLICK.casefold():
            # SeleniumLibrary.ElementKeywords(self.selenium_library()).click_element(element.path_locator)
            self.robopom_plugin().click_element(element.path_locator)
        elif action.casefold() == constants.ACTION_DOUBLE_CLICK.casefold():
            # SeleniumLibrary.ElementKeywords(self.selenium_library()).double_click_element(element.path_locator)
            self.robopom_plugin().double_click_element(element.path_locator)
        elif action.casefold() == constants.ACTION_CONTEXT_CLICK.casefold():
            # SeleniumLibrary.ElementKeywords(self.selenium_library()).open_context_menu(element.path_locator)
            self.robopom_plugin().open_context_menu(element.path_locator)

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def perform_on(self,
                   element: typing.Union[model.PageElement, str],
                   command: typing.Any = None) -> typing.Any:
        """
        Performs a single command in `element`.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.

        `command` (any): The command to execute on `element`.

        A `command` should have one of these structures:

        - `None`. No action is performed.
        - `value`. Same as `set:value` (next line). It allow non string values (booleans, numbers...)
        - `set:value`. Tries to set the `element` value, based on it's `default_role` (if defined) or html `tag`.
        - `get:`. Tries to set the `element` value, based on it's `default_role` (if defined) or html `tag`.
        - `set_text:value`. Same as Perform Set Text.
        - `get_text:`. Same as Perform Get Text.
        - `set_password:value`. Same as Perform Set Password.
        - `get_password:`. Same as Perform Get Password.
        - `set_select:value`. Same as Perform Set Select.
        - `get_select:`. Same as Perform Get Select.
        - `set_checkbox:value`. Same as Perform Set Checkbox.
        - `get_checkbox:`. Same as Perform Get Checkbox.
        - `assert_equals:`. Same as Assert Equals.
        - `assert_not_equals:`. Same as Assert Not Equals.
        - `assert_equals_ignore_case:`. Same as Assert Equals Ignore Case.
        - `assert_not_equals_ignore_case:`. Same as Assert Not Equals Ignore Case.
        - `assert_value_greater_than_expected:`. Same as Assert Value Greater Than Expected.
        - `assert_value_greater_or_equal_than_expected:`. Same as Assert Value Greater Or Equal Than Expected.
        - `assert_value_lower_than_expected:`. Same as Assert Value Lower Than Expected.
        - `assert_value_lower_or_equal_than_expected:`. Same as Assert Value Lower or Equal Than Expected.
        - `assert_value_in_expected:`. Same as Assert Value In Expected.
        - `assert_value_not_in_expected:`. Same as Assert Value Not In Expected.
        - `assert_expected_in_value:`. Same as Assert Expected In Value.
        - `assert_expected_not_in_value:`. Same as Assert Expected Not In Value.
        - `assert_value_len_equals:`. Same as Assert Value Len Equals.
        - `assert_value_len_not_equals:`. Same as Assert Value Len Not Equals.
        - `assert_value_len_greater_than_expected:`. Same as Assert Value Len Greater Than Expected.
        - `assert_value_len_greater_or_equal_than_expected:`. Same as Assert Value Len Greater Or Equal Than Expected.
        - `assert_value_len_lower_than_expected:`. Same as Assert Value Len Lower Than Expected.
        - `assert_value_len_lower_or_equal_than_expected:`. Same as Assert Value Len Lower Or Equal Than Expected.
        - `assert_value_matches_regular_expression:`. Same as Assert Value Matches Regular Expression.
        - `assert_value_not_matches_regular_expression:`. Same as Assert Value Not Matches Regular Expression.

        Some of these commands are special:

        - `get:`. If a custom keyword `Get [element_path]` (where `element_path` is the path of `element`
          inside the page) is defined in the page resource file, that keyword is used to obtain the element's value.
        - `set:value` or `value`. If a custom keyword `Set [element_path]` (where `element_path` is the path
          of `element` inside the page) is defined in the page resource file, that keyword is used to set
          the element's value.

        Tags: flatten
        """
        if command is None:
            return
        element = self.get_page_element(element) if isinstance(element, str) else element

        # Prepare constants
        sep = constants.GET_SET_SEPARATOR

        set_pre = constants.SET_PREFIX.casefold() + sep.casefold()
        get_pre = constants.GET_PREFIX.casefold() + sep.casefold()

        text_set_pre = constants.SET_TEXT_PREFIX.casefold() + sep.casefold()
        text_get_pre = constants.GET_TEXT_PREFIX.casefold() + sep.casefold()
        password_set_pre = constants.SET_PASSWORD_PREFIX.casefold() + sep.casefold()
        password_get_pre = constants.GET_PASSWORD_PREFIX.casefold() + sep.casefold()
        select_set_pre = constants.SET_SELECT_PREFIX.casefold() + sep.casefold()
        select_get_pre = constants.GET_SELECT_PREFIX.casefold() + sep.casefold()
        checkbox_set_pre = constants.SET_CHECKBOX_PREFIX.casefold() + sep.casefold()
        checkbox_get_pre = constants.GET_CHECKBOX_PREFIX.casefold() + sep.casefold()

        action_pre = constants.ACTION_PREFIX.casefold() + sep.casefold()

        assert_equals_pre = constants.ASSERT_EQUALS_PREFIX.casefold() + sep.casefold()
        assert_not_equals_pre = constants.ASSERT_NOT_EQUALS_PREFIX.casefold() + sep.casefold()
        assert_equals_ignore_case_pre = constants.ASSERT_EQUALS_IGNORE_CASE_PREFIX.casefold() + sep.casefold()
        assert_not_equals_ignore_case_pre = constants.ASSERT_NOT_EQUALS_IGNORE_CASE_PREFIX.casefold() + sep.casefold()
        assert_value_greater_than_expected_pre = \
            constants.ASSERT_VALUE_GREATER_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_greater_or_equal_than_expected_pre = \
            constants.ASSERT_VALUE_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_lower_than_expected_pre = \
            constants.ASSERT_VALUE_LOWER_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_lower_or_equal_than_expected_pre = \
            constants.ASSERT_VALUE_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_in_expected_pre = constants.ASSERT_VALUE_IN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_not_in_expected_pre = constants.ASSERT_VALUE_NOT_IN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_expected_in_value_pre = constants.ASSERT_EXPECTED_IN_VALUE_PREFIX.casefold() + sep.casefold()
        assert_expected_not_in_value_pre = constants.ASSERT_EXPECTED_NOT_IN_VALUE_PREFIX.casefold() + sep.casefold()
        assert_value_len_equals_pre = constants.ASSERT_VALUE_LEN_EQUALS_PREFIX.casefold() + sep.casefold()
        assert_value_len_not_equals_pre = constants.ASSERT_VALUE_LEN_NOT_EQUALS_PREFIX.casefold() + sep.casefold()
        assert_value_len_greater_than_expected_pre = \
            constants.ASSERT_VALUE_LEN_GREATER_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_len_greater_or_equal_than_expected_pre = \
            constants.ASSERT_VALUE_LEN_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_len_lower_than_expected_pre = \
            constants.ASSERT_VALUE_LEN_LOWER_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_len_lower_or_equal_than_expected_pre = \
            constants.ASSERT_VALUE_LEN_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX.casefold() + sep.casefold()
        assert_value_matches_regular_expression_pre = \
            constants.ASSERT_VALUE_MATCHES_REGULAR_EXPRESSION_PREFIX.casefold() + sep.casefold()
        assert_value_not_matches_regular_expression_pre = \
            constants.ASSERT_VALUE_NOT_MATCHES_REGULAR_EXPRESSION_PREFIX.casefold() + sep.casefold()

        # Generic get/set conversion
        role_set_prefix_map = {
            constants.ROLE_TEXT: f"{constants.SET_TEXT_PREFIX}{sep}",
            constants.ROLE_PASSWORD: f"{constants.SET_PASSWORD_PREFIX}{sep}",
            constants.ROLE_SELECT: f"{constants.SET_SELECT_PREFIX}{sep}",
            constants.ROLE_CHECKBOX: f"{constants.SET_CHECKBOX_PREFIX}{sep}",
        }
        role_set_method_map = {
            constants.ROLE_TEXT: self.perform_set_text,
            constants.ROLE_PASSWORD: self.perform_set_password,
            constants.ROLE_SELECT: self.perform_set_select,
            constants.ROLE_CHECKBOX: self.perform_set_checkbox,
        }

        role_get_prefix_map = {
            constants.ROLE_TEXT: f"{constants.GET_TEXT_PREFIX}{sep}",
            constants.ROLE_PASSWORD: f"{constants.GET_PASSWORD_PREFIX}{sep}",
            constants.ROLE_SELECT: f"{constants.GET_SELECT_PREFIX}{sep}",
            constants.ROLE_CHECKBOX: f"{constants.GET_CHECKBOX_PREFIX}{sep}",
        }

        if not isinstance(command, str):
            # command is not a string, asume command is "set:"
            executed = self.run_custom_set_keyword(element, command)
            if not executed:
                role = element.default_role
                if role is None:
                    role = self.guess_role(element)
                role_set_method_map[role.lower()](element, command)
            return

        if command.casefold().startswith(set_pre):
            command = command[len(set_pre):]
            executed = self.run_custom_set_keyword(element, command)
            if executed:
                return
            role = element.default_role
            if role is None:
                role = self.guess_role(element)
            command = f"{role_set_prefix_map[role.lower()]}{command}"

        if command.startswith(get_pre):
            command = command[len(get_pre):]
            executed, value = self.run_custom_get_keyword(element)
            if executed:
                return value
            role = element.default_role
            if role is None:
                role = self.guess_role(element)
            command = f"{role_get_prefix_map[role.lower()]}{command}"

        # Specific get/set/action/assert
        if command.casefold().startswith(text_set_pre):
            command = command[len(text_set_pre):]
            self.perform_set_text(element, command)
            return
        elif command.casefold().startswith(text_get_pre):
            return self.perform_get_text(element)
        elif command.casefold().startswith(password_set_pre):
            command = command[len(password_set_pre):]
            self.perform_set_password(element, command)
            return
        elif command.casefold().startswith(password_get_pre):
            return self.perform_get_text(element)
        elif command.casefold().startswith(select_set_pre):
            command = command[len(select_set_pre):]
            self.perform_set_select(element, command)
            return
        elif command.casefold().startswith(select_get_pre):
            return self.perform_get_select(element)
        elif command.casefold().startswith(checkbox_set_pre):
            command = command[len(checkbox_set_pre):]
            if command.casefold() in constants.TRUE:
                self.perform_set_checkbox(element, True)
            else:
                self.perform_set_checkbox(element, False)
            return
        elif command.casefold().startswith(checkbox_get_pre):
            return self.perform_get_checkbox(element)
        # Action
        elif command.casefold().startswith(action_pre):
            command = command[len(action_pre):]
            self.perform_action(element, command)
            return
        # Assert
        elif command.casefold().startswith(assert_equals_pre):
            command = command[len(assert_equals_pre):]
            self.assert_equals(element, command)
            return
        elif command.casefold().startswith(assert_not_equals_pre):
            command = command[len(assert_not_equals_pre):]
            self.assert_not_equals(element, command)
            return
        elif command.casefold().startswith(assert_equals_ignore_case_pre):
            command = command[len(assert_equals_ignore_case_pre):]
            self.assert_equals_ignore_case(element, command)
            return
        elif command.casefold().startswith(assert_not_equals_ignore_case_pre):
            command = command[len(assert_not_equals_ignore_case_pre):]
            self.assert_not_equals_ignore_case(element, command)
            return
        elif command.casefold().startswith(assert_value_greater_than_expected_pre):
            command = command[len(assert_value_greater_than_expected_pre):]
            self.assert_value_greater_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_greater_or_equal_than_expected_pre):
            command = command[len(assert_value_greater_or_equal_than_expected_pre):]
            self.assert_value_greater_or_equal_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_lower_than_expected_pre):
            command = command[len(assert_value_lower_than_expected_pre):]
            self.assert_value_lower_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_lower_or_equal_than_expected_pre):
            command = command[len(assert_value_lower_or_equal_than_expected_pre):]
            self.assert_value_lower_or_equal_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_in_expected_pre):
            command = command[len(assert_value_in_expected_pre):]
            self.assert_value_in_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_not_in_expected_pre):
            command = command[len(assert_value_not_in_expected_pre):]
            self.assert_value_not_in_expected(element, command)
            return
        elif command.casefold().startswith(assert_expected_in_value_pre):
            command = command[len(assert_expected_in_value_pre):]
            self.assert_expected_in_value(element, command)
            return
        elif command.casefold().startswith(assert_expected_not_in_value_pre):
            command = command[len(assert_expected_not_in_value_pre):]
            self.assert_expected_not_in_value(element, command)
            return
        elif command.casefold().startswith(assert_value_len_equals_pre):
            command = command[len(assert_value_len_equals_pre):]
            self.assert_value_len_equals(element, command)
            return
        elif command.casefold().startswith(assert_value_len_not_equals_pre):
            command = command[len(assert_value_len_not_equals_pre):]
            self.assert_value_len_not_equals(element, command)
            return
        elif command.casefold().startswith(assert_value_len_greater_than_expected_pre):
            command = command[len(assert_value_len_greater_than_expected_pre):]
            self.assert_value_len_greater_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_len_greater_or_equal_than_expected_pre):
            command = command[len(assert_value_len_greater_or_equal_than_expected_pre):]
            self.assert_value_len_greater_or_equal_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_len_lower_than_expected_pre):
            command = command[len(assert_value_len_lower_than_expected_pre):]
            self.assert_value_len_lower_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_len_lower_or_equal_than_expected_pre):
            command = command[len(assert_value_len_lower_or_equal_than_expected_pre):]
            self.assert_value_len_lower_or_equal_than_expected(element, command)
            return
        elif command.casefold().startswith(assert_value_matches_regular_expression_pre):
            command = command[len(assert_value_matches_regular_expression_pre):]
            self.assert_value_matches_regular_expression(element, command)
            return
        elif command.casefold().startswith(assert_value_not_matches_regular_expression_pre):
            command = command[len(assert_value_not_matches_regular_expression_pre):]
            self.assert_value_not_matches_regular_expression(element, command)
            return
        else:
            # Assume command is "set:"
            executed = self.run_custom_set_keyword(element, command)
            if not executed:
                role = element.default_role
                if role is None:
                    role = self.guess_role(element)
                role_set_method_map[role.lower()](element, command)
            return

    def guess_role(self, element: typing.Union[model.PageElement, str]) -> str:
        """
        Returns an attempt to guess the `role` (str) of the provided `element`.

        :param element: The element.  Can be a PageElement or the path (string) of a PageElement.
        :return: The guessed role (str).
        """
        element = self.get_page_element(element) if isinstance(element, str) else element
        tag_name = element.tag_name

        if tag_name is None:
            # ROLE_TEXT is the default
            return constants.ROLE_TEXT

        tag_name_casefold = tag_name.casefold()
        if tag_name_casefold == "select".casefold():
            return constants.ROLE_SELECT
        if element.tag_name.casefold() == "input".casefold():
            element_type = element.get_attribute("type")
            if isinstance(element_type, str):
                if element_type.casefold() == "checkbox".casefold():
                    return constants.ROLE_CHECKBOX
                if element_type.casefold() == "password".casefold():
                    return constants.ROLE_PASSWORD
        return constants.ROLE_TEXT

    def run_custom_get_keyword(self, element: typing.Union[model.PageElement, str]) -> typing.Tuple[bool, typing.Any]:
        """
        Tries to run a custom `get` keyword (a keyword that "gets the value" of an element).
        If that custom keyword exists, it is run and a tuple (`True`, `value`) is returned,
        where the `value` is the returned value of that custom keyword.
        If that custom keyword does not exist, a tuple (`False`, `None`) is returned.

        :param element: The element that we want to get the value.
                        Can be a PageElement or the path (string) of a PageElement.
        :return: A tuple (True, value) if the custom keyword exists, (False, None) if not.
        """
        element = self.get_page_element(element) if isinstance(element, str) else element

        # short keyword
        if element.short is not None:
            keyword = f"{element.page.name}.Get {element.short}"
            if self.robopom_plugin().keyword_exists(keyword):
                return True, self.built_in.run_keyword(keyword)

        # path keyword
        keyword = f"{element.page.name}.Get {element.page_path}"
        if self.robopom_plugin().keyword_exists(keyword):
            return True, self.built_in.run_keyword(keyword)

        parent_pages = self.parent_pages_names()
        parent_pages.reverse()
        for parent_name in parent_pages:
            # short keyword
            if element.short is not None:
                keyword = f"{parent_name}.Get {element.short}"
                if self.robopom_plugin().keyword_exists(keyword):
                    return True, self.built_in.run_keyword(keyword)

            # path keyword
            keyword = f"{parent_name}.Get {element.page_path}"
            if self.robopom_plugin().keyword_exists(keyword):
                return True, self.built_in.run_keyword(keyword)
        else:
            return False, None

    def run_custom_set_keyword(self, element: typing.Union[model.PageElement, str], value: typing.Any) -> bool:
        """
        Tries to run a custom `set` keyword (a keyword that "sets the value" of an element).
        If that custom keyword exists, it is run and `True` is returned.
        If that custom keyword does not exist, `False` is returned.

        :param element: The element that we want to set the value.
                        Can be a PageElement or the path (string) of a PageElement.
        :param value: The value to set.
        :return: True if the keyword exists (and is run), False if not.
        """
        element = self.get_page_element(element) if isinstance(element, str) else element

        # short keyword
        if element.short is not None:
            keyword = f"{element.page.name}.Set {element.short}"
            if self.robopom_plugin().keyword_exists(keyword):
                self.built_in.run_keyword(keyword, value)
                return True

        # path keyword
        keyword = f"{element.page.name}.Set {element.page_path}"
        if self.robopom_plugin().keyword_exists(keyword):
            self.built_in.run_keyword(keyword, value)
            return True

        parent_pages = self.parent_pages_names()
        parent_pages.reverse()
        for parent_name in parent_pages:
            # short keyword
            if element.short is not None:
                keyword = f"{parent_name}.Set {element.short}"
                if self.robopom_plugin().keyword_exists(keyword):
                    self.built_in.run_keyword(keyword, value)
                    return True

            # path keyword
            keyword = f"{parent_name}.Set {element.page_path}"
            if self.robopom_plugin().keyword_exists(keyword):
                self.built_in.run_keyword(keyword, value)
                return True
        else:
            return False

    @robot_deco.keyword
    def perform(
            self,
            *varargs: typing.List[typing.Union[model.PageElement, str, bool, int, None]]) -> list:
        """
        Executes a series of Perform On actions. It returns a list based on the `get` commands received.

        `varargs`: The arguments received should be pairs of `element` and `command`
        (each one is a different parameter) that are perfomed in the same way as described in Perform On.

        For each 'get' command received, the value obtained with that `get` is added to the returned list.

        Tags: flatten
        """
        assert len(varargs) % 2 == 0, f"len(actions) should be even, but it is {len(varargs)}"
        # Transform actions in a List of Tuples
        action_tuples = []
        for i in range(0, len(varargs), 2):
            new_tuple = (varargs[i], varargs[i + 1])
            action_tuples.append(new_tuple)

        return_list = []
        for action_list in action_tuples:
            if len(action_list) < 2:
                continue
            element, command = action_list
            if command is None:
                continue
            value = self.perform_on(element, command)
            if isinstance(command, str) and command.lower().startswith(constants.GET_ACTIONS_PREFIXES):
                return_list.append(value)
        return return_list

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement]])
    def get_element_value(self, element: typing.Union[model.PageElement, str]) -> typing.Any:
        """
        Returns the `element`'s value.

        It is the same as:

        | Perform On | `element` | get: |

        As described in Perform On, if a custom keyword `Get [element_path]` (where `element_path` is the path
        of `element` inside the page) is defined in the page resource file, that keyword is used to obtain
        the element's value.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.
        """
        return self.perform_on(element, f"{constants.GET_PREFIX}{constants.GET_SET_SEPARATOR}")

    @robot_deco.keyword(types=[typing.Union[str, model.PageElement], None])
    def set_element_value(self,
                          element: typing.Union[model.PageElement, str],
                          value: typing.Any = None) -> None:
        """
        Sets the `element`'s value.

        It is the same as:

        | Perform On | `element` | `value` |

        As described in Perform On, if a custom keyword `Set [element_path]` (where `element_path` is the path
        of `element` inside the page) is defined in the page resource file, that keyword is used to set
        the element's value.

        `element` (object or string): The page element where action is performed.
        It can be a `page element` object, a `page elements` object (multiple), or the `path` (string) pointing to
        any of these objects.
        """
        return self.perform_on(element, value)

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
