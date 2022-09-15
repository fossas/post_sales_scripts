from glob import glob
import json

def saveFossaDepsJson(dictionary):
    file = open('fossa-deps.json', 'w')
    json.dump(dictionary, file)
    file.close()

if __name__ == '__main__':

    types = ["**/*.rpm", "**/*.tar"]

    rpm_and_tar = []
    for type in types:
         this_type_files = glob(type)
         rpm_and_tar += this_type_files

    vendoredDeps = { "vendored-dependencies": [] }
    name, path = '', ''

    if rpm_and_tar:
        for path in rpm_and_tar:
            filename = path.split('/')[-1].split('.')[0]
            print(filename)
            vendoredDeps["vendored-dependencies"].append({"name": filename, "path":path})

        print('Saving fossa-deps.json...')
        saveFossaDepsJson(vendoredDeps)
    else:
        print('Nothing to convert...')
