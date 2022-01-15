package gradle

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/apex/log"

	"github.com/fossas/fossa-cli/errors"
	"github.com/fossas/fossa-cli/exec"
	"github.com/fossas/fossa-cli/graph"
	"github.com/fossas/fossa-cli/pkg"
)

// Dependency models a gradle dependency.
type Dependency struct {
	Name             string
	RequestedVersion string
	ResolvedVersion  string
	IsProject        bool
}

// Dependencies returns the dependencies of a gradle project
func Dependencies(project string, command string) (map[string]graph.Deps, error) {
	arguments := []string{
		project + ":dependencies",
		"--quiet",
		"--offline",
	}
	stdout, err := Cmd(command, arguments...)
	if err != nil {
		return nil, err
	}

	// Parse individual configurations.
	configurations := make(map[string]graph.Deps)
	// Divide output into configurations. Each configuration is separated by an
	// empty line, started with a configuration name (and optional description),
	// and has a dependency as its second line.
	splitReg := regexp.MustCompile("\r?\n\r?\n")
	sections := splitReg.Split(stdout, -1)
	for _, section := range sections {
		lines := strings.Split(section, "\n")
		if len(lines) < 2 {
			continue
		}
		config := strings.Split(lines[0], " - ")[0]
		if lines[1] == "No dependencies" {
			configurations[config] = graph.Deps{}
		} else if strings.HasPrefix(lines[1], "\\--- ") || strings.HasPrefix(lines[1], "+--- ") {
			imports, deps, err := ParseDependencies(section)
			if err != nil {
				return nil, err
			}
			configurations[config] = NormalizeDependencies(imports, deps)
		}
	}

	return configurations, nil
}

// Cmd executes the gradle shell command.
func Cmd(command string, taskArgs ...string) (string, error) {
	tempcmd := exec.Cmd{
		Name: command,
		Argv: taskArgs,
	}
	fmt.Println(tempcmd)

	stdout, stderr, err := exec.Run(tempcmd)
	if err != nil && stderr != "" {
		return stdout, &errors.Error{
			Cause:           err,
			Type:            errors.Exec,
			Troubleshooting: fmt.Sprintf("Fossa could not run `%s %s` within the current directory. Try running this command and ensure that gradle is installed in your environment.\nstdout: %s\nstderr: %s", command, strings.Join(taskArgs, " "), stdout, stderr),
			Link:            "https://github.com/fossas/fossa-cli/blob/master/docs/integrations/gradle.md#gradle",
		}
	}
	fmt.Println(stdout, stderr)
	return stdout, nil
}

//go:generate bash -c "genny -in=../../graph/readtree.go gen 'Generic=Dependency' | sed -e 's/package graph/package gradle/' > readtree_generated.go"

func ParseDependencies(stdout string) ([]Dependency, map[Dependency][]Dependency, error) {
	r := regexp.MustCompile(`^((?:[|+]? +)*[\\+]--- )(.*)$`)
	splitReg := regexp.MustCompile("\r?\n")
	// Skip non-dependency lines.
	var filteredLines []string
	for _, line := range splitReg.Split(stdout, -1) {
		if r.MatchString(line) {
			filteredLines = append(filteredLines, line)
		}
	}

	return ReadDependencyTree(filteredLines, func(line string) (int, Dependency, error) {
		// Match line.
		matches := r.FindStringSubmatch(line)
		depth := len(matches[1])
		if depth%5 != 0 {
			// Sanity check.
			return -1, Dependency{}, errors.Errorf("bad depth: %#v %s %#v", depth, line, matches)
		}

		// Parse dependency.
		dep := matches[2]
		withoutAnnotations := strings.TrimSuffix(strings.TrimSuffix(strings.TrimSuffix(dep, " (*)"), " (n)"), " FAILED")
		var parsed Dependency
		if strings.HasPrefix(withoutAnnotations, "project ") {
			// TODO: the desired method for handling this might be to recurse into the subproject.
			parsed = Dependency{
				// The project name may or may not have a leading colon.
				Name:      strings.TrimPrefix(strings.TrimPrefix(withoutAnnotations, "project "), ":"),
				IsProject: true,
			}
		} else {
			// The line withoutAnnotations can have the form:
			//  1. group:project:requestedVersion
			//  2. group:project:requestedVersion -> resolvedVersion
			//  3. group:project -> resolvedVersion

			var name, requestedVer, resolvedVer string

			sections := strings.Split(withoutAnnotations, " -> ")
			requestedIsNotResolved := len(sections) == 2

			idSections := strings.Split(sections[0], ":")
			name = idSections[0]
			if len(idSections) > 1 {
				name += ":" + idSections[1]
				if len(idSections) > 2 {
					requestedVer = idSections[2]
				}
			}

			if requestedIsNotResolved {
				resolvedVer = sections[1]
			} else {
				resolvedVer = requestedVer
			}
			parsed = Dependency{
				Name:             name,
				RequestedVersion: requestedVer,
				ResolvedVersion:  resolvedVer,
			}
		}

		log.Debugf("%#v %#v", depth/5, parsed)
		return depth / 5, parsed, nil
	})
}

// NormalizeDependencies turns a dependency map into a FOSSA recognized dependency graph.
func NormalizeDependencies(imports []Dependency, deps map[Dependency][]Dependency) graph.Deps {
	// Set direct dependencies.
	var i []pkg.Import
	for _, dep := range imports {
		if dep.IsProject {
			continue
		}

		i = append(i, pkg.Import{
			Target: dep.RequestedVersion,
			Resolved: pkg.ID{
				Type:     pkg.Gradle,
				Name:     dep.Name,
				Revision: dep.ResolvedVersion,
			},
		})
	}

	// Set transitive dependencies.
	d := make(map[pkg.ID]pkg.Package)
	for parent, children := range deps {
		if parent.IsProject {
			continue
		}

		id := pkg.ID{
			Type:     pkg.Gradle,
			Name:     parent.Name,
			Revision: parent.ResolvedVersion,
		}
		var imports []pkg.Import
		for _, child := range children {
			imports = append(imports, pkg.Import{
				Target: child.ResolvedVersion,
				Resolved: pkg.ID{
					Type:     pkg.Gradle,
					Name:     child.Name,
					Revision: child.ResolvedVersion,
				},
			})
		}
		d[id] = pkg.Package{
			ID:      id,
			Imports: imports,
		}
	}

	return graph.Deps{
		Direct:     i,
		Transitive: d,
	}
}

func contains(array []pkg.Import, check pkg.Import) bool {
	for _, val := range array {
		if val == check {
			return true
		}
	}
	return false
}
