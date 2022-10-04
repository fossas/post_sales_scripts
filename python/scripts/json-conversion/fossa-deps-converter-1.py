from glob import glob
import json
import os

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

if __name__ == '__main__':

    types = ["**/*.rpm", "**/*.tar"]

    rpm_and_tar = []
    for type in types:
         this_type_files = glob(type, recursive=True)
         rpm_and_tar += this_type_files

    vendoredDeps = { "vendored-dependencies": [] }
    name, path = '', ''

    if rpm_and_tar:
        for path in rpm_and_tar:
            filename = os.path.splitext(os.path.basename(path))[0]
            vendoredDeps["vendored-dependencies"].append({"name": filename, "path":path})

        print('Saving fossa-deps.json...')
        saveFossaDepsJson(vendoredDeps)
    else:
        print('Nothing to convert...')
