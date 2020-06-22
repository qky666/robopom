from __future__ import annotations
import anytree
import typing
import SeleniumLibrary
from . import Plugin, Page


class Node(anytree.AnyNode):
    # separator = "__"

    @staticmethod
    def get_selenium_locator(
            locator: str,
            selenium_instance: typing.Optional[SeleniumLibrary.SeleniumLibrary, Plugin.Plugin],
    ) -> str:
        strategies = getattr(selenium_instance.element_finder, "_strategies", [])
        for strategy in strategies:
            if locator.startswith(strategy):
                return locator
        else:
            if locator == "." or locator.startswith("/") or locator.startswith("./"):
                return f"xpath:{locator}"
            else:
                return f"css:{locator}"

    def __init__(self: Node,
                 parent: Node = None,
                 children: typing.Iterable[Node] = None,
                 *,
                 name: str = None,
                 locator: str = None,
                 is_multiple: bool = None,
                 order: int = None,
                 wait_present: bool = None,
                 wait_visible: bool = None,
                 wait_enabled: bool = None,
                 wait_selected: bool = None,
                 html_parent: typing.Union[str, Node] = None,
                 smart_pick: bool = None,
                 # template:
                 is_template: bool = None,
                 template: typing.Union[str, Node] = None,
                 template_args: list = None,
                 template_kwargs: dict = None,
                 # pom_root_for_plugin:
                 pom_root_for_plugin: typing.Union[Plugin.Plugin, str] = None,
                 **kwargs) -> None:
        # Initial calculations and validations
        if children is None:
            children = []

        if self.template_args is None:
            self.template_args = []

        if template_kwargs is None:
            self.template_kwargs = {}

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
        self.pom_root_for_plugin: typing.Optional[Plugin.Plugin] = pom_root_for_plugin
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
            order=self.order,
            is_multiple=self.is_multiple,
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

    def get_plugin(self) -> typing.Optional[Plugin.Plugin]:
        if self.pom_root_for_plugin is not None:
            return self.pom_root_for_plugin
        if self.root.pom_root_for_plugin is not None:
            return self.root.pom_root_for_plugin

        # Try to guess.
        built_in = Plugin.Plugin.built_in
        all_libs: dict = built_in.get_library_instance(all=True)
        selenium_libs: dict = {lib_name: lib_instance for lib_name, lib_instance in all_libs.items()
                               if isinstance(lib_instance, SeleniumLibrary.SeleniumLibrary)
                               and getattr(lib_instance, "robopom_plugin", None) is not None
                               and isinstance(getattr(lib_instance, "robopom_plugin"), Plugin.Plugin)}
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

    @property
    def pom_locator(self) -> str:
        return f"{self.get_plugin().POM_PREFIX}:{self.full_name}"

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

    def get_page_library(self) -> Page.Page:
        return Plugin.Plugin.built_in.get_library_instance(self.page_node.name)

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

        if not self._resolved:

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
                assert len(self.name.split()) == 1, f"'name' can not contain spaces; name: '{self.name}'. Node: {self}"

                if "{order}" in self.name:
                    if self.is_multiple is None:
                        self.is_multiple = True
                    assert self.is_multiple, \
                        f"If 'name' contains '{{order}}', 'is_multiple' can not be False; " \
                        f"name: {self.name}. Node: {self}"

                if self.name.endswith("_template"):
                    if self.is_template is None:
                        self.is_template = True
                    assert self.is_template, \
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

            # Templates do not resolve to a concrete pom node
            if self.is_template is False:

                if self.is_template is None:
                    self.is_template = False

                if self.wait_selected is None:
                    self.wait_selected = False
                elif self.wait_selected:
                    if self.wait_present is None:
                        self.wait_present = True
                    assert self.wait_present, \
                        f"'wait_selected' is {self.wait_selected}, but 'wait_present' is {self.wait_present}"

                if self.wait_enabled is None:
                    self.wait_enabled = False
                elif self.wait_enabled:
                    if self.wait_present is None:
                        self.wait_present = True
                    assert self.wait_present, \
                        f"'wait_enabled' is {self.wait_enabled}, but 'wait_present' is {self.wait_present}"

                if self.wait_visible is None:
                    self.wait_visible = False
                elif self.wait_visible:
                    if self.wait_present is None:
                        self.wait_present = True
                    assert self.wait_visible, \
                        f"'wait_visible' is {self.wait_visible}, but 'wait_present' is {self.wait_present}"

                if self.wait_present is None:
                    self.wait_present = False

                if self.smart_pick is None and self.is_multiple is not None:
                    self.smart_pick = not self.is_multiple

                self.html_parent = self.resolve_html_parent()
                self.template = self.resolve_template()

                self.apply_template()

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
            return self.find_node(self.template)
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

    def find_node(self, name: str = None, only_descendants: bool = False) -> Node:
        if name is None or name == "":
            return self

        named = self.named_or_root_node
        name_parts = name.split()
        first_name = name_parts.pop(0)
        new_name = " ".join(name_parts)

        if named == self.is_pom_root:
            # Force to give an explicit page name if searching from pom root
            page_node: Node = anytree.search.find_by_attr(named, first_name, maxlevel=2)
            assert page_node is not None, \
                f"Error in find_node({name}, {only_descendants}). Page {first_name} not found"
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
                try:
                    values.append(first_candidate.find_node(new_name, only_descendants=True))
                except anytree.search.CountError:
                    continue
            assert len(values) <= 1, \
                f"Found more than 1 node in find_node({name}, {only_descendants}). Using named node: {named}"
            if len(values) == 1:
                return values[0]
            else:
                if only_descendants:
                    assert False, f"Node not found in find_node({name}, {only_descendants}). Using named node: {named}"
                else:
                    return named.parent.find_node(name)

    @property
    def selenium_locator(self) -> typing.Optional[str]:
        if self.locator is None:
            return None
        return self.get_selenium_locator(self.locator, self.get_plugin())

    def find_web_elements(self) -> typing.List[SeleniumLibrary.locators.elementfinder.WebElement]:
        assert self.selenium_locator is not None, \
            f"Error in 'find_web_elements'. Locator: {self.selenium_locator}. Node: {self}"
        assert self._resolved, f"Error in 'find_web_elements'. Node not resolved. Node: {self}"

        html_parent = self.resolve_html_parent()
        if html_parent is not None:
            html_parent_web_element = html_parent.find_web_element(required=False)
            if html_parent_web_element is None:
                return []
            else:
                return self.get_plugin().find_elements(
                    self.selenium_locator,
                    parent=html_parent_web_element,
                )
        else:
            return self.get_plugin().find_elements(self.selenium_locator)

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
        element = plugin.find_element(self.selenium_locator, required=required, parent=html_parent_web_element)
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
        template = template.copy()
        template.apply_format(self.template_args, self.template_kwargs, recursive=True)
        self.update_with_defaults_from(template)

    def is_present(self) -> bool:
        element = self.find_web_element(required=False)
        return True if element is not None else False

    def wait_until_present(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_page_contains_element(
            f"{Plugin.Plugin.POM_PREFIX}:{self.full_name}",
            timeout=timeout,
            # error=f"Element {self} not present after {timeout}",
            # limit=None,
        )

    def is_visible(self) -> typing.Optional[bool]:
        return self.get_plugin().is_visible(self.pom_locator)

    def wait_until_visible(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_element_is_visible(
            f"{Plugin.Plugin.POM_PREFIX}:{self.full_name}",
            timeout=timeout,
            # error=f"Element {self} not visible after {timeout}",
        )

    def is_enabled(self)-> typing.Optional[bool]:
        element = self.find_web_element(required=False)
        return element.is_enabled() if element is not None else None

    def wait_until_enabled(self, timeout=None) -> None:
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library()).wait_until_element_is_enabled(
            f"{Plugin.Plugin.POM_PREFIX}:{self.full_name}",
            timeout=timeout,
            # error=f"Element {self} not enabled after {timeout}",
        )

    def is_selected(self)-> typing.Optional[bool]:
        element = self.find_web_element(required=False)
        return element.is_selected() if element is not None else None

    def wait_until_selected(self, timeout=None) -> None:
        # noinspection PyProtectedMember
        SeleniumLibrary.WaitingKeywords(self.get_selenium_library())._wait_until(
            lambda: self.is_selected(),
            "Element '%s' was not selected in <TIMEOUT>." % self.locator,
            timeout,
            # custom_error=f"Element {self} not selected after {timeout}",
        )

    def wait_until_loaded(self, timeout=None) -> None:
        self._wait_until_loaded(timeout, force_visible=True)

    def _wait_until_loaded(self, timeout=None, force_visible: bool = False) -> None:
        if self.wait_present or force_visible:
            self.wait_until_present(timeout)
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
