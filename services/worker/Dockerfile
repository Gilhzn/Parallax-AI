# SpatialScan GPU worker — RunPod Serverless image.
# Real pipeline: ffmpeg -> COLMAP (via nerfstudio) -> splatfacto (gsplat) -> .splat
#
# Build (needs NVIDIA toolchain to *run*, not to build):
#   docker build -t spatialscan-worker:gpu -f services/worker/Dockerfile services/worker
#
# RunPod endpoint configuration: see infra/runpod/endpoint.md

FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9"

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3-pip python3.10-dev \
        ffmpeg colmap git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Torch first (pinned to the CUDA base), then nerfstudio (brings gsplat).
RUN pip3 install --no-cache-dir torch==2.1.2 torchvision==0.16.2 \
        --index-url https://download.pytorch.org/whl/cu118 \
    && pip3 install --no-cache-dir nerfstudio runpod

WORKDIR /app
COPY pyproject.toml ./
COPY spatialscan_worker ./spatialscan_worker
RUN pip3 install --no-cache-dir -e .

ENV PIPELINE_MODE=real
CMD ["python3", "-m", "spatialscan_worker.runpod_handler"]
