from __future__ import annotations
import typing
import datetime
import dateutil.parser
import os
import pathlib
import time
import SeleniumLibrary
import robot.libraries.BuiltIn
import anytree.importer
import yaml
from . import model

web_element = SeleniumLibrary.locators.elementfinder.WebElement


class Plugin(SeleniumLibrary.LibraryComponent):
    """
    RobopomSeleniumPlugin is a plugin for Robot Framework SeleniumLibrary that makes easier to adopt the
    Page Object Model (POM) methodology.

    It can be imported using something like this:

    | Library | SeleniumLibrary | timeout=10 | plugins=robopom.Plugin, other_plugins.MyOtherPlugin |

    Here, `my_pages.resource` and `my_variables.yaml` are the paths of the `pages` file and `variables` file used in
    Update Variables File keyword.

    If the default values are ok for you (and you do not need any other SeleniumLibrary plugins), it can be simplified:

    | Library | SeleniumLibrary | timeout=10 | plugins=robopom.RobopomSeleniumPlugin |
    """
    POM_PREFIX = "pom"
    POM_LOCATOR_PREFIXES = [f"{POM_PREFIX}:", f"{POM_PREFIX}="]

    built_in = robot.libraries.BuiltIn.BuiltIn()

    PSEUDO_TYPE = {
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

    @staticmethod
    def default_datetime_parser(value: str, dayfirst: bool = True) -> datetime.datetime:
        return dateutil.parser.parse(value, dateutil.parser.parserinfo(dayfirst=dayfirst))

    @staticmethod
    def default_date_parser(value: str, dayfirst: bool = True) -> datetime.date:
        dt = Plugin.default_datetime_parser(value, dayfirst=dayfirst)
        return datetime.date(dt.year, dt.month, dt.day)

    @classmethod
    def is_pom_locator(cls, locator: typing.Any) -> bool:
        return isinstance(locator, str) and locator.startswith(tuple(cls.POM_LOCATOR_PREFIXES))

    @classmethod
    def is_pseudo_boolean(cls, value) -> bool:
        if isinstance(value, str):
            value = value.casefold()
        if value in cls.PSEUDO_BOOLEAN:
            return True
        else:
            return False

    @classmethod
    def pseudo_boolean_as_bool(cls, value) -> typing.Optional[bool]:
        if cls.is_pseudo_boolean(value) is False:
            return None
        return cls.PSEUDO_BOOLEAN[value]

    @classmethod
    def is_pseudo_type(cls, value) -> bool:
        if isinstance(value, str):
            value = value.casefold()
        if value in cls.PSEUDO_TYPE:
            return True
        else:
            return False

    @classmethod
    def pseudo_type_as_type(cls, value) -> typing.Optional[type]:
        if cls.is_pseudo_type(value) is False:
            return None
        return cls.PSEUDO_TYPE[value]

    @classmethod
    def remove_pom_prefix(cls, path: str) -> str:
        """
        It removes the `path prefix` (`path:` or `path=`) if the provided `path` starts with this prefix.
        Otherwise, it returns the same `path` string.

        :param path: The path string where we want to remove the prefix.
        :return: The string without the prefix.
        """
        new_path = path
        for prefix in cls.POM_LOCATOR_PREFIXES:
            if new_path.startswith(prefix):
                new_path = new_path.replace(prefix, "", 1)
        return new_path

    def __init__(self,
                 ctx: SeleniumLibrary,
                 set_library_search_order_in_wait_until_loaded: bool = True,
                 ) -> None:
        """
        Initializes a new `RobopomSeleniumPlugin`. It it executed by the `SeleniumLibrary` itself.

        :param ctx: The SeleniumLibrary instance, provided by the SeleniumLibrary itself.
        """
        self.pom_root = model.Node(name="", pom_root_for_plugin=self).resolve()

        # LibraryComponent.__init__(self, ctx)
        super().__init__(ctx)
        ctx.robopom_plugin = self

        self.set_library_search_order_in_wait_until_loaded = set_library_search_order_in_wait_until_loaded

        # Register Path Locator Strategy
        SeleniumLibrary.ElementKeywords(ctx).add_location_strategy(
            self.POM_PREFIX,
            self.pom_locator_strategy,
            persist=True,
        )

        # Register listener
        self.built_in.import_library("robopom.Listener")

        # self.working_dir = abspath(".")

    @property
    def selenium_library(self) -> SeleniumLibrary:
        return self.ctx

    def get_selenium_library_name(self) -> str:
        all_libs: typing.Dict[str] = self.built_in.get_library_instance(all=True)
        candidates = {name: lib for name, lib in all_libs.items() if lib == self.ctx}
        assert len(candidates) == 1, \
            f"Error in 'get_selenium_library_name'. There should be ony one library candidate, " \
            f"but candidates are: {candidates}"
        return list(candidates.keys())[0]

    def wait_until(self,
                   timeout: typing.Union[int, float] = None,
                   expected: typing.Any = True,
                   raise_error: bool = True,
                   error: str = None,
                   poll: typing.Union[int, float] = 0.2,
                   executable: typing.Callable = None,
                   args: list = None,
                   kwargs: dict = None, ) -> bool:
        if timeout is None:
            timeout = self.selenium_library.timeout
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        value = executable(*args, **kwargs)
        while timeout >= 0:
            if value == expected:
                break
            time.sleep(poll)
            timeout -= poll
            value = executable(*args, **kwargs)
        else:
            # Condition not met
            if error is None:
                error = f"Timeout ({timeout}) in 'wait_until': executable: {executable}, args: {args}, " \
                        f"kwargs: {kwargs}, expected: {expected}, raise_error: {raise_error}. " \
                        f"Last value obtained: {value}"
            if raise_error is True:
                assert False, error
            else:
                self.built_in.log(error)
                return False
        return True

    @SeleniumLibrary.base.keyword
    def keyword_exists(self, kw: str) -> bool:
        """
        Returns `True` if given keyword exists, `False` otherwise.
        """
        try:
            self.built_in.keyword_should_exist(kw)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def pom_locator_strategy(self, parent, locator: str, tag, constraints) -> typing.List[web_element]:
        """
        Keyword that defines the `Path Locator Strategy`.

        Usually it is not necessary to run this keyword directly (it is used by the Robopom Plugin internally).
        """
        # Validation
        assert isinstance(parent, web_element) is False, \
            f"'parent' should not be a WebElement in 'pom_locator_strategy', but it is: {parent}"
        assert tag is None, \
            f"'tag' should be a None in 'pom_locator_strategy', but it is: {tag}"
        assert constraints is None or (isinstance(constraints, dict) and len(constraints) == 0), \
            f"'constraints' should be a None or an empty dict in 'pom_locator_strategy', but it is: {constraints}"

        log_info = f"parent={parent}, locator={locator}, tag={tag}, constraints={constraints}"
        self.debug(f"Starting 'pom_locator_strategy' with: {log_info}")

        pom_node = self.get_node(locator)
        log_info = f"{log_info}. Real locator used: {pom_node.locator}"

        if pom_node.is_multiple is True:
            elements = pom_node.find_web_elements()
            log_info = f"{log_info}. Node is multiple"
        else:
            element = pom_node.find_web_element(required=False)
            if element is None:
                elements = []
            else:
                elements = [element]
            log_info = f"{log_info}. Node is not multiple"

        if len(elements) == 0:
            self.info(f"No element not found using 'Pom Locator Strategy': {log_info}")
        elif len(elements) == 1:
            self.debug(f"Found element '{elements[0]}' using 'Pom Locator Strategy': {log_info}")
        else:
            self.debug(f"Found elements '{elements}' using 'Pom Locator Strategy': {log_info}")
        return elements

    @SeleniumLibrary.base.keyword
    def log_pom_tree(self) -> None:
        """
        Writes the `model tree` to the log file.
        """
        self.info(self.pom_root.pom_tree)

    @SeleniumLibrary.base.keyword
    def exists_unique_node(self, name: str = None) -> bool:
        """
        Returns `True` if component defined by `path` (string) exists, `False` otherwise.
        """
        try:
            self.get_node(name)
        except anytree.ResolverError:
            return False
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def get_node(self, name: str) -> model.Node:
        """
        Returns the component obtained from `path`.

        If the component defined by path does not exist, it generates an error.

        `path` (string): Path of the component. If path is `None`, returns the root component.
        """
        name = self.remove_pom_prefix(name)
        return self.pom_root.find_node(name)

    @SeleniumLibrary.base.keyword
    def create_new_node(self,
                        # *,
                        name: str = None,
                        locator: str = None,
                        is_multiple: bool = None,
                        order: int = None,
                        wait_present: bool = None,
                        wait_visible: bool = None,
                        wait_enabled: bool = None,
                        wait_selected: bool = None,
                        html_parent: str = None,
                        smart_pick: bool = None,
                        is_template: bool = None,
                        template: typing.Union[str, model.Node] = None,
                        template_args: list = None,
                        template_kwargs: dict = None,
                        **kwargs) -> model.Node:

        return model.Node(name=name,
                          locator=locator,
                          is_multiple=is_multiple,
                          order=order,
                          wait_present=wait_present,
                          wait_visible=wait_visible,
                          wait_enabled=wait_enabled,
                          wait_selected=wait_selected,
                          html_parent=html_parent,
                          smart_pick=smart_pick,
                          is_template=is_template,
                          template=template,
                          template_args=template_args,
                          template_kwargs=template_kwargs,
                          **kwargs)

    @SeleniumLibrary.base.keyword
    def attach_node(self,
                    node: model.Node,
                    parent: typing.Union[model.Node, str] = None) -> str:
        """
        Adds `component` (object) to the model tree, inserting it as a child of `parent`.
        Returns the `path` of the inserted component.

        `parent` (object or string): If parent is `None`, component is inserted as a child of the root component.
        Can be the component (object) itself or the `path` (string) of the parent component.
        """
        if isinstance(parent, str):
            parent = self.get_node(parent)

        if parent is not None:
            node.parent = parent
            # Try to avoid duplicates
            if node.name is not None:
                # If find_node ends without error, it is OK
                parent.find_node(node.name, only_descendants=True)
        else:
            # Validate
            assert node.name is not None, f"Without 'parent', the node should have a 'name'"

            # Try to avoid duplicates
            nodes = [p for p in self.pom_root.children if p.name == node.name]
            assert len(nodes) == 0, \
                f"Page with name '{node.name}' already exists: {nodes}"
            # Add the new node
            node.parent = self.pom_root

        # Resolve node
        node.resolve()

        return node.full_name

    # def add_page_if_needed(self, page_lib: page.Page) -> None:
    #     """
    #     Adds a new page object to the model with the specified `name`. Returns the `path` of the inserted page object.
    #     """
    #     pages = [p for p in self.pages if page_lib.name == p.name]
    #     assert len(pages) <= 1, f"Too many pages with name '{page_lib.name}': {pages}"
    #     if len(pages) == 1:
    #         prev_node = pages[0]
    #         assert page_lib.page_resource_file_path == prev_node.file_path, \
    #             f"Trying to add a Page with duplicated name. " \
    #             f"New page: {page_lib.page_resource_file_path}. Previous page: {prev_node.file_path}"
    #         # No need to add, the page already exists
    #     else:
    #         # TODO: A ver qué pongo aquí
    #         self.pages.append(page_lib)

    @SeleniumLibrary.base.keyword
    def attach_new_node(self,
                        parent: typing.Union[model.Node, str],
                        # *,
                        name: str = None,
                        locator: str = None,
                        is_multiple: bool = None,
                        order: int = None,
                        wait_present: bool = None,
                        wait_visible: bool = None,
                        wait_enabled: bool = None,
                        wait_selected: bool = None,
                        html_parent: str = None,
                        smart_pick: bool = None,
                        is_template: bool = None,
                        template: typing.Union[str, model.Node] = None,
                        template_args: list = None,
                        template_kwargs: dict = None,
                        **kwargs) -> str:
        """
        Creates a new `page element` and adds it to the model tree. Returns the `path` of the inserted page element.

        `locator` (string): The SeleniumLibrary locator of the page element.

        `parent` (object or string): Parent of the page element newly created.
        Can be the page component (object) itself or the `path` (string) of the parent page component.

        `name` (string): Optional. Name of the new page element.
        If not provided, a pseudo random numeric string (string with only numeric characters) is used.

        `always_visible` (boolean or True-False-string): Optional. Establishes if the page element should always
        be visible in the page.
        Default value: `False`.

        `html_parent` (object or string): Optional. If `parent` is not the `real html parent` in the page,
        can be set here. Can be a page element (object) or a SeleniumLibrary locator (string).

        `order` (integer or integer-like-string): Optional. If `locator` returns more than one element,
        you can determine which to use (zero-based).

        `default_role` (string): Optional. Establishes the default role of the page element that is used
        in get/set operations. If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
        Possible values: `text`, `select`, `checkbox`, `password`.

        `prefer_visible` (boolean or True-False-string): Optional. If `prefer_visible` is `True`
        and `locator` returns more than one element, the first 'visible' element is used.
        If `False`, the first element is used (visible or not). Default value: `True`.
        """
        node = model.Node(name=name,
                          locator=locator,
                          is_multiple=is_multiple,
                          order=order,
                          wait_present=wait_present,
                          wait_visible=wait_visible,
                          wait_enabled=wait_enabled,
                          wait_selected=wait_selected,
                          html_parent=html_parent,
                          smart_pick=smart_pick,
                          is_template=is_template,
                          template=template,
                          template_args=template_args,
                          template_kwargs=template_kwargs,
                          **kwargs)
        return self.attach_node(node, parent)

    @SeleniumLibrary.base.keyword
    def set_node_name(self, node: typing.Union[model.Node, str], name: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.name = name

    @SeleniumLibrary.base.keyword
    def set_node_locator(self, node: typing.Union[model.Node, str], locator: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.locator = locator

    @SeleniumLibrary.base.keyword
    def set_node_is_multiple(self, node: typing.Union[model.Node, str], is_multiple: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.is_multiple = is_multiple

    @SeleniumLibrary.base.keyword
    def set_node_order(self, node: typing.Union[model.Node, str], order: typing.Optional[int]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.order = order

    @SeleniumLibrary.base.keyword
    def set_node_wait_present(self, node: typing.Union[model.Node, str], wait_present: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_present = wait_present

    @SeleniumLibrary.base.keyword
    def set_node_wait_visible(self, node: typing.Union[model.Node, str], wait_visible: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_visible = wait_visible

    @SeleniumLibrary.base.keyword
    def set_node_wait_enabled(self, node: typing.Union[model.Node, str], wait_enabled: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_enabled = wait_enabled

    @SeleniumLibrary.base.keyword
    def set_node_wait_selected(self, node: typing.Union[model.Node, str], wait_selected: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_selected = wait_selected

    @SeleniumLibrary.base.keyword
    def set_node_html_parent(self,
                             node: typing.Union[model.Node, str],
                             html_parent: typing.Union[None, str, model.Node]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if isinstance(html_parent, str):
            html_parent = self.get_node(html_parent)
        node.html_parent = html_parent

    @SeleniumLibrary.base.keyword
    def set_node_smart_pick(self, node: typing.Union[model.Node, str], smart_pick: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.smart_pick = smart_pick

    @SeleniumLibrary.base.keyword
    def set_node_is_template(self, node: typing.Union[model.Node, str], is_template: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.is_template = is_template

    @SeleniumLibrary.base.keyword
    def set_node_template(self, node: typing.Union[model.Node, str], template: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.template = template

    @SeleniumLibrary.base.keyword
    def set_node_template_args(self, node: typing.Union[model.Node, str], template_args: typing.Any) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if template_args is None:
            template_args = []
        if not isinstance(template_args, list):
            template_args = [template_args]
        node.template_args = template_args

    @SeleniumLibrary.base.keyword
    def set_node_template_kwargs(self,
                                 node: typing.Union[model.Node, str],
                                 template_kwargs: typing.Union[None, dict]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if template_kwargs is None:
            template_kwargs = {}
        node.template_kwargs = template_kwargs

    @SeleniumLibrary.base.keyword
    def get_node_from_file(self, file: os.PathLike, name: str = None) -> model.Node:
        file = pathlib.Path(os.path.abspath(file))
        file_name = os.path.splitext(os.path.basename(file))[0]
        with open(file, encoding="utf-8") as src_file:
            file_data = src_file.read()
        yaml_data = yaml.safe_load(file_data)
        importer = anytree.importer.DictImporter(model.Node)
        node: model.Node = importer.import_(yaml_data)
        # Override node name with file name
        if node.name is None:
            node.name = file_name
        assert node.name == file_name, \
            f"Name of root node in file {file} should be 'None' or '{file_name}', but it is {node.name}"
        return node.find_node(name)

    def locator_keyword_ends_ok(self, kw: str, locator, *args, **kwargs) -> typing.Optional[bool]:
        element = self.find_element(locator, required=False)
        if element is None:
            return None
        return self.built_in.run_keyword_and_return_status(
            f"{self.get_selenium_library_name()}.{kw}",
            locator,
            *args,
            **kwargs,
        ) if element is not None else None

    # Get element status
    @SeleniumLibrary.base.keyword
    def page_contains_element(self, locator) -> bool:
        try:
            self.assert_page_contains(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_visible(self, locator) -> typing.Optional[bool]:
        return self.is_visible(locator)

    @SeleniumLibrary.base.keyword
    def element_is_enabled(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        return self.is_element_enabled(locator)

    @SeleniumLibrary.base.keyword
    def element_is_focused(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.ElementKeywords(self.ctx).element_should_be_focused(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_selected(self, locator) -> typing.Optional[bool]:
        element = self.find_element(locator, required=False)
        if element is None:
            return None
        return element.is_selected()

    @SeleniumLibrary.base.keyword
    def checkbox_is_selected(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.FormElementKeywords(self.ctx).checkbox_should_be_selected(locator)
        except AssertionError:
            return False
        return True

    # Wait keywords
    @SeleniumLibrary.base.keyword
    def wait_until_element_is_not_enabled(self,
                                          locator,
                                          timeout=None,
                                          error=None,
                                          ) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.ctx)._wait_until(
            lambda: self.element_is_enabled(locator) is False,
            "Element '%s' is enabled (or not present) after <TIMEOUT>." % locator,
            timeout,
            error,
        )

    @SeleniumLibrary.base.keyword
    def wait_until_element_is_focused(self,
                                      locator,
                                      timeout=None,
                                      error=None, ) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.ctx)._wait_until(
            lambda: self.element_is_focused(locator),
            "Element '%s' is not focused (or not present) after <TIMEOUT>." % locator,
            timeout,
            error,
        )

    @SeleniumLibrary.base.keyword
    def wait_until_element_is_not_focused(self,
                                          locator,
                                          timeout=None,
                                          error=None, ) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.ctx)._wait_until(
            lambda: self.element_is_focused(locator) is False,
            "Element '%s' is focused (or not present) after <TIMEOUT>." % locator,
            timeout,
            error,
        )

    @SeleniumLibrary.base.keyword
    def wait_until_element_is_selected(self,
                                       locator,
                                       timeout=None,
                                       error=None, ) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.ctx)._wait_until(
            lambda: self.element_is_selected(),
            "Element '%s' is not selected (or not present) after <TIMEOUT>." % locator,
            timeout,
            error,
        )

    @SeleniumLibrary.base.keyword
    def wait_until_element_is_not_selected(self,
                                           locator,
                                           timeout=None,
                                           error=None, ) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.ctx)._wait_until(
            lambda: self.element_is_selected() is False,
            "Element '%s' is selected (or not present) after <TIMEOUT>." % locator,
            timeout,
            error,
        )

    # Element types
    @SeleniumLibrary.base.keyword
    def element_is_button(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_button(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_checkbox(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_checkbox(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_image(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.ElementKeywords(self.ctx).page_should_contain_image(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_link(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.ElementKeywords(self.ctx).page_should_contain_link(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_list(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.SelectElementKeywords(self.ctx).page_should_contain_list(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_radio(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_radio_button(locator)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def element_is_textfield(self, locator) -> typing.Optional[bool]:
        if not self.page_contains_element(locator):
            return None
        try:
            SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_textfield(locator)
        except AssertionError:
            return False
        return True

    # Get / Set Field Value
    @SeleniumLibrary.base.keyword
    def get_field_value(self,
                        locator: typing.Union[str, web_element],
                        parent: typing.Union[web_element, str, typing.List[str]] = None,
                        ) -> typing.Union[None, str, bool]:
        method_name = "get_field_value"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values'. Locator: {locator}. Node: {node}"
            return node.get_field_value()
        else:
            return self.default_get_field_value(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values(self,
                         locator: typing.Union[str, web_element, typing.List[web_element]],
                         parent: typing.Union[web_element, str, typing.List[str]] = None,
                         ) -> list:
        method_name = "get_field_values"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value'. Locator: {locator}. Node: {node}"
            return node.get_field_value()
        else:
            return self.default_get_field_values(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_string(self,
                                  locator: typing.Union[str, web_element],
                                  parent: typing.Union[web_element, str, typing.List[str]] = None,
                                  ) -> typing.Optional[str]:
        method_name = "get_field_value_as_string"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_strings'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_string()
        else:
            return self.default_get_field_value_as_string(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_strings(self,
                                    locator: typing.Union[str, web_element, typing.List[web_element]],
                                    parent: typing.Union[web_element, str, typing.List[str]] = None,
                                    ) -> list:
        method_name = "get_field_values_as_strings"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_string'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_string()
        else:
            return self.default_get_field_values_as_strings(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_integer(self,
                                   locator: typing.Union[str, web_element],
                                   parent: typing.Union[web_element, str, typing.List[str]] = None,
                                   ) -> typing.Optional[int]:
        method_name = "get_field_value_as_integer"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_integers'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_integer()
        else:
            return self.default_get_field_value_as_integer(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_integers(self,
                                     locator: typing.Union[str, web_element, typing.List[web_element]],
                                     parent: typing.Union[web_element, str, typing.List[str]] = None,
                                     ) -> list:
        method_name = "get_field_values_as_integers"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_integer'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_integer()
        else:
            return self.default_get_field_values_as_integers(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_float(self,
                                 locator: typing.Union[str, web_element],
                                 parent: typing.Union[web_element, str, typing.List[str]] = None,
                                 ) -> typing.Optional[float]:
        method_name = "get_field_value_as_float"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_floats'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_float()
        else:
            return self.default_get_field_value_as_float(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_floats(self,
                                   locator: typing.Union[str, web_element, typing.List[web_element]],
                                   parent: typing.Union[web_element, str, typing.List[str]] = None,
                                   ) -> list:
        method_name = "get_field_values_as_floats"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_float'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_float()
        else:
            return self.default_get_field_values_as_floats(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_boolean(self,
                                   locator: typing.Union[str, web_element],
                                   parent: typing.Union[web_element, str, typing.List[str]] = None,
                                   ) -> typing.Optional[bool]:
        method_name = "get_field_value_as_boolean"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_booleans'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_boolean()
        else:
            return self.default_get_field_value_as_boolean(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_booleans(self,
                                     locator: typing.Union[str, web_element, typing.List[web_element]],
                                     parent: typing.Union[web_element, str, typing.List[str]] = None,
                                     ) -> list:
        method_name = "get_field_values_as_booleans"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_boolean'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_boolean()
        else:
            return self.default_get_field_values_as_booleans(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_date(self,
                                locator: typing.Union[str, web_element],
                                parent: typing.Union[web_element, str, typing.List[str]] = None,
                                ) -> typing.Optional[datetime.date]:
        method_name = "get_field_value_as_date"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_dates'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_date()
        else:
            return self.default_get_field_value_as_date(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_dates(self,
                                  locator: typing.Union[str, web_element, typing.List[web_element]],
                                  parent: typing.Union[web_element, str, typing.List[str]] = None,
                                  ) -> list:
        method_name = "get_field_values_as_dates"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_date'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_date()
        else:
            return self.default_get_field_values_as_dates(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_value_as_datetime(self,
                                    locator: typing.Union[str, web_element],
                                    parent: typing.Union[web_element, str, typing.List[str]] = None,
                                    ) -> typing.Optional[datetime.datetime]:
        method_name = "get_field_value_as_datetime"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values_as_datetimes'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_datetime()
        else:
            return self.default_get_field_value_as_datetime(locator, parent)

    @SeleniumLibrary.base.keyword
    def get_field_values_as_datetimes(self,
                                      locator: typing.Union[str, web_element, typing.List[web_element]],
                                      parent: typing.Union[web_element, str, typing.List[str]] = None,
                                      ) -> list:
        method_name = "get_field_values_as_datetimes"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value_as_datetime'. Locator: {locator}. Node: {node}"
            return node.get_field_value_as_datetime()
        else:
            return self.default_get_field_values_as_datetimes(locator, parent)

    @SeleniumLibrary.base.keyword
    def set_field_value(self,
                        locator: typing.Union[str, web_element],
                        parent: typing.Union[web_element, str, typing.List[str]] = None,
                        value: typing.Any = None,
                        force: bool = False,
                        ) -> None:
        if value is None:
            return

        method_name = "set_field_value"

        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'set_field_values'. Locator: {locator}. Node: {node}"
            node.set_field_value(value, force=force)
        else:
            return self.default_set_field_value(locator, parent, value, force=force)

    @SeleniumLibrary.base.keyword
    def set_field_values(self,
                         locator: typing.Union[str, web_element, typing.List[web_element]],
                         parent: typing.Union[web_element, str, typing.List[str]] = None,
                         values: typing.Optional[list] = None,
                         force: bool = False,
                         ) -> None:
        if values is None or len(values) == 0:
            return

        method_name = "set_field_values"

        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'set_field_value'. Locator: {locator}. Node: {node}"
            return node.set_field_value(values, force=force)
        else:
            return self.default_set_field_values(locator, parent, values, force=force)

    @SeleniumLibrary.base.keyword
    def default_get_field_value(self,
                                locator: typing.Union[str, web_element],
                                parent: typing.Union[web_element, str, typing.List[str]] = None,
                                ) -> typing.Union[None, str, bool]:

        is_web_element = isinstance(locator, web_element)

        if is_web_element:
            element = locator
        else:
            if isinstance(parent, str):
                parent = [parent]
            if isinstance(parent, list):
                parent_element = None
                for p in parent:
                    parent_element = self.find_element(p, required=False, parent=parent_element)
                    if parent_element is None:
                        return None
                parent = parent_element

            element = self.find_element(locator, required=False, parent=parent)

        if element is None:
            value = None
        elif self.element_is_checkbox(locator):
            value = element.is_selected()
        elif self.element_is_image(locator):
            value = element.get_attribute("src")
        elif self.element_is_list(locator):
            labels = SeleniumLibrary.SelectElementKeywords(self.ctx).get_selected_list_labels(locator)
            if len(labels) == 1:
                value = labels[0]
            else:
                value = labels
        elif self.element_is_radio(locator):
            value = element.is_selected()
        elif self.element_is_textfield(locator):
            value = element.get_attribute("value")
        else:
            value = SeleniumLibrary.ElementKeywords(self.ctx).get_text(locator)

        return value

    @SeleniumLibrary.base.keyword
    def default_get_field_values(self,
                                 locator: typing.Union[str, web_element, typing.List[web_element]],
                                 parent: typing.Union[web_element, str, typing.List[str]] = None,
                                 ) -> list:
        if isinstance(locator, web_element):
            locator = [locator]
        is_web_element_list = isinstance(locator, list)

        if is_web_element_list:
            elements = locator
        else:
            if isinstance(parent, str):
                parent = [parent]
            if isinstance(parent, list):
                parent_element = None
                for p in parent:
                    parent_element = self.find_element(p, required=False, parent=parent_element)
                    if parent_element is None:
                        return []
                parent = parent_element

            elements = self.find_elements(locator, parent=parent)

        return [self.default_get_field_value(element) for element in elements]

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_string(self,
                                          locator: typing.Union[str, web_element],
                                          parent: typing.Union[web_element, str, typing.List[str]] = None,
                                          ) -> typing.Optional[str]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        else:
            return str(value)

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_strings(self,
                                            locator: typing.Union[str, web_element, typing.List[web_element]],
                                            parent: typing.Union[web_element, str, typing.List[str]] = None,
                                            ) -> typing.List[None, str]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            else:
                values.append(str(value))
        return values

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_integer(self,
                                           locator: typing.Union[str, web_element],
                                           parent: typing.Union[web_element, str, typing.List[str]] = None,
                                           ) -> typing.Optional[int]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        else:
            return int(value)

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_integers(self,
                                             locator: typing.Union[str, web_element, typing.List[web_element]],
                                             parent: typing.Union[web_element, str, typing.List[str]] = None,
                                             ) -> typing.List[None, int]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            else:
                values.append(int(value))
        return values

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_float(self,
                                         locator: typing.Union[str, web_element],
                                         parent: typing.Union[web_element, str, typing.List[str]] = None,
                                         ) -> typing.Optional[float]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        else:
            return float(value)

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_floats(self,
                                           locator: typing.Union[str, web_element, typing.List[web_element]],
                                           parent: typing.Union[web_element, str, typing.List[str]] = None,
                                           ) -> typing.List[None, float]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            else:
                values.append(float(value))
        return values

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_boolean(self,
                                           locator: typing.Union[str, web_element],
                                           parent: typing.Union[web_element, str, typing.List[str]] = None,
                                           ) -> typing.Optional[bool]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        elif self.is_pseudo_boolean(value):
            return self.pseudo_boolean_as_bool(value)
        else:
            return bool(value)

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_booleans(self,
                                             locator: typing.Union[str, web_element, typing.List[web_element]],
                                             parent: typing.Union[web_element, str, typing.List[str]] = None,
                                             ) -> typing.List[None, bool]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            elif self.is_pseudo_boolean(value):
                values.append(self.pseudo_boolean_as_bool(value))
            else:
                values.append(bool(value))
        return values

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_date(self,
                                        locator: typing.Union[str, web_element],
                                        parent: typing.Union[web_element, str, typing.List[str]] = None,
                                        ) -> typing.Optional[datetime.date]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        elif isinstance(value, str):
            return Plugin.default_date_parser(value)
        elif isinstance(value, (tuple, list, set)):
            return datetime.date(*value)
        elif isinstance(value, dict):
            return datetime.date(**value)
        else:
            assert False, f"Do not know how to convert to Date: {value}"

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_dates(self,
                                          locator: typing.Union[str, web_element, typing.List[web_element]],
                                          parent: typing.Union[web_element, str, typing.List[str]] = None,
                                          ) -> typing.List[None, datetime.date]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            elif isinstance(value, str):
                values.append(Plugin.default_date_parser(value))
            elif isinstance(value, (tuple, list, set)):
                values.append(datetime.date(*value))
            elif isinstance(value, dict):
                values.append(datetime.date(**value))
            else:
                assert False, f"Do not know how to convert to Date: {value}"
        return values

    @SeleniumLibrary.base.keyword
    def default_get_field_value_as_datetime(self,
                                            locator: typing.Union[str, web_element],
                                            parent: typing.Union[web_element, str, typing.List[str]] = None,
                                            ) -> typing.Optional[datetime.datetime]:
        value = self.get_field_value(locator, parent=parent)
        if value is None:
            return None
        elif isinstance(value, str):
            return Plugin.default_datetime_parser(value)
        elif isinstance(value, (tuple, list, set)):
            return datetime.datetime(*value)
        elif isinstance(value, dict):
            return datetime.datetime(**value)
        else:
            assert False, f"Do not know how to convert to Datetime: {value}"

    @SeleniumLibrary.base.keyword
    def default_get_field_values_as_datetimes(self,
                                              locator: typing.Union[str, web_element, typing.List[web_element]],
                                              parent: typing.Union[web_element, str, typing.List[str]] = None,
                                              ) -> typing.List[None, datetime.datetime]:
        values = []
        for value in self.get_field_values(locator, parent=parent):
            if value is None:
                values.append(None)
            elif isinstance(value, str):
                values.append(Plugin.default_datetime_parser(value))
            elif isinstance(value, (tuple, list, set)):
                values.append(datetime.datetime(*value))
            elif isinstance(value, dict):
                values.append(datetime.datetime(**value))
            else:
                assert False, f"Do not know how to convert to Datetime: {value}"
        return values

    @SeleniumLibrary.base.keyword
    def default_set_field_value(self,
                                locator: typing.Union[str, web_element],
                                parent: typing.Union[web_element, str, typing.List[str]] = None,
                                value: typing.Any = None,
                                force: bool = False,
                                ) -> None:
        if value is None:
            return

        is_web_element = isinstance(locator, web_element)

        if is_web_element:
            element = locator
        else:
            if isinstance(parent, str):
                parent = [parent]
            if isinstance(parent, list):
                parent_element = None
                for p in parent:
                    parent_element = self.find_element(p, required=False, parent=parent_element)
                    if parent_element is None:
                        return None
                parent = parent_element

            element = self.find_element(locator, required=False, parent=parent)

        if self.element_is_button(element):
            value = self.pseudo_boolean_as_bool(value)
            if value is True:
                self.click_button(element)
        elif self.element_is_checkbox(element):
            value = self.pseudo_boolean_as_bool(value)
            if value is True:
                SeleniumLibrary.FormElementKeywords(self.ctx).select_checkbox(element)
            else:
                SeleniumLibrary.FormElementKeywords(self.ctx).unselect_checkbox(element)
        elif self.element_is_image(element):
            value = self.pseudo_boolean_as_bool(value)
            if value is True:
                self.click_image(element)
        elif self.element_is_link(element):
            value = self.pseudo_boolean_as_bool(value)
            if value is True:
                self.click_link(element)
        elif self.element_is_list(element):
            if not isinstance(value, list):
                value = [value]
            try:
                # noinspection PyTypeChecker
                value = [int(v) for v in value]
            except ValueError:
                self.select_from_list_by_label(element, *value)
            else:
                self.select_from_list_by_index(element, *value)
        elif self.element_is_radio(element):
            value = self.pseudo_boolean_as_bool(value)
            # get element group name
            group_name = SeleniumLibrary.ElementKeywords(self.ctx).get_element_attribute(element, "name")
            radio_value = SeleniumLibrary.ElementKeywords(self.ctx).get_element_attribute(element, "value")
            if value is True:
                if force or \
                        self.built_in.run_keyword_and_return_status(
                            f"{self.get_selenium_library_name()}.Radio Button Should Not Be Set To",
                            group_name,
                            radio_value,
                        ):
                    self.select_radio_button(group_name, radio_value)
        elif self.element_is_textfield(element):
            element_type = SeleniumLibrary.ElementKeywords(self.ctx).get_element_attribute("type")
            if isinstance(element_type, str) and element_type.lower() == "password":
                self.input_password(element, str(value))
            else:
                self.input_text(element, str(value))
        else:
            # It will probably generate an error, but have to try...
            self.input_text(element, str(value))

    @SeleniumLibrary.base.keyword
    def default_set_field_values(self,
                                 locator: typing.Union[str, web_element, typing.List[web_element]],
                                 parent: typing.Union[web_element, str, typing.List[str]] = None,
                                 values: typing.Optional[list] = None,
                                 force: bool = False,
                                 ) -> None:
        if values is None or len(values) == 0:
            return

        if isinstance(locator, web_element):
            locator = [locator]
        is_web_element_list = isinstance(locator, list)

        if is_web_element_list:
            elements = locator
        else:
            if isinstance(parent, str):
                parent = [parent]
            if isinstance(parent, list):
                parent_element = None
                for p in parent:
                    parent_element = self.find_element(p, required=True, parent=parent_element)
                parent = parent_element
            elements = self.find_elements(locator, parent=parent)

        for i, element in enumerate(elements):
            self.set_field_value(element, value=values[i], force=force)

    ###############################################
    # SELENIUM OVERRIDES  (and auxiliary methods) #
    ###############################################

    def locator_description(self, locator=None):
        """
        Returns a detailed description of a provided `locator` if that locator is a `path` locator
        (it is a string an starts with `path:` or `path=`).
        Otherwise it returns the locator itself.

        :param locator: The locator.
        :return: The detailed description.
        """
        if locator is None:
            return "None"
        locator_desc = locator
        if self.is_pom_locator(locator):
            node = self.get_node(self.remove_pom_prefix(locator))
            locator_desc = f"page: '{node.page_node.name}', full_name: '{node.full_name}', " \
                           f"real locator: '{node.locator}'"
        return locator_desc

    @SeleniumLibrary.base.keyword
    def get_current_frame(self) -> web_element:
        return self.driver.execute_script('return window.frameElement')

    def embed_screenshot(self, kw: str, locator=None, moment: str = "before") -> None:
        """
        Adds a message (always) and embeds a screenshot (only if log level is `DEBUG` or `TRACE`) to the log file.

        :param kw: The keyword that is being executed.
        :param locator: The associated locator.
        :param moment: The moment when the screenshot is captured. Default value: "before" (before keyword execution).
        :return: None.
        """
        # Only embed in DEBUG or TRACE
        log_level = self.built_in.get_variable_value("${LOG_LEVEL}")
        log_screenshot = log_level in ["DEBUG", "TRACE"]
        locator_desc = self.locator_description(locator)
        if log_screenshot:
            msg = f"Screenshot {moment} '{kw}': \n{locator_desc}"
        else:
            msg = f"We are at {moment} '{kw}': \n{locator_desc}"
        self.info(msg)
        if log_screenshot:
            SeleniumLibrary.ScreenshotKeywords(self.ctx).capture_page_screenshot(filename="EMBED")

    def embed_screenshot_after(self, kw: str, locator=None) -> None:
        """
        Adds a message (always) and embeds a screenshot (only if log level is `DEBUG` or `TRACE`) to the log file.
        Same as `embed_screenshot` with `moment = after`.

        :param kw: The keyword that is being executed.
        :param locator: The associated locator.
        :return: None.
        """
        self.embed_screenshot(kw, locator, "after")

    @SeleniumLibrary.base.keyword()
    def alert_should_be_present(self, text='', action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        kw = "Alert Should Be Present"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.AlertKeywords(self.ctx).alert_should_be_present(
            text=text,
            action=action,
            timeout=timeout,
        )
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def alert_should_not_be_present(self, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=0):
        kw = "Alert Should Not Be Present"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.AlertKeywords(self.ctx).alert_should_not_be_present(action=action, timeout=timeout)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def choose_file(self, locator, file_path):
        kw = "Choose File"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).choose_file(locator=locator, file_path=file_path)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def clear_element_text(self, locator):
        kw = "Clear Element Text"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).clear_element_text(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_button(self, locator, modifier=False):
        kw = "Click Button"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_button(locator=locator, modifier=modifier)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_element(self, locator, modifier=False, action_chain=False):
        kw = "Click Element"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_element(
            locator=locator,
            modifier=modifier,
            action_chain=action_chain,
        )
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_element_at_coordinates(self, locator, xoffset, yoffset):
        kw = "Click Element At Coordinates"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_element_at_coordinates(
            locator=locator,
            xoffset=xoffset,
            yoffset=yoffset,
        )
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_image(self, locator, modifier=False):
        kw = "Click Image"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_image(locator=locator, modifier=modifier)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_link(self, locator, modifier=False):
        kw = "Click Link"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_link(locator=locator, modifier=modifier)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def cover_element(self, locator):
        kw = "Cover Element"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).cover_element(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def double_click_element(self, locator):
        kw = "Double Click Element"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).double_click_element(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def drag_and_drop(self, locator, target):
        kw = "Drag And Drop"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).drag_and_drop(locator=locator, target=target)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def drag_and_drop_by_offset(self, locator, xoffset, yoffset):
        kw = "Drag And Drop By Offset"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).drag_and_drop_by_offset(
            locator=locator,
            xoffset=xoffset,
            yoffset=yoffset,
        )
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def execute_async_javascript(self, *code):
        kw = "Execute Async Javascript"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.JavaScriptKeywords(self.ctx).execute_async_javascript(*code)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def execute_javascript(self, *code):
        kw = "Execute Javascript"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.JavaScriptKeywords(self.ctx).execute_javascript(*code)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def handle_alert(self, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        kw = "Handle Alert"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.AlertKeywords(self.ctx).handle_alert(action=action, timeout=timeout)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def input_password(self, locator, password, clear=True):
        kw = "Input Password"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).input_password(
            locator=locator,
            password=password,
            clear=clear,
        )
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def input_text(self, locator, text, clear=True):
        kw = "Input Text"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).input_text(locator=locator, text=text, clear=clear)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def input_text_into_alert(self, text, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        kw = "Input Text Into Alert"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.AlertKeywords(self.ctx).input_text_into_alert(text=text, action=action, timeout=timeout)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down(self, locator):
        kw = "Mouse Down"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down_on_image(self, locator):
        kw = "Mouse Down On Image"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down_on_image(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down_on_link(self, locator):
        kw = "Mouse Down On Link"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down_on_link(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_out(self, locator):
        kw = "Mouse Out"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_out(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_over(self, locator):
        kw = "Mouse Over"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_over(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_up(self, locator):
        kw = "Mouse Up"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_up(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def open_context_menu(self, locator):
        kw = "Open Context Menu"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).open_context_menu(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def press_keys(self, locator=None, *keys):
        kw = "Press Keys"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).press_keys(locator, *keys)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def reload_page(self):
        kw = "Reload Page"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.BrowserManagementKeywords(self.ctx).reload_page()
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def scroll_element_into_view(self, locator):
        kw = "Scroll Element Into View"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).scroll_element_into_view(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_all_from_list(self, locator):
        kw = "Select All From List"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_all_from_list(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_checkbox(self, locator):
        kw = "Select Checkbox"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).select_checkbox(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_index(self, locator, *indexes):
        kw = "Select From List By Index"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_index(locator, *indexes)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_label(self, locator, *labels):
        kw = "Select From List By Label"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_label(locator, *labels)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_value(self, locator, *values):
        kw = "Select From List By Value"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_value(locator, *values)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_radio_button(self, group_name, value):
        kw = "Select Radio Button"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).select_radio_button(group_name=group_name, value=value)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def simulate_event(self, locator, event):
        kw = "Simulate Event"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).simulate_event(locator=locator, event=event)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def submit_form(self, locator):
        kw = "Submit Form"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).submit_form(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def switch_browser(self, index_or_alias):
        kw = "Switch Browser"
        self.embed_screenshot(kw)
        value = SeleniumLibrary.BrowserManagementKeywords(self.ctx).switch_browser(index_or_alias=index_or_alias)
        self.embed_screenshot_after(kw)
        return value

    @SeleniumLibrary.base.keyword()
    def switch_window(self, locator='MAIN', timeout=None, browser='CURRENT'):
        kw = "Switch Window"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.WindowKeywords(self.ctx).switch_window(
            locator=locator,
            timeout=timeout,
            browser=browser,
        )
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_all_from_list(self, locator):
        kw = "Unselect All From List"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_all_from_list(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_checkbox(self, locator):
        kw = "Unselect Checkbox"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).unselect_checkbox(locator=locator)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_index(self, locator, *indexes):
        kw = "Unselect From List By Index"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_index(locator, *indexes)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_label(self, locator, *labels):
        kw = "Unselect From List By Label"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_label(locator, *labels)
        self.embed_screenshot_after(kw, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_value(self, locator, *values):
        kw = "Unselect From List By Value"
        self.embed_screenshot(kw, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_value(locator, *values)
        self.embed_screenshot_after(kw, locator)
        return value


# Documenting overrides
Plugin.alert_should_be_present.__doc__ = SeleniumLibrary.AlertKeywords.alert_should_be_present.__doc__
Plugin.alert_should_not_be_present.__doc__ = SeleniumLibrary.AlertKeywords.alert_should_not_be_present.__doc__
Plugin.choose_file.__doc__ = SeleniumLibrary.FormElementKeywords.choose_file.__doc__
Plugin.clear_element_text.__doc__ = SeleniumLibrary.ElementKeywords.clear_element_text.__doc__
Plugin.click_button.__doc__ = SeleniumLibrary.ElementKeywords.click_button.__doc__
Plugin.click_element.__doc__ = SeleniumLibrary.ElementKeywords.click_element.__doc__
Plugin.click_element_at_coordinates.__doc__ = SeleniumLibrary.ElementKeywords.click_element_at_coordinates.__doc__
Plugin.click_image.__doc__ = SeleniumLibrary.ElementKeywords.click_image.__doc__
Plugin.click_link.__doc__ = SeleniumLibrary.ElementKeywords.click_link.__doc__
Plugin.cover_element.__doc__ = SeleniumLibrary.ElementKeywords.cover_element.__doc__
Plugin.double_click_element.__doc__ = SeleniumLibrary.ElementKeywords.double_click_element.__doc__
Plugin.drag_and_drop.__doc__ = SeleniumLibrary.ElementKeywords.drag_and_drop.__doc__
Plugin.drag_and_drop_by_offset.__doc__ = SeleniumLibrary.ElementKeywords.drag_and_drop_by_offset.__doc__
Plugin.execute_async_javascript.__doc__ = SeleniumLibrary.JavaScriptKeywords.execute_async_javascript.__doc__
Plugin.execute_javascript.__doc__ = SeleniumLibrary.JavaScriptKeywords.execute_javascript.__doc__
Plugin.handle_alert.__doc__ = SeleniumLibrary.AlertKeywords.handle_alert.__doc__
Plugin.input_password.__doc__ = SeleniumLibrary.FormElementKeywords.input_password.__doc__
Plugin.input_text.__doc__ = SeleniumLibrary.FormElementKeywords.input_text.__doc__
Plugin.input_text_into_alert.__doc__ = SeleniumLibrary.AlertKeywords.input_text_into_alert.__doc__
Plugin.mouse_down.__doc__ = SeleniumLibrary.ElementKeywords.mouse_down.__doc__
Plugin.mouse_down_on_image.__doc__ = SeleniumLibrary.ElementKeywords.mouse_down_on_image.__doc__
Plugin.mouse_down_on_link.__doc__ = SeleniumLibrary.ElementKeywords.mouse_down_on_link.__doc__
Plugin.mouse_out.__doc__ = SeleniumLibrary.ElementKeywords.mouse_out.__doc__
Plugin.mouse_over.__doc__ = SeleniumLibrary.ElementKeywords.mouse_over.__doc__
Plugin.mouse_up.__doc__ = SeleniumLibrary.ElementKeywords.mouse_up.__doc__
Plugin.open_context_menu.__doc__ = SeleniumLibrary.ElementKeywords.open_context_menu.__doc__
Plugin.press_keys.__doc__ = SeleniumLibrary.ElementKeywords.press_keys.__doc__
Plugin.reload_page.__doc__ = SeleniumLibrary.BrowserManagementKeywords.reload_page.__doc__
Plugin.scroll_element_into_view.__doc__ = SeleniumLibrary.ElementKeywords.scroll_element_into_view.__doc__
Plugin.select_all_from_list.__doc__ = SeleniumLibrary.SelectElementKeywords.select_all_from_list.__doc__
Plugin.select_checkbox.__doc__ = SeleniumLibrary.FormElementKeywords.select_checkbox.__doc__
Plugin.select_from_list_by_index.__doc__ = SeleniumLibrary.SelectElementKeywords.select_from_list_by_index.__doc__
Plugin.select_from_list_by_label.__doc__ = SeleniumLibrary.SelectElementKeywords.select_from_list_by_label.__doc__
Plugin.select_from_list_by_value.__doc__ = SeleniumLibrary.SelectElementKeywords.select_from_list_by_value.__doc__
Plugin.select_radio_button.__doc__ = SeleniumLibrary.ElementKeywords.press_keys.__doc__
Plugin.simulate_event.__doc__ = SeleniumLibrary.ElementKeywords.simulate_event.__doc__
Plugin.submit_form.__doc__ = SeleniumLibrary.FormElementKeywords.submit_form.__doc__
Plugin.switch_browser.__doc__ = SeleniumLibrary.BrowserManagementKeywords.switch_browser.__doc__
Plugin.switch_window.__doc__ = SeleniumLibrary.WindowKeywords.switch_window.__doc__
Plugin.unselect_all_from_list.__doc__ = SeleniumLibrary.SelectElementKeywords.unselect_all_from_list.__doc__
Plugin.unselect_checkbox.__doc__ = SeleniumLibrary.FormElementKeywords.unselect_checkbox.__doc__
Plugin.unselect_from_list_by_index.__doc__ = SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_index.__doc__
Plugin.unselect_from_list_by_label.__doc__ = SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_label.__doc__
Plugin.unselect_from_list_by_value.__doc__ = SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_value.__doc__
