import re
from typing import Optional


def locator_dict_from_str(loc: str) -> Optional[dict]:
	pattern = re.compile("(?P<fetcher>.{3,4})\+(?P<package>.+)\$(?P<version>(?:\d\.?)+)")
	return pattern.match(loc).groupdict()  # type: ignore


def project_locator_dict_from_str(loc: str) -> Optional[dict]:
	r = '(?P<fetcher>(?:custom|archive)(?:%2B|\+)\d{4,5})(?:%2F|\/)(?P<package>.+)(?:%24|\$)(?P<revision>.+\\b)'
	pattern = re.compile(r, re.I)
	return pattern.match(loc).groupdict()  # type: ignore


def locator_str_from_dict(d: dict) -> str:
	return f"{d['fetcher']}+{d['package']}${d['version']}"
