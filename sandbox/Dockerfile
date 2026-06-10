# Minimal kubectl executor for Sentinel-X sandbox (W6).
# Offline / mirror-friendly: copy host kubectl before build (not bitnami from docker.io):
#   cp "$(command -v kubectl)" sandbox/kubectl && chmod +x sandbox/kubectl
#   docker build -t sentinel-x-sandbox:latest sandbox/
#
# Base image matches MCP compose (python:3.12-slim) so servers with daocloud mirror need no extra pulls.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY kubectl /usr/local/bin/kubectl
RUN chmod +x /usr/local/bin/kubectl

# Run as root so a root-only host kubeconfig bind-mount (k3s.yaml mode 600) remains readable.
ENTRYPOINT ["kubectl"]
