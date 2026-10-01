"""Reparação de translineação confirmada pelo texto de referência independente."""

import re

WRAPPED = re.compile(r"([^\W\d_]{2,})[ \t]*-[ \t\n]+([^\W\d_]{2,})", re.UNICODE)


def repair_wrapped(text: str, reference_words) -> str:
    reference = set(reference_words)

    def replace(match):
        left, right = match.groups()
        joined = left + right
        if right[0].islower() and joined in reference:
            return joined
        return match.group(0)

    return WRAPPED.sub(replace, text)
