"""Karmada helper class and utility functions."""

from kubernetes import client, config
from kubernetes.utils import parse_quantity

from utils.helpers import format_memory


class KarmadaHelper:
    """Karmada helper class."""

    def __init__(self, config_file_path, namespace="default"):
        self.namespace = namespace
        self.config_file_path = config_file_path

        KARMADA_CONTEXT_NAME = "karmada-apiserver"

        try:
            config.load_kube_config(
                config_file=self.config_file_path, context=KARMADA_CONTEXT_NAME
            )
            print(f"Successfully loaded kubeconfig for context: {KARMADA_CONTEXT_NAME}")
        except config.ConfigException as e:
            print(
                f"ERROR: Failed to load Karmada kubeconfig context '{KARMADA_CONTEXT_NAME}': {e}"
            )
            print(
                "Check ~/.kube/karmada-apiserver.config file has the 'karmada-apiserver' context."
            )
            raise

        self.custom_api = client.CustomObjectsApi()
        self.v1_api_client = client.AppsV1Api()

    def get_cluster_info(self):
        group = "cluster.karmada.io"
        version = "v1alpha1"
        plural = "clusters"

        clusters = self.custom_api.list_cluster_custom_object(group, version, plural)

        result = {}
        for cluster in clusters["items"]:
            cluster_name = cluster["metadata"]["name"]
            allocatable = cluster["status"]["resourceSummary"]["allocatable"]
            allocated = cluster["status"]["resourceSummary"]["allocated"]

            total_cpu = parse_quantity(allocatable["cpu"])
            allocated_cpu = parse_quantity(allocated["cpu"])

            total_memory = parse_quantity(allocatable["memory"])
            allocated_memory = parse_quantity(allocated["memory"])

            status = next(
                (
                    cond["status"]
                    for cond in cluster["status"]["conditions"]
                    if cond["reason"] == "ClusterReady"
                ),
                None,
            )
            availability = True if status == "True" else False

            result[cluster_name] = {
                "total_cpu": float(total_cpu),
                "allocated_cpu": float(allocated_cpu),
                "remaining_cpu": float(total_cpu - allocated_cpu),
                "total_memory_bytes": format_memory(total_memory),
                "allocated_memory_bytes": format_memory(allocated_memory),
                "remaining_memory_bytes": format_memory(
                    total_memory - allocated_memory
                ),
                "availability": availability,
            }

        return result

    def get_desired_replicas(self, name):
        """Returns the desired number of replicas for the specified deployment."""

        response = self.v1_api_client.read_namespaced_deployment_scale(
            name, self.namespace
        )
        return response.spec.replicas

    def get_replicas(self, name):
        """Returns the current number of replicas for the specified deployment."""

        response = self.v1_api_client.read_namespaced_deployment(name, self.namespace)

        return response.status.available_replicas

    def get_cpu_limit(self, name):
        """Returns the current CPU limit for the specific deployment."""

        response = self.v1_api_client.read_namespaced_deployment(name, self.namespace)
        cpu_lim = response.spec.template.spec.containers[0].resources.limits["cpu"]
        if "m" in cpu_lim:
            return float(cpu_lim.replace("m", "")) * 1e-3
        else:
            return float(cpu_lim)

    def scale_deployment(self, name, replicas):
        """Scales the given application to the desired number of replicas"""

        try:
            self.v1_api_client.patch_namespaced_deployment_scale(
                name=name,
                namespace=self.namespace,
                body={"spec": {"replicas": replicas}},
            )
        except Exception as exception:
            print(str(exception))
