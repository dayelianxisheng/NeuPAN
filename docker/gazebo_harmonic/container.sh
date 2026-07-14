#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE="sgcf-gazebo-harmonic:local"
CONTAINER="sgcf_gz_harmonic"
FIX_IMAGE="sgcf-gazebo-harmonic:ogre2-fix"
FIX_CONTAINER="sgcf_gz_harmonic_ogre2_fix"
ALIAS_IMAGE="sgcf-gazebo-harmonic:abi8-plugin-alias"
ALIAS_CONTAINER="sgcf_gz_harmonic_abi8_alias"
HLMS_IMAGE="sgcf-gazebo-harmonic:hlms-media-fix"
HLMS_CONTAINER="sgcf_gz_harmonic_hlms_media_fix"
COMMAND="${1:-check}"

# Docker daemon proxy settings cover image pulls, but they are not guaranteed
# to reach Dockerfile RUN instructions.  BuildKit receives explicit proxy args
# and host networking so the host loopback proxy remains reachable.
HTTP_PROXY_URL="${HTTP_PROXY:-${http_proxy:-http://127.0.0.1:7897}}"
HTTPS_PROXY_URL="${HTTPS_PROXY:-${https_proxy:-$HTTP_PROXY_URL}}"
NO_PROXY_VALUE="${NO_PROXY:-${no_proxy:-localhost,127.0.0.1}}"

# The local proxy intermittently returns 502 for Ubuntu archive payloads.
# Fetch Ubuntu packages directly while keeping OSRF / Gazebo downloads on the
# proxy.  Append without discarding any caller-provided exclusions.
for direct_host in archive.ubuntu.com security.ubuntu.com; do
    case ",$NO_PROXY_VALUE," in
        *",$direct_host,"*) ;;
        *) NO_PROXY_VALUE="$NO_PROXY_VALUE,$direct_host" ;;
    esac
done

build_image() {
    local target="$1"
    local image="$2"
    docker build \
        --network=host \
        --build-arg "HTTP_PROXY=$HTTP_PROXY_URL" \
        --build-arg "HTTPS_PROXY=$HTTPS_PROXY_URL" \
        --build-arg "http_proxy=$HTTP_PROXY_URL" \
        --build-arg "https_proxy=$HTTPS_PROXY_URL" \
        --build-arg "NO_PROXY=$NO_PROXY_VALUE" \
        --build-arg "no_proxy=$NO_PROXY_VALUE" \
        --target "$target" \
        -t "$image" \
        "$SCRIPT_DIR"
}

run_container() {
    local image="${1:-$IMAGE}"
    local container="${2:-$CONTAINER}"
    local device_args=()
    if [ -d /dev/dri ]; then
        device_args+=(--device /dev/dri)
    fi
    docker run -d \
        --name "$container" \
        --network host \
        --ipc host \
        "${device_args[@]}" \
        -v "$REPO_ROOT:/workspace" \
        -e QT_QPA_PLATFORM=offscreen \
        -e GZ_SIM_RENDER_ENGINE_SERVER=ogre2 \
        -e GZ_RENDERING_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins \
        -e GZ_RENDERING_RESOURCE_PATH=/usr/share/gz/gz-rendering8 \
        -e GZ_SIM_PHYSICS_ENGINE_PATH=/usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins \
        -e GZ_SIM_RESOURCE_PATH=/workspace/sgcf_nrmp_project/gazebo/models:/workspace/sgcf_nrmp_project/gazebo \
        "$image" sleep infinity
}

ensure_running() {
    if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
        return
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
        docker start "$CONTAINER" >/dev/null
    else
        run_container
    fi
}

ensure_fix_running() {
    if docker ps --format '{{.Names}}' | grep -qx "$FIX_CONTAINER"; then
        return
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "$FIX_CONTAINER"; then
        docker start "$FIX_CONTAINER" >/dev/null
    else
        run_container "$FIX_IMAGE" "$FIX_CONTAINER"
    fi
}

ensure_alias_running() {
    if docker ps --format '{{.Names}}' | grep -qx "$ALIAS_CONTAINER"; then
        return
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "$ALIAS_CONTAINER"; then
        docker start "$ALIAS_CONTAINER" >/dev/null
    else
        run_container "$ALIAS_IMAGE" "$ALIAS_CONTAINER"
    fi
}

ensure_hlms_running() {
    if docker ps --format '{{.Names}}' | grep -qx "$HLMS_CONTAINER"; then
        return
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "$HLMS_CONTAINER"; then
        docker start "$HLMS_CONTAINER" >/dev/null
    else
        run_container "$HLMS_IMAGE" "$HLMS_CONTAINER"
    fi
}

case "$COMMAND" in
    build)
        build_image runtime-base "$IMAGE"
        ;;
    build-ogre2)
        build_image runtime-base "$FIX_IMAGE"
        ;;
    build-abi8-alias)
        build_image abi8-plugin-alias "$ALIAS_IMAGE"
        ;;
    build-hlms-media)
        build_image hlms-media-fix "$HLMS_IMAGE"
        ;;
    create)
        docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
        run_container
        ;;
    create-ogre2)
        docker rm -f "$FIX_CONTAINER" >/dev/null 2>&1 || true
        run_container "$FIX_IMAGE" "$FIX_CONTAINER"
        ;;
    create-abi8-alias)
        docker rm -f "$ALIAS_CONTAINER" >/dev/null 2>&1 || true
        run_container "$ALIAS_IMAGE" "$ALIAS_CONTAINER"
        ;;
    create-hlms-media)
        docker rm -f "$HLMS_CONTAINER" >/dev/null 2>&1 || true
        run_container "$HLMS_IMAGE" "$HLMS_CONTAINER"
        ;;
    check)
        ensure_running
        docker exec "$CONTAINER" bash -lc '
            set -e
            command -v gz
            gz --commands
            gz sim --versions
            gz sdf --versions
            gz topic --help >/dev/null
            gz service --help >/dev/null
            gz model --help >/dev/null
            gz --versions >/dev/null 2>&1 || true
        '
        ;;
    check-ogre2)
        ensure_fix_running
        docker exec "$FIX_CONTAINER" bash -lc '
            set -e
            test "$GZ_RENDERING_PLUGIN_PATH" = "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins"
            test -e "$GZ_RENDERING_PLUGIN_PATH/libgz-rendering8-ogre2.so.8"
            ! ldd "$GZ_RENDERING_PLUGIN_PATH/libgz-rendering8-ogre2.so.8" | grep -q "not found"
            gz sim --versions
            gz sdf --versions
        '
        ;;
    check-abi8-alias)
        ensure_alias_running
        docker exec "$ALIAS_CONTAINER" bash -lc '
            set -e
            alias="$GZ_RENDERING_PLUGIN_PATH/libgz-rendering-ogre2.so"
            test -L "$alias"
            test -e "$alias"
            test "$(readlink -f "$alias")" = "/usr/lib/x86_64-linux-gnu/libgz-rendering8-ogre2.so.8.2.3"
            ! ldd "$(readlink -f "$alias")" | grep -q "not found"
            test -f /usr/local/share/sgcf/compat/gz-rendering8-ogre2-alias.json
            gz sim --versions
            gz sdf --versions
        '
        ;;
    check-hlms-media)
        ensure_hlms_running
        docker exec "$HLMS_CONTAINER" bash -lc '
            set -e
            test "$GZ_RENDERING_PLUGIN_PATH" = "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins"
            test "$GZ_RENDERING_RESOURCE_PATH" = "/usr/share/gz/gz-rendering8"
            alias="$GZ_RENDERING_PLUGIN_PATH/libgz-rendering-ogre2.so"
            test -L "$alias"
            test "$(readlink -f "$alias")" = "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8.2.3"
            dpkg -S "$alias" | grep -q "^libgz-rendering8-ogre2-dev:"
            test -s "$GZ_RENDERING_RESOURCE_PATH/ogre2/media/Hlms/Unlit/GLSL/PixelShader_ps.glsl"
            test -s "$GZ_RENDERING_RESOURCE_PATH/ogre2/media/materials/scripts/GpuRays.compositor"
            gz sim --versions
            gz sdf --versions
        '
        ;;
    shell)
        ensure_running
        docker exec -it "$CONTAINER" bash
        ;;
    shell-ogre2)
        ensure_fix_running
        docker exec -it "$FIX_CONTAINER" bash
        ;;
    shell-abi8-alias)
        ensure_alias_running
        docker exec -it "$ALIAS_CONTAINER" bash
        ;;
    shell-hlms-media)
        ensure_hlms_running
        docker exec -it "$HLMS_CONTAINER" bash
        ;;
    stop)
        docker stop "$CONTAINER"
        ;;
    stop-ogre2)
        docker stop "$FIX_CONTAINER"
        ;;
    stop-abi8-alias)
        docker stop "$ALIAS_CONTAINER"
        ;;
    stop-hlms-media)
        docker stop "$HLMS_CONTAINER"
        ;;
    remove)
        docker rm -f "$CONTAINER"
        ;;
    *)
        echo "Usage: $0 {build|create|check|shell|stop|remove|build-ogre2|create-ogre2|check-ogre2|shell-ogre2|stop-ogre2|build-abi8-alias|create-abi8-alias|check-abi8-alias|shell-abi8-alias|stop-abi8-alias|build-hlms-media|create-hlms-media|check-hlms-media|shell-hlms-media|stop-hlms-media}" >&2
        exit 2
        ;;
esac
