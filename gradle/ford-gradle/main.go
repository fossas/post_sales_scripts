package main

import (
	"fmt"
	"io/ioutil"

	"ford-gradle/gradle"

	"github.com/apex/log"
	"gopkg.in/yaml.v2"
)

/* TODO list
1. Remove dependencies on other fossa modules
2. Add a Makefile to build in linux
3. Refactor so its somewhat clean
4. Determine how to handle things we may want to accept as inputs
*/

var acceptedConfigs = []string{"runtime", "default", "compile"}

func main() {
	deps, err := gradle.Dependencies("app", "./gradlew")
	if err != nil {
		panic(err)
	}

	fmt.Printf("%d total dependencies discovered. Duplicates may exist\n", len(deps))
	formatted, err := gradle.FormatFossaDeps(deps)

	yamlData, err := yaml.Marshal(&formatted)
	if err != nil {
		panic(err)
	}

	fileName := "fossa-deps.yml"
	err = ioutil.WriteFile(fileName, yamlData, 0644)
	if err != nil {
		log.Fatalf("unable to write data into the file.\nerror message %s\ndata attempted to be written %s", err, yamlData)
	}
}

func contains(s []string, str string) bool {
	for _, v := range s {
		if v == str {
			return true
		}
	}

	return false
}
