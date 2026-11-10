#!/usr/bin/env bash
# Run as ec2-user on Amazon Linux 2023. Downloads only official Docker releases.
set -euo pipefail

sudo dnf install -y docker git curl-minimal
sudo systemctl enable --now docker

compose_version=v2.40.3
install_tmp=$(mktemp -d)
trap 'rm -rf -- "$install_tmp"' EXIT
(
  cd "$install_tmp"
  release="https://github.com/docker/compose/releases/download/$compose_version"
  curl -fsSLO "$release/docker-compose-linux-x86_64"
  curl -fsSLO "$release/docker-compose-linux-x86_64.sha256"
  sha256sum -c docker-compose-linux-x86_64.sha256
  sudo install -D -m 0755 docker-compose-linux-x86_64 /usr/local/lib/docker/cli-plugins/docker-compose
)
sudo docker compose version

project_dir=/home/ec2-user/explain-this-codebase
if [[ ! -e "$project_dir" ]]; then
  git clone https://github.com/arshtomar583/Mini-project-.git "$project_dir"
else
  test "$(git -C "$project_dir" remote get-url origin)" = 'https://github.com/arshtomar583/Mini-project-.git'
  git -C "$project_dir" pull --ff-only
fi
cd "$project_dir"
sudo docker compose -f deploy/aws/compose.yaml config --quiet

# Amazon Linux's Docker 25 package has no Buildx plugin. Its built-in builder
# supports this multi-stage Dockerfile and an explicit build memory bound.
sudo env DOCKER_BUILDKIT=0 docker build --memory=512m -t explain-codebase-app:latest .
sudo docker compose -f deploy/aws/compose.yaml up -d --no-build app
python3 scripts/smoke_deployment.py http://127.0.0.1:10000 --wait-seconds 30 --github
sudo docker compose -f deploy/aws/compose.yaml ps
