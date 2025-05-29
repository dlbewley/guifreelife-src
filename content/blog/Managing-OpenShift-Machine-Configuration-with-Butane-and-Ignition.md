---
title: "Managing Readable OpenShift MachineConfigs with Butane"
date: 2025-05-29
banner: /images/machineconfigs-butane.png
layout: post
mermaid: false
asciinema: true
tags:
  - automation
  - openshift
  - kubernetes
  - operators
description: The OpenShift Machine Configuration Operator applies configuration changes to nodes using a syntax called Ignition, but managing base64 encoded text can be challenging. Using plain text doesn't have to be difficult."
---

The OpenShift Machine Configuration Operator applies configuration changes to to nodes using a syntax called [Ignition][1],
but managing base64 encoded text can be challenging. What if I told you that you can use plain text and normal files?

<!--more-->

# Machine Config Operator

OpenShift manages the operating system running on cluster nodes using the [Machine Config Operator][6] (MCO).

Components of the MCO include the Machine Config Sever (MCS) which provides ignition files to clients over HTTPS, and an agent running on each node called the Machine Config Daemon (MCD).

The MCD detects drift in the local machine configuration from the desired configuration expressed by the MCS.

# Machine Config Pools

There are a number of settings and artifacts created during the OpenShift cluster installation process. Settings like the kubelet configuration or artifacts like ssh keys. These are all formatted into MachineConfig resources and correlated to nodes by way of Machine Config Pools (MCPs). By default there will be a pool for the control plane and a pool for the worker nodes.

All the MachineConfigs for a given pool are rendered into one large JSON blob for publishing by the MCS.  Nodes are associated to MCPs by matching labels. You may need to create unique MCPs for heterogenous hardware, or you may just need to add some configuration to an existing MCP to enable multipath I/O or some other service.


> {{< collapsable prompt=" **Truncated Worker MCP Example**" collapse=false md=true >}}
  MachineConfigs are associated with the pool using `machineConfigSelectors`, and nodes are assocatied with a pool by `nodeSelctors`.
  ```yaml {{hl_lines=[8,11]}}
  apiVersion: machineconfiguration.openshift.io/v1
  kind: MachineConfigPool
  metadata:
    name: worker
  spec:
    configuration:
      ...
    machineConfigSelector:
      matchLabels:
        machineconfiguration.openshift.io/role: worker
    nodeSelector:
      matchLabels:
        node-role.kubernetes.io/worker: ""
  ```
  {{< /collapsable>}}

## MachineConfigs

Because an Ignition file is JSON formatted, a MachineConfig must be encoded into a safe representation. Here is what an example MachineConfiguration file looks like.

At a glance, maybe you can tell it is writing a file but you can't easily read what's in it or make changes to it.

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: dne
  name: 99-worker-message
spec:
  config:
    ignition:
      version: 3.4.0
    storage:
      files:
        - contents:
            compression: ""
            source: data:,Hello%2C%20world!%0A
          mode: 420
          overwrite: true
          path: /tmp/message.txt
```

This text is URL encoded, but you will find base64 encoding used to for longer strings. Let's decode the mystery text.

```bash
$ cat `which urldecode`
#!/bin/bash
python3 -c "import sys, urllib.parse as ul; print(ul.unquote_plus(sys.argv[1]))" $*

$ urldecode 'Hello%2C%20world!%0A'
Hello, world!
```

OK, that example was pretty clearly writing "Hello, world!", but can you read this one:

> {{< collapsable prompt=" **👹 Uglier Example**" collapse=true md=true >}}
  In this example, the `/etc/multipath.conf` file contents are gzipped and then base64 encoded.
  ```yaml
  apiVersion: machineconfiguration.openshift.io/v1
  kind: MachineConfig
  metadata:
    labels:
      machineconfiguration.openshift.io/role: worker
    name: 99-worker-multipathd-config
  spec:
    config:
      ignition:
        version: 3.4.0
      storage:
        files:
          - contents:
              compression: gzip
              source: data:;base64,H4sIAAAAAAAC/1SPQYorMQxE9zpFgbf5yT4H+NdoPLYci3HbjSUnE0LuPnSSaeiVoBD1XjkkKXzGiS2c5lFMFm/5GFpN5PC/dXiENi+FjVFEDS3BMiNy8qMY1k+5jO5NWsXVl8F6QB8VLJa5n8kBWzH+GTm0vgsjNLfbp2mj/sH2gLasR3ETy4isocs7OUCZVzNy2O/A7CsWf+EjfaQVDwKGcp9SF66x3KfqZ1bcWQlIUuO0lbzTJzlIDWXEdftVAitS6+CfUIZKq+ReBvRVfPh+yT/o+RsAAP//NbWKB18BAAA=
            mode: 420
            path: /etc/multipath.conf
            user:
              name: root
      systemd:
        units:
          - enabled: true
            name: multipathd.service
  ```
  {{</collapsable>}}

# 🔥 Butane

Fortunately it is possible to write MachineConfigs in a more legible format called [Butane][4].

With Butane you might put the text in plainly like this:

```yaml  {hl_lines=[14,15]}
variant: openshift
version: 4.18.0
metadata:
  name: 99-worker-message
  labels:
    machineconfiguration.openshift.io/role: dne

storage:
  files:
    - path: /tmp/message.txt
      mode: 0644
      overwrite: true
      contents:
        inline: |-
          Goodbye, moon!
```

Or you could reference a stand alone file.

```yaml  {hl_lines=[2]}
      contents:
        local: message.txt
```

This is particularly helpful if you are managing a complex configuration file like [`multipath.conf`][8]. Just place the multipath.conf into a folder called `inc/` and generate the machineconfig using the [butane command][9].

**Generate a MachineConfig with Butane**

```bash
cp multipath.conf inc/
butane -d inc < 99-worker-multipath.bu > 99-worker-multipah.yaml 
```

# Generating MachineConfigs 

Once you adopt butane you will then need a scalable way to maintain your MachineConfigs to make sure they are always up to date.  The following [Makefile][10] from [this repo][2] provides a way to do that.

The MachineConfigs stored in `*.yaml` files are generated from the Butane `butane/*.bu` files.  Any configuration files or scripts that are included from the `inc/` directory are detected by the Makefile and noted in dependencies files in `.deps/`.

When you run `make`, these dependincies are checked. If either an included file or a Butane file changes, then the MachineConfig file is automatically flagged as stale and regenerated.

> **⭐ Pro Tip** Because dependencies are ephemeral and generated on the fly, there isn't need to store them in git. You can safely add them to `.gitignore`. 

## Makefile

```make  {linenos=inline}
BUTANES = $(wildcard butane/*.bu)
MACHINECONFIGS = $(BUTANES:butane/%.bu=%.yaml)
INCLUDES_DIR = inc
DEPS_DIR = .deps

# Enumerate all files that might be included
INCLUDE_FILES = $(wildcard $(INCLUDES_DIR)/*)

# Create deps directory if it doesn't exist
$(shell mkdir -p $(DEPS_DIR))

all: $(MACHINECONFIGS)

# Generate dependencies for each butane file
$(DEPS_DIR)/%.d: butane/%.bu
	@echo "Generating dependencies for $<"
	@printf "%s: %s %s\n" "$*.yaml" "$<" "$$(grep -o 'local: [^[:space:]]*' $< | cut -d' ' -f2 | sed 's|^|$(INCLUDES_DIR)/|' | tr '\n' ' ' | sed 's/ *$$//')" > $@

# Include all dependency files
-include $(BUTANES:butane/%.bu=$(DEPS_DIR)/%.d)

# Each machineconfig ends in yaml and depends on the same named file ending in bu
%.yaml: butane/%.bu
	butane -d $(INCLUDES_DIR) < $< > $@

# rm the machineconfigs and dependency files generated from butane files
clean:
	rm -f $(MACHINECONFIGS)
	rm -rf $(DEPS_DIR)
```
_[Source][10]_

# Demo 

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Managing MachineConfig resources with Butane and Make</p>
  {{< asciinema key="machineconfig-20250529" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}

# Summary

Leave the base64 encoding to the robots 🤖. Make things easier on yourself. Write in plain text with Butane 🔥!

# References

* [Demo Github Repo][2]
* [Demo Recording][3]
* [CoreOS Ignition Specification][1]
* [OpenShift 4.18 Butane Spec][5]
* [OpenShift Machine Config Operator][6] - Github
* [OpenShift 4.18 Machine Config Docs][7]
* [Download Butane][9]

[1]: <https://coreos.github.io/ignition/specs/> "CoreOS Ignition Spec"
[2]: <https://github.com/dlbewley/demo-machineconfig/> "Demo Github Repo"
[3]: <https://asciinema.org/a/721227> "Asciinema Demo Recording"
[4]: <https://coreos.github.io/butane/> "Butane"
[5]: <https://coreos.github.io/butane/config-openshift-v4_18/> "OpenShift 4.18 Butane Spec"
[6]: <https://github.com/openshift/machine-config-operator> "OpenShift Machine Config Operator"
[7]: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/machine_configuration/machine-config-index> "OpenShift 4.18 Machine Config Docs"
[8]: <https://github.com/dlbewley/demo-machineconfig/blob/main/machineconfigs/inc/multipath.conf> "multipath.conf"
[9]: <https://mirror.openshift.com/pub/openshift-v4/clients/butane/latest/> "Download Butane"
[10]: <https://github.com/dlbewley/demo-machineconfig/blob/main/machineconfigs/Makefile> "Makefile"