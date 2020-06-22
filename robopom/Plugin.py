from __future__ import annotations
import typing
import os
import pathlib
import SeleniumLibrary
import robot.libraries.BuiltIn
import anytree.importer
import yaml
from . import model


class Plugin(SeleniumLibrary.LibraryComponent):
    """
    RobopomSeleniumPlugin is a plugin for Robot Framework SeleniumLibrary that makes easier to adopt the
    Page Object Model (POM) methodology.

    It can be imported using something like this:

    | Library | SeleniumLibrary | timeout=10 | plugins=robopom.RobopomSeleniumPlugin;my_pages.resource;my_variables.yaml, plugins.MyOtherPlugin |

    Here, `my_pages.resource` and `my_variables.yaml` are the paths of the `pages` file and `variables` file used in
    Update Variables File keyword.

    If the default values are ok for you (and you do not need any other SeleniumLibrary plugins), it can be simplified:

    | Library | SeleniumLibrary | timeout=10 | plugins=robopom.RobopomSeleniumPlugin |
    """
    POM_PREFIX = "pom"
    POM_LOCATOR_PREFIXES = [f"{POM_PREFIX}:", f"{POM_PREFIX}="]

    built_in = robot.libraries.BuiltIn.BuiltIn()

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
            "Pom Locator Strategy",
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
    def pom_locator_strategy(self,
                             browser,
                             locator: str,
                             tag,
                             constraints,
                             ) -> typing.Optional[SeleniumLibrary.locators.elementfinder.WebElement]:
        """
        Keyword that defines the `Path Locator Strategy`.

        Usually it is not necessary to run this keyword directly (it is used by the Robopom Plugin internally).
        """
        self.debug(
            f"Starting 'pom_locator_strategy' with: "
            f"browser={browser}, locator={locator}, tag={tag}, constraints={constraints}")
        pom_node = self.get_node(locator)
        element = pom_node.find_web_element(required=False)

        log_info = f"browser={browser}, locator={locator}, tag={tag}, constraints={constraints}. " \
                   f"Real locator used: {pom_node.locator}"
        if element is not None:
            self.debug(f"Found element '{element}' using 'Pom Locator Strategy': {log_info}")
        else:
            self.info(f"Element not found using 'Pom Locator Strategy': {log_info}")
        return element

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

    @SeleniumLibrary.base.keyword
    def wait_until_node_is_present(self,
                                   node: typing.Union[model.Node, str],
                                   timeout=None, ) -> None:
        node = self.get_node(node) if isinstance(node, str) else node
        node.wait_until_present(timeout)

    @SeleniumLibrary.base.keyword
    def wait_until_node_is_visible(self,
                                   node: typing.Union[model.Node, str],
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
        node = self.get_node(node) if isinstance(node, str) else node
        node.wait_until_visible(timeout)

    @SeleniumLibrary.base.keyword
    def wait_until_node_is_enabled(self,
                                   node: typing.Union[model.Node, str],
                                   timeout=None, ) -> None:
        node = self.get_node(node) if isinstance(node, str) else node
        node.wait_until_enabled(timeout)

    @SeleniumLibrary.base.keyword
    def wait_until_node_is_selected(self,
                                    node: typing.Union[model.Node, str],
                                    timeout=None, ) -> None:
        node = self.get_node(node) if isinstance(node, str) else node
        node.wait_until_selected(timeout)

    ##############################################
    # SELENIUM OVERRIDES  (and auxiliar methods) #
    ##############################################

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
        if isinstance(locator, str) and locator.startswith(tuple(self.POM_LOCATOR_PREFIXES)):
            node = self.get_node(self.remove_pom_prefix(locator))
            locator_desc = f"page: '{node.page_node.name}', full_name: '{node.full_name}', " \
                           f"real locator: '{node.locator}'"
        return locator_desc

    @SeleniumLibrary.base.keyword
    def get_current_frame(self) -> SeleniumLibrary.locators.elementfinder.WebElement:
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
