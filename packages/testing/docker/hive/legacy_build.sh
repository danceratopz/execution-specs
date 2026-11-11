#!/bin/sh
# Keep the Dockerfile.git build arguments of the hive eels simulators working
# while they are deprecated. The ONBUILD trigger of the latest-legacy image
# (Dockerfile.legacy) runs this as `RUN eels-legacy-build` in hive's wrapper
# build, with its build arguments in the environment:
#
#   tag       a published image tag; when set, fixtures and branch are ignored
#   fixtures  the consume input, cached at build time as Dockerfile.git did: a
#             release name, a URL, or /fixtures with a staged fixtures.tar.gz
#   branch    an execution-specs ref whose framework, and for an execute
#             simulator whose tests, replace the image's, installed with a
#             plain `uv sync` as Dockerfile.git did, Python downloads allowed
#
# Without tag, fixtures or branch it does nothing. Otherwise it records the
# values it applied as files under $EELS_LEGACY_STATE; the entry point reads
# them and prints a deprecation notice in every run. Paths are overridable
# for tests only.
set -eu

state=${EELS_LEGACY_STATE:-/etc/eels-simulator/legacy}
staged=${EELS_LEGACY_STAGED:-/staged}
repo=${EELS_LEGACY_REPO:-/execution-specs}
fixtures_dir=${EELS_LEGACY_FIXTURES_DIR:-/fixtures}
tag=${tag:-}
fixtures=${fixtures:-}
branch=${branch:-}

trap 'rm -rf "$staged"' EXIT

if [ -n "$tag" ] || [ -z "$fixtures$branch" ]; then
    exit 0
fi

echo "eels-legacy-build: the fixtures and branch build arguments are deprecated;" \
    "pass --sim.buildarg tag=<tag> instead, see ethereum/execution-specs#3866" >&2
mkdir -p "$state"

case "${EEST_SIMULATOR:-}" in
execute-*)
    if [ -n "$fixtures" ]; then
        echo "eels-legacy-build: execute simulators take no fixtures; ignoring fixtures=$fixtures" >&2
        fixtures=""
    fi
    ;;
esac

if [ -n "$branch" ]; then
    src=$(mktemp -d)
    git clone --depth 1 https://github.com/ethereum/execution-specs.git "$src"
    git -C "$src" fetch --depth 1 origin "$branch"
    git -C "$src" checkout --quiet FETCH_HEAD
    rm -rf "$repo"
    mv "$src" "$repo"
    (cd "$repo/packages/testing" && UV_PYTHON_DOWNLOADS=automatic uv sync)
    printf '%s\n' "$branch" > "$state/branch"
    git -C "$repo" rev-parse HEAD > "$state/commit"
fi

if [ -n "$fixtures" ]; then
    if [ "$fixtures" = /fixtures ]; then
        if [ -f "$staged/fixtures.tar.gz" ]; then
            # The image's own formats, the fixture directories beside .meta.
            formats=$(find "$fixtures_dir" -mindepth 1 -maxdepth 1 -type d ! -name .meta -exec basename {} \; | sort)
            if [ -z "$formats" ]; then
                echo "eels-legacy-build: error: no fixture format in $fixtures_dir to extract" >&2
                exit 1
            fi
            members=""
            for format in $formats; do
                members="$members fixtures/$format"
            done
            rm -rf "$fixtures_dir"
            mkdir -p "$fixtures_dir"
            # A release from before one of the formats existed lacks its
            # directory; extract the formats it has.
            # shellcheck disable=SC2086 # one member per format
            tar -xzf "$staged/fixtures.tar.gz" -C "$fixtures_dir" --strip-components=1 \
                fixtures/.meta $members 2> "$staged/tar.log" || {
                if grep -v -e "Not found in archive" -e "Exiting with failure status" "$staged/tar.log" >&2; then
                    echo "eels-legacy-build: error: extracting $staged/fixtures.tar.gz failed" >&2
                    exit 1
                fi
            }
            extracted=""
            for format in $formats; do
                if [ -d "$fixtures_dir/$format" ]; then
                    extracted="$extracted $format"
                else
                    echo "eels-legacy-build: warning: the staged fixtures have no $format" >&2
                fi
            done
            if [ -z "$extracted" ] || [ ! -d "$fixtures_dir/.meta" ]; then
                echo "eels-legacy-build: error: the staged fixtures have none of:" $formats >&2
                exit 1
            fi
            printf '%s\n' /fixtures > "$state/fixtures"
        fi
        # Without a staged tarball, /fixtures is the image's own content.
    else
        (cd "$repo/packages/testing" && uv run --no-sync consume cache --input "$fixtures")
        printf '%s\n' "$fixtures" > "$state/fixtures"
    fi
fi
