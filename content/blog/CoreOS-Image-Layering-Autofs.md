---
title: "CoreOS Image Layering Autofs - Title WIP"
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
description: CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node operating system. This detailed walk through installs and configures autofs, enabling automatic filesystem mounting across cluster nodes.
---

CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node operating system. This detailed walk through installs and configures autofs, enabling automatic filesystem mounting across cluster nodes.

<!--more-->

RHEL CoreOS is a container optimized operating system which is distributed via a container image. OpenShift leverages this capability to keep the operating system up to date without the need to apply individual patches to nodes in the cluster.

Typically software will not be installed directly into the host operating system, but instead provided in images running in containers on top of Kubernetes. There are cases where it may be desirable to add packages directly to the operating system, however.

The RHCOS [Image Layering][3] feature of OpenShift allows to the ability to modify the container image that provides the CoreOS operating system image, in a manner compatible with the automated node lifecycle management performed by OpenShift.

# The Challenge - Missing RPMs

> ❓ **How can I install the `autofs` RPM on my OpenShift nodes?**

I want to run the automount daemon on cluster nodes so I can expose dynamic NFS mounts from existing infrastructure to OpenShift workloads. Once the mounts are trigged by accessing a path on the host, the mounted filesystem can be exposed to pods via a [hostPath volume][10], but the `autofs` RPM is not on installed on the nodes.

I could run automountd [in a container][6], but that presents some significant challenges like also configuring and accessing `sssd` for user and automount lookups in LDAP, propagating the mounts back to the host, and properly surviving pod destruction. Having automountd running directly in the node operating system is the prefered solution in this case.

So how do I get the autofs and related RPMs installed on the nodes?

By adding the RPMs to the container image the nodes are running.

> 💡 **Install RPMs by rebuilding the node CoreOS image!**

## Understanding On-Cluster Layering

On-Cluster Layering or OCL is a GA feature in OpenShift 4.19 with shipped v1 of the MachineOSConfig API.

The MachineOSConfig resource is key to producing the layered image, and it specifies the following parameters:

* Associated to a single MachineConfigPool
* Location push & pull the layered image
* The push and pull secrets to use with registries
* A Containerfile (Dockerfile) to build the image

The Containerfile will be embeded, but on it's own it may look like this:

```dockerfile
FROM configs AS final
RUN dnf install -y \
        autofs \
        openldap-clients \
        && dnf clean all \
        && ostree container commit
```

# Preparing for On-Cluster Image Layering

## Image Registry

The custom image we are creating must be pushed to a container image registry. The on-cluster registry can be used for that if it is [enabled][8]. That is what I will [use here][9].

## Creating Pull Secrets for the Image Build

To upload (push) or download (pull) an image from a registry requires a credential called a "pull-secret". 

OpenShift includes a global pull secret which is supplied during installation and stored in the `openshift-config` namespace. This has privilege to download the CoreOS image, but we also need a credential to push our custom image to a registry.

The image will be built by the _builder_ ServiceAccount in the `openshift-machine-config-operator` namespace, so we need to create a credential and associate it with this "user".


> {{< collapsable prompt=" 🔧 **Creating a Builder Pull Secret for Pushing**" collapse=false md=true >}}
  📓 **Important**
  Tokens have a default 1 hour expiration. In this example we will set this to 2 years. Your approach may differ.
  ```bash {{linenos=inline}}
  # 🔧 prepare a service account to build and push images to the registry
  export REGISTRY=image-registry.openshift-image-registry.svc:5000
  export REGISTRY_NAMESPACE=openshift-machine-config-operator
  # 🤖 the builder serviceaccount has rolebinding/system:image-builders
  export REGISTRY_USER=builder

  # 🔧 create a long duration (2 years) token for the service account
  export TOKEN=$(oc create token $REGISTRY_USER -n $REGISTRY_NAMESPACE --duration=$((720*24))h)

  # 🔧 use this token to create a pull secret for the cluster registry
  oc create secret docker-registry push-secret \
    -n openshift-machine-config-operator \
    --docker-server=$REGISTRY \
    --docker-username=$REGISTRY_USER \
    --docker-password=$TOKEN
  ```
  {{< /collapsable >}}


Testing revealed that the same pull secret is used for pulling the standard images, so we need to combine this created secret with the global pull secret.


> {{< collapsable prompt=" 🔧 **Combining the Global Pull Secret with the Builder Pull Secret for Pulling**" collapse=false md=true >}}
  ```bash {{linenos=inline}}
  # 🪏 extract the just created 'push' secret to a file
  oc extract secret/push-secret -n openshift-machine-config-operator --to=- > push-secret.json

  # 🪏 extract the cluster global pull secret to a file
  oc extract secret/pull-secret -n openshift-config --to=- > pull-secret.json

  # 🔧 combine the global pull secret and the just created push secret
  jq -s '.[0] * .[1]' pull-secret.json push-secret.json > pull-and-push-secret.json

  # 🔧 create a new secret to hold the pull-and-push secret
  oc create secret generic pull-and-push-secret \
    -n openshift-machine-config-operator \
    --from-file=.dockerconfigjson=pull-and-push-secret.json \
    --type=kubernetes.io/dockerconfigjson
  ```
  {{< /collapsable >}}

### Demo

_Watch a demonstration of above!_

> {{< collapsable prompt="📺 **Ascii Screencast Demo of Pull and Push Secret Configuration**" collapse=true >}}
  <p>CoreOS Image Layering Demo - Pull and Push Secrets</p>
  {{< asciinema key="layering-01-secrets-20250603_1502" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  <a href=https://asciinema.org/a/721881>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-01.sh>Script</a>
  {{< /collapsable >}}

# Building

## MachineConfigPool and MachineOSConfig

### The MachineOSConfig Resource

To apply a custom layered image to your cluster by using the on-cluster build process, make a MachineOSConfig custom resource (CR) that specifies the following parameters:

One MachineOSConfig resource per machine config pool specifies:
the Containerfile to build
the machine config pool to associate the build
where the final image should be pushed and pulled from
the push and pull secrets to use with the image

```yaml {{linenos=inline hl_lines=[20,23]}}
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineOSConfig
metadata:
  name: worker-automount
spec:
  machineConfigPool:
    name: worker-automount
  containerFile: 
  - content: |-
      FROM configs AS final
      RUN dnf install -y \
        autofs \
        libsss_autofs \
        openldap-clients \
        && dnf clean all \
        && ostree container commit
  imageBuilder: 
    imageBuilderType: Job
  baseImagePullSecret: 
    # baseImagePullSecret is the secret used to pull the base image
    name: pull-and-push-secret
  renderedImagePushSecret: 
    # renderedImagePushSecret is the secret used to push the custom image
    name: push-secret
  renderedImagePushSpec: image-registry.openshift-image-registry.svc:5000/openshift-machine-config-operator/os-image:latest 
```
_[MachineOSConfig][4]_

> ⭐ **TIP**
> Using a custom layered image does have a few caveats relative to conditions which require more reboots during configuration updates than with the default image. For example, making changes to MachineCOnfigs will trigger an image rebuild. Pausing the machineconfigPool while making changes can minimize reboots.


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


### Demo

_Watch a demonstration of above!_

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=true thumbnail="/images/layering-cake-trans.png" >}}
  <p>CoreOS Image Layering Demo - Machine Config Pool and MachineOSConfig</p>
  {{< asciinema key="layering-02-machineosconfig-20250609_1929" rows="50" font-size="smaller" poster="npt:0:07" loop=true >}}
  <a href=https://asciinema.org/a/722700>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-02.sh>Script</a>
  {{< /collapsable >}}

# Building

## MachineConfigPool and MachineOSConfig

### The MachineOSConfig Resource

To apply a custom layered image to your cluster by using the on-cluster build process, make a MachineOSConfig custom resource (CR) that specifies the following parameters:

One MachineOSConfig resource per machine config pool specifies:
the Containerfile to build
the machine config pool to associate the build
where the final image should be pushed and pulled from
the push and pull secrets to use with the image

```yaml {{linenos=inline hl_lines=[20,23]}}
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineOSConfig
metadata:
  name: worker-automount
spec:
  machineConfigPool:
    name: worker-automount
  containerFile: 
  - content: |-
      FROM configs AS final
      RUN dnf install -y \
        autofs \
        libsss_autofs \
        openldap-clients \
        && dnf clean all \
        && ostree container commit
  imageBuilder: 
    imageBuilderType: Job
  baseImagePullSecret: 
    # baseImagePullSecret is the secret used to pull the base image
    name: pull-and-push-secret
  renderedImagePushSecret: 
    # renderedImagePushSecret is the secret used to push the custom image
    name: push-secret
  renderedImagePushSpec: image-registry.openshift-image-registry.svc:5000/openshift-machine-config-operator/os-image:latest 
```
_[MachineOSConfig][4]_

> ⭐ **TIP**
> Using a custom layered image does have a few caveats relative to conditions which require more reboots during configuration updates than with the default image. For example, making changes to MachineCOnfigs will trigger an image rebuild. Pausing the machineconfigPool while making changes can minimize reboots.


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


### Demo

_Watch a demonstration of above!_

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=true thumbnail="/images/layering-cake-trans.png" >}}
  <p>CoreOS Image Layering Demo - Machine Config Pool and MachineOSConfig</p>
  {{< asciinema key="layering-02-machineosconfig-20250609_1929" rows="50" font-size="smaller" poster="npt:0:07" loop=true >}}
  <a href=https://asciinema.org/a/722700>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-03.sh>Script</a>
  {{< /collapsable >}}


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


> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=true >}}
  <p>CoreOS Image Layering Demo - Node Imaging</p>
  {{< asciinema key="layering-03-imaging-20250611_1148" rows="50" font-size="smaller" poster="npt:0:11" loop=true >}}
  <a href=https://asciinema.org/a/722913>Asciinema</a>
  {{< /collapsable >}}


## Autofs Configuration

This step demonstrates:
* Regenerating machineconfigs with `make`
* Applying machineconfigs with `oc apply -k`
* Observing the MCP go into an updating state
* Waiting for the node to reboot and MCP to be updated
* Verifying the home directory is an NFS mount

### Demo

_Watch a demonstration of above!_

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=true >}}
  <p>CoreOS Image Layering Demo - Autofs Configuration</p>
  {{< asciinema key="layering-04-autofs-config-20250611_1530" rows="50" font-size="smaller" poster="npt:0:04" loop=true >}}
  <a href=https://asciinema.org/a/722936>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-04.sh>Script</a>
  {{< /collapsable >}}


# Testing AutoFS

## Demo 

# Summary


# References

* [Demo Github Repo][1]
* [Demo Recording][2]
* [RHCOS Image Layering Docs][3]
* [🐛 layered image update loops on failure to find systemd unit files][5]
* [Automount in a container][6]
* [Automount on the node][7]
* [Configuring the OpenShift Image Registry][8]
* [Kubernetes hostPath Volumes][10]

[1]: <https://github.com/dlbewley/demo-autofs> "Demo Github Repo"
[2]: <https://asciinema.org/a/721881> "Asciinema Demo Recording"
[3]: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/machine_configuration/mco-coreos-layering> "RHCOS image layering Docs"
[4]: <https://github.com/dlbewley/demo-autofs/blob/main/layering/machineosconfig.yaml> "MachineOSConfig"
[5]: <https://issues.redhat.com/browse/OCPBUGS-56648> "Bug: layered image update loops on failure to find systemd unit files"
[6]: <https://github.com/dlbewley/demo-autofs/tree/main/automount> "Automount in a container"
[7]: <https://github.com/dlbewley/demo-autofs/tree/main/layering> "Automount on the node"
[8]: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/registry/setting-up-and-configuring-the-registry#configuring-registry-storage-baremetal> "Configuring the OpenShift Image Registry"
[9]: <https://github.com/dlbewley/demo-autofs/blob/main/layering/readme.md#provisioning-an-image-registry-to-hold-layered-image> "Image Registry Configuration Notes"
[10]: <https://kubernetes.io/docs/concepts/storage/volumes/#hostpath> "Kubernetes hostPath Volumes"
