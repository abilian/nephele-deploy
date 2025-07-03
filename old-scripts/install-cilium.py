from pyinfra.operations import server

CILIUM_CLI_VERSION = "v0.18.3"
CLI_ARCH = "amd64"
FILE = f"cilium-linux-{CLI_ARCH}.tar.gz"


def setup_cilium() -> None:
    server.shell(
        name="Setup Cilium",
        commands=[
            "microk8s enable community",
            "microk8s enable cilium",
        ],
    )



def install_cilium() -> None:
    server.shell(
        name="install Cilium",
        commands=[
            "rm -f /usr/local/bin/cilium",
            f"curl -LO https://github.com/cilium/cilium-cli/releases/download/{CILIUM_CLI_VERSION}/{FILE}",
            f"curl -LO https://github.com/cilium/cilium-cli/releases/download/{CILIUM_CLI_VERSION}/{FILE}.sha256sum",
            f"sha256sum --check {FILE}.sha256sum",
            f"tar xzvfC cilium-linux-{CLI_ARCH}.tar.gz /usr/local/bin",
            f"rm -f {FILE}",
            f"rm -f {FILE}.sha256sum",
        ],
        _get_pty=True,
    )
