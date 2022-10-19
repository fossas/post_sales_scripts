from glob import glob
import json
import os

def readArtifacts():
    data = {}

    # may need to change this to the actual file that contains deps that need to be converted
    artifactsFile = 'artifacts.json'

    if os.path.exists(artifactsFile):
        file = open(artifactsFile, 'r')
        data = json.load(file)
        file.close()
    return data

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

def findRpmTarVendoredDependencies():

    rpm_and_tar = []

    # walk the root of this current dir
    for root, dirs, files in os.walk(os.curdir):
    	for file in files:
    		if(file.endswith(".rpm") or file.endswith(".tar")):
    			rpm_and_tar.append(os.path.join(root,file))

    vendoredDeps = { "vendored-dependencies": [] }
    name, path = '', ''

    if rpm_and_tar:
        for path in rpm_and_tar:
            filename = path.rsplit('/')[-1].rsplit('.',1)[0]

            # take out dupes
            if not any(dep.get('name', None) == filename for dep in vendoredDeps["vendored-dependencies"]):
                vendoredDeps["vendored-dependencies"].append({"name": filename, "path":path})

        print('Converted vendored dependencies...')
        return vendoredDeps
    else:
        print('Vendored Dependencies: Nothing to convert...')
        return {}

def findReferenceDependencies():
    artifactsFile = readArtifacts()

    referencedDeps = { "referenced-dependencies": [] }
    name, version, type = '', '', ''

    # Figure out the mapping for your org. Here's an example.
    if artifactsFile:
        for dep in artifactsFile['rows']:
            for key, val in dep.items():
                if key == 'packageSpec':
                    name = val
                if key == 'packageVersion':
                    version = val
                if key == 'location':
                    type = val.lower()
            referencedDeps["referenced-dependencies"].append({"type": type, "name":name, "version":version})

        print('Converted referenced dependencies...')
        return referencedDeps
    else:
        print('Referenced Dependencies: Nothing to convert...')
        return {}

if __name__ == '__main__':

    vendoredDeps = findRpmTarVendoredDependencies()
    referencedDeps = findReferenceDependencies()

    convertedDeps = {**vendoredDeps,**referencedDeps}

    saveFossaDepsJson(convertedDeps)
