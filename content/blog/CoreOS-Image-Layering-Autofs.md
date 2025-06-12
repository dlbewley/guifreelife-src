---
title: "CorOS Image Layering Autofs - Title WIP"
date: 2025-06-12
banner: /images/layering-cake-trans.png
layout: post
mermaid: false
asciinema: true
draft: true
tags:
  - draft
  - coreos
  - openshift
  - kubernetes
  - operators
description: CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node operating system. This detailed walk through adds autofs to enable automatic filesystem mounting across cluster nodes.
---

CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node operating system. This detailed walk through adds autofs to enable automatic filesystem mounting across cluster nodes.
but managing base64 encoded text can be challenging. What if I told you that you can use plain text and normal files?

<!--more-->

# The Problem
I want to run automountd on cluster nodes, but the autofs RPM is not installed. I could run this in a container, but that presents some significant challenges as well. Having it directly in the node operating system is the prefered solution in this case.

# Prep

## Pull Secrets

[demo-script-layering-01.sh](demo-script-layering-01.sh)

This step demonstrates:
* Creating a push secret for the internal registry using a service account token
* Extracting and examining the push secret
* Extracting and examining the global cluster pull secret 
* Combining the push and pull secrets into a new pull-and-push secret
* Creating a secret in openshift-machine-config-operator namespace
* Verifying the secrets exist and match the MachineOSConfig requirements


> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Title</p>
  [asciicast](https://asciinema.org/a/721881)
  {{< asciinema key="layering-01-secrets-20250603_1502" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}


# Build

## MachineConfigPool and MachineOSConfig

This step demonstrates:
* Explaining MachineConfigPools and how they associate nodes with MachineConfigs
* Examining existing MCPs and their node selectors
* Showing how MCPs reference multiple MachineConfigs via labels
* Exploring the rendered MachineConfig that combines individual configs
* Demonstrating how rendered configs contain systemd units, files, and OS image info
* Creating a new worker-automount MachineConfigPool for autofs nodes
* Explaining how worker-automount will get both worker and worker-automount configs
* Creating a MachineOSConfig to build custom image with added RPMs
* Monitoring the MachineOSBuild process and job completion
* Verifying the custom image is associated with the worker-automount pool

* [![asciicast](https://asciinema.org/a/722700.svg)](https://asciinema.org/a/722700)

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Title</p>
  {{< asciinema key="layering-02-machineosconfig-20250609_1929" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}


# Deploy
## Node Imaging and Configuration

[demo-script-layering-03.sh](demo-script-layering-03.sh)

This step demonstrates:
* Checking cluster state with `oc get clusterversion`, `oc get nodes`, and `oc get mcp`
* Selecting a test worker node and setting it as $TEST_WORKER
* Relabeling the node from worker to worker-automount role
* Verifying the worker-automount MCP shows 1 node
* Unpausing the MCP to trigger the node update
* Monitoring the node as it drains and reboots
* Watching Machine Config Daemon logs for update completion
* Verifying successful update via MCP and node status checks
* Confirming autofs RPM is installed on the updated node

* [![asciicast](https://asciinema.org/a/722913.svg)](https://asciinema.org/a/722913)

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Title</p>
  {{< asciinema key="layering-03-imaging-20250611_1148" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}


## Autofs Configuration

[demo-script-layering-04.sh](demo-script-layering-04.sh)

This step demonstrates:
* Regenerating machineconfigs with `make`
* Applying machineconfigs with `oc apply -k`
* Observing the MCP go into an updating state
* Waiting for the node to reboot and MCP to be updated
* Verifying the home directory is an NFS mount

* [![asciicast](https://asciinema.org/a/722936.svg)](https://asciinema.org/a/722936)

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Title</p>
  {{< asciinema key="layering-04-autofs-config-20250611_1530" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}


# Test

# Demo 

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Managing MachineConfig resources with Butane and Make</p>
  {{< asciinema key="machineconfig-20250529" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}

# Summary

Allowing t
Sometimes 

# References

* [Demo Github Repo][1]
* [Demo Recording][2]

[1]: <https://github.com/dlbewley/demo-autofs> "Demo Github Repo"
[2]: <https://asciinema.org/a/721881> "Asciinema Demo Recording"
