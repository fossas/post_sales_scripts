import json
import re

def readDepsBzl():
    file = open('deps.bzl', 'r')
    text = file.read()
    file.close()
    return str(text)

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

def findGoRepostoryBlocks(input):
    goRepositoryBlockRegex = re.compile(r"go_repository\([^)]*\)", re.IGNORECASE)
    goRepositoryBlockMatches = goRepositoryBlockRegex.findall(input)
    return goRepositoryBlockMatches

def findImportPathValue(input):
    importPathNameRegex = re.compile(r'importpath\s*=\s*"\s*(.*?)\s*"', re.IGNORECASE)
    importPathNameMatch = importPathNameRegex.search(go_repo).group(1)
    return importPathNameMatch

def findDependencyVersionValue(input):
    dependencyVersionRegex = re.compile(r'(?:version|commit|tag)\s*=\s*"\s*(.*?)\s*"', re.IGNORECASE)
    dependencyVersionMatch = dependencyVersionRegex.search(go_repo).group(1)
    return dependencyVersionMatch

if __name__ == '__main__':
    bazelFile = readDepsBzl()
    goRepositoryBlobs = findGoRepostoryBlocks(bazelFile)

    referencedDepsDict = { "referenced-dependencies": [] }

    for go_repo in goRepositoryBlobs:
        importPath = findImportPathValue(go_repo)
        dependencyVersion = findDependencyVersionValue(go_repo)

        referencedDepsDict["referenced-dependencies"].append({"type":"gomod", "name":importPath, "version":dependencyVersion})

    saveFossaDepsJson(referencedDepsDict)
