"""Fetch go dependencies.
"""

load("//bazel/go:repository.bzl", "go_repository")

def manual_go_deps():
    go_repository(
        name = "com_github_gogo_protobuf_121",
        build_file_proto_mode = "disable_global",
        importpath = "github.com/gogo/protobuf",
        commit = "ba06b47c162d49f2af050fb4c75bcbc86a159d5c",
    )

    go_repository(
        name = "com_github_grpc_grpc_go_v1_37_0",
        build_file_proto_mode = "disable_global",
        importpath = "github.com/grpc/grpc-go",
        tag = "v1.37.0",
    )

    go_repository(
        name = "com_github_google_go_containerregistry",
        importpath = "github.com/google/go-containerregistry",
        commit = "628a2ff5f006eca399a316a66cc714106fcb3943",
        build_directives = [
            # the k8schain package is not used.  Gazelle and go modules are
            # confused by it:
            # https://github.com/vdemeester/k8s-pkg-credentialprovider#k8siokubernetespkgcredentialprovider-temporary-fork
            "gazelle:exclude pkg/authn/k8schain/**/*",
        ],
    )

    go_repository(
        name = "com_github_aws_aws_lambda_go_v1_22_0",
        build_file_proto_mode = "disable_global",
        importpath = "github.com/aws/aws-lambda-go",
        tag = "v1.22.0",
    )

    go_repository(
        name = "com_github_shirou_gopsutil",
        importpath = "github.com/shirou/gopsutil",
        commit = "3b417071a5835600ae0d654231cfb9ce226f2b6b",
    )

def fetch_go_deps():
    go_repository(
        name = "cc_mvdan_gofumpt",
        build_file_proto_mode = "disable_global",
        importpath = "mvdan.cc/gofumpt",
        sum = "h1:bi/1aS/5W00E2ny5q65w9SnKpWEF/UIOqDYBILpo9rA=",
        version = "v0.1.1",
    )
    go_repository(
        name = "cc_mvdan_interfacer",
        build_file_proto_mode = "disable_global",
        importpath = "mvdan.cc/interfacer",
        sum = "h1:WX1yoOaKQfddO/mLzdV4wptyWgoH/6hwLs7QHTixo0I=",
        version = "v0.0.0-20180901003855-c20040233aed",
    )
