# syntax=docker/dockerfile:1

FROM sgcf-local/ros2-bridge-base:stage11cc1

ARG AUTHORITATIVE_BASE_IMAGE_ID
ARG PLANNER_LOCK_SHA256

LABEL org.sgcf.authoritative-base-image-id="${AUTHORITATIVE_BASE_IMAGE_ID}" \
      org.sgcf.base-binding-method="verified-local-bootstrap-alias" \
      org.sgcf.planner-lock-sha256="${PLANNER_LOCK_SHA256}"

ENV CUDA_VISIBLE_DEVICES="" \
    NVIDIA_VISIBLE_DEVICES=void \
    SGCF_PLANNER_PYTHON=/opt/sgcf_planner_venv/bin/python

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends python3.10-venv; \
    rm -rf /var/lib/apt/lists/*

COPY planner_runtime_requirements.lock /tmp/planner_runtime_requirements.lock

RUN set -eux; \
    python3 -m venv --system-site-packages /opt/sgcf_planner_venv; \
    /opt/sgcf_planner_venv/bin/python -m pip install \
      --ignore-installed \
      --only-binary=:all: \
      --require-hashes \
      --index-url https://pypi.org/simple \
      --extra-index-url https://download.pytorch.org/whl/cu128 \
      -r /tmp/planner_runtime_requirements.lock; \
    /opt/sgcf_planner_venv/bin/python -m pip check; \
    rm -f /tmp/planner_runtime_requirements.lock

COPY dependency_source_manifest.json /usr/local/share/sgcf/planner-runtime/dependency_source_manifest.json
COPY runtime_entrypoint.sh /usr/local/bin/sgcf-planner-runtime
RUN chmod 0755 /usr/local/bin/sgcf-planner-runtime

ENTRYPOINT ["/usr/local/bin/sgcf-planner-runtime"]
CMD ["python", "-c", "import torch; print(torch.__version__, torch.cuda.is_available())"]
