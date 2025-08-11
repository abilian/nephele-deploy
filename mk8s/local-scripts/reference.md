# Karmada CLI Reference

## karmadactl token create

```text
root@nephele-sf-mk8s:~/local-scripts# karmadactl token create --help
This command will create a bootstrap token for you. You can specify the usages for this token, the "time to live" and an
optional human friendly description.

 This should be a securely generated random token of the form "[a-z0-9]{6}.[a-z0-9]{16}".

Options:
    --description='':
	A human friendly description of how this token is used.

    --groups=[system:bootstrappers:karmada:default-cluster-token]:
	Extra groups that this token will authenticate as when used for authentication. Must match
	"\\Asystem:bootstrappers:[a-z0-9:-]{0,255}[a-z0-9]\\z"

    --karmada-context='':
	The name of the kubeconfig context to use

    --kubeconfig='':
	Path to the kubeconfig file to use for CLI requests.

    --print-register-command=false:
	Instead of printing only the token, print the full 'karmadactl register' flag needed to register the member
	cluster using the token.

    --ttl=24h0m0s:
	The duration before the token is automatically deleted (e.g. 1s, 2m, 3h). If set to '0', the token will never
	expire

    --usages=[signing,authentication]:
	Describes the ways in which this token can be used. You can pass --usages multiple times or provide a comma
	separated list of options. Valid options: [signing,authentication]

Usage:
  karmadactl token create [options]

Use "karmadactl options" for a list of global command-line options (applies to all commands).
```

## karmadactl register

```text
root@nephele-sf-mk8s:~# karmadactl register --help
Register a cluster to Karmada control plane with Pull mode.

Examples:
  # Register cluster into karmada control plane with Pull mode.
  # If '--cluster-name' isn't specified, the cluster of current-context will be used by default.
  karmadactl register [karmada-apiserver-endpoint] --cluster-name=<CLUSTER_NAME> --token=<TOKEN>
--discovery-token-ca-cert-hash=<CA-CERT-HASH>

  # UnsafeSkipCAVerification allows token-based discovery without CA verification via CACertHashes. This can weaken
  # the security of register command since other clusters can impersonate the control-plane.
  karmadactl register [karmada-apiserver-endpoint] --token=<TOKEN>  --discovery-token-unsafe-skip-ca-verification=true

Options:
    --cert-expiration-seconds=31536000:
	The expiration time of certificate.

    --cluster-name='':
	The name of member cluster in the control plane, if not specified, the cluster of current-context is used by
	default.

    --cluster-namespace='karmada-cluster':
	Namespace in the control plane where member cluster secrets are stored.

    --cluster-provider='':
	Provider of the joining cluster. The Karmada scheduler can use this information to spread workloads across
	providers for higher availability.

    --cluster-region='':
	The region of the joining cluster. The Karmada scheduler can use this information to spread workloads across
	regions for higher availability.

    --cluster-zones=[]:
	The zones of the joining cluster. The Karmada scheduler can use this information to spread workloads across
	zones for higher availability.

    --context='':
	Name of the cluster context in kubeconfig file.

    --discovery-timeout=5m0s:
	The timeout to discovery karmada apiserver client.

    --discovery-token-ca-cert-hash=[]:
	For token-based discovery, validate that the root CA public key matches this hash (format: "<type>:<value>").

    --discovery-token-unsafe-skip-ca-verification=false:
	For token-based discovery, allow joining without --discovery-token-ca-cert-hash pinning.

    --dry-run=false:
	Run the command in dry-run mode, without making any server requests.

    --enable-cert-rotation=false:
	Enable means controller would rotate certificate for karmada-agent when the certificate is about to expire.

    --karmada-agent-image='docker.io/karmada/karmada-agent:v1.14.2':
	Karmada agent image.

    --karmada-agent-replicas=1:
	Karmada agent replicas.

    --kubeconfig='':
	Path to the kubeconfig file of member cluster.

    -n, --namespace='karmada-system':
	Namespace the karmada-agent component deployed.

    --proxy-server-address='':
	Address of the proxy server that is used to proxy to the cluster.

    --token='':
	For token-based discovery, the token used to validate cluster information fetched from the API server.

Usage:
  karmadactl register [karmada-apiserver-endpoint] [options]

Use "karmadactl options" for a list of global command-line options (applies to all commands).
```

## karmadactl options
```text
root@nephele-sf-mk8s:~/local-scripts# karmadactl options
The following options can be passed to any command:

    --add-dir-header=false:
	If true, adds the file directory to the header of the log messages

    --alsologtostderr=false:
	log to standard error as well as files (no effect when -logtostderr=true)

    --kubeconfig='':
	Paths to a kubeconfig. Only required if out-of-cluster.

    --log-backtrace-at=:0:
	when logging hits line file:N, emit a stack trace

    --log-dir='':
	If non-empty, write log files in this directory (no effect when -logtostderr=true)

    --log-file='':
	If non-empty, use this log file (no effect when -logtostderr=true)

    --log-file-max-size=1800:
	Defines the maximum size a log file can grow to (no effect when -logtostderr=true). Unit is megabytes. If the
	value is 0, the maximum file size is unlimited.

    --log-flush-frequency=5s:
	Maximum number of seconds between log flushes

    --logtostderr=true:
	log to standard error instead of files

    --one-output=false:
	If true, only write logs to their native severity level (vs also writing to each lower severity level; no
	effect when -logtostderr=true)

    --skip-headers=false:
	If true, avoid header prefixes in the log messages

    --skip-log-headers=false:
	If true, avoid headers when opening log files (no effect when -logtostderr=true)

    --stderrthreshold=2:
	logs at or above this threshold go to stderr when writing to files and stderr (no effect when
	-logtostderr=true or -alsologtostderr=true)

    -v, --v=0:
	number for the log level verbosity

    --vmodule=:
	comma-separated list of pattern=N settings for file-filtered logging
```
