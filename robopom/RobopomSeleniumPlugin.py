from __future__ import annotations
import typing
import os
import pathlib
import SeleniumLibrary
import selenium.webdriver.remote.webelement as webelement
import anytree
import robot.libraries.BuiltIn as robot_built_in
import robopom.model as model
import robopom.component_loader as file_loader
import robopom.constants as constants


class RobopomSeleniumPlugin(SeleniumLibrary.base.LibraryComponent):
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

    def __init__(self,
                 ctx: SeleniumLibrary.SeleniumLibrary = None,
                 pages_files: typing.Union[os.PathLike, typing.List[os.PathLike]] = None,
                 variables_file: os.PathLike = None, ) -> None:
        self.root = model.RootComponent(constants.ROOT_NAME)
        self.resolver = anytree.resolver.Resolver()
        self.loader = file_loader.ComponentLoader()
        self.separator = model.Component.separator
        self.built_in = robot_built_in.BuiltIn()
        if ctx is not None:
            SeleniumLibrary.base.LibraryComponent.__init__(self, ctx)
            ctx.robopom_plugin = self
            # Register Path Locator Strategy
            SeleniumLibrary.keywords.element.ElementKeywords(ctx).add_location_strategy(
                constants.PATH_PREFIX,
                "Path Locator Strategy",
                persist=True,
            )

        self.working_dir = os.path.abspath(".")

        if pages_files is None:
            pages_files = [constants.PAGES_FILE]
        if isinstance(pages_files, os.PathLike):
            pages_files = [pages_files]
        if variables_file is None:
            variables_file = constants.VARIABLES_FILE
        self.pages_files = []
        for page_file in pages_files:
            if os.path.isabs(page_file):
                self.pages_files.append(page_file)
            else:
                for found in pathlib.Path(self.working_dir).rglob(str(page_file)):
                    self.pages_files.append(str(found))

        self.variables_file = variables_file
        self._robot_running = None

    @staticmethod
    def is_robot_running() -> bool:
        built_in = robot_built_in.BuiltIn()
        try:
            prev_log_level = built_in.set_log_level("NONE")
            built_in.set_log_level(prev_log_level)
        except robot_built_in.RobotNotRunningError:
            return False
        return True

    @staticmethod
    def remove_path_prefix(path: str) -> str:
        remove = [f"{constants.PATH_PREFIX}=", f"{constants.PATH_PREFIX}:"]
        new_path = path
        for prefix in remove:
            if new_path.startswith(prefix):
                new_path = new_path.replace(prefix, "", 1)
        return new_path

    @staticmethod
    def remove_separator_prefix(path: str) -> str:
        new_path = path
        sep = model.Component.separator
        while new_path.startswith(sep):
            new_path = new_path.replace(sep, "", 1)
        return new_path

    @staticmethod
    def remove_root_prefix(path: str) -> str:
        new_path = path
        root = constants.ROOT_NAME
        while new_path.startswith(f"{root}{constants.SEPARATOR}"):
            new_path = new_path.replace(root, "", 1)
        return new_path

    @property
    def robot_running(self) -> bool:
        if self._robot_running is None:
            self._robot_running = self.is_robot_running()
        return self._robot_running

    @SeleniumLibrary.base.keyword
    def keyword_exists(self, keyword) -> bool:
        """
        Returns `True` if given keyword exists, `False` otherwise.
        """
        if not self.robot_running:
            return False
        try:
            self.built_in.keyword_should_exist(keyword)
        except AssertionError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def get_component(self, path: str = None) -> model.Component:
        """
        Returns the component obtained from `path`.

        If the component defined by path does not exist, it generates an error.

        `path` (string): Path of the component. If path is `None`, returns the root component.
        """
        if path is None:
            return self.root
        path = self.remove_path_prefix(path)
        path = self.remove_separator_prefix(path)
        path = self.remove_root_prefix(path)
        path = self.remove_separator_prefix(path)

        path = f"{self.separator}{constants.ROOT_NAME}{self.separator}{path}"

        # Try to find component by short
        path_split = path.split(self.separator)
        if len(path_split) == 4:
            # 0 -> "", 1 -> Root, 2 -> Page -> 3 Possible short
            _, _, page, short = path_split
            if self.exists_component_with_short(page, short):
                return self.get_component_with_short(page, short)

        # Find component by path
        return self.resolver.get(self.root, path)

    @SeleniumLibrary.base.keyword
    def get_component_with_short(self,
                                 page: typing.Union[model.PageObject, str],
                                 short: str = None, ) -> model.PageComponent:
        """
        Returns the page component in `page` with short `short`.

        If the component does not exist, it generates an error.

        `page` (string or object): Page where component is searched. It can be the page name (string)
        or the `page object` itself (object).

        `short` (string): Short value of the component. If short is `None`, returns the page object.
        """
        if isinstance(page, str):
            page = self.get_component(page)
        if short is None:
            return page
        return anytree.search.findall_by_attr(page, short, "short", mincount=1, maxcount=1)[0]

    @SeleniumLibrary.base.keyword
    def path_locator_strategy(
            self,
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
            f"Starting 'path_locator_strategy' with: "
            f"browser={browser}, locator={locator}, tag={tag}, constraints={constraints}")
        page_element = self.get_component(locator)
        assert isinstance(page_element, model.PageElement), \
            f"'page_element' should be a PageElement, but it is a {type(page_element)}"
        element = page_element.find_element(required=False)

        log_info = f"browser={browser}, locator={locator}, tag={tag}, constraints={constraints}. " \
                   f"Real locator used: {page_element.locator}"
        if page_element.short is not None:
            log_info += f". Short: {page_element.short}"
        if element is not None:
            self.debug(f"Found element '{element}' using 'Path Locator Strategy': {log_info}")
        else:
            self.info(f"Element not found using 'Path Locator Strategy': {log_info}")
        return element

    @SeleniumLibrary.base.keyword
    def get_current_frame(self) -> webelement.WebElement:
        return self.driver.execute_script('return window.frameElement')

    @SeleniumLibrary.base.keyword
    def log_model(self) -> None:
        """
        Writes the `model tree` to the log file.
        """
        self.info(anytree.RenderTree(self.root))

    @SeleniumLibrary.base.keyword
    def exists_component(self, path: str = None) -> bool:
        """
        Returns `True` if component defined by `path` (string) exists, `False` otherwise.
        """
        try:
            self.get_component(path)
        except anytree.resolver.ResolverError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def exists_component_with_short(self,
                                    page: typing.Union[model.PageObject, str],
                                    short: str, ) -> bool:
        """
        Returns `True` if component with short `short` (string) exists in page `page`, `False` otherwise.

        `page` (string or object): Page where component is searched. It can be the page name (string)
        or the `page object` itself (object).

        `short` (string): Short value of the component.
        """
        try:
            self.get_component_with_short(page, short)
        except anytree.search.CountError:
            return False
        return True

    @SeleniumLibrary.base.keyword
    def add_page_component(self,
                           component: model.PageComponent,
                           parent: typing.Union[model.AnyParent, str] = None) -> str:
        """
        Adds `component` (object) to the model tree, inserting it as a child of `parent`.
        Returns the `path` of the inserted component.

        `parent` (object or string): If parent is `None`, component is inserted as a child of the root component.
        Can be the component (object) itself or the `path` (string) of the parent component.
        """
        if parent is None:
            parent_object = self.root
        elif isinstance(parent, str):
            parent_object = self.get_component(parent)
        else:
            parent_object = parent

        if isinstance(component, model.PageObject):
            assert parent_object == self.root, f"Tried to add a PageObject, but parent is not root: {component}"

        if self.exists_component(f"{parent_object.absolute_path}{self.separator}{component.name}"):
            raise RuntimeError(f"Element '{component.name}' already exists in {parent_object.absolute_path}")

        short = getattr(component, "short", None)
        if short is not None:
            if self.exists_component_with_short(parent_object.page, short):
                raise RuntimeError(
                    f"Element '{component.name}' with short '{short}' is not correct. "
                    f"Already exists another element with that short in page '{parent_object.page.name}'"
                )
            if self.exists_component(f"{parent_object.page.name}{self.separator}{short}"):
                raise RuntimeError(
                    f"Element '{component.name}' with short '{short}' is not correct. "
                    f"Already exists another element with that name that is child of page '{parent_object.page.name}'"
                )

        component.parent = parent_object

        return component.absolute_path

    @SeleniumLibrary.base.keyword
    def add_new_page_object(self, name: str) -> str:
        """
        Adds a new page object to the model with the specified `name`. Returns the `path` of the inserted page object.
        """
        if self.exists_component(f"{self.root.absolute_path}{self.separator}{name}"):
            raise RuntimeError(f"Page {name} already exists")
        page = model.PageObject(name)
        return self.add_page_component(page)

    @SeleniumLibrary.base.keyword
    def add_new_page_element(self,
                             locator: str,
                             parent: typing.Union[model.AnyPageParent, str],
                             name: str = None,
                             # *,
                             always_visible: typing.Union[bool, str] = False,
                             html_parent: typing.Union[str, model.PageElement] = None,
                             order: typing.Union[int, str] = None,
                             default_role: str = None,
                             prefer_visible: typing.Union[bool, str] = True, ) -> str:
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
        element = model.PageElement(locator=locator,
                                    name=name,
                                    always_visible=always_visible,
                                    html_parent=html_parent,
                                    order=order,
                                    default_role=default_role,
                                    prefer_visible=prefer_visible)
        return self.add_page_component(element, parent)

    @SeleniumLibrary.base.keyword
    def add_new_page_elements(self,
                              locator: str,
                              parent: typing.Union[model.AnyPageParent, str],
                              name: str = None,
                              # *,
                              always_visible: typing.Union[bool, str] = False,
                              html_parent: typing.Union[None, str, model.PageElement] = None,
                              default_role: str = None, ) -> str:
        """
        Creates a new `page elements` (single object - multiple elements) and adds it to the model tree.
        Returns the `path` of the inserted `page elements` object.

        `locator` (string): The SeleniumLibrary locator used to find the elements.

        `parent` (object or string): Parent of the `page elements` newly created.
        Can be the page component (object) itself or the `path` (string) of the parent page component.

        `name` (string): Optional. Name of the new page element.
        If not provided, a pseudo random numeric string (string with only numeric characters) is used.

        `always_visible` (boolean or True-False-string): Optional. Establishes if at least one page element
        defined by the locator should always be visible in the page. Default value: `False`.

        `html_parent` (object or string): Optional. If `parent` is not the `real html parent` in the page,
        can be set here. Can be a page element (object) or a SeleniumLibrary locator (string).

        `default_role` (string): Optional. Establishes the default role of the page elements that is used
        in get/set operations. If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
        Possible values: `text`, `select`, `checkbox`, `password`.
        """
        if isinstance(always_visible, str):
            if always_visible.casefold() == "True".casefold():
                always_visible = True
            elif always_visible.casefold() == "False".casefold():
                always_visible = False
            else:
                assert False, \
                    f"'always_visible' should be a boolean or 'True-False-like-string', but it is {always_visible}"
        elements = model.PageElements(locator=locator,
                                      name=name,
                                      always_visible=always_visible,
                                      html_parent=html_parent,
                                      default_role=default_role, )
        return self.add_page_component(elements, parent)

    @SeleniumLibrary.base.keyword
    def add_new_page_element_generator(self,
                                       locator_generator: str,
                                       parent: typing.Union[model.AnyPageParent, str],
                                       name: str = None,
                                       # *,
                                       always_visible: typing.Union[bool, str] = False,
                                       html_parent: typing.Union[None, str, model.PageElement] = None,
                                       order: typing.Union[int, str] = None,
                                       default_role: str = None,
                                       prefer_visible: typing.Union[bool, str] = True, ) -> str:
        """
        Creates a new `page element generator` object and adds it to the model tree.
        Returns the `path` of the inserted page element generator.

        `locator_generator` (string): SeleniumLibrary locator that contains
        `Python string formatting parts` (like `{}`).

        `parent` (object or string): Parent of the page element generator newly created.
        It will be the default `parent` of the page elements generated from this generator.
        Can be the page component (object) itself or the `path` (string) of the parent page component.

        `name`(string): Optional. Name of the new page element generator.
        If not provided, a pseudo random numeric string (string with only numeric characters) is used.

        `always_visible` (boolean or True-False-string): Optional. Establishes if the page elements generated
        from this generator should always be visible in the page by default. Default value: `False`.

        `html_parent` (object or string): Optional. If `parent` is not the `real html parent` in the page,
        can be set here. It will be the default `html_parent` of the page elements generated from this generator.
        Can be a page element (object) or a SeleniumLibrary locator (string).

        `order` (integer or integer-like-string): Optional. It will be the default `order`
        of the page elements generated from this generator.

        `default_role` (string): Optional. Establishes the default role of the page elements generated
        from this generator that is used in get/set operations.
        If not provided, Robopom will try to guess it in any page element generated from this generator
        ('text' is used as default if can not guess).
        Possible values: `text`, `select`, `checkbox`, `password`.

        `prefer_visible` (boolean or True-False-string): Optional. It will be the default `prefer_visible`
        of the page elements generated from this generator. Default value: `True`.
        """
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
        generator = model.PageElementGenerator(locator_generator=locator_generator,
                                               name=name,
                                               always_visible=always_visible,
                                               html_parent=html_parent,
                                               order=order,
                                               default_role=default_role,
                                               prefer_visible=prefer_visible)
        return self.add_page_component(generator, parent)

    @SeleniumLibrary.base.keyword
    def add_new_page_element_generator_instance(self,
                                                generator: typing.Union[str, model.PageElementGenerator],
                                                name: str = None,
                                                # *,
                                                format_args: typing.Union[str, typing.List[str]] = None,
                                                format_kwargs: typing.Dict[str, str] = None,
                                                always_visible: typing.Union[bool, str] = None,
                                                html_parent: typing.Union[None, str, model.PageElement] = None,
                                                order: typing.Union[int, str] = None,
                                                default_role: str = None,
                                                prefer_visible: typing.Union[bool, str] = None, ) -> str:
        """
        Creates a new `page element generator instance` (a `page element` generated from a `page element generator`)
        and adds it to the model tree. Returns the `path` of the inserted page element.

        `generator` (object or string): The `page element generator` used to generate the new page element.
        Can be the page element generator (object) itself or the `path` (string) of the `page element generator`.

        `name` (string): Optional. Name of the new page element.
        If not provided, a pseudo random numeric string (string with only numeric characters) is used.

        `format_args` (list or string): Optional. The `Python format arguments` (list) used in the `locator_generator`
        of the page element generator to determine the final `locator` of the new page element.
        It can be a list of strings (or just a single string, if the list has just one element).

        `format_kwargs` (dictionary): Optional. The` Python format keyword arguments` (dictionary)
        used in the `locator_generator` of the page element generator to determine the final `locator`
        of the new page element.

        `always_visible` (boolean or True-False-string): Optional. Establishes if the generated page element
        should always be visible in the page. Default value: Value of the `always_visible` property of `generator`.

        `html_parent` (object or string): Optional. If the generator `parent` is not the `real html parent`
        in the page, can be set here. Can be a page element (object) or a SeleniumLibrary locator (string).
        Default value: Value of the `html_parent` property of `generator`.

        `order` (integer or integer-like-string): Optional. If the generated `locator` returns more than one element,
        you can determine which to use (zero-based).
        Default value: Value of the `order` property of `generator`.

        `default_role` (string): Optional. Establishes the default role of the generated page element that is used
        in get/set operations.
        Default value: Value of the `default_role` property of `generator`. If not provided here nor in `generator`,
        Robopom tries to guess it ('text' is used as default if can not guess).
        Possible values: `text`, `select`, `checkbox`, `password`.

        `prefer_visible` (boolean or True-False-string): Optional. If `prefer_visible` is `True`
        and `locator` returns more than one element, the first 'visible' element is used.
        If `False`, the first element is used (visible or not).
        Default value: Value of the `prefer_visible` property of `generator`.
        """
        if isinstance(generator, str):
            generator = self.get_component(generator)
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
        return model.PageElementGeneratorInstance(generator=generator,
                                                  name=name,
                                                  format_args=format_args,
                                                  format_kwargs=format_kwargs,
                                                  always_visible=always_visible,
                                                  html_parent=html_parent,
                                                  order=order,
                                                  default_role=default_role,
                                                  prefer_visible=prefer_visible).absolute_path

    @SeleniumLibrary.base.keyword
    def load_component_from_file(self,
                                 file: os.PathLike,
                                 component_path: str = None,
                                 ) -> model.PageComponent:
        """
        Returns a `page component` created from a YAML file. The component is not added to the model tree.

        `file` (string): Path to the YAML file.

        `component_path` (string): Optional. If only a sub-component of the main component
        defined in the YAML file is needed, here you can provide the `path` to that sub-component.
        """
        return file_loader.ComponentLoader.load_component_from_file(file, component_path)

    @SeleniumLibrary.base.keyword
    def add_component_from_file(self,
                                file: os.PathLike,
                                component_path: str = None,
                                parent: typing.Union[model.Component, str] = None, ) -> str:
        """
        Creates a `page component` from a YAML file and adds it to the model tree.
        It returns the `path` of the newly created component.

        `file` (string): Path to the YAML file.

        `component_path` (string): Optional. If only a sub-component of the main component
        defined in the YAML file is needed, here you can provide the `path` to that sub-component.

        `parent` (object or string): If parent is `None`, component is inserted as a child of the root component.
        Can be the component (object) itself or the `path` (string) of the parent component.
        """
        return self.add_page_component(self.load_component_from_file(file, component_path), parent)

    @SeleniumLibrary.base.keyword
    def wait_until_page_element_is_visible(self,
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
        element = self.get_component(element) if isinstance(element, str) else element
        element.wait_until_visible(timeout)

    @SeleniumLibrary.base.keyword
    def update_variables_file(self) -> None:
        """
        Generates a `variables` YAML file (or updates if it exist) with the paths of the components of the model tree.

        It usually generates the model reading the `pages.resource` file,
        and writes the variables file to `variables.yaml`, but these file names can be changed
        in the import statement of the SeleniumLibrary with the Robopom Plugin.
        """
        text = ""
        text = text + "#####################\n"
        text = text + "# GENERAL VARIABLES #\n"
        text = text + "#####################\n"

        # General: Roles
        roles_dict = {
            "ROLE_TEXT": constants.ROLE_TEXT,
            "ROLE_PASSWORD": constants.ROLE_PASSWORD,
            "ROLE_SELECT": constants.ROLE_SELECT,
            "ROLE_CHECKBOX": constants.ROLE_CHECKBOX,
        }
        text = text + "# ROLES VARIABLES #\n"
        text = text + self.dictionary_to_text(roles_dict)

        # General: Get/Set
        get_set_dict = {
            "SET_TEXT": f"{constants.SET_TEXT_PREFIX}{constants.GET_SET_SEPARATOR}",
            "GET_TEXT": f"{constants.GET_TEXT_PREFIX}{constants.GET_SET_SEPARATOR}",
            "SET_PASSWORD": f"{constants.SET_PASSWORD_PREFIX}{constants.GET_SET_SEPARATOR}",
            "GET_PASSWORD": f"{constants.GET_PASSWORD_PREFIX}{constants.GET_SET_SEPARATOR}",
            "SET_SELECT": f"{constants.SET_SELECT_PREFIX}{constants.GET_SET_SEPARATOR}",
            "GET_SELECT": f"{constants.GET_SELECT_PREFIX}{constants.GET_SET_SEPARATOR}",
            "SET_CHECKBOX": f"{constants.SET_CHECKBOX_PREFIX}{constants.GET_SET_SEPARATOR}",
            "GET_CHECKBOX": f"{constants.GET_CHECKBOX_PREFIX}{constants.GET_SET_SEPARATOR}",
            "SET": f"{constants.SET_PREFIX}{constants.GET_SET_SEPARATOR}",
            "GET": f"{constants.GET_PREFIX}{constants.GET_SET_SEPARATOR}",
        }
        text = text + "# GET-SET VARIABLES #\n"
        text = text + self.dictionary_to_text(get_set_dict)

        # General: Actions
        actions_dict = {
            "ACTION_CLICK": f"{constants.ACTION_PREFIX}{constants.GET_SET_SEPARATOR}{constants.ACTION_CLICK}",
            "ACTION_DOUBLE_CLICK":
                f"{constants.ACTION_PREFIX}{constants.GET_SET_SEPARATOR}{constants.ACTION_DOUBLE_CLICK}",
            "ACTION_CONTEXT_CLICK":
                f"{constants.ACTION_PREFIX}{constants.GET_SET_SEPARATOR}{constants.ACTION_CONTEXT_CLICK}",
        }
        text = text + "# ACTIONS VARIABLES #\n"
        text = text + self.dictionary_to_text(actions_dict)

        # General: Asserts
        assert_dict = {
            "ASSERT_EQUALS": f"{constants.ASSERT_EQUALS_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_NOT_EQUALS": f"{constants.ASSERT_NOT_EQUALS_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_EQUALS_IGNORE_CASE": f"{constants.ASSERT_EQUALS_IGNORE_CASE_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_NOT_EQUALS_IGNORE_CASE":
                f"{constants.ASSERT_NOT_EQUALS_IGNORE_CASE_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_GREATER_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_GREATER_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_GREATER_OR_EQUAL_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LOWER_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LOWER_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LOWER_OR_EQUAL_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_IN_EXPECTED": f"{constants.ASSERT_VALUE_IN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_NOT_IN_EXPECTED":
                f"{constants.ASSERT_VALUE_NOT_IN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_EXPECTED_IN_VALUE": f"{constants.ASSERT_EXPECTED_IN_VALUE_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_EXPECTED_NOT_IN_VALUE":
                f"{constants.ASSERT_EXPECTED_NOT_IN_VALUE_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_EQUALS": f"{constants.ASSERT_VALUE_LEN_EQUALS_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_NOT_EQUALS":
                f"{constants.ASSERT_VALUE_LEN_NOT_EQUALS_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_GREATER_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LEN_GREATER_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_GREATER_OR_EQUAL_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LEN_GREATER_OR_EQUAL_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_LOWER_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LEN_LOWER_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_LEN_LOWER_OR_EQUAL_THAN_EXPECTED":
                f"{constants.ASSERT_VALUE_LEN_LOWER_OR_EQUAL_THAN_EXPECTED_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_MATCHES_REGULAR_EXPRESSION":
                f"{constants.ASSERT_VALUE_MATCHES_REGULAR_EXPRESSION_PREFIX}{constants.GET_SET_SEPARATOR}",
            "ASSERT_VALUE_NOT_MATCHES_REGULAR_EXPRESSION":
                f"{constants.ASSERT_VALUE_NOT_MATCHES_REGULAR_EXPRESSION_PREFIX}{constants.GET_SET_SEPARATOR}"
        }
        text = text + "# ASSERTS VARIABLES #\n"
        text = text + self.dictionary_to_text(assert_dict)

        # Pages variables
        pages_variables = {}
        assert self.robot_running, f"Robot Framework should be running to 'update_variables_file'"
        self.load_pages_files()
        pages_variables.update(self.root.variables_dictionary())
        text = text + "###################\n"
        text = text + "# PAGES VARIABLES #\n"
        text = text + "###################\n"
        text = text + self.dictionary_to_text(pages_variables)

        with open(self.variables_file, "w") as file:
            file.write(text)

    @staticmethod
    def dictionary_to_text(dictionary: typing.Dict[str, str]) -> str:
        text = ""
        for key, value in dictionary.items():
            text += f'{key}: "{value}"\n'
        return text

    def load_pages_files(self) -> None:
        if not self.robot_running:
            return
        for page_file in self.pages_files:
            if os.path.isfile(page_file):
                # It seems that import_resource only accepts unix like path separator
                self.built_in.import_resource(str(page_file).replace("\\", "/"))

    ##############################################
    # SELENIUM OVERRIDES  (and auxiliar methods) #
    ##############################################

    def locator_description(self, locator=None):
        if locator is None:
            return "None"
        locator_desc = locator
        if isinstance(locator, str) \
                and locator.startswith((f"{constants.PATH_PREFIX}:", f"{constants.PATH_PREFIX}=")):
            element = self.get_component(locator)
            assert isinstance(element, model.PageElement), \
                f"element should be a PageElement, but it is a {type(element)}"
            locator_desc = f"page: '{element.page.name}', "
            if not element.auto_named:
                locator_desc = locator_desc + f"path: '{element.page_path}', "
            if element.short is not None:
                locator_desc = locator_desc + f"short: '{element.short}', "
            locator_desc = locator_desc + f"real locator: '{element.locator}'"
        return locator_desc

    def embed_screenshot(self, keyword: str, locator=None, moment: str = "before") -> None:
        # Only embed in DEBUG or TRACE
        log_level = self.built_in.get_variable_value("${LOG_LEVEL}")
        log_screenshot = log_level in ["DEBUG", "TRACE"]
        locator_desc = self.locator_description(locator)
        if log_screenshot:
            msg = f"Screenshot {moment} '{keyword}': \n{locator_desc}"
        else:
            msg = f"We are at {moment} '{keyword}': \n{locator_desc}"
        self.info(msg)
        if log_screenshot:
            SeleniumLibrary.ScreenshotKeywords(self.ctx).capture_page_screenshot(filename="EMBED")

    def embed_screenshot_after(self, keyword: str, locator=None) -> None:
        self.embed_screenshot(keyword, locator, "after")

    @SeleniumLibrary.base.keyword()
    def alert_should_be_present(self, text='', action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        keyword = "Alert Should Be Present"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.AlertKeywords(self.ctx).alert_should_be_present(
            text=text,
            action=action,
            timeout=timeout,
        )
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def alert_should_not_be_present(self, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=0):
        keyword = "Alert Should Not Be Present"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.AlertKeywords(self.ctx).alert_should_not_be_present(action=action, timeout=timeout)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def choose_file(self, locator, file_path):
        keyword = "Choose File"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).choose_file(locator=locator, file_path=file_path)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def clear_element_text(self, locator):
        keyword = "Clear Element Text"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).clear_element_text(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_button(self, locator, modifier=False):
        keyword = "Click Button"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_button(locator=locator, modifier=modifier)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_element(self, locator, modifier=False, action_chain=False):
        keyword = "Click Element"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_element(
            locator=locator,
            modifier=modifier,
            action_chain=action_chain,
        )
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_element_at_coordinates(self, locator, xoffset, yoffset):
        keyword = "Click Element At Coordinates"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_element_at_coordinates(
            locator=locator,
            xoffset=xoffset,
            yoffset=yoffset,
        )
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_image(self, locator, modifier=False):
        keyword = "Click Image"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_image(locator=locator, modifier=modifier)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def click_link(self, locator, modifier=False):
        keyword = "Click Link"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).click_link(locator=locator, modifier=modifier)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def cover_element(self, locator):
        keyword = "Cover Element"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).cover_element(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def double_click_element(self, locator):
        keyword = "Double Click Element"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).double_click_element(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def drag_and_drop(self, locator, target):
        keyword = "Drag And Drop"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).drag_and_drop(locator=locator, target=target)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def drag_and_drop_by_offset(self, locator, xoffset, yoffset):
        keyword = "Drag And Drop By Offset"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).drag_and_drop_by_offset(
            locator=locator,
            xoffset=xoffset,
            yoffset=yoffset,
        )
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def execute_async_javascript(self, *code):
        keyword = "Execute Async Javascript"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.JavaScriptKeywords(self.ctx).execute_async_javascript(*code)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def execute_javascript(self, *code):
        keyword = "Execute Javascript"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.JavaScriptKeywords(self.ctx).execute_javascript(*code)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def handle_alert(self, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        keyword = "Handle Alert"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.AlertKeywords(self.ctx).handle_alert(action=action, timeout=timeout)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def input_password(self, locator, password, clear=True):
        keyword = "Input Password"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).input_password(locator=locator, password=password, clear=clear)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def input_text(self, locator, text, clear=True):
        keyword = "Input Text"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).input_text(locator=locator, text=text, clear=clear)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def input_text_into_alert(self, text, action=SeleniumLibrary.AlertKeywords.ACCEPT, timeout=None):
        keyword = "Input Text Into Alert"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.AlertKeywords(self.ctx).input_text_into_alert(text=text, action=action, timeout=timeout)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down(self, locator):
        keyword = "Mouse Down"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down_on_image(self, locator):
        keyword = "Mouse Down On Image"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down_on_image(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_down_on_link(self, locator):
        keyword = "Mouse Down On Link"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_down_on_link(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_out(self, locator):
        keyword = "Mouse Out"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_out(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_over(self, locator):
        keyword = "Mouse Over"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_over(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def mouse_up(self, locator):
        keyword = "Mouse Up"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).mouse_up(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def open_context_menu(self, locator):
        keyword = "Open Context Menu"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).open_context_menu(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def press_keys(self, locator=None, *keys):
        keyword = "Press Keys"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).press_keys(locator, *keys)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def reload_page(self):
        keyword = "Reload Page"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.BrowserManagementKeywords(self.ctx).reload_page()
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def scroll_element_into_view(self, locator):
        keyword = "Scroll Element Into View"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).scroll_element_into_view(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_all_from_list(self, locator):
        keyword = "Select All From List"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_all_from_list(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_checkbox(self, locator):
        keyword = "Select Checkbox"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).select_checkbox(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_index(self, locator, *indexes):
        keyword = "Select From List By Index"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_index(locator, *indexes)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_label(self, locator, *labels):
        keyword = "Select From List By Label"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_label(locator, *labels)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_from_list_by_value(self, locator, *values):
        keyword = "Select From List By Value"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).select_from_list_by_value(locator, *values)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def select_radio_button(self, group_name, value):
        keyword = "Select Radio Button"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).select_radio_button(group_name=group_name, value=value)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def simulate_event(self, locator, event):
        keyword = "Simulate Event"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.ElementKeywords(self.ctx).simulate_event(locator=locator, event=event)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def submit_form(self, locator):
        keyword = "Submit Form"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).submit_form(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def switch_browser(self, index_or_alias):
        keyword = "Switch Browser"
        self.embed_screenshot(keyword)
        value = SeleniumLibrary.BrowserManagementKeywords(self.ctx).switch_browser(index_or_alias=index_or_alias)
        self.embed_screenshot_after(keyword)
        return value

    @SeleniumLibrary.base.keyword()
    def switch_window(self, locator='MAIN', timeout=None, browser='CURRENT'):
        keyword = "Switch Window"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.WindowKeywords(self.ctx).switch_window(
            locator=locator,
            timeout=timeout,
            browser=browser,
        )
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_all_from_list(self, locator):
        keyword = "Unselect All From List"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_all_from_list(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_checkbox(self, locator):
        keyword = "Unselect Checkbox"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.FormElementKeywords(self.ctx).unselect_checkbox(locator=locator)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_index(self, locator, *indexes):
        keyword = "Unselect From List By Index"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_index(locator, *indexes)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_label(self, locator, *labels):
        keyword = "Unselect From List By Label"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_label(locator, *labels)
        self.embed_screenshot_after(keyword, locator)
        return value

    @SeleniumLibrary.base.keyword()
    def unselect_from_list_by_value(self, locator, *values):
        keyword = "Unselect From List By Value"
        self.embed_screenshot(keyword, locator)
        value = SeleniumLibrary.SelectElementKeywords(self.ctx).unselect_from_list_by_value(locator, *values)
        self.embed_screenshot_after(keyword, locator)
        return value


# Documenting overrides

RobopomSeleniumPlugin.alert_should_be_present.__doc__ = \
    SeleniumLibrary.AlertKeywords.alert_should_be_present.__doc__
RobopomSeleniumPlugin.alert_should_not_be_present.__doc__ = \
    SeleniumLibrary.AlertKeywords.alert_should_not_be_present.__doc__
RobopomSeleniumPlugin.choose_file.__doc__ = \
    SeleniumLibrary.FormElementKeywords.choose_file.__doc__
RobopomSeleniumPlugin.clear_element_text.__doc__ = \
    SeleniumLibrary.ElementKeywords.clear_element_text.__doc__
RobopomSeleniumPlugin.click_button.__doc__ = \
    SeleniumLibrary.ElementKeywords.click_button.__doc__
RobopomSeleniumPlugin.click_element.__doc__ = \
    SeleniumLibrary.ElementKeywords.click_element.__doc__
RobopomSeleniumPlugin.click_element_at_coordinates.__doc__ = \
    SeleniumLibrary.ElementKeywords.click_element_at_coordinates.__doc__
RobopomSeleniumPlugin.click_image.__doc__ = \
    SeleniumLibrary.ElementKeywords.click_image.__doc__
RobopomSeleniumPlugin.click_link.__doc__ = \
    SeleniumLibrary.ElementKeywords.click_link.__doc__
RobopomSeleniumPlugin.cover_element.__doc__ = \
    SeleniumLibrary.ElementKeywords.cover_element.__doc__
RobopomSeleniumPlugin.double_click_element.__doc__ = \
    SeleniumLibrary.ElementKeywords.double_click_element.__doc__
RobopomSeleniumPlugin.drag_and_drop.__doc__ = \
    SeleniumLibrary.ElementKeywords.drag_and_drop.__doc__
RobopomSeleniumPlugin.drag_and_drop_by_offset.__doc__ = \
    SeleniumLibrary.ElementKeywords.drag_and_drop_by_offset.__doc__
RobopomSeleniumPlugin.execute_async_javascript.__doc__ = \
    SeleniumLibrary.JavaScriptKeywords.execute_async_javascript.__doc__
RobopomSeleniumPlugin.execute_javascript.__doc__ = \
    SeleniumLibrary.JavaScriptKeywords.execute_javascript.__doc__
RobopomSeleniumPlugin.handle_alert.__doc__ = \
    SeleniumLibrary.AlertKeywords.handle_alert.__doc__
RobopomSeleniumPlugin.input_password.__doc__ = \
    SeleniumLibrary.FormElementKeywords.input_password.__doc__
RobopomSeleniumPlugin.input_text.__doc__ = \
    SeleniumLibrary.FormElementKeywords.input_text.__doc__
RobopomSeleniumPlugin.input_text_into_alert.__doc__ = \
    SeleniumLibrary.AlertKeywords.input_text_into_alert.__doc__
RobopomSeleniumPlugin.mouse_down.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_down.__doc__
RobopomSeleniumPlugin.mouse_down_on_image.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_down_on_image.__doc__
RobopomSeleniumPlugin.mouse_down_on_link.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_down_on_link.__doc__
RobopomSeleniumPlugin.mouse_out.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_out.__doc__
RobopomSeleniumPlugin.mouse_over.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_over.__doc__
RobopomSeleniumPlugin.mouse_up.__doc__ = \
    SeleniumLibrary.ElementKeywords.mouse_up.__doc__
RobopomSeleniumPlugin.open_context_menu.__doc__ = \
    SeleniumLibrary.ElementKeywords.open_context_menu.__doc__
RobopomSeleniumPlugin.press_keys.__doc__ = \
    SeleniumLibrary.ElementKeywords.press_keys.__doc__
RobopomSeleniumPlugin.reload_page.__doc__ = \
    SeleniumLibrary.BrowserManagementKeywords.reload_page.__doc__
RobopomSeleniumPlugin.scroll_element_into_view.__doc__ = \
    SeleniumLibrary.ElementKeywords.scroll_element_into_view.__doc__
RobopomSeleniumPlugin.select_all_from_list.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.select_all_from_list.__doc__
RobopomSeleniumPlugin.select_checkbox.__doc__ = \
    SeleniumLibrary.FormElementKeywords.select_checkbox.__doc__
RobopomSeleniumPlugin.select_from_list_by_index.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.select_from_list_by_index.__doc__
RobopomSeleniumPlugin.select_from_list_by_label.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.select_from_list_by_label.__doc__
RobopomSeleniumPlugin.select_from_list_by_value.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.select_from_list_by_value.__doc__
RobopomSeleniumPlugin.select_radio_button.__doc__ = \
    SeleniumLibrary.ElementKeywords.press_keys.__doc__
RobopomSeleniumPlugin.simulate_event.__doc__ = \
    SeleniumLibrary.ElementKeywords.simulate_event.__doc__
RobopomSeleniumPlugin.submit_form.__doc__ = \
    SeleniumLibrary.FormElementKeywords.submit_form.__doc__
RobopomSeleniumPlugin.switch_browser.__doc__ = \
    SeleniumLibrary.BrowserManagementKeywords.switch_browser.__doc__
RobopomSeleniumPlugin.switch_window.__doc__ = \
    SeleniumLibrary.WindowKeywords.switch_window.__doc__
RobopomSeleniumPlugin.unselect_all_from_list.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.unselect_all_from_list.__doc__
RobopomSeleniumPlugin.unselect_checkbox.__doc__ = \
    SeleniumLibrary.FormElementKeywords.unselect_checkbox.__doc__
RobopomSeleniumPlugin.unselect_from_list_by_index.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_index.__doc__
RobopomSeleniumPlugin.unselect_from_list_by_label.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_label.__doc__
RobopomSeleniumPlugin.unselect_from_list_by_value.__doc__ = \
    SeleniumLibrary.SelectElementKeywords.unselect_from_list_by_value.__doc__
