from io import StringIO

from pyinfra.operations import files, systemd

DOCKER_OVERRIDE_CONTENT = """\
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock -H tcp://localhost:2375
"""


def main():
    tweak_docker_service()


def tweak_docker_service():
    """
    Create a systemd override file for the Docker service to set the default
    cgroup driver to systemd.
    """
    files.directory(
        name="Create directory for Docker service override",
        path="/etc/systemd/system/docker.service.d/",
        present=False,
    )
    files.put(
        name="Create docker service override file",
        src=StringIO(DOCKER_OVERRIDE_CONTENT),
        dest="/etc/systemd/system/docker.service.d/override.conf",
    )
    # systemd.daemon_reload(
    #     name="Reload systemd to apply Docker service override",
    # )
    systemd.service(
        name="Restart docker service",
        service="docker",
        restarted=True,
        daemon_reload=True,
    )


main()
