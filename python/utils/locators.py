import re
from typing import Optional


def locator_dict_from_str(loc: str) -> Optional[dict]:
	pattern = re.compile("(?P<fetcher>.{3,4})\+(?P<package>.+)\$(?P<version>(?:\d\.?)+)")
	return pattern.match(loc).groupdict()  # type: ignore


def locator_str_from_dict(d: dict) -> str:
	return f"{d['fetcher']}+{d['package']}${d['version']}"
