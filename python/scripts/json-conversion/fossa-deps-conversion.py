from glob import glob
import json

def readArtifacts():
    file = open('artifacts.json', 'r')
    data = json.load(file)
    file.close()
    return data

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

def findRpmTarVendoredDependencies():
    types = ["**/*.rpm", "**/*.tar"]

    rpm_and_tar = []
    for type in types:
         this_type_files = glob(type, recursive=True)
         rpm_and_tar += this_type_files

    vendoredDeps = { "vendored-dependencies": [] }
    name, path = '', ''

    if rpm_and_tar:
        for path in rpm_and_tar:
            filename = path.split('/')[-1].split('.')[0]
            print(filename)
            vendoredDeps["vendored-dependencies"].append({"name": filename, "path":path})

        print('Converted vendored dependencies...')
        print(vendoredDeps)
        return vendoredDeps
    else:
        print('Vendored Dependencies: Nothing to convert...')
        return {}

def findReferenceDependencies():
    artifactsFile = readArtifacts()

    referencedDeps = { "referenced-dependencies": [] }
    name, version, type = '', '', ''

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
        print(referencedDeps)
        return referencedDeps
    else:
        print('Referenced Dependencies: Nothing to convert...')
        return {}

if __name__ == '__main__':

    vendoredDeps = findRpmTarVendoredDependencies()
    referencedDeps = findReferenceDependencies()

    convertedDeps = dict(list(vendoredDeps.items()) + list(referencedDeps.items()))

    saveFossaDepsJson(convertedDeps)
