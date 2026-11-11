# Hive simulator image for a consume simulator: the fixture image of the
# release, the format the simulator consumes, with the repository image at the
# branch head flattened on top. A simulator that consumes a second format
# (consume-wirex) is built with `--target second-format`, which adds that
# format's fixture image and an index that covers both. Published as
# ghcr.io/ethereum/execution-specs/hive/<simulator>. The tag selects the version
# of the tests, here the fixtures, and the framework follows the branch; the
# execute counterpart is Dockerfile.execute. The fixture image is the base layer
# so that it is shared by digest between every simulator image built from the
# same release. Because the base is a data-only image, the runtime
# configuration of the repository image is restated below.
# See docs/running_tests/hive/images/.
#
# Build with packages/testing/docker/hive/build.sh, or directly:
#
#   docker build -f packages/testing/docker/hive/Dockerfile \
#       --build-arg BASE_REF=ghcr.io/ethereum/execution-specs:sha-abc1234 \
#       --build-arg FIXTURES_REF=ghcr.io/ethereum/execution-specs/fixtures/blockchain_tests_engine:v20.0.2 \
#       --build-arg EEST_SIMULATOR=consume-engine \
#       -t hive/consume-engine:local packages/testing/docker/hive
# Both are required: the repository and fixture images carry no channel tags.
ARG BASE_REF
ARG FIXTURES_REF
# The fixture image of the second format; only `second-format` reads it.
ARG EXTRA_FIXTURES_REF=${FIXTURES_REF}

FROM ${BASE_REF} AS base

FROM ${FIXTURES_REF} AS consume
COPY --from=base / /
COPY entrypoint.sh /usr/local/bin/eels-simulator
COPY legacy_build.sh /usr/local/bin/eels-legacy-build

ARG EEST_SIMULATOR
ARG EEST_GIT_SHA=""
ARG EEST_GIT_REF=""
ARG EEST_FIXTURES_RELEASE=""
ARG EEST_REPOSITORY="ethereum/execution-specs"

ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 \
    UV_PYTHON_DOWNLOADS=never \
    FIXTURES=/fixtures \
    EEST_SIMULATOR=${EEST_SIMULATOR} \
    EEST_GIT_SHA=${EEST_GIT_SHA} \
    EEST_GIT_REF=${EEST_GIT_REF} \
    EEST_FIXTURES_RELEASE=${EEST_FIXTURES_RELEASE}

LABEL org.opencontainers.image.source="https://github.com/${EEST_REPOSITORY}" \
      org.opencontainers.image.revision="${EEST_GIT_SHA}" \
      org.opencontainers.image.version="${EEST_GIT_REF}" \
      org.ethereum.eest.simulator="${EEST_SIMULATOR}" \
      org.ethereum.eest.fixtures-release="${EEST_FIXTURES_RELEASE}"

WORKDIR /execution-specs/packages/testing
ENTRYPOINT ["eels-simulator"]

# A second fixture format: its directory, and an index that lists the test
# cases of both formats. Both fixture images come from the same release, so
# the rest of .meta is the same in each.
FROM ${EXTRA_FIXTURES_REF} AS extra_fixtures

FROM base AS merged_index
COPY merge_index.py /merge_index.py
RUN --mount=type=bind,from=consume,source=/fixtures/.meta,target=/first \
    --mount=type=bind,from=extra_fixtures,source=/fixtures/.meta,target=/second \
    python3 /merge_index.py /first/index.json /second/index.json /out/index.json

FROM consume AS second-format
ARG EXTRA_FORMAT
COPY --from=extra_fixtures /fixtures/${EXTRA_FORMAT} /fixtures/${EXTRA_FORMAT}
COPY --from=merged_index /out/index.json /fixtures/.meta/index.json

# The default target: a simulator that consumes one format.
FROM consume
