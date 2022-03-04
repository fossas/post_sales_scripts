import re


def project_locator_from_url(project_summary_page_url: str) -> dict[str, str]:
    """
    Returns project locator dictionary

    :param project_summary_page_url:
    :return:
    """
    r = r"https:\/\/app\.fossa\.com\/projects\/(?P<fetcher>custom%2B\d{5})%2F(?P<package>.+?)(?:\/refs\/branch\/).+?" \
        "\/(?P<revision>\d+\\b)"
    pattern = re.compile(r, re.I)
    match = pattern.match(project_summary_page_url)
    if match is not None:
        return match.groupdict()
    else:
        raise ValueError(f"Could not parse project locator from url: {project_summary_page_url}")


if __name__ == '__main__':
    print('enter url')
    url = input('> ')
    print(project_locator_from_url(url))
