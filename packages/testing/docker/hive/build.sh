#!/usr/bin/env sh
# Build one hive simulator image: the test content of a release with the
# framework at a commit of the repository.
#
#   packages/testing/docker/hive/build.sh <simulator> <base-ref> <registry> <release> <image-ref> [docker build args...]
#
#   <simulator>  consume-rlp | consume-engine | consume-enginex | consume-wirex | consume-sync | execute-blobs
#   <base-ref>   the repository image, e.g. ghcr.io/ethereum/execution-specs:sha-abc1234
#   <registry>   where the fixture and tests images live, e.g.
#                ghcr.io/ethereum/execution-specs; "-" for local images without
#                a prefix (fixtures/<format>:<release>, tests:<release>)
#   <release>    release tag of the test content, e.g. v20.0.2 or
#                glamsterdam-devnet-v8.1.4
#   <image-ref>  tag for the result, e.g. hive/consume-engine:local
#
# A consume simulator takes the fixture image of each format it consumes from
# the registry, an execute simulator the tests image. Provenance is taken from
# the environment when set: EEST_GIT_SHA, EEST_GIT_REF, EEST_FIXTURES_RELEASE,
# EEST_TESTS_RELEASE, EEST_TESTS_GIT_SHA, EEST_REPOSITORY; an execute simulator
# also takes its default fork, the fork the release was filled for, from
# EEST_DEFAULT_FORK.
set -eu

if [ $# -lt 5 ]; then
    sed -n '2,22p' "$0" >&2
    exit 2
fi
simulator=$1
base_ref=$2
registry=$3
release=$4
image=$5
shift 5
here=$(cd "$(dirname "$0")" && pwd)

prefix=""
if [ "$registry" != "-" ]; then
    prefix="${registry}/"
fi

# Simulator -> test content: the fixture formats it consumes, the first as the
# base layer, or the test sources.
case "$simulator" in
consume-rlp) formats=blockchain_tests ;;
consume-engine) formats=blockchain_tests_engine ;;
consume-enginex) formats=blockchain_tests_engine_x ;;
consume-wirex) formats="blockchain_tests_engine_x blockchain_tests_x" ;;
consume-sync) formats=blockchain_tests_sync ;;
execute-blobs) formats="" ;;
*)
    echo "error: unknown simulator '$simulator'" >&2
    exit 1
    ;;
esac

if [ -n "$formats" ]; then
    dockerfile=Dockerfile
    format=${formats%% *}
    second=${formats#"$format"}
    second=${second# }
    set -- "$@" --build-arg "FIXTURES_REF=${prefix}fixtures/${format}:${release}"
    if [ -n "$second" ]; then
        case "$second" in
        *" "*)
            echo "error: '$simulator' consumes more than two formats" >&2
            exit 1
            ;;
        esac
        set -- "$@" --target second-format \
            --build-arg "EXTRA_FIXTURES_REF=${prefix}fixtures/${second}:${release}" \
            --build-arg "EXTRA_FORMAT=${second}"
    fi
    provenance="EEST_GIT_SHA EEST_GIT_REF EEST_FIXTURES_RELEASE EEST_REPOSITORY"
else
    dockerfile=Dockerfile.execute
    set -- "$@" --build-arg "TESTS_REF=${prefix}tests:${release}"
    provenance="EEST_GIT_SHA EEST_GIT_REF EEST_TESTS_RELEASE EEST_TESTS_GIT_SHA EEST_REPOSITORY EEST_DEFAULT_FORK"
fi
set -- "$@" --build-arg "BASE_REF=$base_ref" --build-arg "EEST_SIMULATOR=$simulator"
for var in $provenance; do
    eval "value=\${$var:-}"
    if [ -n "$value" ]; then
        set -- "$@" --build-arg "$var=$value"
    fi
done

DOCKER_BUILDKIT=1 docker build -f "$here/$dockerfile" -t "$image" "$@" "$here"
