# /usr/bin/env python

import json
import os
from pathlib import Path

import yaml

GITS = "/root/gits"
TOP_DIR = f"{GITS}/h3ni-demos/"
DEMO_DIR = f"{TOP_DIR}/2-gpu-offloading-demo"
DIST_DIR = f"{TOP_DIR}/2-gpu-offloading-demo/dist"
STATE_DIR = f"{DEMO_DIR}/state"
ARTIF_FILE = f"{STATE_DIR}/artifact.json"
APP_ARTIFACTS = {
    "web-frontend": {},
    "ml-inference": {},
}

HDAG_ARTIFACT = {"hdag": {}}

DOCKER_SOURCES = {
    "web-frontend": Path("src/web-frontend"),
    "ml-inference": Path("src/ml-inference"),
}

# ======
# == Helper Functions & Dynamic Metadata
# ======


def get_chart_info(artifact_dir: Path):
    """Parses Chart.yaml to get name and version."""
    chart_yaml = artifact_dir / "Chart.yaml"
    with chart_yaml.open("r") as f:
        data = yaml.safe_load(f)
    return data["name"], data["version"]


def get_hdag_info(hdag_dir: Path):
    """Parses hdag.yaml to get the graph's id and version."""
    hdag_yaml = hdag_dir / "hdag.yaml"
    with hdag_yaml.open("r") as f:
        data = yaml.safe_load(f)
    return data["hdaGraph"]["id"], data["hdaGraph"]["version"]


os.chdir(DEMO_DIR)


for name in APP_ARTIFACTS:
    path = Path(name)
    chart_name, version = get_chart_info(path)
    APP_ARTIFACTS[name] = {
        "path": str(path),
        "name": chart_name,
        "version": version,
        "tarball": str(Path(DIST_DIR) / f"{chart_name}-{version}.tar.gz"),
    }

hdag_name = list(HDAG_ARTIFACT.keys())[0]
hdag_path = Path(hdag_name)
graph_id, version = get_hdag_info(hdag_path)
HDAG_ARTIFACT[hdag_name] = {
    "path": str(hdag_path),
    "name": graph_id,
    "version": version,
    "tarball": str(Path(DIST_DIR) / f"{graph_id}-{version}.tar.gz"),
}

ALL_ARTIFACTS = {**APP_ARTIFACTS, **HDAG_ARTIFACT}

Path(ARTIF_FILE).write_text(json.dumps(ALL_ARTIFACTS, ensure_ascii=False, indent=4))
