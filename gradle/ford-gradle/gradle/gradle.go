package gradle

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"

	"github.com/apex/log"
)

type FossaDeps struct {
	ReferencedDependencies []FossaDepsDependency `yaml:"referenced-dependencies"`
}

type FossaDepsDependency struct {
	DepType string `yaml:"type"`
	Name    string `yaml:"name"`
	Version string `yaml:"version"`
}

// Dependency models a gradle dependency.
type Dependency struct {
	Name             string
	RequestedVersion string
	ResolvedVersion  string
	IsProject        bool
}

// These types mimic the package fossas/fossa-cli/pkg.
// They may not be optimal and could be refactored, but they accurately gather the dependency graph.
type Import struct {
	Target   string
	Resolved ID
}

type ID struct {
	Name     string
	Revision string
}

type Package struct {
	ID      ID
	Imports []Import
}

type graph struct {
	Direct     []Import
	Transitive map[ID]Package
}

// Dependencies returns the dependencies of a gradle project
func Dependencies(project string, command string) ([]ID, error) {
	arguments := []string{
		project + ":dependencies",
		"--offline",
	}

	stdout, err := Cmd(command, arguments...)
	if err != nil {
		return nil, err
	}

	// Parse individual configurations.
	configurations := make(map[string]graph)
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
			configurations[config] = graph{}
		} else if strings.HasPrefix(lines[1], "\\--- ") || strings.HasPrefix(lines[1], "+--- ") {
			imports, deps, err := ParseDependencies(section)
			if err != nil {
				return nil, err
			}
			configurations[config] = NormalizeDependencies(imports, deps)
		}
	}

	// Dedupe the dependencies across all of the different configurations taking each unique ID.
	depMap := make(map[ID]bool)
	for _, set := range configurations {
		// TODO: Implement configuration sorting:
		// for config, set := range configurations {
		// if contains(acceptedConfigs, config) {
		for pack := range set.Transitive {
			depMap[pack] = true
		}
	}

	filteredDeps := []ID{}
	for dep := range depMap {
		filteredDeps = append(filteredDeps, dep)
	}

	return filteredDeps, nil
}

func FormatFossaDeps(deps []ID) (FossaDeps, error) {
	finalDeps := []FossaDepsDependency{}
	for _, dep := range deps {
		finalDeps = append(finalDeps, FossaDepsDependency{
			DepType: "maven",
			Name:    dep.Name,
			Version: dep.Revision,
		})
	}
	formattedDeps := FossaDeps{finalDeps}

	return formattedDeps, nil
}

// Cmd executes the gradle shell command.
func Cmd(command string, taskArgs ...string) (string, error) {
	var stdout, stderr string
	var stdoutBuf []byte

	log.WithFields(log.Fields{
		"name": command,
		"argv": taskArgs,
	}).Info("called Run")

	stderrBuffer := new(bytes.Buffer)
	xc := exec.Command(command, taskArgs...)
	xc.Stderr = stderrBuffer
	xc.Env = os.Environ()
	log.Info("Running the command")
	stdoutBuf, err := xc.Output()
	stdout = string(stdoutBuf)
	stderr = stderrBuffer.String()

	if err != nil && stderr != "" {
		return stdout, fmt.Errorf("Fossa could not run %s %s within the current directory.\nstdout: %s\nstderr: %s", command, strings.Join(taskArgs, " "), stdout, stderr)
	}
	log.WithFields(log.Fields{
		"stdout": stdout,
		"stderr": stderr,
	}).Info("done running")
	return stdout, err
}

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
			return -1, Dependency{}, fmt.Errorf("bad depth: %#v %s %#v", depth, line, matches)
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
func NormalizeDependencies(imports []Dependency, deps map[Dependency][]Dependency) graph {
	// Set direct dependencies.
	var i []Import
	for _, dep := range imports {
		if dep.IsProject {
			continue
		}

		i = append(i, Import{
			Target: dep.RequestedVersion,
			Resolved: ID{
				Name:     dep.Name,
				Revision: dep.ResolvedVersion,
			},
		})
	}

	// Set transitive dependencies.
	d := make(map[ID]Package)
	for parent, children := range deps {
		if parent.IsProject {
			continue
		}

		id := ID{
			Name:     parent.Name,
			Revision: parent.ResolvedVersion,
		}
		var imports []Import
		for _, child := range children {
			imports = append(imports, Import{
				Target: child.ResolvedVersion,
				Resolved: ID{
					Name:     child.Name,
					Revision: child.ResolvedVersion,
				},
			})
		}
		d[id] = Package{
			ID:      id,
			Imports: imports,
		}
	}

	return graph{
		Direct:     i,
		Transitive: d,
	}
}

func contains(array []Import, check Import) bool {
	for _, val := range array {
		if val == check {
			return true
		}
	}
	return false
}
