import re


def project_locator_from_url(project_summary_page_url: str) -> dict[str, str]:
    """
    Returns project locator dictionary

    :param project_summary_page_url:
    :return:
    """
    r = 'https:\/\/app\.fossa\.com\/projects\/(?P<fetcher>(?:custom|archive)%2B\d{4,5})%2F(?P<package>.+)' \
        '(?:\/refs\/branch\/.+?\/)(?P<revision>\d+\\b)'
    pattern = re.compile(r, re.I)
    match = pattern.match(project_summary_page_url)
    if match is not None:
        return match.groupdict()
    else:
        raise ValueError(f"Could not parse project locator from url: {project_summary_page_url}")


def encode_project_locator(project_locator: dict[str, str]) -> str:
    """
    Encodes project locator as string

    :param project_locator:
    :return:
    """
    # %2B = +
    # %24 = $
    # %2F = /

    encoded = f"{project_locator['fetcher']}%2B{project_locator['package']}%24{project_locator['revision']}"
    return encoded.replace('/', '%2F')


if __name__ == '__main__':
    print('enter url:')
    url = input('> ')
    print(project_locator_from_url(url))
    # locator = {
    #      "fetcher": "archive",
    #      "package": "2146/msrest-0.6.10",
    #      "revision": "1645628883888"
    #  }
    # print(encode_project_locator(locator))
