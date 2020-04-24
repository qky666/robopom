from __future__ import annotations
import anytree
import typing
import os
import robot.libraries.BuiltIn as robot_built_in
import robot.errors
import SeleniumLibrary
import robopom.RobopomSeleniumPlugin as robopom_selenium_plugin
import robopom.constants as constants
import robopom.component_loader as component_loader

T = typing.TypeVar('T', bound='Component')


class Component(anytree.Node):
    """
    Generic ``node`` used in the POM (Page Object Model) tree.

    Every object in the POM tree is a ``Component`` instance (or a ``Component`` subclass instance).
    It defines common basic behaviour for a POM tree nodes.
    """
    separator = constants.SEPARATOR

    def __init__(self,
                 name: str = None,
                 parent: Component = None,
                 children: typing.Iterable[PageComponent] = None,
                 **kwargs) -> None:
        """
        Creates a new ``Component``.

        :param name: Name of the new Component. If None, a unique name (based on object id) is used.
        :param parent: Parent node of the new Component.
        :param children: Children of the new Component.
        :param kwargs: Additional attributes of the new Component.
        """
        if name is None:
            name = str(id(self))
        super().__init__(name=name, parent=parent, children=children, **kwargs)
        self._robopom_plugin = None

    @property
    def auto_named(self) -> bool:
        """
        Returns ``True`` if the component was not given an explicit name, ``False`` otherwise.

        :return: ``True`` if the component was not given an explicit name, ``False`` otherwise.
        """
        try:
            if int(self.name) == id(self):
                return True
        except ValueError:
            pass
        return False

    @property
    def has_ancestor_auto_named(self) -> bool:
        """
        Returns ``True`` if the component has any auto-named ancestor, ``False`` otherwise.

        :return: ``True`` if the component has any auto-named ancestor, ``False`` otherwise.
        """
        if self.parent is None:
            return False
        parent: Component = self.parent
        if parent.auto_named or parent.has_ancestor_auto_named:
            return True
        return False

    @property
    def absolute_path(self) -> str:
        """
        Returns the ``absolute path`` of the component.

        The format is: ``__ancestor1_name__ancestor2_name__component_name``.
        In the POM tree, it will be something like this:
        ``__root__page_name__page_ancestor1_name__page_ancestor2_name__component_name``.

        :return: The absolute path of the component.
        """
        if self.is_root:
            path = f"{self.separator}{self.name}"
        else:
            path = f"{self.parent.absolute_path}{self.separator}{self.name}"
        path = self.robopom_plugin.remove_separator_prefix(path)
        path = self.robopom_plugin.remove_root_prefix(path)
        path = self.robopom_plugin.remove_separator_prefix(path)
        return path

    @property
    def built_in(self) -> robot_built_in.BuiltIn:
        """
        A Robot Framework ``Built In`` object.

        It is used to run ``Built In`` keywords from ``Python`` code.

        :return: A Robot Framework Built In object.
        """
        return robot_built_in.BuiltIn()

    @property
    def selenium_library(self) -> typing.Optional[SeleniumLibrary.SeleniumLibrary]:
        """
        The Robot Framework ``SeleniumLibrary`` instance if Robot is running, None if Robot is not runnning.

        :return: The Robot Framework ``SeleniumLibrary`` instance if Robot is running, None if Robot is not runnning.
        """
        try:
            return self.built_in.get_library_instance(constants.SELENIUM_LIBRARY_NAME)
        except robot_built_in.RobotNotRunningError:
            return None
        except robot.errors.RobotError:
            return None
        except RuntimeError:
            return None

    @property
    def robopom_plugin(self) -> typing.Optional[robopom_selenium_plugin.RobopomSeleniumPlugin]:
        """
        The Robot Framework ``RobopomSeleniumPlugin`` instance.

        If Robot is running, it is obtained from ``SeleniumLibrary``.
        Otherwise, a new instance is created and stored (and this instance used from that moment).

        :return: The Robot Framework ``RobopomSeleniumPlugin`` instance.
        """
        if self.selenium_library is None:
            if getattr(self, "_robopom_plugin", None) is None:
                self._robopom_plugin = robopom_selenium_plugin.RobopomSeleniumPlugin()
            return self._robopom_plugin
        return getattr(self.selenium_library, "robopom_plugin", None)

    def add_child(self, child: T) -> T:
        """
        Adds a child component.

        :param child: The child component to add.
        :return: The same received child.
        """
        child.parent = self
        return child

    def variables_dictionary(self, prev_dict: typing.Dict[str, str] = None) -> typing.Dict[str, str]:
        """
        Generates a dictionary from the component.

        Dictionary key-value format is one of:

        - Key: ``[PAGE_NAME]__[PAGE_COMPONENT__PATH]``. Value: ``path:[page_name]__[page_component__path]``.
          It can have ``separators`` (``__``) in ``page_component__path``.
          The ``page_component__path`` is formed with the names (``name`` property) of the components
          in the page component path joined with a ``separator`` (``__``).
          If any of the page component ancestors (or the page component itself) has no explicit ``name`` attribute,
          it does not generate a key-value pair.

        - ``[PAGE_NAME]__[PAGE_COMPONENT_SHORT]``.  Value: ``path:[page_name]__[page_component_short]``.
          It can not have ``separators`` (``__``) in ``page_component_short``.
          If the page component has no explicit ``short`` attribute, it does not generate a key-value pair.

        :param prev_dict: The previous dictionary. It is used internally to manage recursion.
                          The key-value pairs are added to the prev_dict if provided.
        :return: The obtained dictionary.
        """
        if prev_dict is None:
            prev_dict = {}

        sep = self.separator

        if not self.auto_named and not self.has_ancestor_auto_named:
            # "name" key-value calculation
            path = self.absolute_path
            key = path.upper()
            while key.startswith(sep):
                key = key[len(sep):]
            prev_dict[key] = f"{constants.PATH_PREFIX}:{path}"

        # "short" key-value calculation
        short: str = getattr(self, "short", None)
        if short is not None:
            page: PageObject = getattr(self, "page")
            key = f"{page.name}{sep}{short}"
            prev_dict[key.upper()] = f"{constants.PATH_PREFIX}:{key}"

        # children
        children = getattr(self, "children", [])
        for child in children:
            prev_dict = child.variables_dictionary(prev_dict)
        prev_dict.pop("", None)
        return prev_dict


class RootComponent(Component):
    """
    Component used as POM tree root node.

    """
    def __init__(self,
                 name: str = None,
                 children: typing.Iterable[PageObject] = None,
                 **kwargs) -> None:
        """
        Creates a new ``RootComponent``.

        :param name: Name of the new RootComponent. If None, "root" is used.
        :param children: Children of the new RootComponent.
        :param kwargs: Additional attributes of the new RootComponent.
        """
        if name is None:
            name = constants.ROOT_NAME
        super().__init__(name=name, parent=None, children=children, **kwargs)


class PageComponent(Component):
    """
    ``Generic Component`` used in a Page.

    It defines common behaviour for ``PageObject`` (an object that represents a page itself) and ``PageElement``
    and similar objects (objects that represents page elements inside an html page).
    """
    def __init__(self,
                 name: str = None,
                 parent: AnyParent = None,
                 children: typing.Iterable[AnyPageElement] = None,
                 **kwargs, ) -> None:
        """
        Creates a new ``PageComponent``.

        :param name: Name of the new PageComponent. If None, a unique name (based on object id) is used.
        :param parent: Parent node of the new PageComponent.
        :param children: Children of the new PageComponent.
        :param kwargs: Additional attributes of the new PageComponent.
        """
        super().__init__(name=name, parent=parent, children=children, **kwargs)

    def wait_until_loaded(self, timeout=None) -> None:
        self._wait_until_loaded(timeout, force=True)

    def _wait_until_loaded(self, timeout=None, force: bool = False) -> None:
        if isinstance(self, (PageElement, PageElements)):
            if self.always_visible or force:
                self.wait_until_visible(timeout)
        if not self.is_leaf:
            for e in self.children:
                e: PageComponent
                e._wait_until_loaded(timeout)

    @property
    def real_html_parent(self) -> typing.Union[None, PageElement, str]:
        html_parent = getattr(self, "html_parent", None)
        if html_parent is not None:
            return html_parent
        if isinstance(self.parent, PageElement):
            return self.parent
        return None

    @property
    def page(self) -> PageObject:
        if isinstance(self, PageObject):
            return self
        else:
            return self.parent.page


class PageObject(PageComponent):
    def __init__(self,
                 name: str,
                 parent: RootComponent = None,
                 children: typing.Iterable[AnyPageElement] = None, ) -> None:
        super().__init__(name=name, parent=parent, children=children)


class PageElement(PageComponent):

    def __init__(self,
                 locator: str,
                 name: str = None,
                 parent: AnyPageParent = None,
                 *,
                 short: str = None,
                 always_visible: bool = False,
                 html_parent: typing.Union[str, PageElement] = None,
                 order: int = None,
                 children: typing.Iterable[AnyPageElement] = None,
                 default_role: str = None,
                 prefer_visible: bool = True, ):
        super().__init__(name=name,
                         locator=locator,
                         parent=parent,
                         short=short,
                         always_visible=always_visible,
                         html_parent=html_parent,
                         order=order,
                         children=children,
                         prefer_visible=prefer_visible, )
        self.locator = locator
        self.short = short
        self.always_visible = always_visible
        self.html_parent = html_parent
        self.order = order
        self.default_role = default_role
        self.prefer_visible = prefer_visible

    def find_element(self, required: bool = True) -> typing.Optional[SeleniumLibrary.locators.elementfinder.WebElement]:
        assert self.robopom_plugin is not None, \
            f"find_element: self.robopom_plugin should not be None"
        # locator transformation: If strategy not explicitly set,
        # xpath is used if locator is "." or starts with "./" or "/", css otherwise
        strategies = getattr(self.robopom_plugin.element_finder, "_strategies", [])
        for strategy in strategies:
            if self.locator.startswith(strategy):
                locator = self.locator
                break
        else:
            if self.locator == "." or self.locator.startswith("/") or self.locator.startswith("./"):
                locator = f"xpath:{self.locator}"
            else:
                locator = f"css:{self.locator}"

        if locator.startswith("xpath:/"):
            # Do not mind html_parent
            parent_element = None
        elif isinstance(self.real_html_parent, str):
            parent_element = self.robopom_plugin.find_element(self.real_html_parent, required=required)
            if parent_element is None:
                return None
        elif isinstance(self.real_html_parent, PageElement):
            parent_element = self.real_html_parent.find_element(required=required)
            if parent_element is None:
                return None
        else:
            parent_element = None

        element = self.robopom_plugin.find_element(locator, required=required, parent=parent_element)
        if self.prefer_visible is False and self.order is None:
            return element
        elements = self.robopom_plugin.find_elements(locator, parent=parent_element)
        if self.order is not None:
            return elements[self.order]
        else:
            for e in elements:
                if e.is_displayed():
                    return e
            else:
                return element

    @property
    def status(self) -> PageElementStatus:
        element = self.find_element(required=False)
        if element is None:
            return PageElementStatus(present=False)
        else:
            return PageElementStatus(present=True,
                                     visible=element.is_displayed(),
                                     enabled=element.is_enabled(),
                                     selected=element.is_selected(), )

    def is_present(self) -> bool:
        return self.status.present

    def is_visible(self) -> bool:
        return self.status.visible

    def is_enabled(self) -> bool:
        return self.status.enabled

    def is_selected(self) -> bool:
        return self.status.selected

    @property
    def page_path(self) -> str:
        if isinstance(self.parent, PageObject):
            return self.name
        else:
            return f"{self.parent.page_path}{self.separator}{self.name}"
    
    @property
    def path_locator(self) -> str:
        return f"{constants.PATH_PREFIX}:{self.absolute_path}"

    @property
    def tag_name(self) -> typing.Optional[str]:
        element = self.find_element(False)
        if element is None:
            return None
        else:
            return element.tag_name

    def get_attribute(self, name: str) -> typing.Optional[str]:
        element = self.find_element(False)
        if element is None:
            return None
        else:
            return element.get_attribute(name)

    def wait_until_visible(self, timeout=None) -> None:
        assert self.robopom_plugin is not None, \
            f"wait_until_visible: self.robopom_plugin should not be None"
        SeleniumLibrary.WaitingKeywords(self.selenium_library).wait_until_element_is_visible(
            f"{constants.PATH_PREFIX}:{self.absolute_path}",
            timeout=timeout,
            # error=f"Element {self} not visible after {timeout}",
        )


class PageElementStatus:
    def __init__(self,
                 present: typing.Optional[bool] = None,
                 visible: typing.Optional[bool] = None,
                 enabled: typing.Optional[bool] = None,
                 selected: typing.Optional[bool] = None, ) -> None:
        self.present = present
        self.visible = visible
        self.enabled = enabled
        self.selected = selected
        # Apply restrictions
        if self.visible or self.enabled or self.selected:
            self.present = True
        if self.present is False:
            self.visible = False
            self.enabled = False
            self.selected = False


class PageElements(PageComponent):

    def __init__(
            self,
            locator: str,
            name: str = None,
            parent: AnyPageParent = None,
            *,
            short: str = None,
            always_visible: bool = False,
            html_parent: typing.Union[str, PageElement] = None,
            default_role: str = None,
    ) -> None:

        super().__init__(name=name,
                         locator=locator,
                         parent=parent,
                         short=short,
                         always_visible=always_visible,
                         html_parent=html_parent, )
        self.locator = locator
        self.short = short
        self.always_visible = always_visible
        self.html_parent = html_parent
        self.default_role = default_role
        self._previous_page_elements: typing.List[PageElement] = []

    def find_elements(self) -> typing.List[SeleniumLibrary.locators.elementfinder.WebElement]:
        assert self.robopom_plugin is not None, \
            f"find_element: self.robopom_plugin should not be None"
        # locator transformation: If strategy not explicitly set,
        # xpath is used if locator is "." or starts with "./" or "/", css otherwise
        strategies = getattr(self.robopom_plugin.element_finder, "_strategies", [])
        for strategy in strategies:
            if self.locator.startswith(strategy):
                locator = self.locator
                break
        else:
            if self.locator == "." or self.locator.startswith("/") or self.locator.startswith("./"):
                locator = f"xpath:{self.locator}"
            else:
                locator = f"css:{self.locator}"

        if locator.startswith("xpath:/"):
            # Do not mind html_parent
            parent_element = None
        elif isinstance(self.real_html_parent, str):
            parent_element = self.robopom_plugin.find_element(self.real_html_parent, required=False)
            if parent_element is None:
                return []
        elif isinstance(self.real_html_parent, PageElement):
            parent_element = self.real_html_parent.find_element(required=False)
            if parent_element is None:
                return []
        else:
            parent_element = None

        elements = self.robopom_plugin.find_elements(locator, parent=parent_element)
        return elements

    @property
    def page_elements(self) -> typing.List[PageElement]:
        # Remove from pom previous page elements:
        for e in self._previous_page_elements:
            e.parent = None

        num = len(self.find_elements())
        page_elements = []
        for i in range(num):
            page_elements.append(PageElement(
                locator=self.locator,
                name=f"{self.name}_{i}",
                parent=self.parent,
                short=f"self.short_{i}" if self.short is not None else None,
                html_parent=self.html_parent,
                order=i,
                default_role=self.default_role,
                prefer_visible=False,
            ))

        # Store page elements
        self._previous_page_elements = page_elements

        return page_elements

    def wait_until_visible(self, timeout=None) -> None:
        assert self.robopom_plugin is not None, \
            f"PageElements.wait_until_visible: self.robopom_plugin should not be None"
        pe = PageElement(
                locator=self.locator,
                parent=self.parent,
                html_parent=self.html_parent,
                default_role=self.default_role,
            )
        pe.wait_until_visible(timeout)
        # remove pe from pom tree
        pe.parent = None


class PageElementGenerator(PageComponent):

    def __init__(self,
                 locator_generator: str,
                 name: str = None,
                 parent: typing.Union[AnyPageParent, PageElementGenerator] = None,
                 *,
                 short: str = None,
                 always_visible: bool = False,
                 html_parent: typing.Union[str, PageElement] = None,
                 order: int = None,
                 default_role: str = None,
                 prefer_visible: bool = True, ):
        super().__init__(name=name,
                         locator_generator=locator_generator,
                         parent=parent,
                         short=short,
                         always_visible=always_visible,
                         html_parent=html_parent,
                         order=order,
                         prefer_visible=prefer_visible, )
        self.locator_generator = locator_generator
        self.short = short
        self.always_visible = always_visible
        self.html_parent = html_parent
        self.order = order
        self.default_role = default_role
        self.prefer_visible = prefer_visible
        
    def child_generator(self,
                        name: str = None,
                        locator_generator: str = None,
                        *,
                        short: str = None,
                        always_visible: bool = None,
                        html_parent: typing.Union[None, str, PageElement] = None,
                        order: typing.Optional[int] = None,
                        default_role: str = None,
                        prefer_visible: bool = None, ) -> PageElementGenerator:
        # name and short are not inherited
        if always_visible is None:
            always_visible = self.always_visible
        if html_parent is None:
            html_parent = self.html_parent
        if order is None:
            order = self.order
        if default_role is None:
            default_role = self.default_role
        if prefer_visible is None:
            prefer_visible = self.prefer_visible
        return PageElementGenerator(
            locator_generator=locator_generator,
            name=name,
            parent=self,
            short=short,
            always_visible=always_visible,
            html_parent=html_parent,
            order=order,
            default_role=default_role,
            prefer_visible=prefer_visible,
        )

    def page_element_with(self,
                          name: str = None,
                          format_args: typing.List[str] = None,
                          format_kwargs: typing.Dict[str, str] = None,
                          *,
                          short: str = None,
                          always_visible: bool = None,
                          html_parent: typing.Union[None, str, PageElement] = None,
                          order: typing.Optional[int] = None,
                          default_role: str = None,
                          prefer_visible: bool = None, ) -> PageElementGeneratorInstance:

        return PageElementGeneratorInstance(
            generator=self,
            name=name,
            format_args=format_args,
            format_kwargs=format_kwargs,
            short=short,
            always_visible=always_visible,
            html_parent=html_parent,
            order=order,
            default_role=default_role,
            prefer_visible=prefer_visible,
        )


class PageElementGeneratorInstance(PageElement):
    def __init__(self,
                 generator: PageElementGenerator,
                 name: str = None,
                 format_args: typing.List[str] = None,
                 format_kwargs: typing.Dict[str, str] = None,
                 *,
                 short: str = None,
                 always_visible: bool = None,
                 html_parent: typing.Union[str, PageElement] = None,
                 order: int = None,
                 default_role: str = None,
                 prefer_visible: bool = None, ):
        
        if format_args is None:
            format_args = []
        if format_kwargs is None:
            format_kwargs = {}

        # name and short are not inherited.

        locator = generator.locator_generator.format(*format_args, **format_kwargs)
        if isinstance(generator.parent, PageElementGenerator):
            parent = generator.parent.page_element_with(format_args=format_args, format_kwargs=format_kwargs)
        else:
            parent = generator.parent
        if always_visible is None:
            always_visible = generator.always_visible
        if html_parent is None:
            html_parent = generator.html_parent
        if order is None:
            order = generator.order
        if default_role is None:
            default_role = generator.default_role
        if prefer_visible is None:
            prefer_visible = generator.prefer_visible
        super().__init__(
            locator=locator,
            name=name,
            parent=parent,
            short=short,
            always_visible=always_visible,
            html_parent=html_parent,
            order=order,
            default_role=default_role,
            prefer_visible=prefer_visible,
        )
        self.locator = locator
        self.short = short
        self.always_visible = always_visible
        self.html_parent = html_parent
        self.order = order
        self.default_role = default_role
        self.prefer_visible = prefer_visible

        self.generator = generator
        self.format_args = format_args
        self.format_kwargs = format_kwargs


class PageElementFrame(PageElement):
    def wait_until_loaded(self, timeout=None) -> None:
        prev_frame = self.robopom_plugin.get_current_frame()
        SeleniumLibrary.FrameKeywords(self.selenium_library).select_frame(self.path_locator)
        super().wait_until_loaded(timeout=timeout)
        self.robopom_plugin.driver.switch_to.frame(prev_frame)


class GenericComponent(Component):
    # property_component_type_map: typing.Dict[str, typing.List[str]] = dict(
    #     locator=["PageElement", "PageElements"],
    #     locator_generator=["PageElementGenerator"],
    #     always_visible=["PageElement", "PageElements", "PageElementGeneratorInstance"],
    #     html_parent=["PageElement", "PageElements", "PageElementGenerator", "PageElementGeneratorInstance"],
    #     order=["PageElement", "PageElementGenerator", "PageElementGeneratorInstance"],
    #     default_role=["PageElement", "PageElements", "PageElementGenerator", "PageElementGeneratorInstance"],
    #     prefer_visible=["PageElement", "PageElements", "PageElementGenerator", "PageElementGeneratorInstance"],
    #     base_generator=["PageElementGeneratorInstance"],
    #     base_generator_format_args=["PageElementGeneratorInstance"],
    #     base_generator_format_kwargs=["PageElementGeneratorInstance"],
    #     import_file=["PageElement", "PageElements", "PageElementGenerator", "PageElementGeneratorInstance"],
    #     import_path=["PageElement", "PageElements", "PageElementGenerator", "PageElementGeneratorInstance"],
    # )
    page_components_props = [
        "locator",
        "locator_generator",
        "short",
        "always_visible",
        "html_parent",
        "order",
        "default_role",
        "prefer_visible",
        "format_args",
        "format_kwargs"
    ]

    def __init__(self,
                 name: str = None,
                 parent: Component = None,
                 children: typing.Iterable[GenericComponent] = None,
                 *,
                 component_type: str = None,
                 locator: str = None,
                 locator_generator: str = None,
                 short: str = None,
                 always_visible: bool = None,
                 html_parent: str = None,
                 order: int = None,
                 default_role: str = None,
                 prefer_visible: bool = None,
                 generator: str = None,
                 format_args: typing.List[str] = None,
                 format_kwargs: typing.Dict[str, str] = None,
                 import_file: os.PathLike = None,
                 import_path: str = None) -> None:
        kwargs = dict(
            component_type=component_type,
            locator=locator,
            locator_generator=locator_generator,
            short=short,
            always_visible=always_visible,
            html_parent=html_parent,
            order=order,
            default_role=default_role,
            prefer_visible=prefer_visible,
            generator=generator,
            format_args=format_args,
            format_kwargs=format_kwargs,
            import_file=import_file,
            import_path=import_path,
        )

        if format_args is None:
            format_args = []
        if format_kwargs is None:
            format_kwargs = {}

        super().__init__(
            name=name,
            parent=parent,
            children=children,
            **kwargs,
        )
        self.component_type = component_type
        self.locator = locator
        self.locator_generator = locator_generator
        self.short = short
        self.always_visible = always_visible
        self.html_parent = html_parent
        self.order = order
        self.default_role = default_role
        self.prefer_visible = prefer_visible
        self.generator = generator
        self.format_args = format_args
        self.format_kwargs = format_kwargs
        self.import_file = import_file
        self.import_path = import_path

        self.not_none_initial_kwargs = {
            key: value for key, value in kwargs.items() if value not in constants.ALMOST_NONE
        }
        self.not_none_initial_page_component_kwargs = {
            key: value for key, value in self.not_none_initial_kwargs.items() if key in self.page_components_props
        }

        # Import validations
        if self.import_file is not None:
            assert self.import_path is not None, f"If import_file is not None, import_path should not be None: " \
                                                 f"import_file={self.import_file}, import_path={self.import_path}"
        if self.import_path is not None:
            assert self.import_file is not None, f"If import_path is not None, import_file should not be None: " \
                                                 f"import_path={self.import_path}, import_file={self.import_file}"
        # Import
        if self.import_file is not None:
            imported = component_loader.ComponentLoader.load_generic_component_from_file(
                self.import_file,
                self.import_path,
            )
            self.update_with_imported(imported)
        else:
            self.guess_component_type()

    @property
    def kwargs(self) -> dict:
        return dict(
            component_type=self.component_type,
            locator=self.locator,
            locator_generator=self.locator_generator,
            short=self.short,
            always_visible=self.always_visible,
            html_parent=self.html_parent,
            order=self.order,
            default_role=self.default_role,
            prefer_visible=self.prefer_visible,
            generator=self.generator,
            format_args=self.format_args,
            format_kwargs=self.format_kwargs,
            import_file=self.import_file,
            import_path=self.import_path,
        )

    @property
    def not_none_kwargs(self) -> dict:
        return {
            key: value for key, value in self.kwargs.items() if value not in constants.ALMOST_NONE}

    @property
    def not_none_page_component_kwargs(self) -> dict:
        return {
            key: value for key, value in self.not_none_kwargs.items() if key in self.page_components_props
        }

    def update_with_imported(self, imported: GenericComponent) -> None:
        imported.guess_component_type()

        self.name = imported.name if self.name is None else self.name
        if len(self.children) == 0 and len(imported.children) > 0:
            self.children = imported.children
        self.component_type = imported.component_type if self.component_type is None else self.component_type
        self.locator = imported.locator if self.locator is None else self.locator
        self.locator_generator = imported.locator_generator if self.locator_generator is None \
            else self.locator_generator
        self.short = imported.short if self.short is None else self.short
        self.always_visible = imported.always_visible if self.always_visible is None else self.always_visible
        self.html_parent = imported.html_parent if self.html_parent is None else self.html_parent
        self.order = imported.order if self.order is None else self.order
        self.default_role = imported.default_role if self.default_role is None else self.default_role
        self.prefer_visible = imported.prefer_visible if self.prefer_visible is None else self.prefer_visible
        self.generator = imported.generator if self.generator is None else self.generator
        self.format_args = imported.format_args if len(self.format_args) == 0 else self.format_args
        self.format_kwargs = imported.format_kwargs if len(self.format_kwargs) == 0 else self.format_kwargs

        # self.guess_component_type()

        # Children
        for imported_child in imported.children:
            for child in self.children:
                if imported_child.name == child.name:
                    child.update_with_imported(imported_child)
                    break
            else:
                imported_child.parent = self

    def guess_component_type(self):
        if self.component_type is None:
            # Try to guess component_type
            if self.locator is None and self.locator_generator is None and self.generator is None:
                self.component_type = "PageObject"
            elif self.locator_generator is not None:
                self.component_type = "PageElementGenerator"
            elif self.generator is not None:
                self.component_type = "PageElementGeneratorInstance"
            else:
                self.component_type = "PageElement"

    def get_component_type_instance(self, parent: PageComponent = None) -> PageComponent:
        # Create a new instance, with children
        name = None if self.auto_named else self.name
        if self.component_type.casefold() == "PageObject".casefold():
            new_instance = PageObject(
                name=name,
                parent=parent,
            )
            assert len(self.not_none_initial_page_component_kwargs) == 0, \
                f"PageObject should not define: {self.not_none_kwargs}"
        elif self.component_type.casefold() == "PageElement".casefold():
            new_instance = PageElement(
                name=name,
                parent=parent,
                **self.not_none_page_component_kwargs,
            )
        elif self.component_type.casefold() == "PageElements".casefold():
            new_instance = PageElements(
                name=name,
                parent=parent,
                **self.not_none_page_component_kwargs,
            )
        elif self.component_type.casefold() == "PageElementGenerator".casefold():
            new_instance = PageElementGenerator(
                name=name,
                parent=parent,
                **self.not_none_page_component_kwargs,
            )
        elif self.component_type.casefold() == "PageElementGeneratorInstance".casefold():
            # Find generator
            generator = [possible for possible in parent.children if possible.name == self.generator][0]
            assert isinstance(generator, PageElementGenerator), \
                f"generator should be a PageElementGenerator, but it is a {type(generator)}"
            new_instance = PageElementGeneratorInstance(
                generator=generator,
                name=name,
                **self.not_none_page_component_kwargs,
            )
        elif self.component_type.casefold() == "PageElementFrame".casefold():
            new_instance = PageElementFrame(
                name=name,
                parent=parent,
                **self.not_none_page_component_kwargs,
            )
        else:
            assert False, f"Component type not defined: {self.component_type}"

        for child in self.children:
            child: GenericComponent
            child.get_component_type_instance(parent=new_instance)
        return new_instance


# Type aliases
AnyPageElement = typing.Union[PageElement, PageElements, PageElementGenerator]
AnyConcretePageElement = typing.Union[PageElement, PageElements]
AnyParent = typing.Union[RootComponent, PageObject, PageElement]
AnyPageParent = typing.Union[PageObject, PageElement]
