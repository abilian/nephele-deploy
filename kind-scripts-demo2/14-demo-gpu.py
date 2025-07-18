"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 14-demo-gpu.py
"""

from pathlib import Path

from pyinfra.operations import files, python, server
import io
from common import log_callback
from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos"
DEMO_DIR = f"{TOP_DIR}/2-gpu-offloading-demo"
SMO_CLI = "/usr/local/bin/smo-cli"

HOST_ADDR = "127.0.0.1"
REGISTRY = f"{HOST_ADDR}:5000"
HDAR = f"http://{HOST_ADDR}:5000"
PROJECT = "demo2"
SMO_URL = f"http://{HOST_ADDR}:8000"
REGISTRY_URL = f"http://{HOST_ADDR}:5000"
GRAPH_NAME = "gpu-offloading-graph"
HDAG_YAML = f"{DEMO_DIR}/hdag.yaml"
# --- Path Definitions ---

BUILD_DIR = f"{DEMO_DIR}/build"
DIST_DIR = f"{DEMO_DIR}/dist"
STATE_DIR = f"{DEMO_DIR}/state"

# --- Artifact and Image Definitions ---

DOCKER_SOURCES = {
    "web-frontend": Path("src/web-frontend"),
    "ml-inference": Path("src/ml-inference"),
}

HDAG_ARTIFACT = {
    "hdag": {
        "path": "hdag",
        "name": "gpu-offloading-graph",
        "version": "1.0.0",
        "tarball": "/root/gits/h3ni-demos/2-gpu-offloading-demo/dist/gpu-offloading-graph-1.0.0.tar.gz",
    }
}
APP_ARTIFACTS = {
    "web-frontend": {
        "path": "web-frontend",
        "name": "web-frontend",
        "version": "0.1.0",
        "tarball": "/root/gits/h3ni-demos/2-gpu-offloading-demo/dist/web-frontend-0.1.0.tar.gz",
    },
    "ml-inference": {
        "path": "ml-inference",
        "name": "ml-inference",
        "version": "0.1.0",
        "tarball": "/root/gits/h3ni-demos/2-gpu-offloading-demo/dist/ml-inference-0.1.0.tar.gz",
    },
}
ALL_ARTIFACTS = {**APP_ARTIFACTS, **HDAG_ARTIFACT}

HDAG_YAML_CONTENT = """\
hdaGraph:
  imVersion: 0.4.0
  id: gpu-offloading-graph
  version: "1.0.0"
  designer: Abilian
  description: A demo application to showcase GPU-based placement.
  # Global intents for the graph, SMO might use these for placement/scaling policies
  hdaGraphIntent:
    # Example: if we want SMO to generally aim for high availability through scaling
    highAvailability:
      enabled: true
      minReplicasOverall: 1 # SMO could ensure at least this many total, H3NI scaler refines
      maxReplicasOverall: 10 # Global cap
    # Other intents like energyEfficiency could be false for this demo
    # to focus purely on load-based scaling.
    energyEfficiency:
      enabled: false
  services:
    - id: web-frontend
      deployment:
        trigger:
          auto:
            dependencies: []
        intent:
          network:
            # This service needs to connect to the ml-inference service
            connectionPoints: ["ml-inference"]
          compute:
            cpu: "small"
            ram: "small"
            gpu:
               # Explicitly does NOT need a GPU
               enabled: False
      artifact:
        ociImage: "oci://127.0.0.1:5000/test/web-frontend"
        ociConfig: { type: App, implementer: HELM }
        ociRun: { name: HELM, version: v3 }
        valuesOverwrite: {}

    - id: ml-inference
      deployment:
        trigger:
          auto:
            dependencies: []
        intent:
          network:
            connectionPoints: []
          compute:
            cpu: "medium"
            ram: "medium"
            gpu:
               # Explicitly REQUIRES a GPU
               enabled: True
      artifact:
        ociImage: "oci://127.0.0.1:5000/test/ml-inference"
        ociConfig: { type: App, implementer: HELM }
        ociRun: { name: HELM, version: v3 }
        valuesOverwrite: {}

"""


def main() -> None:
    pip_install()
    remove_known_graphs()
    mk_dir()
    mk_artifact()
    build_images()
    push_images()
    mk_change_ips()
    tune_hdag_yaml()
    package_artifacts()
    push_artifacts()


def pip_install():
    server.shell(
        name="Deploy -> add python packages",
        commands=[(f"cd {TOP_DIR} && . .venv/bin/activate && uv pip install pyyaml")],
        _get_pty=True,
    )


def remove_known_graphs():
    for name in ("hello-world-graph", "image-detection-graph", "gpu-offloading-graph"):
        server.shell(
            name="Remove prior known graphes",
            commands=[(f"yes | {SMO_CLI} graph remove {name} || true")],
            _get_pty=True,
        )


def mk_dir():
    for directory in (BUILD_DIR, DIST_DIR, STATE_DIR):
        files.directory(
            name=f"mkdir {directory}",
            path=BUILD_DIR,
        )


def mk_artifact():
    script = "mk_artifact_dict.py"
    files.put(
        name=f"Upload script {script}",
        src=script,
        dest=f"{STATE_DIR}/{script}",
        mode="755",
    )
    server.shell(
        name=f"Exec {script}",
        commands=[
            f"cd {TOP_DIR} && . .venv/bin/activate && cd {STATE_DIR} && python {script}"
        ],
        _get_pty=True,
    )


def build_images():
    for name, src_path in DOCKER_SOURCES.items():
        image_name = APP_ARTIFACTS[name]["name"]
        server.shell(
            name=f"Deploy -> Building image: {REGISTRY}/{image_name}",
            commands=[
                (
                    f"cd {TOP_DIR} && . .venv/bin/activate && cd 2-gpu-offloading-demo && "
                    f'docker build -t "{REGISTRY}/{image_name}" {src_path}'
                )
            ],
            _get_pty=True,
        )


def push_images():
    for name, src_path in DOCKER_SOURCES.items():
        image_name = APP_ARTIFACTS[name]["name"]
        server.shell(
            name=f"Deploy -> Pushing image: {REGISTRY}/{image_name}",
            commands=[
                (
                    f"cd {TOP_DIR} && . .venv/bin/activate && cd 2-gpu-offloading-demo && "
                    f'docker push "{REGISTRY}/{image_name}"'
                )
            ],
            _get_pty=True,
        )


def mk_change_ips():
    script = "mk_change_ips.py"
    files.put(
        name=f"Upload script {script}",
        src=script,
        dest=f"{STATE_DIR}/{script}",
        mode="755",
    )
    result = server.shell(
        name=f"Exec {script}",
        commands=[
            f"cd {TOP_DIR} && . .venv/bin/activate && cd {STATE_DIR} && python {script}"
        ],
        _get_pty=True,
    )
    python.call(
        name=f"Exec {script} (result)",
        function=log_callback,
        result=result,
    )


def tune_hdag_yaml():
    files.put(
        name=f"Modify content of {HDAG_YAML}",
        src=io.StringIO(HDAG_YAML_CONTENT),
        dest=HDAG_YAML,
        force=True,
    )


def package_artifacts():
    for artifact in ALL_ARTIFACTS.values():
        path_to_package = Path(BUILD_DIR) / artifact["path"]
        server.shell(
            name=f"Deploy -> Packaging: {path_to_package} into {DIST_DIR}/",
            commands=f"/usr/bin/hdarctl package tar -d {DIST_DIR} {path_to_package}",
            _get_pty=True,
        )


def push_artifacts():
    for artifact in ALL_ARTIFACTS.values():
        tarball = artifact["tarball"]
        server.shell(
            name=f"Deploy -> Pushing {tarball} to {HDAR}/{PROJECT}",
            commands=f"/usr/bin/hdarctl push {tarball} {HDAR}/{PROJECT}",
            _get_pty=True,
        )


def deploy_using_cli():
    """Deploy the application graph using the SMO CLI."""
    artifact_url = f"{REGISTRY_URL}/{PROJECT}/{GRAPH_NAME}"
    server.shell(
        name=f"🚀 Deploying graph '{GRAPH_NAME}' using CLI...",
        commands=f"{SMO_CLI} graph deploy --project {PROJECT} {artifact_url}",
        _get_pty=True,
    )
    result = server.shell(
        name="Show graph list",
        commands=[f"{SMO_CLI} graph list"],
        _get_pty=True,
    )
    python.call(
        name="Show graph list (result)",
        function=log_callback,
        result=result,
    )


main()
