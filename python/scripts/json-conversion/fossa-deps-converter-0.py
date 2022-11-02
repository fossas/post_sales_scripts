import json
import re

def readArtifacts():
    file = open('artifacts.json', 'r')
    data = json.load(file)
    file.close()
    return data

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

if __name__ == '__main__':
    artifactsFile = readArtifacts()

    referencedDepsDict = { "referenced-dependencies": [] }
    name, version, type = '', '', ''

    for dep in artifactsFile['rows']:
        for key, val in dep.items():
            if key == 'packageSpec':
                name = val
            if key == 'packageVersion':
                version = val
            if key == 'location':
                type = val.lower()
        referencedDepsDict["referenced-dependencies"].append({"type": type, "name":name, "version":version})

    saveFossaDepsJson(referencedDepsDict)
