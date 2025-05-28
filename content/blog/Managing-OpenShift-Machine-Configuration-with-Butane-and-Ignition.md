---
title: "Managing Actually Readable OpenShift MachineConfigs using Butane"
date: 2025-05-23
banner: /images/machineconfigs-butane.png
layout: post
mermaid: false
asciinema: true
draft: true
tags:
  - automation
  - openshift
  - kubernetes
description: The OpenShift Machine Configuration Operator applies configuration changes to using a syntax called ignition, but managing base64 encoded text can be challenging. Using plain text doesn't have to be difficult."
---

The OpenShift Machine Configuration Operator applies configuration changes to using a syntax called ignition,
but managing base64 encoded text can be challenging. What if I cold you that you can use plain text and normal files?

<!--more-->

MachineConfiguration files look like this. At a glance, maybe you can tell it is writing a file but you can't easily read what's in it.

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

# Makefile

```make  {linenos=inline}
BUTANES = $(wildcard butane/*.bu)
MACHINECONFIGS = $(BUTANES:butane/%.bu=%.yaml)
INCLUDES_DIR = inc
DEPS_DIR = .deps

# Find all script files that might be referenced
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

%.yaml: butane/%.bu
	butane -d $(INCLUDES_DIR) < $< > $@

# rm the machineconfigs and dependency files generated from butane files
clean:
	rm -f $(MACHINECONFIGS)
	rm -rf $(DEPS_DIR)
```

* Demo

```bash
make clean
make
vi inc/foo
make
git add .
git commit -m 'update foo machineconfig'
oc apply -k .
```

## References

* [Demo Github Repo][2]
* [CoreOS Ignition Specification][1]


[1]: <https://coreos.github.io/ignition/specs/> "CoreOS Ignition Spec"
[2]: <https://github.com/dlbewley/demo-machineconfig/> "Demo Github Repo"