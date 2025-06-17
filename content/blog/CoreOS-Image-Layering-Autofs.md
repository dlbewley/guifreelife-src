---
title: "OpenShift CoreOS On-Cluster Image Layering"
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
description: CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node the operating system. This detailed walk through customizes the node operating system, adding RPMs.
---

CoreOS On-cluster Image Layering in OpenShift 4.19 allows modifications to node the operating system. This detailed walk through customizes the node operating system, adding RPMs.
In part 2 we will configure autofs and enabling automatic filesystem mounting across cluster nodes.

<!--more-->

# Background

RHEL CoreOS is a container optimized operating system which is distributed via a container image. OpenShift leverages this capability to keep the operating system up to date without the need to apply individual patches to nodes in the cluster.

Typically software will not be installed directly into the host operating system, but instead provided via images running in containers managed by Kubernetes. There are cases where it may be desirable to add packages directly to the operating system, however.

The RHCOS [Image Layering][3] feature of OpenShift allows to the ability to modify the container image that provides the CoreOS operating system image, in a manner compatible with the automated node lifecycle management performed by OpenShift.

# The Challenge - Missing RPMs

> ❓ **How can I install RPMs on my OpenShift nodes?**

I want to run the automount daemon on cluster nodes so I can expose dynamic NFS mounts from existing infrastructure to OpenShift workloads. Once the mounts are trigged by accessing a path on the host, the mounted filesystem can be exposed to pods via a [hostPath volume][10], but the `autofs` RPM is not on installed on the nodes.

I could run automountd [in a container][6], but that presents some significant challenges like also configuring and accessing `sssd` for user and automount lookups in LDAP, propagating the mounts back to the host, and properly surviving pod destruction. Having automountd running directly in the node operating system is the prefered solution in this case.

So how do I get the autofs and related RPMs installed on the nodes?

By adding the RPMs to the container image the nodes are running.

> 💡 **Install RPMs by layering on top of the node CoreOS image.**

## Understanding On-Cluster Layering

Out-of-cluster layering made it possible to build and host a custom CoreOS image for nodes on a n external registry.

On-Cluster Layering or OCL is a GA feature in OpenShift 4.19 which shipped v1 of the `MachineOSConfig` API and enables the building and managment of custom images to take place entirely within the cluster.

The `MachineOSConfig` resource defines the production of the layered image. It specifies the following parameters:

* Association to a single `MachineConfigPool`
* Registry location to push & pull the layered image
* The regsitry credentials required to push and pull
* Containerfile (Dockerfile) to build the image

The Containerfile will be embeded in the MachineOSConfig, but on it's own it may look like this:

```dockerfile
FROM configs AS final
RUN dnf install -y \
        autofs \
        openldap-clients \
        && dnf clean all \
        && ostree container commit
```

> ⭐ **Tip**
>
> Using a custom layered image does have a few caveats relative to conditions which require more reboots during configuration updates than with the default image. For example, making changes to the `MachineConfig` will trigger an image rebuild. _Pausing the `MachineConfigPool` while making changes can minimize reboots._

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

👀 _Watch a demonstration of above._

> {{< collapsable prompt="📺 **ASCII Screencast Demo of Pull and Push Secret Configuration**" collapse=false >}}
  <p>CoreOS Image Layering Demo - Pull and Push Secrets</p>
  {{< asciinema key="layering-01-secrets-20250603_1502" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  <a href=https://asciinema.org/a/721881>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-01.sh>Script</a>
  {{< /collapsable >}}

# Building the CoreOS Image

While it is possible to build the image and make it available the process is less integrated, so let's configure the on cluster method of building and using the image.

## Creating the worker-automount MachineConfigPool

We need a way to associate the custom image with the nodes of our choosing. This will be done using the `MachineConfigPool` (MCP) resource as shown below. This is also how we will associate the added configuration values a bit later. You can learn a bit more about MachineConfigPools in [this blog post][13].

```yaml {{linenos=inline hl_lines=[8,15,16,19,20]}}
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfigPool
metadata:
  annotation:
    description: Worker nodes with automount enabled
  labels:
    pools.operator.machineconfiguration.openshift.io/worker-automount: ""
  name: worker-automount
spec:
  machineConfigSelector:
    matchExpressions:
      - key: machineconfiguration.openshift.io/role
        operator: In
        values:
          - worker
          - worker-automount
  nodeSelector:
    matchLabels:
      node-role.kubernetes.io/worker-automount: ""
  paused: true
```
_[MachineConfigPool][11]_

On line 19 we say that this MCP will be applied to nodes that are labeled with "node-role.kubernetes.io/worker-automount", and on lines 15 and 16 we specify that any `MachineConfig` resources labeled with either "worker" or "worker-automount" will be used for those machines. Also notice on line 20 that we are defining this pool as "paused" by default.

> 🔧 **Creating the "worker-automount" MachineConfigPool**
> ```bash
> oc create -f machineconfigpool.yaml
> ```

Because we are not creating any MachineConfig resources [yet][14] the nodes in this pool will be configured just like any existing worker nodes, _except_ once we create the MachineOSConfig below the nodes in the pool will also have our custom image applied.

## Creating the worker-automount MachineOSConfig

Here is the `MachineOSConfig` which will be associated with the worker-automount `MachineConfigPool` above. This will define how to build the image.

Using the pull secrets we created above, it will push the image to the registry at the location specified.

```yaml {{linenos=inline hl_lines=[7,9,21,24,25]}}
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

> 🔧 **Creating the "worker-automount" MachineOSConfig**
> ```bash
> oc create -f machineosconfig.yaml
> ```

On line 7 we are specifying that this MachineOSConfig is to be applied to the "worker-automount" pool. In the content section we have the Containerfile instructions. On line 21 and 24 we reference the secrets holding the necessary registry credentials, and line 25 defines where the built image will be pushed to.

🌳 **In the Weeds**

Here is what happens when you create a `MachineOSConfig` named "worker-automount":
* creates a `deployment/machine-os-builder` which creates a `pod/machine-os-builder-<hash>`
* `pod/machine-os-builder-<hash>` waits to acquire a lease
* `pod/machine-os-builder-<hash>` creates a `machineosbuild/worker-automount-<hash>` resource  
* `pod/machine-os-builder-<hash>` creates a `job/build-worker-automount-<hash>`
* `job/build-worker-automount-<hash>`  creates a `pod/build-worker-automount-<hash>` to perform the build.
* ^ This pod log shows the build progress.

Once the image is pushed it is visible in an `ImageStream` in the openshift-machine-config-operator namespace.

```bash
oc get describe imagestream/os-image -n openshift-machine-config-operator
...
```

### Demo

👀 _Watch a demonstration of above._

> {{< collapsable prompt="📺 **ASCII Screencast Demo of MachineConfigPool and Custom Image Setup**" collapse=true >}}
  <p>CoreOS Image Layering Demo - Machine Config Pool and MachineOSConfig</p>
  {{< asciinema key="layering-02-machineosconfig-20250609_1929" rows="50" font-size="smaller" poster="npt:0:07" loop=true >}}
  <a href=https://asciinema.org/a/722700>Asciinema</a>, <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-02.sh>Script</a>
  {{< /collapsable >}}


# Deploying and Configuring

> ⚠️ **Warning!**
>
> Until [🐛 OCPBUGS-56648][5] is repaired, it is important that the custom image is deployed to nodes before any MachineConfigs that refer to new components [are added][14]. eg. Do not `systemctl enable autofs` until the layered image having autofs installed is fully deployed.
>
> _Another possible workaround would be to make this change in the Containerfile._
>

## Node Imaging

With the necessary changes layered onto the CoreOS image and that image assocated to a pool, the next step is to add a node to the pool and cause the CoreOS image to be redeployed.

This is done by labeling the node with the role variable the pool is using to select nodes.

> 🔧 **Adding a Node to the "worker-automount" MachineConfigPool**
> ```bash
> # 🎯 Select a test node
> TEST_WORKER=hub-v57jl-worker-0-jlvfs
>
> # 🏷️  Adjust node-role label & move it to worker-automount pool
> oc label node $TEST_WORKER node-role.kubernetes.io/worker- node-role.kubernetes.io/worker-automount=''
>
> # 🔍 worker-automount MCP now has a node count of 1
> oc get mcp -o custom-columns='NAME:.metadata.name, MACHINECOUNT:.status.machineCount'
> NAME               MACHINECOUNT
> master             3
> worker             7
> worker-automount   1
> ```

Now the update can be triggered by unpausing the pool. After this change, any further changes that affect the "worker-automount" MachineConfigPool will automatically be applied.

> 🔧 Unpausing the MCP to begin updates
> ```bash
> oc patch machineconfigpool/worker-automount \
>     --type merge --patch '{"spec":{"paused":false}}'"
> ```


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

👀 _Watch a demonstration of above._

> {{< collapsable prompt="📺 **ASCII Screencast Demo of Applying Custom Image to Nodes**" collapse=true >}}
  <p>CoreOS Image Layering Demo - Node Imaging</p>
  {{< asciinema key="layering-03-imaging-20250611_1148" rows="50" font-size="smaller" poster="npt:0:11" loop=true >}}
  <a href=https://asciinema.org/a/722913>Asciinema</a>,
 <a href=https://github.com/dlbewley/demo-autofs/blob/main/layering/demo-script-layering-03.sh>Script</a>
  {{< /collapsable >}}


# Summary

Now that we have added the RPMs to support it, be sure to checkout [part 2][14] where we will configure and use autofs.

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
[11]: <https://github.com/dlbewley/demo-autofs/blob/main/layering/machineconfigpool.yaml> "MachineConfigPool"
[12]: <https://issues.redhat.com/browse/OCPBUGS-56279> "applying on cluster layering fails with Old and new refs are equal - 4.18 problem i had"
[13]: {{< ref "/blog/Managing-OpenShift-Machine-Configuration-with-Butane-and-Ignition.md" >}} "Managing MachineConfigs with Butane"
[14]: {{< ref "/coming-soon.md" >}} "Configuring AutoFS on OpenShift"