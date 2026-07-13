FROM ubuntu:22.04 AS runtime-base

ARG DEBIAN_FRONTEND=noninteractive

RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        python3 \
        python3-venv \
        jq \
        procps \
        libegl1 \
        libgl1-mesa-dri \
        mesa-utils

RUN curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
        -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/gazebo-stable.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gz-tools2 \
        gz-sim8-cli \
        gz-transport13-cli \
        libgz-sim8-plugins \
        libgz-rendering8-ogre2 \
        sdformat14-sdf \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgz-physics7-dartsim \
    && ln -s libgz-physics7-dartsim-plugin.so.7 \
        /usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins/libgz-physics7-dartsim-plugin.so \
    && ln -s libgz-physics7-dartsim-plugin.so.7 \
        /usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins/libgz-physics-dartsim-plugin.so \
    && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen \
    GZ_SIM_RENDER_ENGINE_SERVER=ogre2 \
    GZ_RENDERING_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins \
    GZ_SIM_PHYSICS_ENGINE_PATH=/usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins \
    GZ_SIM_RESOURCE_PATH=/workspace/sgcf_nrmp_project/gazebo/models:/workspace/sgcf_nrmp_project/gazebo

WORKDIR /workspace

CMD ["bash"]

FROM runtime-base AS abi8-plugin-alias

RUN set -eux; \
    target="/usr/lib/x86_64-linux-gnu/libgz-rendering8-ogre2.so.8"; \
    plugin_dir="/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins"; \
    alias="${plugin_dir}/libgz-rendering-ogre2.so"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8-ogre2)" = "8.2.3-1~jammy"; \
    test -e "${target}"; \
    test -r "${target}"; \
    echo "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef  ${target}" | sha256sum -c -; \
    test -d "${plugin_dir}"; \
    test ! -e "${alias}"; \
    ln -s "${target}" "${alias}"; \
    test -L "${alias}"; \
    test -e "${alias}"; \
    test "$(readlink -f "${alias}")" = "$(readlink -f "${target}")"; \
    mkdir -p /usr/local/share/sgcf/compat; \
    printf '%s\n' \
      '{' \
      '  "type": "LOCAL_PACKAGING_COMPATIBILITY_SHIM",' \
      '  "ownership": "NOT_OWNED_BY_DEBIAN_PACKAGE",' \
      '  "abi_policy": "ABI_LOCKED_TO_GZ_RENDERING_8",' \
      '  "logical_name": "libgz-rendering-ogre2.so",' \
      '  "target_soname": "libgz-rendering8-ogre2.so.8",' \
      '  "gz_rendering_abi": 8,' \
      '  "runtime_package": "libgz-rendering8-ogre2",' \
      '  "runtime_version": "8.2.3-1~jammy",' \
      '  "reason": "Jammy OSRF package lacks the unversioned engine-plugin alias expected by gz-rendering8 loader",' \
      '  "scope": "Stage 11B Gazebo Docker runtime only"' \
      '}' \
      > /usr/local/share/sgcf/compat/gz-rendering8-ogre2-alias.json

FROM runtime-base AS hlms-media-fix

ARG HLMS_PACKAGE_URL="https://osrf-distributions.s3.us-east-1.amazonaws.com/gz-rendering/releases/libgz-rendering8-ogre2-dev_8.2.3-1~jammy_amd64.deb"
ARG HLMS_PACKAGE_FILENAME="libgz-rendering8-ogre2-dev_8.2.3-1~jammy_amd64.deb"
ARG HLMS_PACKAGE_SHA256="f7963e5c70dc933d5c3e402de6491a28b22e7229ce918bec69f0fc7a69f1df6b"

RUN set -eux; \
    package_file="/tmp/${HLMS_PACKAGE_FILENAME}"; \
    plugin_dir="/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins"; \
    logical_alias="${plugin_dir}/libgz-rendering-ogre2.so"; \
    media_root="/usr/share/gz/gz-rendering8/ogre2/media"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8)" = "8.2.3-1~jammy"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8-ogre2)" = "8.2.3-1~jammy"; \
    test ! -e "${logical_alias}"; \
    curl --fail --location --silent --show-error --retry 5 \
      --proto '=https' --tlsv1.2 \
      --output "${package_file}" "${HLMS_PACKAGE_URL}"; \
    echo "${HLMS_PACKAGE_SHA256}  ${package_file}" | sha256sum -c -; \
    test "$(dpkg-deb --field "${package_file}" Package)" = "libgz-rendering8-ogre2-dev"; \
    test "$(dpkg-deb --field "${package_file}" Version)" = "8.2.3-1~jammy"; \
    test "$(dpkg-deb --field "${package_file}" Architecture)" = "amd64"; \
    apt-get update; \
    apt-get install -y --no-install-recommends "${package_file}"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8-ogre2-dev)" = "8.2.3-1~jammy"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8)" = "8.2.3-1~jammy"; \
    test "$(dpkg-query -W -f='${Version}' libgz-rendering8-ogre2)" = "8.2.3-1~jammy"; \
    test -L "${logical_alias}"; \
    test "$(readlink -f "${logical_alias}")" = "${plugin_dir}/libgz-rendering8-ogre2.so.8.2.3"; \
    echo "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef  $(readlink -f "${logical_alias}")" | sha256sum -c -; \
    dpkg -S "${logical_alias}" | grep -q '^libgz-rendering8-ogre2-dev:'; \
    test -s "${media_root}/Hlms/Unlit/GLSL/PixelShader_ps.glsl"; \
    test -s "${media_root}/Hlms/Unlit/GLSL/VertexShader_vs.glsl"; \
    test -s "${media_root}/Hlms/Pbs/GLSL/PixelShader_ps.glsl"; \
    test -s "${media_root}/Hlms/Terra/GLSL/PixelShader_ps.glsl"; \
    test -s "${media_root}/Hlms/Gz/Pbs/500.GzPbsStructs_piece_all.any"; \
    test -s "${media_root}/materials/scripts/GpuRays.compositor"; \
    test -s "${media_root}/materials/scripts/wide_angle_camera.compositor"; \
    dpkg -S "${media_root}/Hlms/Unlit/GLSL/PixelShader_ps.glsl" | grep -q '^libgz-rendering8-ogre2-dev:'; \
    dpkg -S "${media_root}/materials/scripts/GpuRays.compositor" | grep -q '^libgz-rendering8-ogre2-dev:'; \
    rm -f "${package_file}"; \
    rm -rf /var/lib/apt/lists/*

ENV GZ_RENDERING_RESOURCE_PATH=/usr/share/gz/gz-rendering8

FROM runtime-base AS default
