package main

import (
	"fmt"
	"io/ioutil"

	"github.com/fossas/fossa-cli/pkg"
	"github.com/fossas/gradle-script/gradle"
	"gopkg.in/yaml.v2"
)

type fossaDeps struct {
	ReferencedDependencies []Dependency `yaml:"referenced-dependencies"`
}

type Dependency struct {
	DepType string `yaml:"type"`
	Name    string `yaml:"name"`
	Version string `yaml:"version"`
}

var acceptedConfigs = []string{"runtime", "default", "compile"}

func main() {
	fmt.Println("vim-go")
	deps, _ := gradle.Dependencies("grpc-all", "./gradlew")

	depMap := make(map[pkg.ID]bool)

	for config, set := range deps {
		if contains(acceptedConfigs, config) {
			for pack := range set.Transitive {
				depMap[pack] = true
			}
		}
	}

	finalDeps := []Dependency{}
	for dep := range depMap {
		finalDeps = append(finalDeps, Dependency{
			DepType: "maven",
			Name:    dep.Name,
			Version: dep.Revision,
		})
	}
	fmt.Println(finalDeps)
	// Turn the map into an array

	outputFile := fossaDeps{finalDeps}
	yamlData, err := yaml.Marshal(&outputFile)
	if err != nil {
		panic(err)
	}

	fileName := "fossa-deps.yml"
	err = ioutil.WriteFile(fileName, yamlData, 0644)
	if err != nil {
		panic("Unable to write data into the file")
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
