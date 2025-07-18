# /usr/bin/env python
import json
import os
import re
import shutil
from pathlib import Path

import yaml

GITS = "/root/gits"
TOP_DIR = f"{GITS}/h3ni-demos/"
DEMO_DIR = f"{TOP_DIR}/2-gpu-offloading-demo"
DIST_DIR = f"{TOP_DIR}/2-gpu-offloading-demo/dist"
BUILD_DIR = f"{TOP_DIR}/2-gpu-offloading-demo/build"
STATE_DIR = f"{DEMO_DIR}/state"
ARTIF_FILE = f"{STATE_DIR}/artifact.json"
APP_ARTIFACTS = {
    "web-frontend": {},
    "ml-inference": {},
}

HOST_ADDR = "127.0.0.1"
REGISTRY = f"{HOST_ADDR}:5000"
HDAR = f"http://{HOST_ADDR}:5000"
PROJECT = "demo2"
SMO_URL = f"http://{HOST_ADDR}:8000"
REGISTRY_URL = f"http://{HOST_ADDR}:5000"
GRAPH_NAME = "gpu-offloading-graph"


DOCKER_SOURCES = {
    "web-frontend": Path("src/web-frontend"),
    "ml-inference": Path("src/ml-inference"),
}


ALL_ARTIFACTS = json.loads(Path(ARTIF_FILE).read_text())
HDAG_ARTIFACT = {k: v for k, v in ALL_ARTIFACTS.items() if k == "hdag"}
APP_ARTIFACTS = {k: v for k, v in ALL_ARTIFACTS.items() if k != "hdag"}


def change_ips():
    """(Internal) Replaces placeholder IPs and projects in artifact files."""
    print(f"🔧 Patching artifact files with REGISTRY={REGISTRY}, PROJECT={PROJECT}")

    # 1. Copy all source artifacts to the build directory
    for artifact in ALL_ARTIFACTS.values():
        shutil.copytree(
            Path(DEMO_DIR) / artifact["path"],
            Path(BUILD_DIR) / artifact["path"],
            dirs_exist_ok=True,
        )
    print("  - Copied sources to build/ directory.")

    # 2. Modify deployment.yaml files
    for name in APP_ARTIFACTS:
        deployment_path = Path(BUILD_DIR) / name / "templates" / "deployment.yaml"
        if deployment_path.exists():
            content = deployment_path.read_text()
            content = re.sub(r"image: .*/", f"image: {REGISTRY}/", content)
            deployment_path.write_text(content)
            print(f"  - Patched {deployment_path}")

    # 3. Modify hdag.yaml with specific OCI paths for each service
    hdag_yaml_path = Path(BUILD_DIR) / "hdag" / "hdag.yaml"
    content = hdag_yaml_path.read_text()
    for name, info in APP_ARTIFACTS.items():
        # Replace the ociImage path for each specific service
        oci_placeholder = f'ociImage: "oci://.*/{info["name"]}"'
        oci_replacement = f'ociImage: "oci://{REGISTRY}/{PROJECT}/{info["name"]}"'
        content, count = re.subn(oci_placeholder, oci_replacement, content)
        if count > 0:
            print(f"  - Patched OCI path for {info['name']} in {hdag_yaml_path}")
    hdag_yaml_path.write_text(content)


change_ips()
