import re
import requests
import yaml
import os

MODULE_BAZEL_PATH = "MODULE.bazel"
FOSSA_DEPS_PATH = "fossa-deps.yaml"

def get_source_url(package_name, version):
    url = f"https://raw.githubusercontent.com/bazelbuild/bazel-central-registry/main/modules/{package_name}/{version}/source.json"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("url")
        else:
            print(f"Failed to fetch source.json for {package_name}@{version} (Status: {response.status_code})")
            return None
    except Exception as e:
        print(f"Error fetching source.json for {package_name}@{version}: {e}")
        return None

def parse_module_bazel(path):
    deps = []
    with open(path, "r") as f:
        for line in f:
            match = re.match(r'bazel_dep\(name = "(.*?)", version = "(.*?)"\)', line.strip())
            if match:
                name, version = match.groups()
                if name != "rules_cc":
                    deps.append({"name": name, "version": version})
    return deps

def create_fossa_deps_yaml(deps, output_path):
    fossa_deps = {"remote-dependencies": []}
    for dep in deps:
        url = get_source_url(dep["name"], dep["version"])
        if url:
            fossa_deps["remote-dependencies"].append({
                "name": dep["name"],
                "version": dep["version"],
                "url": url
            })
        else:
            print(f"Skipping {dep['name']}@{dep['version']} due to missing source URL.")
    with open(output_path, "w") as f:
        yaml.dump(fossa_deps, f, sort_keys=False)
    print(f"fossa-deps.yaml written to {output_path}")

if __name__ == "__main__":
    deps = parse_module_bazel(MODULE_BAZEL_PATH)
    create_fossa_deps_yaml(deps, FOSSA_DEPS_PATH)
