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
        :param parent: Parent node of the new Component. Default value: 'None'.
        :param children: Children of the new Component. Default value: 'None'.
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
            return self.built_in.get_library_instance(constants.DEFAULT_SELENIUM_LIBRARY_NAME)
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
        :param children: Children of the new RootComponent. Default value: 'None'.
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
        :param parent: Parent node of the new PageComponent. Default value: 'None'.
        :param children: Children of the new PageComponent. Default value: 'None'.
        :param kwargs: Additional attributes of the new PageComponent.
        """
        super().__init__(name=name, parent=parent, children=children, **kwargs)

    def wait_until_loaded(self, timeout=None) -> None:
        """
        Stops execution until all page components marked as ``always_visible`` (this and all of it's descendants)
        are visible.

        If ``timeout`` is reached and not all page components marked as ``always_visible`` are visible, an exception
        is raised.

        :param timeout: If timeout is reached and not all page components marked as always_visible are visible,
                        an exception is raised. If timeout is None, the SeleniumLibrary default timeout is used.
        :return: None.
        """
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
        """
        Returns the ``real html`` parent of this PageComponent.

        If ``html_parent`` attribute is not None, then ``html_parent`` is returned.
        If ``html_parent`` is ``None`` and ``parent`` is a ``PageElement``, ``parent`` attribute is returned.
        Otherwise ``None`` is returned.

        :return: The 'real html parent' os this PageComponent.
        """
        html_parent = getattr(self, "html_parent", None)
        if html_parent is not None:
            return html_parent
        if isinstance(self.parent, PageElement):
            return self.parent
        return None

    @property
    def page(self) -> PageObject:
        """
        The ``PageObject`` this ``PageComponent`` belongs to.

        It returns the ``PageObject`` that is an ancestor of this ``PageComponent``
        (or ``self``, if it is a ``PageObject`` itself).

        :return: The ``PageObject`` this ``PageComponent`` belongs to.
        """
        if isinstance(self, PageObject):
            return self
        else:
            return self.parent.page


class PageObject(PageComponent):
    """
    Object that represents an individual html page.

    It can have any number of children (``PageElement`` and the like objects) that are included in the page.
    These children can have, in turn, more children. All these objects form the POM (Page Object Model) tree
    for this page.

    All pages (``PageObject`` instances) have the same parent, called the ``root component``.
    This root component is "artificially" included to have an unique POM tree.
    """
    def __init__(self,
                 name: str,
                 parent: RootComponent = None,
                 children: typing.Iterable[AnyPageElement] = None, ) -> None:
        """
        Creates a new ``PageObject``.

        In ``PageObject`` instances, ``parent`` is usually the ``root component``, or ``None``
        (if for some reason the ``PageObject`` is not yet attached to the POM tree)

        :param name: Name of the new PageObject.
        :param parent: Parent node of the new PageObject. Usually the 'root component', or None.
        :param children: Children of the new PageObject. Default value: 'None'.
        """
        super().__init__(name=name, parent=parent, children=children)


class PageElement(PageComponent):
    """
    Class that represents a single html object (``WebElement`` in ``SeleniumLibrary`` language).

    The most basic kind of descendant that a PageObject can have.
    A ``PageElement`` can have, in turn, more children.
    """

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
        """
        Creates a new ``PageElement``.

        :param locator: SeleniumLibrary locator used to identify the element in the page.
        :param name: Name of the new PageElement. If None, a unique name (based on object id) is used.
        :param parent: Parent node of the new PageElement. Default value: 'None'.
        :param short: A 'shortcut' name used to identify an element in the page. Default value: 'None'.
        :param always_visible: Establishes if the new PageElement should always be visible in the page.
                               Default value: 'False'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            Default value: 'None.'
        :param order: If 'locator' returns more than one element, this determine which to use (zero-based).
                      Default value: 'None.'
        :param children: Children of the new PageElement. Default value: 'None.'
        :param default_role: Establishes the default role of the new PageElement that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
        :param prefer_visible: If 'prefer_visible' is 'True' and 'locator' returns more than one element,
                               the first 'visible' element is used. If 'False', the first element is used
                               (visible or not). Default value: 'True'.
        """
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
        """
        Returns a ``PageElementStatus`` instance with the status info of the ``PageElement``
        (``present``, ``visible``, ``enabled``, ``selected``).

        :return: The PageElementStatus info of the PageElement.
        """
        element = self.find_element(required=False)
        if element is None:
            return PageElementStatus(present=False)
        else:
            return PageElementStatus(present=True,
                                     visible=element.is_displayed(),
                                     enabled=element.is_enabled(),
                                     selected=element.is_selected(), )

    def is_present(self) -> bool:
        """
        Returns if this ``PageElement`` is present in current page.

        :return: True if this PageElement is present in page, False otherwise.
        """
        return self.status.present

    def is_visible(self) -> bool:
        """
        Returns if this ``PageElement`` is visible in current page.

        :return: True if this PageElement is visible in page, False otherwise.
        """
        return self.status.visible

    def is_enabled(self) -> bool:
        """
        Returns if this ``PageElement`` is enabled in current page.

        :return: True if this PageElement is enabled in page, False otherwise.
        """
        return self.status.enabled

    def is_selected(self) -> bool:
        """
        Returns if this ``PageElement`` is selected in current page.

        :return: True if this PageElement is selected in page, False otherwise.
        """
        return self.status.selected

    @property
    def page_path(self) -> str:
        """
        The ``path`` of this ``PageElement`` in the page.

        Format is: ``page_name__page_ancestor1_name__page_ancestor2_name__self_name``

        :return: The path of this PageElement in the page.
        """
        if isinstance(self.parent, PageObject):
            return self.name
        else:
            return f"{self.parent.page_path}{self.separator}{self.name}"
    
    @property
    def path_locator(self) -> str:
        """
        The ``absolute_path`` of the ``PageElement`` preceded by ``path:``.

        It is used to find the element in the page using a custom ``Location Strategy`` of ``SeleniumLibrary``.
        See the ``Add Location Strategy`` keyword.

        :return: The absolute_path of the PageElement preceded by 'path:'.
        """
        return f"{constants.PATH_PREFIX}:{self.absolute_path}"

    @property
    def tag_name(self) -> typing.Optional[str]:
        """
        The ``tag name`` of the found ``WebElement``. ``None`` if no element is found.

        :return: The tag name of the found WebElement. None if no element is found.
        """
        element = self.find_element(False)
        if element is None:
            return None
        else:
            return element.tag_name

    def get_attribute(self, name: str) -> typing.Optional[str]:
        """
        The value of the attribute ``name`` of the found ``WebElement``. ``None`` if no element is found.

        :param name: The name of the attribute.
        :return: The value of the attribute. None if no element is found.
        """
        element = self.find_element(False)
        if element is None:
            return None
        else:
            return element.get_attribute(name)

    def wait_until_visible(self, timeout=None) -> None:
        """
        Stops execution until this ``PageElement`` is visible in current page.

        If ``timeout`` is reached and this element is not visible, an exception is raised.

        :param timeout: If timeout is reached and this element is not visible, an exception is raised.
        If timeout is None, the SeleniumLibrary default timeout is used.
        :return: None.
        """
        assert self.robopom_plugin is not None, \
            f"wait_until_visible: self.robopom_plugin should not be None"
        SeleniumLibrary.WaitingKeywords(self.selenium_library).wait_until_element_is_visible(
            f"{constants.PATH_PREFIX}:{self.absolute_path}",
            timeout=timeout,
            # error=f"Element {self} not visible after {timeout}",
        )


class PageElementStatus:
    """
    Class that represents the ``status`` of a ``PageElement`` (``present``, ``visible``, ``enabled``, ``selected``).
    """
    def __init__(self,
                 present: typing.Optional[bool] = None,
                 visible: typing.Optional[bool] = None,
                 enabled: typing.Optional[bool] = None,
                 selected: typing.Optional[bool] = None, ) -> None:
        """
        Creates a new ``PageElementStatus``.

        If some of the parameters are not provided, it applies some restrictions
        (an element that is not present can not be visible, for example).

        :param present: If element is present in the page. Default value: 'None'.
        :param visible: If element is visible in the page. Default value: 'None'.
        :param enabled: If element is enabled in the page. Default value: 'None'.
        :param selected: If element is selected in the page. Default value: 'None'.
        """
        self.present = present
        self.visible = visible
        self.enabled = enabled
        self.selected = selected
        # Apply restrictions
        if self.present is None:
            if self.visible or self.enabled or self.selected:
                self.present = True
        if self.present is False:
            if self.visible is None:
                self.visible = False
            if self.enabled is None:
                self.enabled = False
            if self.selected is None:
                self.selected = False


class PageElements(PageComponent):
    """
    Class that represents a ``multiple`` html object. It is a ``locator`` that can return more than one ``WebElement``.

    This kind of ``PageComponent`` should not have any children.
    """
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
        """
        Creates a new ``PageElements`` object.

        :param locator: SeleniumLibrary locator used to identify the 'PageElements' in the page.
        :param name: Name of the new 'PageElements'. If None, a unique name (based on object id) is used.
        :param parent: Parent node of the new 'PageElements'.
                       This will be the 'parent' of the PageElement objects found using this PageElements object.
                       Default value: 'None'.
        :param short: A 'shortcut' name used to identify an element in the page. Default value: 'None'.
        :param always_visible: Establishes if al least one WebElement defined by this object
                               should always be visible in the page. Default value: 'False'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            Default value: 'None'.
        :param default_role: Establishes the default role of the WebElements defined by this object
                             that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
        """

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
        """
        Returns the list of ``WebElements`` (in ``SeleniumLibrary`` language) found using the ``locator`` attribute.

        :return: List of WebElements found (can be an empty list).
        """
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
        """
        List of ``PageElement`` objects found using this ``PageElements`` object.

        The names of the generated ``PageElement`` objects have the following format: ``[page_elements_name]_[order]``
        where ``page_elements_name`` is the name of this object, and ``order`` is the index (zero based) in the list.
        The same format applies to ``short`` (if it is not ``None``).

        :return: List of PageElement objects found. Can be an empty list.
        """
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
        """
        Stops execution until at least one ``WebElement`` found using this object is visible in current page.

        If ``timeout`` is reached and no element is visible, an exception is raised.

        :param timeout: If timeout is reached and no element is visible, an exception is raised.
        If timeout is None, the SeleniumLibrary default timeout is used.
        :return: None.
        """
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
    """
    Class that represents a single html object (``WebElement`` in ``SeleniumLibrary`` language) ``generator``.

    It is like a ``PageElement``, but its locator (or any of its ancestors locators) has at least one python
    ``replacement field`` (like ``{}``).

    It is used to generate ``PageElement`` objects that for some reason require one or more "parameters".
    """

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
        """
        Creates a new ``PageElementGenerator`` object.

        :param locator_generator: SeleniumLibrary locator used to identify the element in the page.
                                  It can contain python "replacement fields" (like "{}").
        :param name: Name of the new PageElementGenerator. If None, a unique name (based on object id) is used.
        :param parent: Parent node of the new PageElementGenerator. This will be the 'parent' of the PageElement objects
                       generated using this PageElementGenerator object. Default value: 'None'.
        :param short: A 'shortcut' name used to identify an element in the page. This will be the 'shortcut' of the
                      PageElement objects generated using this PageElementGenerator object. Default value: 'None'.
        :param always_visible: Establishes if the new PageElement should always be visible in the page.
                               This will be the 'always_visible' of the PageElement objects generated using this
                               PageElementGenerator object. Default value: 'False'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            This will be the 'html_parent' of the PageElement objects generated using this
                            PageElementGenerator object. Default value: 'None'.
        :param order: If 'locator' returns more than one element, this determine which to use (zero-based).
                      This will be the 'order' of the PageElement objects generated using this
                      PageElementGenerator object. Default value: 'None'.
        :param default_role: Establishes the default role of the PageElement that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
                             This will be the 'order' of the PageElement objects generated using this
                             PageElementGenerator object.
        :param prefer_visible: If 'prefer_visible' is 'True' and 'locator' returns more than one element,
                               the first 'visible' element is used. If 'False', the first element is used
                               (visible or not).
                               This will be the 'prefer_visible' of the PageElement objects generated using this
                               PageElementGenerator object. Default value: 'True'.
        """
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
        """
        Returns a new ``PageElementGenerator`` that is a ``self``'s child.

        When PageElementGeneratorInstance objects are generated from this new PageElementGenerator,
        substitutions are made in both ``locator_generator`` (self's one, and the new created object's one).

        :param name: Name of the new PageElementGenerator. If None, a unique name (based on object id) is used.
        :param locator_generator: SeleniumLibrary locator used to identify the element in the page.
                                  It can contain python "replacement fields" (like "{}").
        :param short: A 'shortcut' name used to identify an element in the page. This will be the 'shortcut' of the
                      PageElement objects generated using this PageElementGenerator object. Default value: 'None'.
        :param always_visible: Establishes if the new PageElement should always be visible in the page.
                               This will be the 'always_visible' of the PageElement objects generated using this
                               PageElementGenerator object. Default value: 'self.always_visible'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            This will be the 'html_parent' of the PageElement objects generated using this
                            PageElementGenerator object. Default value: 'self.html_parent'.
        :param order: If 'locator' returns more than one element, this determine which to use (zero-based).
                      This will be the 'order' of the PageElement objects generated using this
                      PageElementGenerator object. Default value: 'self.order'.
        :param default_role: Establishes the default role of the PageElement that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
                             This will be the 'order' of the PageElement objects generated using this
                             PageElementGenerator object. Default value: 'self.default_role'.
        :param prefer_visible: If 'prefer_visible' is 'True' and 'locator' returns more than one element,
                               the first 'visible' element is used. If 'False', the first element is used
                               (visible or not).
                               This will be the 'prefer_visible' of the PageElement objects generated using this
                               PageElementGenerator object. Default value: 'self.prefer_visible'.
        :return: A new 'PageElementGenerator' that is a self's child.
        """
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
        """
        Returns a ``PageElementGeneratorInstance`` (a ``PageElement`` generated from a ``PageElementGenerator``)
        using the ``format_args`` and ``format_kwargs`` provided.

        The ``locator`` of the new ``PageElementGeneratorInstance`` is calculated using:
        ``locator_generator.format(*format_args, **format_kwargs)``.
        If ``self.parent`` is a ``PageElementGenerator`` too, same ``format`` is applied to it.

        :param name: Name of the new PageElementGeneratorInstance. If None, a unique name (based on object id) is used.
        :param format_args: Positional argument list used to generate the new locator.
        :param format_kwargs: Named argument dictionary used to generate the new locator.
        :param short: A 'shortcut' name used to identify the new element in the page. Default value: 'None'.
        :param always_visible: Establishes if the new PageElement should always be visible in the page.
                               Default value: 'self.always_visible'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            Default value: 'self.html_parent'.
        :param order: If 'locator' returns more than one element, this determine which to use (zero-based).
                      Default value: 'self.order'.
        :param default_role: Establishes the default role of the PageElement that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
                             Default value: 'self.default_role'.
        :param prefer_visible: If 'prefer_visible' is 'True' and 'locator' returns more than one element,
                               the first 'visible' element is used. If 'False', the first element is used
                               (visible or not). Default value: 'self.prefer_visible'.
        :return: A new 'PageElementGeneratorInstance' using 'format_args' and 'format_kwargs'.
        """
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
    """
    Class that represents a single html object (same as ``PageElement``), but a ``PageElementGeneratorInstance``
    is a special kind of ``PageElement`` obtained from a ``PageElementGenerator``.
    """
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
        """
        Creates a new ``PageElementGeneratorInstance`` object.

        The ``locator`` of the new ``PageElementGeneratorInstance`` is calculated using:
        ``locator_generator.format(*format_args, **format_kwargs)``.
        If ``generator.parent`` is a ``PageElementGenerator`` too, same ``format`` is applied to it.

        The ``parent`` of the new ``PageElementGeneratorInstance`` is obtained from ``generator.parent``.

        :param generator: The 'PageElementGenerator' used to generate the new 'PageElement'.
        :param name: Name of the new PageElementGeneratorInstance. If None, a unique name (based on object id) is used.
        :param format_args: Positional argument list used to generate the new locator.
        :param format_kwargs: Named argument dictionary used to generate the new locator.
        :param short: A 'shortcut' name used to identify the new element in the page. Default value: 'None'.
        :param always_visible: Establishes if the new PageElement should always be visible in the page.
                               Default value: 'generator.always_visible'.
        :param html_parent: The 'html parent' of the new PageElement, if it is different from 'parent'
                            ('parent' is used as the 'real_html_parent' if 'html_parent' is None).
                            Default value: 'generator.html_parent'.
        :param order: If 'locator' returns more than one element, this determine which to use (zero-based).
                      Default value: 'generator.order'.
        :param default_role: Establishes the default role of the PageElement that is used in get/set operations.
                             If not provided, Robopom tries to guess it ('text' is used as default if can not guess).
                             Possible values: `text`, `select`, `checkbox`, `password`.
                             Default value: 'generator.default_role'.
        :param prefer_visible: If 'prefer_visible' is 'True' and 'locator' returns more than one element,
                               the first 'visible' element is used. If 'False', the first element is used
                               (visible or not). Default value: 'generator.prefer_visible'.
        """
        
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
    """
    Class that represents a ``Frame`` in a web page.
    """
    def wait_until_loaded(self, timeout=None) -> None:
        """
        Stops execution until all page components marked as ``always_visible`` (this and all of it's descendants)
        are visible.

        If ``timeout`` is reached and not all page components marked as ``always_visible`` are visible, an exception
        is raised.

        :param timeout: If timeout is reached and not all page components marked as always_visible are visible,
                        an exception is raised. If timeout is None, the SeleniumLibrary default timeout is used.
        :return: None.
        """
        prev_frame = self.robopom_plugin.get_current_frame()
        SeleniumLibrary.FrameKeywords(self.selenium_library).select_frame(self.path_locator)
        super().wait_until_loaded(timeout=timeout)
        self.robopom_plugin.driver.switch_to.frame(prev_frame)


class GenericComponent(Component):
    """
    Class that represents a ``Component`` (or any of its subclases).
    It is used to read data from a file and generate the correct ``Component`` subclass instance.

    The correct ``Component`` subclass is can be explicitly established with ``component_type``.
    Possible values: PageObject, PageElement, PageElements, PageElementGenerator, PageElementGeneratorInstance,
    PageElementFrame. If ``component_type`` is not provided, Robopom tries to guess it from properties provided.

    Other special properties are: ``import_file`` and ``import_path``. These are used to ``import`` a component
    from other file. The "import_file" is the path to the "other" file, and ``import_path`` is the path of the
    component that we want to import in this other file.
    Example: import_file="pages/other/test_component.yaml", import_path: "body"
    If ``import_file`` and ``import_path``, the values of the imported object are used as "defaults".
    """
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
        """
        Creates a new ``GenericComponent`` object.

        :param name: The name of the new GenericComponent. Default value: None.
        :param parent: The parent of the new GenericComponent. Default value: None.
        :param children: The children of the new GenericComponent. Default value: None.
        :param component_type: Explicit type of the new Component (generated from this GenericComponent).
                               Possible values: PageObject, PageElement, PageElements, PageElementGenerator,
                               PageElementGeneratorInstance, PageElementFrame.
                               If not provided, Robopom tries to guess it. Default value: None.
        :param locator: The locator of the new GenericComponent. Default value: None.
        :param locator_generator: The locator_generator of the new GenericComponent. Default value: None.
        :param short: The short of the new GenericComponent. Default value: None.
        :param always_visible: The always_visible of the new GenericComponent. Default value: None.
        :param html_parent: The html_parent of the new GenericComponent. Default value: None.
        :param order: The order of the new GenericComponent. Default value: None.
        :param default_role: The default_role of the new GenericComponent. Default value: None.
        :param prefer_visible: The prefer_visible of the new GenericComponent. Default value: None.
        :param generator: The generator of the new GenericComponent. Default value: None.
        :param format_args: The format_args of the new GenericComponent. Default value: None.
        :param format_kwargs: The format_kwargs of the new GenericComponent. Default value: None.
        :param import_file: The file path used to import the GenericComponent from. Default value: None.
        :param import_path: The path in import_file of the component that we want to import. Default value: None.
        """
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
        """
        Dictionary with all the properties of the ``GenericComponent``.

        :return: Dictionary with all the properties of the GenericComponent.
        """
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
        """
        Dictionary with all the properties of the ``GenericComponent`` that are not ``None``
        (or "almost None", like an empty list, or an empty dictionary).

        :return: Dictionary with all the properties of the GenericComponent that are not None
        (or almost None, like an empty list, or an empty dictionary).
        """
        return {
            key: value for key, value in self.kwargs.items() if value not in constants.ALMOST_NONE}

    @property
    def not_none_page_component_kwargs(self) -> dict:
        """
        Dictionary with all the properties of the ``GenericComponent`` that are ``PageComponent`` properties
        and are not ``None`` (or "almost None", like an empty list, or an empty dictionary).

        ``PageComponent`` properties are defined in ``page_components_props``.

        :return: Dictionary with all the properties of the GenericComponent that are PageComponent properties
                 and are not None (or almost None, like an empty list, or an empty dictionary).
        """
        return {
            key: value for key, value in self.not_none_kwargs.items() if key in self.page_components_props
        }

    def update_with_imported(self, imported: GenericComponent) -> None:
        """
        Updates the properties of this object with the properties of the ``imported`` object.

        If a property of this object is ``None``, then it is replaced with the same property of the ``imported`` object.

        :param imported: Object used to replace the properties of the object.
        :return: None.
        """
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
        """
        Returns a string with the type that ``robopom`` "thinks" this GenericComponent should be.

        Possible returned values are: "PageObject", "PageElementGenerator", "PageElementGeneratorInstance",
        "PageElement".

        It is used when no explicit ``component_type`` is provided.

        :return: String with the type that robopom thinks this GenericComponent should be.
        """
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
        """
        Returns a new ``PageComponent`` subclass instance generated from this ``GenericComponent`` properties.

        The class of this new instance will be ``component_type`` (guessed by ``robopom`` or not).

        :param parent: The parent of the new PageComponent. Default value: None.
        :return: New PageComponent subclass instance generated from this GenericComponent properties.
        """
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
