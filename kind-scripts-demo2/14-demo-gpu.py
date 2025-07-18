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

HDAG_YAML = f"{DEMO_DIR}/hdag/hdag.yaml"
HDAG_YAML_CONTENT = """\
hdaGraph:
  imVersion: 0.4.0
  id: gpu-offloading-graph
  version: "1.1.0"
  designer: Abilian
  description: A demo application to showcase GPU-based placement.
  hdaGraphIntent:
    security: # Either colocation either VO-related security either app-graph deployed using the same Blueprint
      enabled: False
    highAvailability: # Application graph is not considered for reconfigurations. Placement is final
      enabled: true
      minReplicasOverall: 1 # SMO could ensure at least this many total, H3NI scaler refines
      maxReplicasOverall: 10 # Global cap
    highPerformance: # Defined end-to-end for all services. If selected, overwrites the per service latency qos intent
      enabled: False
    energyEfficiency: # Cost reduction of cloud-deployed services
      enabled: False
  services:
    - id: web-frontend
      deployment:
        trigger:
          auto:
            dependencies: []
        intent:
          network:
            deviceProximity: # Only relevant for the VO
              enabled: False # If true, enable TSN
            latencies:
              - connectionPoint: "" # Relevant for the next service in the application graph
                qos: "best-effort"
                # "ultralow"    - under 10ms
                # "low"         - 1hop maximum
                # "best-effort" - default value
          compute:
            cpu: "small"
            ram: "small"
            storage: "small"
            gpu:
              # Explicitly does NOT need a GPU
              enabled: False
          coLocation: []
            #- id: ml-inference
          #   groundedGraphId: UUID
          # This service needs to connect to the ml-inference service
          connectionPoints: ["ml-inference"]
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
            deviceProximity: # Only relevant for the VO
              enabled: False # If true, enable TSN
            latencies:
              - connectionPoint: "" # Relevant for the next service in the application graph
                qos: "best-effort"
                # "ultralow"    - under 10ms
                # "low"         - 1hop maximum
                # "best-effort" - default value
          compute:
            cpu: "medium"
            ram: "medium"
            storage: "small"
            gpu:
               # Explicitly REQUIRES a GPU
               enabled: True
          coLocation: []
            #- id: ml-inference
            #   groundedGraphId: UUID
          connectionPoints: []
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
    list_images_in_registry()
    tune_hdag_yaml()
    mk_change_ips()
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


def list_images_in_registry():
    result = server.shell(
        name="List images in registry",
        commands=f"curl -X GET {REGISTRY}/v2/_catalog",
        _get_pty=True,
    )
    python.call(
        name="List images in registry (result)",
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
