### Dependency conversions to fossa-deps.yml 

#### fossa-deps-converter-0.py
Convert a known dependency manifest file into a `fossa-deps.json` file.

#### fossa-deps-converter-1.py
Convert a list of existing vendored dependencies into a `fossa-deps.json` file.

### fossa-deps-converter.py
Combines `fossa-deps-converter-0.py` and `fossa-deps-converter-1.py`. Please note that these scripts are examples of converting data into FOSSA's dependency types, namely vendored dependencies and referenced dependencies. In this example, we showcase how to convert file paths for rpm and tar files and we also convert an artifacts json to a referenced dependency section in the `fossa-deps.json`. In order to use this script, please review how your data (dependencies list) is structured and adjust the mapping logic appropriattely (e.g. review the logic for both referenced dependencies and vendored dependencies).
