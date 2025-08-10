## Karmada CLI Reference

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
