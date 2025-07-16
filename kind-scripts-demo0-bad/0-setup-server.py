"""
Minimal recipe to deploy
- full docker dependencies and registry

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 0-setup-server.py
"""

import io

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.facts.hardware import Ipv4Addrs
from pyinfra.facts.server import LsbRelease, User
from pyinfra.operations import apt, docker, files, git, server, systemd
from pyinfra.operations import server
from pyinfra.facts.files import Directory
from pyinfra.facts.server import Command

from common import check_server
from constants import GITS, HDAR_URL, REGISTRY_PORT

BASE_APT_PACKAGES = [
    "ca-certificates",
    "lsb-release",
    "curl",
    "wget",
    "tar",
    "gnupg",
    "vim",
    "build-essential",
    "python3-requests",
    "git",
]

DOCKER_APT_PACKAGES = [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    # "docker-buildx-plugin",
    # "docker-compose-plugin",
]

DOCKER_CONF = """\n
{
  "insecure-registries": ["___ip___:5000", "127.0.0.1:5000"],
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m"
  },
  "storage-driver": "overlay2"
}
"""


def main() -> None:
    check_server()
    delete_kind_clusters()
    kill_docker_containers()
    remove_mk8s()
    update_server()
    setup_server()
    configure_server_limits()
    install_go()
    install_uv()
    install_docker()
    make_hdarctl()
    start_docker_registry()


def delete_kind_clusters() -> None:
    fact = host.get_fact(File, "/usr/local/bin/kind")
    if fact:
        return
    server.shell(
        name="stop running kind clusters",
        commands="kind get clusters | xargs -I {} kind delete cluster --name {} || true",
    )


def kill_docker_containers() -> None:
    fact = host.get_fact(File, "/usr/bin/docker")
    if fact:
        return
    server.shell(
        name="stop running containers",
        commands=[
            "systemctl stop docker.service"
            "systemctl stop docker.socket"
            "/bin/yes | docker system prune -a --volumes"
            "systemctl start docker || true"
        ],
    )


def remove_mk8s() -> None:
    server.shell(
        name="remove .karmada and .kube configurations",
        commands=["rm -fr /root/.karmada", "rm -fr /root/.kube"],
    )
    fact = host.get_fact(File, "/snap/bin/microk8s")
    if fact:
        return
    server.shell(
        name="Stop and remove any remaining microk8s",
        commands="snap remove --purge microk8s || true",
    )


def update_server() -> None:
    apt.update(name="Update apt cache")
    apt.upgrade(name="Upgrade system packages")


def setup_server() -> None:
    packages = BASE_APT_PACKAGES
    apt.packages(
        name="Install base packages",
        packages=packages,
    )


def configure_server_limits() -> None:
    server.shell(
        name="Increase files limit",
        commands=[
            "sysctl fs.inotify.max_user_watches=500000",
            "sysctl fs.inotify.max_user_instances=2048",
            "sysctl fs.inotify.max_queued_events=32768",
        ],
    )
    files.block(
        name="Increase files limit in /etc/sysctl.conf",
        path="/etc/sysctl.conf",
        content="fs.inotify.max_user_watches=500000\nfs.inotify.max_user_instances=2048\nfs.inotify.max_queued_events=32768",
    )
    files.block(
        name="Increase files limit in /etc/security/limits.conf",
        path="/etc/security/limits.conf",
        content="fs.* soft    nofile    999999\n* hard    nofile    999999\nroot     soft    nofile    999999\nroot     hard    nofile    999999",
    )


#
# Go
#
def install_go() -> None:
    apt.ppa(
        name="Add the Go ppa",
        src="ppa:longsleep/golang-backports",
    )
    apt.packages(
        name="Install Go packages",
        packages=["golang-go"],
        update=True,
    )


#
# uv
#
def install_uv() -> None:
    fact = host.get_fact(File, "/usr/bin/uv")
    if not fact:
        server.shell(
            name="install uv",
            commands=["curl -LsSf https://astral.sh/uv/install.sh | sh"],
        )
        server.shell(
            name="copy uv to /usr/bin",
            commands=[
                "cp /root/.local/bin/uv /usr/bin/uv",
            ],
        )


#
# Docker
#
def install_docker() -> None:
    apt.key(
        name="Add the Docker apt gpg key",
        src="https://download.docker.com/linux/ubuntu/gpg",
    )

    lsb_info = host.get_fact(LsbRelease)
    distro = lsb_info["id"].lower()
    code_name = lsb_info["codename"]

    apt.repo(
        name="Add Docker repo",
        src=f"deb https://download.docker.com/linux/{distro} {code_name} stable",
    )

    packages = DOCKER_APT_PACKAGES
    apt.packages(
        name="Install Docker packages",
        packages=packages,
        update=True,
    )

    user = host.get_fact(User)
    server.user(
        name=f"give docker group to {user!r}",
        user=user,
        groups=["docker"],
    )


def make_hdarctl():
    HDACTL = "/usr/bin/hdarctl"
    REPO = f"{GITS}/hdar"

    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )

    server.shell(
        name="Clone/pull HDAR repository if needed",
        commands=[
            f"[ -x {HDACTL} ] || [ -d {REPO} ] || git clone {HDAR_URL} {REPO}",
            f"cd  {REPO} && git pull",
        ],
    )

    workdir = f"{REPO}/components/hdar-ctl"
    server.shell(
        name="Build HDAR if needed",
        # commands=f"""cd {workdir} && [ -x {HDACTL} -a $({GIT_LAST}) -gt {LAST_KNOWN} ] && {{
        #         CGO_ENABLED=0 go build -a -installsuffix cgo -o hdarctl .
        #         f"{workdir}/hdarctl -h",
        #         f"cp {workdir}/hdarctl {HDACTL}",
        #     }} || true
        #     """,
        commands=f"""[ ! -x {HDACTL} ] && cd {workdir} && {{
                CGO_ENABLED=0 go build -a -installsuffix cgo -o hdarctl .
                f"{workdir}/hdarctl -h",
                f"cp {workdir}/hdarctl {HDACTL}",
            }} || true
            """,
    )


def start_docker_registry() -> None:
    # server.shell(
    #     name="start docker registry",
    #     commands=[
    #         f"docker run -d -p {REGISTRY_PORT}:5000 --restart=always --name registry registry:latest || true"
    #     ],
    # )

    docker.container(
        name="Deploy docker registry",
        container="registry",
        image="registry:latest",
        ports=[f"{REGISTRY_PORT}:5000"],
    )

    ips = host.get_fact(Ipv4Addrs)
    eth0 = ips["eth0"][0]
    config = DOCKER_CONF.replace("___ip___", eth0)
    files.put(
        name="Put file /etc/docker/daemon.json",
        src=io.StringIO(config),
        dest="/etc/docker/daemon.json",
    )

    systemd.service(
        name="restart docker daemon",
        service="docker",
        restarted=True,
    )

    result = server.shell(
        name="check containers",
        commands=["docker container ls -a"],
    )
    print(result)


main()
