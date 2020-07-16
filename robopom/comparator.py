import typing
from . import model


def equals(value: typing.Any, expected: typing.Any) -> bool:
    return value == expected


class Comparator:
    COMPARATOR_FUNCTIONS: typing.Dict[str, typing.Callable[[typing.Any, typing.Any], bool]] = {
        "equals": equals,
    }

    @staticmethod
    def compare_using(value: typing.Any,
                      expected: typing.Any,
                      comparator: typing.Union[str,
                                               typing.Callable[[typing.Any, typing.Any], bool]] = "equals",
                      ) -> bool:
        if isinstance(comparator, str):
            comparator = Comparator.COMPARATOR_FUNCTIONS[comparator]
        return comparator(value, expected)

    @staticmethod
    def compare_field_value_using(node: model.Node,
                                  expected: typing.Any,
                                  comparator: typing.Union[str,
                                                           typing.Callable[
                                                               [typing.Any, typing.Any], bool]] = "equals",
                                  compare_as: str = None,
                                  **kwargs,
                                  ) -> bool:
        if compare_as is None:
            value = node.get_field_value(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["String", "str"]]:
            value = node.get_field_value_as_string(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["Integer", "int"]]:
            value = node.get_field_value_as_integer(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["Float"]]:
            value = node.get_field_value_as_float(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["Boolean", "bool"]]:
            value = node.get_field_value_as_boolean(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["Date"]]:
            value = node.get_field_value_as_date(**kwargs)
        elif compare_as.casefold() in [t.casefold for t in ["Datetime"]]:
            value = node.get_field_value_as_datetime(**kwargs)
        else:
            assert False, f"'compare_as' not valid: {compare_as}"

        return Comparator.compare_using(value, expected, comparator)

    def __init__(self, compare_function: typing.Callable[[typing.Any, typing.Any], bool] = None):
        if compare_function is None:
            compare_function = equals
        self.compare_function = compare_function

    def compare(self, value: typing.Any, expected: typing.Any) -> bool:
        return self.compare_using(value, expected, self.compare_function)

    def compare_field_value(self,
                            node: model.Node,
                            expected: typing.Any,
                            compare_as: str = None,
                            **kwargs,
                            ) -> bool:
        return self.compare_field_value_using(node, expected, self.compare_function, compare_as, **kwargs)
