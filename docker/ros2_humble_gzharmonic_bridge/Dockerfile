# Docker BuildKit does not accept a bare local image ID in FROM.  This alias is
# created only after verifying that it resolves to the immutable ID documented
# in package_lock_manifest.json.
FROM sgcf-ros2-humble-base:4cbeac7831833

ARG DEBIAN_FRONTEND=noninteractive
RUN curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
      -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && printf '%s\n' \
      'deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable jammy main' \
      > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ros-humble-ros-gzharmonic \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=humble
ENV ROS_DOMAIN_ID=42
ENV GZ_PARTITION=sgcf_stage11ca
WORKDIR /workspace
CMD ["bash"]
