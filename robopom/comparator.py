from __future__ import annotations
import typing
import re


def equals(value: typing.Any, expected: typing.Any) -> bool:
    return value == expected


def equals_ignore_case(value: typing.Any, expected: typing.Any) -> bool:
    return str(value).casefold() == str(expected).casefold()


def value_greater_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value > expected


def value_greater_or_equal_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value >= expected


def value_lower_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value < expected


def value_lower_or_equal_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value >= expected


def value_in_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value in expected


def value_not_in_expected(value: typing.Any, expected: typing.Any) -> bool:
    return value not in expected


def expected_in_value(value: typing.Any, expected: typing.Any) -> bool:
    return expected in value


def expected_not_in_value(value: typing.Any, expected: typing.Any) -> bool:
    return expected not in value


def value_len_equals(value: typing.Any, expected: typing.Any) -> bool:
    return len(value) == expected


def value_len_greater_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return len(value) > expected


def value_len_greater_or_equal_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return len(value) >= expected


def value_len_lower_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return len(value) < expected


def value_len_lower_or_equal_than_expected(value: typing.Any, expected: typing.Any) -> bool:
    return len(value) <= expected


def value_matches_regular_expression(value: typing.Any, expected: typing.Any) -> bool:
    return re.search(expected, value) is not None


class Comparator:

    COMPARATOR_FUNCTIONS: typing.Dict[str, typing.Callable[[typing.Any, typing.Any], bool]] = {
        "equals".casefold(): equals,
        "==": equals,
        "=": equals,

        "equals_ignore_case".casefold(): equals_ignore_case,
        "equals ignore case".casefold(): equals_ignore_case,
        "=(ignore_case)".casefold(): equals_ignore_case,
        "==(ignore_case)".casefold(): equals_ignore_case,
        "=(ignore case)".casefold(): equals_ignore_case,
        "==(ignore case)".casefold(): equals_ignore_case,

        "value_greater_than_expected".casefold(): value_greater_than_expected,
        "value greater than expected".casefold(): value_greater_than_expected,
        ">".casefold(): value_greater_than_expected,

        "value_greater_or_equal_than_expected".casefold(): value_greater_than_expected,
        "value greater or equal than expected".casefold(): value_greater_than_expected,
        ">=".casefold(): value_greater_than_expected,

        "value_lower_than_expected".casefold(): value_lower_than_expected,
        "value lower than expected".casefold(): value_lower_than_expected,
        ">".casefold(): value_lower_than_expected,

        "value_lower_or_equal_than_expected".casefold(): value_lower_than_expected,
        "value lower or equal than expected".casefold(): value_lower_than_expected,
        ">=".casefold(): value_lower_than_expected,

        "value_in_expected".casefold(): value_in_expected,
        "value in expected".casefold(): value_in_expected,

        "value_not_in_expected".casefold(): value_not_in_expected,
        "value not in expected".casefold(): value_not_in_expected,

        "expected_in_value".casefold(): expected_in_value,
        "expected in value".casefold(): expected_in_value,

        "expected_not_in_value".casefold(): expected_not_in_value,
        "expected not in value".casefold(): expected_not_in_value,

        "value_len_equals".casefold(): value_len_equals,
        "value len equals".casefold(): value_len_equals,
        "len(value) == expected".casefold(): value_len_equals,

        "value_len_greater_than_expected".casefold(): value_len_greater_than_expected,
        "value len greater than expected".casefold(): value_len_greater_than_expected,
        "len(value) > expected".casefold(): value_len_greater_than_expected,

        "value_len_greater_or_equal_than_expected".casefold(): value_len_greater_or_equal_than_expected,
        "value len greater or equal than expected".casefold(): value_len_greater_or_equal_than_expected,
        "len(value) >= expected".casefold(): value_len_greater_or_equal_than_expected,

        "value_len_lower_than_expected".casefold(): value_len_lower_than_expected,
        "value len lower than expected".casefold(): value_len_lower_than_expected,
        "len(value) < expected".casefold(): value_len_lower_than_expected,

        "value_len_lower_or_equal_than_expected".casefold(): value_len_lower_or_equal_than_expected,
        "value len lower or equal than expected".casefold(): value_len_lower_or_equal_than_expected,
        "len(value) <= expected".casefold(): value_len_lower_or_equal_than_expected,

        "value_matches_regular_expression".casefold(): value_matches_regular_expression,
        "value matches regular expression".casefold(): value_matches_regular_expression,
        "regexp".casefold(): value_matches_regular_expression,
    }

    @staticmethod
    def compare(value: typing.Any,
                expected: typing.Any,
                comparator: typing.Union[str,
                                         typing.Callable[[typing.Any, typing.Any], bool]] = equals,
                ) -> bool:
        if isinstance(comparator, str):
            comparator = Comparator.COMPARATOR_FUNCTIONS[comparator.casefold()]
        return comparator(value, expected)
