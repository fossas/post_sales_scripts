import argparse
import logging
from botocore.exceptions import ClientError
import requests
import os
from urllib.parse import quote
import json
from http.client import HTTPConnection

logger = logging.getLogger(__name__)

def generate_s3_signed_url(packageSpec, revisionVersion):
    """
    FOSSA generates the s3 signed url
    """
    try:
        url = 'https://app.fossa.com/api/components/signed_url?packageSpec={packageSpec}&revision={revisionVersion}'.format(packageSpec=packageSpec, revisionVersion=revisionVersion)
        response = requests.get(url, headers={"Authorization": "Bearer %s" %os.environ['FOSSA_API_KEY']})
        signedUrl = response.json().get('signedUrl')
        logger.info("Got a presigned response: %s", signedUrl)

    except ClientError:
        logger.exception("Couldn't get a presigned URL for client method")
        raise
    return signedUrl

def build_dependency(title, version, description, dependencyUrl):
    """
    FOSSA builds the uploaded dependency
    """
    try:
        fossa_api_token = os.environ['FOSSA_API_KEY']
        url_endpoint = 'https://app.fossa.com/api/components/build'

        headersAuth = {
            'Authorization': 'Bearer ' + fossa_api_token,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }

        params = (
            ('description', description),
            ('projectURL', dependencyUrl),
            ('title', title),
            ('dependency', 'true'),
            ('rawLicenseScan', 'true')
        )

        data = 'archives%5B0%5D%5BpackageSpec%5D={packageSpec}&archives%5B0%5D%5Brevision%5D={version}'.format(packageSpec=title, version=version)

        response = requests.post(url_endpoint, headers=headersAuth, params=params, data=data, verify=True)
        logger.info("Built dependency.... %s", response.status_code)

    except HTTPException:
        logger.exception("Couldn't do it, fail")
        raise

def replace_dependency_in_project(projectLocator, name, version, homepage, description, overwrittenDepLocator):
        """
        FOSSA replaces the dependency
        """
        try:
            fossa_api_token = os.environ['FOSSA_API_KEY']
            url_endpoint = 'https://app.fossa.com/api/revisions/{projectLocator}/dependencies'.format(projectLocator=quote(projectLocator,safe=''))

            headersAuth = {
                'Authorization': 'Bearer ' + fossa_api_token,
                'Content-Type': 'application/json'
            }

            data = {
                "dependencyData": {
                    "kind":"replace",
                    "newDependency": {
                        "kind":"archive",
                        "name": name,
                        "version": version,
                        "homepage": homepage,
                        "description": description
                    },
                    "overwrittenLocator": overwrittenDepLocator
                }
            }

            response = requests.post(url_endpoint, headers=headersAuth, json=data, verify=True)
            logger.info("Overwrote dependency in project: %s", response.status_code)

        except HTTPException:
            logger.exception("Couldn't do it, fail")
            raise

def overwrite_dependency():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    # HTTPConnection.debuglevel = 1

    print('-'*88)
    print("Welcome to misery.")
    print('-'*88)

    parser = argparse.ArgumentParser()
    parser.add_argument('packageSpec', help="Name of package spec")
    parser.add_argument('version', help="Version of the package spec")
    parser.add_argument('title', help="Title of dependency")
    parser.add_argument('description', help="Description of dependency")
    parser.add_argument('dependencyUrl', help="The URL of the dependency")
    parser.add_argument('projectLocator', help="The locator of the target project")
    parser.add_argument('overwrittenDepLocator', help="The locator of the dep to overwrite")
    parser.add_argument('objectUpload', help="The name of a file to upload")
    args = parser.parse_args()

    url = generate_s3_signed_url(args.packageSpec, args.version)

    response = None
    try:
        with open(args.objectUpload, 'rb') as object_file:
            object_text = object_file.read()
            logger.info("Reading file...")

        logger.info("Uploading...")
        response = requests.put(url, data=object_text)
        logger.info("Done uploading...")

    except FileNotFoundError:
        print(f"Couldn't find {args.objectUpload}. The objectUpload must be the "
              f"name of a file that exists on your computer.")

    if response is not None:
        print("Got response:")
        print(f"Status: {response.status_code}")

    if response.status_code == 200:
        build_dependency(args.title, args.version, args.description, args.dependencyUrl)
        replace_dependency_in_project(args.projectLocator, args.title, args.version, args.dependencyUrl, args.description, args.overwrittenDepLocator)
        logger.info("Finished overwriting a dependency...")

    print('-'*88)

if __name__ == '__main__':
    overwrite_dependency()
