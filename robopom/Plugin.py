from __future__ import annotations
import typing
# import logging
import anytree
import itertools
import datetime
import dateutil.parser
import os
import pathlib
import time
import SeleniumLibrary
import robot.libraries.BuiltIn
import robot.utils
import inspect
import robot.api.deco as robot_deco
import anytree.importer
import yaml
import robopom.constants
# import robopom.model as model
import robopom.comparator

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
    built_in = robot.libraries.BuiltIn.BuiltIn()

    @staticmethod
    def default_datetime_parser(value: str, dayfirst: bool = True) -> datetime.datetime:
        return dateutil.parser.parse(value, dateutil.parser.parserinfo(dayfirst=dayfirst))

    @staticmethod
    def default_date_parser(value: str, dayfirst: bool = True) -> datetime.date:
        dt = Plugin.default_datetime_parser(value, dayfirst=dayfirst)
        return datetime.date(dt.year, dt.month, dt.day)

    @staticmethod
    def is_pom_locator(locator: typing.Any) -> bool:
        return isinstance(locator, str) and locator.startswith(tuple(robopom.constants.POM_LOCATOR_PREFIXES))

    @staticmethod
    def is_pseudo_boolean(value) -> bool:
        if isinstance(value, str):
            value = value.casefold()
        if value in robopom.constants.PSEUDO_BOOLEAN:
            return True
        else:
            return False

    @staticmethod
    def pseudo_boolean_as_bool(value) -> typing.Optional[bool]:
        if Plugin.is_pseudo_boolean(value) is False:
            return None
        return robopom.constants.PSEUDO_BOOLEAN[value]

    @staticmethod
    def is_pseudo_type(value) -> bool:
        if isinstance(value, str):
            value = value.casefold()
        if value in robopom.constants.TYPES:
            return True
        else:
            return False

    @staticmethod
    def pseudo_type_as_type(value) -> typing.Optional[type]:
        if Plugin.is_pseudo_type(value) is False:
            return None
        if isinstance(value, str):
            value = value.casefold()
        return robopom.constants.TYPES[value]

    @staticmethod
    def remove_pom_prefix(path: str) -> str:
        """
        It removes the `path prefix` (`path:` or `path=`) if the provided `path` starts with this prefix.
        Otherwise, it returns the same `path` string.

        :param path: The path string where we want to remove the prefix.
        :return: The string without the prefix.
        """
        new_path = path
        for prefix in robopom.constants.POM_LOCATOR_PREFIXES:
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
        self.pom_root = Node(name="", pom_root_for_plugin=self).resolve()

        # LibraryComponent.__init__(self, ctx)
        super().__init__(ctx)
        ctx.robopom_plugin = self

        self.set_library_search_order = set_library_search_order_in_wait_until_loaded

        # Register Path Locator Strategy
        SeleniumLibrary.ElementKeywords(ctx).add_location_strategy(
            robopom.constants.POM_PREFIX,
            self.pom_locator_strategy,
            persist=True,
        )

        self.active_page_name: typing.Optional[str] = None

    @SeleniumLibrary.base.keyword
    def set_active_page(self, page: [str, Node, Page]) -> None:
        if isinstance(page, Node):
            assert page.is_page, f"Tried to set active page a Node that is not a Page: {page}"
            page = page.name
        elif isinstance(page, Page):
            page = page.real_name
        self.active_page_name = page

        if self.set_library_search_order:
            self.built_in.set_library_search_order(self.active_page_name)

    @property
    def active_page_node(self) -> typing.Optional[Node]:
        if self.active_page_name is None:
            return None
        else:
            return self.pom_root.find_node(self.active_page_name)

    def reset_pom_tree(self) -> None:
        self.pom_root = Node(name="", pom_root_for_plugin=self).resolve()

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
                   timeout: typing.Union[str, int, float] = None,
                   expected: typing.Any = True,
                   raise_error: bool = True,
                   error: str = None,
                   poll: typing.Union[int, float] = 0.2,
                   executable: typing.Callable = None,
                   args: list = None,
                   kwargs: dict = None, ) -> bool:
        if timeout is None:
            timeout = self.selenium_library.timeout
        else:
            timeout = robot.utils.timestr_to_secs(timeout)
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        remaining = timeout
        value = executable(*args, **kwargs)
        while remaining >= 0:
            if value == expected:
                break
            time.sleep(poll)
            remaining -= poll
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
                self.info(error)
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
            f"'parent' should not be a WebElement in 'pom_locator_strategy', but it is: {parent}. Locator: {locator}"
        if tag is not None:
            self.debug(f"'tag' is not None in 'pom_locator_strategy': {tag}. Locator: {locator}")
        assert constraints is None or (isinstance(constraints, dict) and len(constraints) == 0), \
            f"'constraints' should be a None or an empty dict in 'pom_locator_strategy', but it is: {constraints}. " \
            f"Locator: {locator}"

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
            self.debug(f"Element not found using 'Pom Locator Strategy': {log_info}")
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
        name = self.remove_pom_prefix(name)
        return self.pom_root.find_node(name) is not None

    @SeleniumLibrary.base.keyword
    def get_node(self, name: str) -> Node:
        """
        Returns the component obtained from `path`.

        If the component defined by path does not exist, it generates an error.

        `path` (string): Path of the component. If path is `None`, returns the root component.
        """
        name = self.remove_pom_prefix(name)
        node = self.pom_root.find_node(name)
        if node is None and self.active_page_name is not None:
            # Try to find node in the active page
            node = self.active_page_node.find_node(name)
        assert node is not None, f"Node '{name}' not found"
        return node

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
                        template: typing.Union[str, Node] = None,
                        template_args: typing.Any = None,
                        template_kwargs: dict = None,
                        **kwargs) -> Node:

        return Node(name=name,
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
                    node: Node,
                    parent: typing.Union[Node, str] = None) -> str:
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

        return node.pom_locator

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
    #         # What do I do here?
    #         self.pages.append(page_lib)

    @SeleniumLibrary.base.keyword
    def attach_new_node(self,
                        parent: typing.Union[Node, str],
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
                        template: typing.Union[str, Node] = None,
                        template_args: typing.Any = None,
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
        node = Node(name=name,
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
    def set_node_name(self, node: typing.Union[Node, str], name: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.name = name

    @SeleniumLibrary.base.keyword
    def set_node_locator(self, node: typing.Union[Node, str], locator: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.locator = locator

    @SeleniumLibrary.base.keyword
    def set_node_is_multiple(self, node: typing.Union[Node, str], is_multiple: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.is_multiple = is_multiple

    @SeleniumLibrary.base.keyword
    def set_node_order(self, node: typing.Union[Node, str], order: typing.Optional[int]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.order = order

    @SeleniumLibrary.base.keyword
    def set_node_wait_present(self, node: typing.Union[Node, str], wait_present: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_present = wait_present

    @SeleniumLibrary.base.keyword
    def set_node_wait_visible(self, node: typing.Union[Node, str], wait_visible: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_visible = wait_visible

    @SeleniumLibrary.base.keyword
    def set_node_wait_enabled(self, node: typing.Union[Node, str], wait_enabled: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_enabled = wait_enabled

    @SeleniumLibrary.base.keyword
    def set_node_wait_selected(self, node: typing.Union[Node, str], wait_selected: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.wait_selected = wait_selected

    @SeleniumLibrary.base.keyword
    def set_node_html_parent(self,
                             node: typing.Union[Node, str],
                             html_parent: typing.Union[None, str, Node]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if isinstance(html_parent, str):
            html_parent = self.get_node(html_parent)
        node.html_parent = html_parent

    @SeleniumLibrary.base.keyword
    def set_node_smart_pick(self, node: typing.Union[Node, str], smart_pick: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.smart_pick = smart_pick

    @SeleniumLibrary.base.keyword
    def set_node_is_template(self, node: typing.Union[Node, str], is_template: typing.Optional[bool]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.is_template = is_template

    @SeleniumLibrary.base.keyword
    def set_node_template(self, node: typing.Union[Node, str], template: typing.Optional[str]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        node.template = template

    @SeleniumLibrary.base.keyword
    def set_node_template_args(self, node: typing.Union[Node, str], template_args: typing.Any) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if template_args is None:
            template_args = []
        if not isinstance(template_args, list):
            template_args = [template_args]
        node.template_args = template_args

    @SeleniumLibrary.base.keyword
    def set_node_template_kwargs(self,
                                 node: typing.Union[Node, str],
                                 template_kwargs: typing.Union[None, dict]) -> None:
        if isinstance(node, str):
            node = self.get_node(node)
        if template_kwargs is None:
            template_kwargs = {}
        node.template_kwargs = template_kwargs

    @SeleniumLibrary.base.keyword
    def get_node_from_file(self, file: os.PathLike, name: str = None) -> Node:
        file = pathlib.Path(os.path.abspath(file))
        file_name = os.path.splitext(os.path.basename(file))[0]
        with open(file, encoding="utf-8") as src_file:
            file_data = src_file.read()
        yaml_data = yaml.safe_load(file_data)
        importer = anytree.importer.DictImporter(Node)
        file_root_node: Node = importer.import_(yaml_data)
        # Override node name with file name
        if file_root_node.name is None:
            file_root_node.name = file_name
        assert file_root_node.name == file_name, \
            f"Name of root node in file {file} should be 'None' or '{file_name}', but it is {file_root_node.name}"
        node = file_root_node.find_node(name)
        assert node is not None, f"Node '{name}' not found in file '{file}'"
        return node

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
    def element_is_button(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_button(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "button":
            return True
        elif tag == "input":
            type_prop: typing.Optional[str] = element.get_attribute("type")
            if type_prop is None:
                return False
            type_prop = type_prop.lower()
            if type_prop == "button":
                return True
            else:
                return False
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_checkbox(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_checkbox(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "input":
            type_prop: typing.Optional[str] = element.get_attribute("type")
            if type_prop is None:
                return False
            type_prop = type_prop.lower()
            if type_prop == "checkbox":
                return True
            else:
                return False
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_image(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.ElementKeywords(self.ctx).page_should_contain_image(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "img":
            return True
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_link(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.ElementKeywords(self.ctx).page_should_contain_link(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "a":
            return True
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_list(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.SelectElementKeywords(self.ctx).page_should_contain_list(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "select":
            return True
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_radio(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_radio_button(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "input":
            type_prop: typing.Optional[str] = element.get_attribute("type")
            if type_prop is None:
                return False
            type_prop = type_prop.lower()
            if type_prop == "radio":
                return True
            else:
                return False
        else:
            return False

    @SeleniumLibrary.base.keyword
    def element_is_textfield(self, locator: typing.Union[str, web_element]) -> typing.Optional[bool]:
        if isinstance(locator, web_element):
            element = locator
        else:
            element = self.find_element(locator, required=False)
        if element is None:
            return None
        # SeleniumLibrary.FormElementKeywords(self.ctx).page_should_contain_textfield(locator)
        tag: str = element.tag_name
        tag = tag.lower()
        if tag == "textarea":
            return True
        elif tag == "input":
            type_prop: typing.Optional[str] = element.get_attribute("type")
            if type_prop is None:
                return False
            type_prop = type_prop.lower()
            if type_prop in ['date', 'datetime-local', 'email', 'month', 'number', 'password', 'search', 'tel',
                             'text', 'time', 'url', 'week', 'file']:
                return True
            else:
                return False
        else:
            return False

    def value_as_type(self,
                      value: typing.Any,
                      as_type: typing.Union[type, str] = None) -> typing.Any:
        if value is None or as_type is None:
            return value

        if isinstance(value, list):
            return [self.value_as_type(v, as_type) for v in value]

        as_type = self.pseudo_type_as_type(as_type)

        if as_type in [str, int, float]:
            return as_type(value)
        elif as_type == bool:
            if self.is_pseudo_boolean(value):
                return self.pseudo_boolean_as_bool(value)
            else:
                return bool(value)
        elif as_type == datetime.date:
            if isinstance(value, str):
                return Plugin.default_date_parser(value)
            elif isinstance(value, (tuple, list, set)):
                return datetime.date(*value)
            elif isinstance(value, dict):
                return datetime.date(**value)
            else:
                assert False, f"Do not know how to convert to Date: {value}"
        elif as_type == datetime.datetime:
            if isinstance(value, str):
                return Plugin.default_datetime_parser(value)
            elif isinstance(value, (tuple, list, set)):
                return datetime.datetime(*value)
            elif isinstance(value, dict):
                return datetime.datetime(**value)
            else:
                assert False, f"Do not know how to convert to Datetime: {value}"

    # Get / Set Field Value
    @SeleniumLibrary.base.keyword
    def get_field_value(self,
                        locator: typing.Union[str, web_element],
                        parent: typing.Union[web_element, str, typing.List[str]] = None,
                        as_type: typing.Union[type, str] = None,
                        kwargs: dict = None,
                        ) -> typing.Union[None, str, bool]:
        if kwargs is None:
            kwargs = {}
        method_name = "get_field_value"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'get_field_values'. Locator: {locator}. Node: {node}"
            return node.get_field_value(as_type, **kwargs)
        else:
            return self.default_get_field_value(locator, parent=parent, as_type=as_type, kwargs=kwargs)

    @SeleniumLibrary.base.keyword
    def get_field_values(self,
                         locator: typing.Union[str, web_element, typing.List[web_element]],
                         parent: typing.Union[web_element, str, typing.List[str]] = None,
                         as_type: typing.Union[type, str] = None,
                         kwargs: dict = None,
                         ) -> list:
        if kwargs is None:
            kwargs = {}
        method_name = "get_field_values"
        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'get_field_value'. Locator: {locator}. Node: {node}"
            return node.get_field_value(as_type, **kwargs)
        else:
            return self.default_get_field_values(locator, parent=parent, as_type=as_type)

    @SeleniumLibrary.base.keyword
    def set_field_value(self,
                        locator: typing.Union[str, web_element],
                        parent: typing.Union[web_element, str, typing.List[str]] = None,
                        value: typing.Any = None,
                        force: bool = False,
                        kwargs: dict = None,
                        ) -> None:
        if value is None:
            return
        if kwargs is None:
            kwargs = {}

        method_name = "set_field_value"

        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple is False, \
                f"Node should not be multiple in '{method_name}'. " \
                f"Should use 'set_field_values'. Locator: {locator}. Node: {node}"
            node.set_field_value(value, force=force, **kwargs)
        else:
            return self.default_set_field_value(locator, parent, value, force=force)

    @SeleniumLibrary.base.keyword
    def set_field_values(self,
                         locator: typing.Union[str, web_element, typing.List[web_element]],
                         parent: typing.Union[web_element, str, typing.List[str]] = None,
                         values: typing.Optional[list] = None,
                         force: bool = False,
                         kwargs: dict = None,
                         ) -> None:
        if values is None or len(values) == 0:
            return
        if kwargs is None:
            kwargs = {}

        method_name = "set_field_values"

        if self.is_pom_locator(locator):
            assert parent is None, \
                f"'parent' should be None in '{method_name}' but it is: {parent}. Locator: {locator}"
            node = self.get_node(locator)
            assert node.is_multiple, \
                f"Node should be multiple in '{method_name}'. " \
                f"Should use 'set_field_value'. Locator: {locator}. Node: {node}"
            return node.set_field_value(values, force=force, **kwargs)
        else:
            return self.default_set_field_values(locator, parent, values, force=force)

    @SeleniumLibrary.base.keyword
    def default_get_field_value(self,
                                locator: typing.Union[str, web_element],
                                parent: typing.Union[web_element, str, typing.List[str]] = None,
                                as_type: typing.Union[type, str] = None,
                                kwargs: dict = None,
                                ) -> typing.Union[None, str, bool]:
        if kwargs is None:
            kwargs = {}

        if as_type is not None:
            value = self.get_field_value(locator, parent=parent, kwargs=kwargs)
            return self.value_as_type(value, as_type)

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
                                 as_type: typing.Union[type, str] = None,
                                 kwargs: dict = None,
                                 ) -> list:
        if kwargs is None:
            kwargs = {}

        if as_type is not None:
            values = self.get_field_values(locator, parent=parent, kwargs=kwargs)
            return self.value_as_type(values, as_type)

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
            element_type = SeleniumLibrary.ElementKeywords(self.ctx).get_element_attribute(element, "type")
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

    @SeleniumLibrary.base.keyword
    def field_value_satisfies(
            self,
            locator: typing.Union[str, web_element],
            parent: typing.Union[web_element, str, typing.List[str]] = None,
            as_type: typing.Union[type, str] = None,
            expected_value: typing.Any = None,
            compare_function: typing.Union[
                str,
                typing.Callable[[typing.Any, typing.Any], bool]] = robopom.comparator.equals,
            kwargs: dict = None,
    ) -> bool:

        if kwargs is None:
            kwargs = {}

        value = self.get_field_value(locator, parent=parent, as_type=as_type, kwargs=kwargs)

        return robopom.comparator.Comparator.compare(value, expected_value, compare_function)

    @SeleniumLibrary.base.keyword
    def wait_until_field_value_satisfies(
            self,
            locator: typing.Union[str, web_element],
            parent: typing.Union[web_element, str, typing.List[str]] = None,
            as_type: typing.Union[type, str] = None,
            expected_value: typing.Any = None,
            compare_function: typing.Union[
                str,
                typing.Callable[[typing.Any, typing.Any], bool]] = robopom.comparator.equals,
            timeout: [int, float, str] = None,
            raise_error: bool = True,
            poll: float = 0.5,
            kwargs: dict = None,
    ) -> bool:

        if kwargs is None:
            kwargs = {}

        def executable() -> bool:
            value = self.get_field_value(locator, parent=parent, as_type=as_type, kwargs=kwargs)
            return robopom.comparator.Comparator.compare(value, expected_value, compare_function)

        return self.wait_until(
            timeout=timeout,
            expected=True,
            raise_error=raise_error,
            poll=poll,
            executable=executable,
        )

    @SeleniumLibrary.base.keyword
    def wait_until_field_value_does_not_satisfy(
            self,
            locator: typing.Union[str, web_element],
            parent: typing.Union[web_element, str, typing.List[str]] = None,
            as_type: typing.Union[type, str] = None,
            expected_value: typing.Any = None,
            compare_function: typing.Union[
                str,
                typing.Callable[[typing.Any, typing.Any], bool]] = robopom.comparator.equals,
            timeout: [int, float, str] = None,
            raise_error: bool = True,
            poll: float = 0.5,
            kwargs: dict = None,
    ) -> bool:

        if kwargs is None:
            kwargs = {}

        def executable() -> bool:
            value = self.get_field_value(locator, parent=parent, as_type=as_type, kwargs=kwargs)
            return robopom.comparator.Comparator.compare(value, expected_value, compare_function)

        return self.wait_until(
            timeout=timeout,
            expected=False,
            raise_error=raise_error,
            poll=poll,
            executable=executable,
        )

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
        SeleniumLibrary.WaitingKeywords(self.ctx).wait_until_element_is_enabled(locator)
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


class Node(anytree.AnyNode):
    # separator = "__"

    def __init__(self: Node,
                 parent: Node = None,
                 children: typing.Iterable[Node] = None,
                 *,
                 name: str = None,
                 locator: str = None,
                 is_multiple: bool = None,
                 order: int = None,
                 limit: int = None,
                 wait_present: bool = None,
                 wait_visible: bool = None,
                 wait_enabled: bool = None,
                 wait_selected: bool = None,
                 html_parent: typing.Union[str, Node] = None,
                 smart_pick: bool = None,
                 # template:
                 is_template: bool = None,
                 template: typing.Union[str, Node] = None,
                 template_args: typing.Any = None,
                 template_kwargs: dict = None,
                 # pom_root_for_plugin:
                 pom_root_for_plugin: typing.Union[Plugin, str] = None,
                 **kwargs) -> None:
        # Initial calculations and validations
        if children is None:
            children = []

        if template_args is None:
            template_args = []
        elif not isinstance(template_args, list):
            template_args = [template_args]

        if template_kwargs is None:
            template_kwargs = {}

        if kwargs is None:
            kwargs = {}

        # TODO: Quitarlo después
        assert len(kwargs) == 0, f"kwargs debería estar vacío: {kwargs}"

        # Used to store "pre resolve" properties.
        _raw_isolated_pre_resolve = {}

        # Used if multiple is True.
        _multiple_nodes: typing.List[Node] = []

        _resolved = False

        super().__init__(
            parent=parent,
            children=children,
            name=name,
            locator=locator,
            order=order,
            limit=limit,
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
            pom_root_for_plugin=pom_root_for_plugin,
            _raw_isolated_pre_resolve=_raw_isolated_pre_resolve,
            _multiple_nodes=_multiple_nodes,
            _resolved=_resolved,
            **kwargs,
        )
        self.parent: typing.Optional[Node] = parent
        self.children: typing.Iterable[Node] = children
        self.name: typing.Optional[str] = name
        self.locator: typing.Optional[str] = locator
        self.is_multiple: typing.Optional[bool] = is_multiple
        self.order: typing.Optional[int] = order
        self.limit: typing.Optional[int] = limit
        self.wait_present: typing.Optional[bool] = wait_present
        self.wait_visible: typing.Optional[bool] = wait_visible
        self.wait_enabled: typing.Optional[bool] = wait_enabled
        self.wait_selected: typing.Optional[bool] = wait_selected
        self.html_parent: typing.Union[None, str, Node] = html_parent
        self.smart_pick: typing.Optional[bool] = smart_pick
        self.is_template: typing.Optional[bool] = is_template
        self.template: typing.Union[None, str, Node] = template
        self.template_args: list = template_args
        self.template_kwargs: dict = template_kwargs
        self.pom_root_for_plugin: typing.Optional[Plugin] = pom_root_for_plugin
        self._raw_isolated_pre_resolve: dict = _raw_isolated_pre_resolve
        self._multiple_nodes: typing.List[Node] = _multiple_nodes
        self._resolved: bool = _resolved

    def __str__(self) -> str:
        if self.name is not None:
            return self.full_name
        else:
            return f"{id(self)}" if self.is_root else f"{self.named_or_root_node.full_name} {id(self)}"

    @property
    def raw_isolated(self) -> typing.Dict[str]:
        return dict(
            name=self.name,
            locator=self.locator,
            is_multiple=self.is_multiple,
            order=self.order,
            limit=self.limit,
            wait_present=self.wait_present,
            wait_visible=self.wait_visible,
            wait_enabled=self.wait_enabled,
            wait_selected=self.wait_selected,
            html_parent=self.html_parent,
            smart_pick=self.smart_pick,
            is_template=self.is_template,
            template=self.template,
            template_args=self.template_args,
            template_kwargs=self.template_kwargs,
            pom_root_for_plugin=self.pom_root_for_plugin,
        )

    @property
    def raw(self) -> typing.Dict[str]:
        value = self.raw_isolated
        value["parent"] = self.parent
        value["children"] = self.children
        return value

    @property
    def raw_isolated_pre_resolve(self) -> typing.Dict[str]:
        if self._raw_isolated_pre_resolve is None:
            return self.raw
        else:
            return self._raw_isolated_pre_resolve

    def copy(self) -> Node:
        node = Node(**self.raw_isolated)
        for child in self.children:
            new_child = child.copy()
            new_child.parent = node
        return node

    def copy_pre_resolve(self) -> Node:
        node = Node(**self.raw_isolated_pre_resolve)
        for child in self.children:
            new_child = child.copy_pre_resolve()
            new_child.parent = node
        return node

    @property
    def object_id(self) -> int:
        return id(self)

    @property
    def name_or_id(self) -> str:
        return self.name if self.name is not None else str(self.object_id)

    @property
    def named_or_root_node(self: Node) -> Node:
        if self.is_root or self.name is not None:
            return self
        else:
            return self.parent.named_or_root_node

    def get_plugin(self) -> typing.Optional[Plugin]:
        if self.pom_root_for_plugin is not None:
            return self.pom_root_for_plugin
        if self.root.pom_root_for_plugin is not None:
            return self.root.pom_root_for_plugin

        # Try to guess.
        built_in = Plugin.built_in
        all_libs: dict = built_in.get_library_instance(all=True)
        selenium_libs: dict = {lib_name: lib_instance for lib_name, lib_instance in all_libs.items()
                               if isinstance(lib_instance, SeleniumLibrary.SeleniumLibrary)
                               and getattr(lib_instance, "robopom_plugin", None) is not None
                               and isinstance(getattr(lib_instance, "robopom_plugin"), Plugin)}
        if len(selenium_libs) == 1:
            # Maybe there is only one "Plugin" defined
            return getattr(list(selenium_libs.values())[0], "robopom_plugin")

        return None

    @property
    def is_pom_root(self) -> bool:
        return self.pom_root_for_plugin is not None

    @property
    def is_attached_to_pom_model(self) -> bool:
        return self.root.is_pom_root

    @property
    def pom_root(self) -> typing.Optional[Node]:
        if not self.is_attached_to_pom_model:
            return None
        return self.root

    @property
    def full_name(self) -> str:
        if self.is_root:
            return self.name if self.name is not None else ""
        else:
            return f"{self.parent.named_or_root_node.full_name} {self.name_or_id}".strip()

    def aliases(self) -> typing.List[str]:
        aliases = []

        names = self.full_name.split()
        if len(names) < 2:
            # It is a page
            return names

        # len(names) >= 2
        page_name = names.pop(0)
        last_name = names.pop()

        names_dict = {name: [(name, True), (name, False)] for name in names}
        possibilities = list(itertools.product(*names_dict.values()))
        middle_names_possibilities = []
        for posible in possibilities:
            possible_name = ""
            for middle_name_bool in posible:
                middle_name, include = middle_name_bool
                if include:
                    possible_name += f" {middle_name}"
            middle_names_possibilities.append(possible_name.strip())
        possible_aliases = [f"{page_name} {middle_name} {last_name}".replace("  ", " ")
                            for middle_name
                            in middle_names_possibilities]
        for possible_alias in possible_aliases:
            try:
                found = self.get_plugin().get_node(possible_alias)
                assert found == self, \
                    f"Found one node using alias '{possible_alias}': {found}. " \
                    f"This node should be the same as 'self': {self}"
                aliases.append(possible_alias)
            except anytree.search.CountError:
                pass

        return aliases

    def aliases_in_page(self) -> typing.List[str]:
        return [" ".join(alias.split()[1:]) for alias in self.aliases()]

    @property
    def pom_locator(self) -> str:
        return f"{robopom.constants.POM_PREFIX}:{self.full_name}"

    @property
    def pom_tree(self) -> str:
        return anytree.RenderTree(self, style=anytree.AsciiStyle()).by_attr()

    @property
    def page_node(self) -> typing.Optional[Node]:
        if not self.is_attached_to_pom_model:
            return None
        if self.is_root:
            return None
        elif self.parent == self.root:
            return self
        else:
            return self.parent.page_node

    @property
    def is_page(self) -> bool:
        return self.is_attached_to_pom_model and self.parent == self.root

    def get_page_library(self) -> Page:
        return Plugin.built_in.get_library_instance(self.page_node.name)

    def get_selenium_library(self) -> SeleniumLibrary:
        return self.get_page_library().get_selenium_library()

    @property
    def is_template_or_template_descendant(self) -> bool:
        path: typing.List[Node] = list(self.path)
        for node in path:
            if node.is_template:
                return True
        else:
            return False

    # TODO: Posible bottomless pit
    def get_template_page_library(self) -> typing.Optional[Page]:
        template = self.resolve_template()
        if template is None:
            return None
        if not template.is_page:
            return None
        return template.get_page_library()

    def set_not_resolved(self, recursive: bool = True) -> Node:
        if recursive:
            for child in self.children:
                child: Node
                child.set_not_resolved(recursive=True)
        self._resolved = False
        return self

    def resolve(self, recursive: bool = True) -> Node:
        # first, resolve children
        if recursive:
            for child in self.children:
                child: Node
                child.resolve(recursive=True)

        if self._resolved is True:
            return self

        # Calculations and validations
        if self.wait_visible or self.wait_enabled or self.wait_selected:
            if self.wait_present is not None:
                assert self.wait_present is True, \
                    f"If 'wait_visible' ({self.wait_visible}) or 'wait_enabled' ({self.wait_enabled}) or " \
                    f"'wait_selected' ({self.wait_selected}), then 'wait_present' can not be False, " \
                    f"but it is {self.wait_present}. Node: {self}"
            else:
                self.wait_present = True

        if self.name is not None:
            name_as_int = None
            try:
                name_as_int = int(self.name)
            except ValueError:
                pass
            assert name_as_int is None, \
                f"'name' can not be an int (or a string that is an int); name: '{self.name}'. Node: {self}"
            assert len(self.name.split()) <= 1, f"'name' can not contain spaces; name: '{self.name}'. Node: {self}"

            if "{order}" in self.name:
                if self.is_multiple is None:
                    self.is_multiple = True
                assert self.is_multiple is True, \
                    f"If 'name' contains '{{order}}', 'is_multiple' can not be False; " \
                    f"name: {self.name}. Node: {self}"

            if self.name.endswith("_template"):
                if self.is_template is None:
                    self.is_template = True
                assert self.is_template is True, \
                    f"If 'name' ends with '_template', 'is_template' can not be False; " \
                    f"name: {self.name}. Node: {self}"

        if self.is_multiple is True:
            assert self.order is None, \
                f"'is_multiple' is True, so 'order' should be None, but it is '{self.order}'. Node: {self}"
            if self.smart_pick is None:
                self.smart_pick = False
            assert self.smart_pick is False, \
                f"'is_multiple' is True, so 'smart_pick' should be False, but it is '{self.smart_pick}'. " \
                f"Node: {self}"

        if self.limit is not None:
            assert self.is_multiple is True, \
                f"'limit' is not None, so 'is_multiple' should be True, but it is '{self.is_multiple}'. " \
                f"Node: {self}"

        if self.is_template is True:
            assert self.template is None, \
                f"'is_template' is True, so 'template' should be None, but it is '{self.template}'. Node: {self}"
            assert self.name is not None, \
                f"'is_template' is True, so 'name' should not be None, but it is '{self.name}'. Node: {self}"

        if self.pom_root_for_plugin is not None:
            assert self.parent is None, \
                f"'pom_root_for_plugin' is not None, so 'parent' should be None, " \
                f"but it is '{self.parent}'. Node: {self}"

        ##################
        # Start resolving
        ##################
        self._raw_isolated_pre_resolve = self.raw_isolated
        self._resolved = True

        self.html_parent = self.resolve_html_parent()

        if self.is_template is None:
            self.is_template = False

        if self.is_template is True:
            # Templates do not resolve to a concrete pom node, and don not apply defaults
            return self

        self.template = self.resolve_template()
        self.apply_template()

        if self.wait_selected is None:
            self.wait_selected = False
        elif self.wait_selected is True:
            if self.wait_present is None:
                self.wait_present = True
            assert self.wait_present, \
                f"'wait_selected' is {self.wait_selected}, but 'wait_present' is {self.wait_present}"

        if self.wait_enabled is None:
            self.wait_enabled = False
        elif self.wait_enabled is True:
            if self.wait_present is None:
                self.wait_present = True
            assert self.wait_present, \
                f"'wait_enabled' is {self.wait_enabled}, but 'wait_present' is {self.wait_present}"

        if self.wait_visible is None:
            self.wait_visible = False
        elif self.wait_visible is True:
            if self.wait_present is None:
                self.wait_present = True
            assert self.wait_visible, \
                f"'wait_visible' is {self.wait_visible}, but 'wait_present' is {self.wait_present}"

        if self.wait_present is None:
            self.wait_present = False

        if self.is_multiple is None:
            self.is_multiple = False

        if self.smart_pick is None:
            self.smart_pick = not self.is_multiple

        return self

    def resolve_html_parent(self) -> typing.Optional[Node]:
        if isinstance(self.html_parent, Node):
            return self.html_parent
        elif isinstance(self.html_parent, str):
            return Node(parent=self.page_node, locator=self.html_parent)
        else:
            # self.html_parent is None
            if self.is_root:
                return None
            if self.parent.locator is not None:
                return self.parent
            return None

    def resolve_template(self) -> typing.Optional[Node]:
        if self.template is None:
            return None
        elif isinstance(self.template, str):
            node = self.find_node(self.template)
            assert node is not None, f"Template node '{self.template}' not found"
            return node
        else:
            return self.template

    def get_node_name_from_self(self, node: Node) -> typing.Optional[str]:
        if node not in self.descendants:
            return None
        else:
            beginning = self.named_or_root_node.full_name
            assert node.full_name.startswith(beginning), \
                f"Node name should start with '{beginning}', but it is '{node.full_name}'"
            return node.full_name.replace(self.full_name, "", 1).strip()

    def find_node(self, name: str = None, only_descendants: bool = False) -> typing.Optional[Node]:
        if name is None or name == "":
            return self

        named = self.named_or_root_node
        name_parts = name.split()
        first_name = name_parts.pop(0)
        new_name = " ".join(name_parts)

        if named.is_pom_root:
            # Force to give an explicit page name if searching from pom root
            page_node: typing.Optional[Node] = anytree.search.find_by_attr(named, first_name, maxlevel=2)
            if page_node is None:
                return None
            else:
                return page_node.find_node(new_name, only_descendants=True)
        else:
            if new_name == "":
                # If first_name is the "last_name" and it is an int, find node by object_id
                try:
                    first_name_as_int = int(first_name)
                    return anytree.search.find_by_attr(named, first_name_as_int, name="object_id")
                except ValueError:
                    pass
            # Find node by name
            first_candidates: typing.List[Node] = anytree.search.findall_by_attr(named, first_name)
            # Try to get the candidates in the same "namespace"
            first_in_namespace = [node for node in first_candidates
                                  if node.full_name.split()[:-1] == named.full_name.split()]
            values = []
            if len(first_in_namespace) > 0:
                first_candidates = first_in_namespace
            for first_candidate in first_candidates:
                new_value = first_candidate.find_node(new_name, only_descendants=True)
                if new_value is not None:
                    values.append(new_value)
            if len(values) > 1:
                self.get_plugin().built_in.log(f"Too many nodes found. Will generate an error.")
                self.get_plugin().log_pom_tree()
            assert len(values) <= 1, \
                f"Found more than 1 node in find_node({name}, {only_descendants}). Using named node: {named}"
            if len(values) == 1:
                return values[0]
            else:
                if only_descendants:
                    return None
                else:
                    return named.parent.find_node(name)

    @property
    def locator_is_explicit(self) -> bool:
        strategies = getattr(self.get_plugin().element_finder, "_strategies", [])
        if self.locator is not None and self.locator.strip().startswith(tuple(strategies)):
            return True
        else:
            return False

    @property
    def xpath_or_css_explicit_locator(self) -> typing.Optional[str]:
        if self.locator_is_explicit:
            return None
        if self.locator == "." or self.locator.startswith(("/", "./")):
            return f"xpath:{self.locator}"
        else:
            return f"css:{self.locator}"

    def find_web_elements(self) -> typing.List[SeleniumLibrary.locators.elementfinder.WebElement]:
        assert self.locator is not None, \
            f"Error in 'find_web_elements'. Locator: {self.locator}. Node: {self}"
        assert self._resolved, f"Error in 'find_web_elements'. Node not resolved. Node: {self}"

        html_parent = self.resolve_html_parent()
        if html_parent is not None:
            html_parent_web_element = html_parent.find_web_element(required=False)
            if html_parent_web_element is None:
                elements = []
            else:
                elements = self.get_plugin().find_elements(
                    self.locator,
                    parent=html_parent_web_element,
                )
                if len(elements) == 0 and self.xpath_or_css_explicit_locator is not None:
                    elements = self.get_plugin().find_elements(
                        self.xpath_or_css_explicit_locator,
                        parent=html_parent_web_element,
                    )
        else:
            elements = self.get_plugin().find_elements(self.locator)
            if len(elements) == 0 and self.xpath_or_css_explicit_locator is not None:
                elements = self.get_plugin().find_elements(self.xpath_or_css_explicit_locator)
        if self.limit is not None:
            assert len(elements) == self.limit, \
                f"'limit' is '{self.limit}', but found {len(elements)} elements. Node: {self}"
        return elements

    def find_web_element(self,
                         required: bool = True,
                         ) -> typing.Optional[SeleniumLibrary.locators.elementfinder.WebElement]:
        """
        Returns the first ``WebElement`` (in ``SeleniumLibrary`` language) found using the ``locator`` attribute.

        If ``prefer_visible`` attribute is ``True``, it returns the first 'visible' element.
        If none is visible, or if ``prefer_visible`` is ``False``, the first element is returned (visible or not).

        If no element is found, an exception is raised if ``required`` is ``True``.
        If ``required`` is ``False`` and no element is found, None is returned.

        :param required: If required is True and no element is found, an exception is raised.
                         If required is False and no element is found, None is returned.
        :return: The WebElement found (or None if no element is found and required is False).
        """
        assert self._resolved, f"Error in 'find_web_element'. Node not resolved. Node: {self}"

        html_parent = self.resolve_html_parent()
        if html_parent is not None:
            html_parent_web_element = self.html_parent.find_web_element(required=required)
            if html_parent_web_element is None:
                return None
        else:
            html_parent_web_element = None

        plugin = self.get_plugin()
        element = plugin.find_element(self.locator, required=False, parent=html_parent_web_element)
        if element is None and self.xpath_or_css_explicit_locator is not None:
            element = self.get_plugin().find_element(
                self.xpath_or_css_explicit_locator,
                required=required,
                parent=html_parent_web_element,
            )
        if self.smart_pick is False and self.order is None:
            return element
        elements = self.find_web_elements()
        if self.order is not None:
            return elements[self.order]
        else:
            # smart_pick logic
            assert self.smart_pick is True, f"Logic error. 'smart_pick' should be True, but it is {self.smart_pick}"
            displayed = [e for e in elements if e.is_displayed()]
            if len(displayed) == 0:
                return element
            else:
                element = displayed[0]
            enabled = [e for e in displayed if e.is_enabled()]
            if len(enabled) == 0:
                return element
            else:
                element = enabled[0]
            selected = [e for e in enabled if e.is_selected()]
            if len(selected) == 0:
                return element
            else:
                return selected[0]

    def get_multiple_nodes(self) -> typing.List[Node]:
        assert self._resolved, f"Error in 'get_multiple_nodes'. Node not resolved. Node: {self}"

        # Remove from pom previous multiple nodes:
        self.reset_multiple_nodes()

        num = len(self.find_web_elements())
        nodes = []

        template = self.copy()
        template.is_multiple = False
        template.order = None,
        template.smart_pick = False
        template.is_template = True

        for i in range(num):
            if template.name is None:
                new_name = None
            elif "{order}" in template.name:
                new_name = template.name.format(order=i)
            else:
                new_name = f"{template.name}_{i}"
            node = Node(
                name=new_name,
                order=i,
                template=template,
            )
            node.parent = self.parent
            node.resolve()
            nodes.append(node)

        # Store nodes
        self._multiple_nodes = nodes

        return nodes

    def reset_multiple_nodes(self) -> None:
        # Remove from pom previous multiple nodes:
        for node in self._multiple_nodes:
            node.parent = None

    def update_with_defaults_from(self, node: Node = None) -> None:
        if node is None:
            return

        node_properties = [
            "name",
            "locator",
            "order",
            "is_multiple",
            "wait_present",
            "wait_visible",
            "wait_enabled",
            "wait_selected",
            "html_parent",
            "smart_pick",
            "is_template",
        ]
        for node_prop in node_properties:
            if getattr(self, node_prop) is None:
                setattr(self, node_prop, getattr(node, node_prop))

        children: typing.Dict[str, Node] = {
            child.name: child for child in self.children if child.name is not None
        }
        node_children: typing.Dict[str, Node] = {
            child.name: child for child in node.children if child.name is not None
        }
        node_children_common = {name: node for name, node in node_children.items() if name in children}

        for name in node_children_common:
            children[name].update_with_defaults_from(node_children_common[name])

        # Node children not common are added (as copy)
        node_children_not_common: typing.List[Node] = [
            node for node in node.children if node not in node_children_common.values()
        ]
        for node_not_common in node_children_not_common:
            node_not_common.copy().parent = self

    def apply_format(self, args: list = None, kwargs: dict = None, recursive: bool = True) -> None:
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        if len(args) > 0:
            self.locator = self.locator.format(*args)
            self.name = self.name.format(*args)
        if len(kwargs) > 0:
            self.locator = self.locator.format(**kwargs)
            self.name = self.name.format(**kwargs)
        if recursive:
            for child in self.children:
                child: Node
                child.apply_format(args, kwargs, recursive=True)

    def apply_template(self) -> None:
        template = self.resolve_template()
        if template is None:
            return

        # Make a copy to avoid problems, but get full_name
        template_full_name = template.full_name
        template = template.copy()

        template.apply_format(self.template_args, self.template_kwargs, recursive=True)
        self.update_with_defaults_from(template)
        # Avoid same name that template
        if template_full_name == self.full_name:
            self.name = None

    def is_present(self) -> bool:
        element = self.find_web_element(required=False)
        return True if element is not None else False

    def wait_until_present(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_page_contains_element(
            self.pom_locator,
            timeout=timeout,
            # error=f"Element {self} not present after {timeout}",
            # limit=None,
        )

    def is_visible(self) -> typing.Optional[bool]:
        return self.get_plugin().is_visible(self.pom_locator)

    def wait_until_visible(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_element_is_visible(
            self.pom_locator,
            timeout=timeout,
            # error=f"Element {self} not visible after {timeout}",
        )

    def is_enabled(self) -> typing.Optional[bool]:
        element = self.find_web_element(required=False)
        return element.is_enabled() if element is not None else None

    def wait_until_enabled(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_element_is_enabled(
            self.pom_locator,
            timeout=timeout,
            # error=f"Element {self} not enabled after {timeout}",
        )

    def is_selected(self) -> typing.Optional[bool]:
        element = self.find_web_element(required=False)
        return element.is_selected() if element is not None else None

    def wait_until_selected(self, timeout=None) -> None:
        self.get_plugin().wait_until_element_is_selected(self.pom_locator, timeout=timeout)

    def wait_until_loaded(self, timeout=None) -> None:
        self._wait_until_loaded(timeout, force_visible=True)

    def _wait_until_loaded(self, timeout=None, force_visible: bool = False) -> None:
        if self.is_template is True:
            return
        if self.locator is not None:
            if self.wait_present or force_visible:
                self.wait_until_present(timeout)
                if self.limit is not None:
                    self.find_web_elements()
            if self.wait_visible or force_visible:
                self.wait_until_visible(timeout)
            if self.wait_enabled:
                self.wait_until_enabled(timeout)
            if self.wait_selected:
                self.wait_until_selected(timeout)

        if force_visible or self.wait_present:
            for e in self.children:
                e: Node
                e._wait_until_loaded(timeout)

    def is_button(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_button(self.pom_locator)

    def is_checkbox(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_checkbox(self.pom_locator)

    def is_image(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_image(self.pom_locator)

    def is_link(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_link(self.pom_locator)

    def is_list(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_list(self.pom_locator)

    def is_radio(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_radio(self.pom_locator)

    def is_textfield(self) -> typing.Optional[bool]:
        return self.get_plugin().element_is_textfield(self.pom_locator)

    def get_field_value(self,
                        as_type: typing.Union[type, str] = None,
                        **kwargs) -> typing.Any:
        return self.get_page_library().get_field_value(self, as_type, **kwargs)

    def set_field_value(self,
                        value: typing.Any = None,
                        force: bool = False,
                        **kwargs) -> typing.Any:
        return self.get_page_library().set_field_value(self, value, force=force, **kwargs)


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
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    guessed_selenium_library_name: typing.Optional[str] = None

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

        file = pathlib.Path(os.path.abspath(file))
        base, ext = os.path.splitext(file)
        if ext in robopom.constants.YAML_EXTENSIONS:
            return file

        for yaml_ext in robopom.constants.YAML_EXTENSIONS:
            yaml_file = pathlib.Path(f"{base}{yaml_ext}")
            if os.path.exists(yaml_file):
                return yaml_file

        return None

    def __init__(self,
                 page_name: str,
                 parent_page_name: str = None,
                 selenium_library_name: str = None) -> None:
        """
        Creates a new `RobopomPage`.

        :param parent_page_name: Optional. Name of the parent page (if it has a parent page).
        :param selenium_library_name: Optional. Name given to the SeleniumLibrary when imported.
        """
        self.real_name = page_name
        # TODO: Posible bottomless pit
        self.override_name = None

        self.parent_page_name = parent_page_name

        if selenium_library_name is None:
            self.selenium_library_name = self.guess_selenium_library_name()

        # Find page_resource_file_path
        possible_file_paths = list(pathlib.Path(".").rglob(f"{page_name}.resource"))
        assert len(possible_file_paths) == 1, \
            f"Error. Found more than one possible file for page {page_name}: {possible_file_paths}"
        # noinspection PyTypeChecker
        self.page_resource_file_path: os.PathLike = possible_file_paths[0]

        # Init page nodes
        self.init_page_nodes()
        self.get_robopom_plugin().pom_root.resolve(recursive=True)

        # Provided by Listener. Listener also adds page to model
        # self.page_resource_file_path: typing.Optional[os.PathLike] = None

    @classmethod
    def guess_selenium_library_name(cls) -> str:
        if cls.guessed_selenium_library_name is None:
            # Try to guess selenium_library_name
            all_libs: typing.Dict[str] = Plugin.built_in.get_library_instance(all=True)
            candidates = {name: lib for name, lib in all_libs.items()
                          if isinstance(lib, SeleniumLibrary.SeleniumLibrary)}
            assert len(candidates) == 1, \
                f"Error in guess_selenium_library_name. " \
                f"The should be one candidate, but candidates are: {candidates}"
            cls.guessed_selenium_library_name = list(candidates.keys())[0]
        return cls.guessed_selenium_library_name

    # TODO: Posible bottomless pit
    @property
    def name(self) -> typing.Optional[str]:
        if self.override_name is not None:
            return self.override_name
        else:
            return self.real_name

    # TODO: Posible bottomless pit
    @robot_deco.keyword
    def set_override_name(self, name: typing.Optional[str] = None) -> typing.Optional[str]:
        prev_override_name = self.override_name
        self.override_name = name
        return prev_override_name

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
        return list(dict.fromkeys(self.local_keyword_names() + self.parent_keyword_names()))

    def super_keyword_names(self) -> typing.List[str]:
        return [f"{robopom.constants.SUPER_PREFIX.lower()}_{parent_kw}" for parent_kw in self.parent_keyword_names()]

    def get_keyword_names(self) -> typing.List[str]:
        """
        Returns the list if keyword names (used by `Robot Framework`).

        :return: List of keyword names.
        """
        return list(dict.fromkeys(
            self.local_and_parent_keyword_names()
            + self.super_keyword_names()
        ))

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
            if name.casefold().startswith(robopom.constants.SUPER_PREFIX.casefold()):
                no_super_name = name[len(robopom.constants.SUPER_PREFIX) + 1:]
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
            if name.casefold().startswith(robopom.constants.SUPER_PREFIX.casefold()):
                no_super_name = name[len(robopom.constants.SUPER_PREFIX) + 1:]
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
            if name.casefold().startswith(robopom.constants.SUPER_PREFIX.casefold()):
                no_super_name = name[len(robopom.constants.SUPER_PREFIX) + 1:]
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
            if name.casefold().startswith(robopom.constants.SUPER_PREFIX.casefold()):
                no_super_name = name[len(robopom.constants.SUPER_PREFIX) + 1:]
                if no_super_name in self.parent_page_library().get_keyword_names():
                    name = no_super_name
            return self.parent_page_library().get_keyword_types(name)

    def get_selenium_library(self) -> SeleniumLibrary.SeleniumLibrary:
        """
        Returns the `SeleniumLibrary` instance been used.

        :return: The SeleniumLibrary instance.
        """
        return Plugin.built_in.get_library_instance(self.selenium_library_name)

    def get_robopom_plugin(self) -> Plugin:
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
        return Plugin.built_in.get_library_instance(self.parent_page_name) \
            if self.parent_page_name is not None else None

    def parent_page_node(self) -> typing.Optional[Node]:
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

    def ancestor_pages_libraries(self) -> typing.List[Page]:
        """
        Returns the list of names of all the `ancestors` pages (starting from `root`).

        :return: List of names of all the ancestors pages.
        """
        return [Plugin.built_in.get_library_instance(name) for name in self.ancestor_pages_names()]

    @robot_deco.keyword
    def get_page_node(self) -> Node:
        """
        Returns the `page object` of this page.
        """
        return self.get_robopom_plugin().get_node(self.name)

    @robot_deco.keyword(types=[str])
    def get_node(self, name: str) -> Node:
        """
        Returns the `page component` defined by `path`. If `path` is `None`, it returns the `page object`.

        Parameter `path` can be a real path, or a `short`.
        """
        name = Plugin.remove_pom_prefix(name)
        node = self.get_page_node().find_node(name)
        assert node is not None, f"Node '{name}' not found in page '{self.name}'"
        return node

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

    @robot_deco.keyword(types=[Node, typing.Union[Node, str]])
    def attach_node_to_page(self,
                            node: Node,
                            parent: typing.Union[Node, str] = None) -> str:
        """
        Adds `component` (object) to the model tree, inserting it as a child of `parent`.
        Returns the `path` of the inserted component.

        `parent` (object or string): If parent is `None`, component is inserted as a child of the root component.
        Can be the component (object) itself or the `path` (string) of the parent component.
        """
        if parent is None:
            parent = self.get_page_node()
        elif isinstance(parent, str):
            parent = self.get_node(parent)
        return self.get_robopom_plugin().attach_node(node, parent)

    @robot_deco.keyword(types=[typing.Union[Node, str],
                               str,
                               str,
                               bool,
                               int,
                               bool,
                               bool,
                               bool,
                               bool,
                               str,
                               bool,
                               bool,
                               typing.Union[str, Node],
                               typing.Any,
                               dict,
                               dict, ])
    def attach_new_node_to_page(self,
                                parent: typing.Union[Node, str] = None,
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
                                template: typing.Union[str, Node] = None,
                                template_args: typing.Any = None,
                                template_kwargs: dict = None,
                                node_kwargs: dict = None) -> str:
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
        if node_kwargs is None:
            node_kwargs = {}

        if parent is None:
            if template is None:
                parent = self.get_page_node()
            else:
                if isinstance(template, str):
                    template_node = self.get_node(template)
                else:
                    template_node = template
                if template_node.page_node == self:
                    parent = template_node.parent
                else:
                    parent = self.get_page_node()
        elif isinstance(parent, str):
            parent = self.get_node(parent)
        return self.get_robopom_plugin().attach_new_node(
            parent,
            name=name,
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
            **node_kwargs,
        )

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
        over_keyword = f"{self.name}.{robopom.constants.OVERRIDE_PREFIX} {keyword}"

        if self.get_robopom_plugin().keyword_exists(over_keyword):
            run_args = list(args[:])
            run_args += [f"{key}={value}" for key, value in kwargs.items()]
            return Plugin.built_in.run_keyword(over_keyword, *run_args)
        else:
            return method(*args, **kwargs)

    @robot_deco.keyword(types=[None])
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
        self.get_robopom_plugin().set_active_page(self)
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

        if self.parent_page_library() is not None:
            self.parent_page_library().wait_until_loaded(timeout)
        self.get_robopom_plugin().set_active_page(self)
        self.get_page_node().wait_until_loaded(timeout)

    def get_page_node_from_file(self) -> Node:
        ancestor_node: typing.Optional[Node] = None
        for ancestor_page_lib in self.ancestor_pages_libraries():
            ancestor_model_file = ancestor_page_lib.model_file
            if ancestor_model_file is not None:
                current_node = self.get_robopom_plugin().get_node_from_file(ancestor_model_file)
            else:
                current_node = Node(name=ancestor_page_lib.name)
            current_node.update_with_defaults_from(ancestor_node)
            ancestor_node = current_node

        model_file = self.model_file
        if model_file is not None:
            page_node = self.get_robopom_plugin().get_node_from_file(model_file)
        else:
            page_node = Node(name=self.name)

        page_node.update_with_defaults_from(ancestor_node)
        return page_node

    # @robot_deco.keyword
    def attach_page_node(self) -> None:
        self.get_robopom_plugin().attach_node(self.get_page_node_from_file())

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
        self.core_init_page_nodes()
        self.parent_init_page_nodes()

    @robot_deco.keyword
    def core_init_page_nodes(self) -> None:
        self.attach_page_node()

    @robot_deco.keyword
    def parent_init_page_nodes(self) -> None:
        for ancestor_page_name in self.ancestor_pages_names():
            ancestor_kw = f"{ancestor_page_name}.{robopom.constants.OVERRIDE_PREFIX} Init Page Nodes"
            if self.get_robopom_plugin().keyword_exists(ancestor_kw):
                Plugin.built_in.run_keyword(ancestor_kw)

    def get_custom_get_set_keyword(self,
                                   element: typing.Union[Node, str],
                                   get_set: str = "Get",
                                   as_type: typing.Union[type, str] = None,
                                   ) -> typing.Optional[str]:
        get_set = get_set.capitalize()
        assert get_set in ["Get", "Set"], f"'get_set' must be 'Get' or 'Set', but it is: {get_set}"
        if isinstance(as_type, type):
            if as_type == str:
                as_type = "String"
            elif as_type == int:
                as_type = "Integer"
            elif as_type == float:
                as_type = "Float"
            elif as_type == bool:
                as_type = "Boolean"
            elif as_type == datetime.date:
                as_type = "Date"
            elif as_type == datetime.datetime:
                as_type = "Datetime"
            else:
                assert False, f"Invalid 'as_type': {as_type}"
        if as_type is not None:
            assert get_set == "Get", \
                f"'as_type' is not None ({as_type}), so 'get_set' should be 'Set', but it is: {get_set}"

        if isinstance(element, str):
            element = self.get_node(element)
        aliases = element.aliases_in_page()
        if as_type is None:
            as_type_str = ""
        else:
            as_type_str = as_type
        possible_keywords = [f"{self.name}.{get_set} {alias} {as_type_str}".strip() for alias in aliases]
        keywords = [keyword for keyword in possible_keywords if self.get_robopom_plugin().keyword_exists(keyword)]
        assert len(keywords) <= 1, f"Found more than one {get_set} keyword for '{element.full_name}': {keywords}"
        if len(keywords) == 1:
            return keywords[0]
        elif self.parent_page_name is not None:
            return self.parent_page_library().get_custom_get_set_keyword(element, get_set, as_type=as_type)
        else:
            return None

    @robot_deco.keyword(types=[typing.Union[str, Node], typing.Union[type, str]])
    def get_field_value(self,
                        element: typing.Union[str, Node],
                        as_type: typing.Union[type, str] = None,
                        **kwargs,
                        ) -> typing.Any:
        custom_keyword = self.get_custom_get_set_keyword(element, get_set="Get", as_type=as_type)
        if custom_keyword is not None:
            # integrate 'as_type' in kwargs
            if as_type is not None:
                kwargs["as_type"] = as_type
            return self.get_robopom_plugin().built_in.run_keyword(custom_keyword, **kwargs)
        else:
            if isinstance(element, str):
                element = self.get_node(element)
            if element.is_multiple:
                return self.get_robopom_plugin().default_get_field_values(element.pom_locator, as_type)
            else:
                return self.get_robopom_plugin().default_get_field_value(element.pom_locator, as_type)

    @robot_deco.keyword(types=[typing.Union[str, Node], None, bool])
    def set_field_value(self,
                        element: typing.Union[str, Node],
                        value: typing.Any = None,
                        force: bool = None,
                        **kwargs,
                        ) -> None:
        if value is None:
            return
        if kwargs is None:
            kwargs = {}

        custom_keyword = self.get_custom_get_set_keyword(element, get_set="Set")
        if custom_keyword is not None:
            # integrate 'force' in kwargs
            if force is not None:
                kwargs["force"] = force
            self.get_robopom_plugin().built_in.run_keyword(custom_keyword, value, **kwargs)
            return
        else:
            if force is None:
                force = False
            if isinstance(element, str):
                element = self.get_node(element)
            if element.is_multiple:
                if not isinstance(value, list):
                    value = [value]
                self.get_robopom_plugin().default_set_field_values(element.pom_locator, values=value, force=force)
                return
            else:
                self.get_robopom_plugin().default_set_field_value(element.pom_locator, value=value, force=force)
