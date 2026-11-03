import unicodedata
from typing import Annotated

from pydantic import AfterValidator


def reject_nul(value: str) -> str:
    # SQLite's length() stops at the first NUL, so "\x00abc" has length 0 and fails the database's
    # not-empty CHECK. Left to the database that is a 500 (or a misleading 409), so refuse it here.
    if "\x00" in value:
        raise ValueError("must not contain a NUL character")
    return value


# For every client-supplied string that ends up in a column with a length check.
NoNul = Annotated[str, AfterValidator(reject_nul)]


def reject_hidden_characters(value: str) -> str:
    """No control characters (NUL, bell, line breaks), invisible formatting characters (zero-width
    space, right-to-left override), Unicode line and paragraph separators (U+2028, U+2029: some
    readers split lines on them) or lone surrogates: they can hide text from a person reviewing it
    or break a line-based file, and a single-line name has no use for them."""
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Zl", "Zp") for ch in value):
        raise ValueError("must not contain control or invisible characters")
    return value
