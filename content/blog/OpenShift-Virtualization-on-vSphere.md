---
title: "OpenShift Virtualization Networking on vSphere"
date: 2022-04-13
draft: true
layout: post
tags:
 - openshift
 - OCP4
 - virtualization
 - draft
---

OpenShift Virtualization builds upon [Kubevirt][2] and provides a container native home for your virtual machine workloads. While bare metal is the only officially platform, it is possible to experiment in a lab using nested virtualization. This post will walk through the basics of enabling OpenShift Virtualization in a vSphere laboratory environment.
<!--more-->

# Understanding OpenShift Virtualization

Why virtual machines in containers?! 

As you begin to migrate applications to a containerized, cloud-native platform like OpenShift you begin to realize benefits like portability, repeatability, and automation. Applications hosted on virtual machines may not be practical to containerize or even compatible. That doesn't mean they may not be positioned right along side containerized applications.

OpenShift Virtualization enables you to run your virtualized workloads on the same platform powering your containerized workloads using a consistent Kubernetes interface.

To experiment with container native virtualization on vSphere let's begin by adjusting the network configuration.
# Configuring vSphere Networking for KubeVirt

You likely already have several networks plumbed to your ESXi Hosts for virtual machine guests to attach to.  It is likely you may attach your containerized virtual machines to these same networks. Virtual Switch Tagging (VST) and Virtual Guest Tagging (VGT) provide the ability to carry a VLAN tag all the way from the physical rack switch through the vSwitch to the guest.

## Adding a PortGroup to vSwitch

Follow the [VMware documentation][4] to configure your standard or distributed vSwitch by adding a PortGroup to carry all the VLANs you would like to be present in the OpenShift Virtualization environment.
Configure the portgroup to have vlan type _"VLAN trunking"_ and specify the appropriate VLANs. For a standard vSwitch select 4095 to carry all. For a distributed vSwitch select 0-4094.

> **:warning: IMPORTANT** Enable promiscuous mode
>
> Switches improve network efficiency by learning where MAC addresses are and not sending traffic where it isn't needed. Because our virtual machines will be using MAC addresses that vSphere does not know about you will see failures such as no response to DHCP requests unless you [modify the security settings of the network or PortGroup][5]. 

<!--  {{< figure src="/images/cnv-trunk-0.gif" link="/images/cnv-trunk-0.gif"  caption="Trunk Port Group" width="100%">}} -->

> {{< figure src="/images/cnv-trunk-1.png" link="/images/cnv-trunk-1.png"  caption="Trunk Port Group for Standard vSwitch" width="100%">}}

> {{< collapsable prompt="Distributed vSwitch Option" collapse=true >}}
  {{< figure src="/images/cnv-trunkpg-1.png" link="/images/cnv-trunkpg-1.png"  caption="Example of Port Group for a Distributed vSwitch" width="100%">}}
  {{< /collapsable>}}

**Why did we do that?**

Now we can create guests for our OpenShift nodes which have a 2nd network interface card. When this NIC is attached to the newly created _"Trunk"_ port group it will receive an an 802.1Q trunk from the vSwitch. The VLANs on that trunk may then be split back out to bridges in the node which provide connectivity to containerized virtual machines.

# Customizing the OpenShift RHCOS Node Template

First, let's restate what we are going to achieve: _A virtual machine in a container on a virtual machine on a physical ESXi host._ For this to work, our Guest (OpenShift Node) running in vSphere needs to know how to "do virtualization".

Things are beginning to feel a bit recursive. 😵
Don't worry. We'll get there.

It all starts with a template...

## Cloning the Existing RHCOS Template as a VM

The [OpenShift Machine API operator][7] builds nodes in vSphere by cloning a guest template that was created during cluster installation. There are changes that must be made to this template to allow for nested virtualization.

Clone the "_\*rhcos_" template to a virtual machine so that it is possible to make edits. Give the VM a name that matches the template with "_-cnv_" on the end. So _"hub-7vxwj-rhcos"_ becomes _"hub-7vxwj-rhcos-cnv"_.

📓 We are using "cnv" as shorthand for Container Native Virtualization which predates the OpenShift Virtualization name.
## Customizing the Temporary VM 

This VM is temporary. Don't boot it. We just want to make some changes to it that aren't possible to do with a static template.

>**Make These Changes**
> * Enable these CPU features: Hardware virtualization, IOMMU, Performance counters
> * Add a 2nd NIC attached to the `Trunk` portgroup
>
> {{< figure src="/images/cnv-cpu-1.png" link="/images/cnv-cpu-1.png"  caption="CNV Node Template with Customizations" width="100%">}}

## Converting the Customized VM to a Template

Once these changes have been made, convert this VM to a template. Keep the same `hub-7vxwj-rhcos-cnv` name.

# Creating a Machineset for Hypervisors

**How do we tell OpenShift to use this template?**

[MachineSets][8] define how many machines to build for nodes and exactly how to build them, so next create a MachineSet that uses the just created template.

Based on the existing worker machineset we will create a new one that is CNV specific.

>  📓 **`MachineSet` For Workers With Virtualization**
> 
>  Notice that line 42 refers to the `Trunk` port group and line 46 refers to the virtual machine template `hub-7vxwj-rhcos-cnv` created above. 
  ```yaml  {linenos=inline,hl_lines=[9,17,24,28,42,46]}
  apiVersion: machine.openshift.io/v1beta1
  kind: MachineSet
  metadata:
    annotations:
      machine.openshift.io/memoryMb: "16384"
      machine.openshift.io/vCPU: "6"
    labels:
      machine.openshift.io/cluster-api-cluster: hub-7vxwj
    name: hub-7vxwj-cnv
    namespace: openshift-machine-api
    resourceVersion: "162348847"
  spec:
    replicas: 1
    selector:
      matchLabels:
        machine.openshift.io/cluster-api-cluster: hub-7vxwj
        machine.openshift.io/cluster-api-machineset: hub-7vxwj-cnv
    template:
      metadata:
        labels:
          machine.openshift.io/cluster-api-cluster: hub-7vxwj
          machine.openshift.io/cluster-api-machine-role: worker
          machine.openshift.io/cluster-api-machine-type: worker
          machine.openshift.io/cluster-api-machineset: hub-7vxwj-cnv
      spec:
        metadata:
          labels:
            machine.openshift.io/cluster-api-machineset: hub-7vxwj-cnv
        providerSpec:
          value:
            apiVersion: vsphereprovider.openshift.io/v1beta1
            credentialsSecret:
              name: vsphere-cloud-credentials
            diskGiB: 90
            kind: VSphereMachineProviderSpec
            memoryMiB: 16384
            metadata:
              creationTimestamp: null
            network:
              devices:
              - networkName: lab-192-168-4-0-b24
              - networkName: Trunk
            numCPUs: 6
            numCoresPerSocket: 1
            snapshot: ""
            template: hub-7vxwj-rhcos-cnv
            userDataSecret:
              name: worker-user-data
            workspace:
              datacenter: Garden
              datastore: VMData-HD
              folder: /Garden/vm/hub-7vxwj
              resourcePool: /Garden/host/Goat/Resources
              server: vcenter.lab.bewley.net
  ```

# Configuring OpenShift Virtualization Networking

Install OpenShift Virtualization (also known as CNV) using the web UI or GitOps and [this repo](https://github.com/redhat-cop/gitops-catalog/tree/main/virtualization-operator).

Once CNV is installed and a `Hyperconverged` resource has been created the _nmstate.io_ API group will become available.

```shell
$ oc api-resources --api-group nmstate.io
NAME                                 SHORTNAMES   APIVERSION           NAMESPACED   KIND
nodenetworkconfigurationenactments   nnce         nmstate.io/v1beta1   false        NodeNetworkConfigurationEnactment
nodenetworkconfigurationpolicies     nncp         nmstate.io/v1beta1   false        NodeNetworkConfigurationPolicy
nodenetworkstates                    nns          nmstate.io/v1beta1   false        NodeNetworkState
```

## Creating a Node Network Configuration Policy

If we want to use all the VLANs we are trunking to a node, we need to tell OpenShift how to configure the network.
Using resources from the [NMState API][3] we can configure the networking in the node operating system.

Create a `NodeNetworkConfigurationPolicy` that will be used to configure the 2nd NIC for us in a way that will present each VLAN as a bridge.

You may optionally log in to the node using `oc debug node` or ssh, and look at the current network settings before making changes.

Notice in this case that the 2nd NIC _ens224_ exists, but it has no useful configuration.

{{< figure src="/images/cnv-nncp-1.png" link="/images/cnv-nncp-1.png" width="100%" caption="Node Network before NNCP">}}

> 📓 **`NodeNetworkConfigurationPolicy` For Workers With Virtualization**
>
> Notice on line 7 we are checking for a label that that is common to our nodes with nested virtualization. This will cause our NNCP to be applied only to the appropriate nodes.

```yaml  {linenos=inline,hl_lines=[7]}
apiVersion: nmstate.io/v1beta1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: ens224-policy
spec:
  nodeSelector:
    machine.openshift.io/cluster-api-machineset: hub-7vxwj-cnv
  desiredState:
    interfaces:

      # defined only to facilitate disabling DHCP
      - name: ens224
        type: ethernet
        state: up
        ipv4:
          enabled: false
        ipv6:
          enabled: false

      # trans proxy
      - name: ens224.1925
        type: vlan
        state: up
        vlan:
          base-iface: ens224
          id: 1925
        ipv4:
          enabled: false
        ipv6:
          enabled: false
      - name: br-1925
        type: linux-bridge
        state: up
        ipv4:
          enabled: false
        ipv6:
          enabled: false
        bridge:
          options:
            stp:
              enabled: false
          port:
          - name: ens224.1925
            vlan: {}

      # disco
      - name: ens224.1926
        type: vlan
        state: up
        vlan:
          base-iface: ens224
          id: 1926
        ipv4:
          enabled: false
        ipv6:
          enabled: false
      - name: br-1926
        type: linux-bridge
        state: up
        ipv4:
          enabled: false
        ipv6:
          enabled: false
        bridge:
          options:
            stp:
              enabled: false
          port:
          - name: ens224.1926
            vlan: {}

      # metal
      - name: ens224.1927
        type: vlan
        state: up
        vlan:
          base-iface: ens224
          id: 1927
        ipv4:
          enabled: false
        ipv6:
          enabled: false
      - name: br-1927
        type: linux-bridge
        state: up
        ipv4:
          enabled: false
        ipv6:
          enabled: false
        bridge:
          options:
            stp:
              enabled: false
          port:
          - name: ens224.1927
            vlan: {}

      # provisioning
      - name: ens224.1928
        type: vlan
        state: up
        vlan:
          base-iface: ens224
          id: 1928
        ipv4:
          enabled: false
        ipv6:
          enabled: false
      - name: br-1928
        type: linux-bridge
        state: up
        ipv4:
          enabled: false
        ipv6:
          enabled: false
        bridge:
          options:
            stp:
              enabled: false
          port:
          - name: ens224.1928
            vlan: {}
```

> :warning: **Inaccurate Kubevirt Labels**
>
> Ideally, we could rely on the label _cpu-feature.node.kubevirt.io/hypervisor: "true"_, 
> unfortunately all workers wil will be automatically labeled to indicate they have virtualization features even if they do not.
> I'm not yet sure how to avoid this and need to create a BZ. **TODO** ⭐
## Confirming Node Networking Configuration Changes

After creation of the NodeNetworkConfigurationPolicy, a `NodeNetworkConfigurationEnablement` will be created for each node that satisfies the node selector in the policy. (_machine.openshift.io/cluster-api-machineset: hub-7vxwj-cnv_)

```shell
$ oc get nodes -l machine.openshift.io/cluster-api-machineset=hub-7vxwj-cnv
NAME                  STATUS   ROLES    AGE    VERSION
hub-7vxwj-cnv-drhkz   Ready    worker   162m   v1.23.5+9ce5071

$ oc create -f nodenetworkconfigurationpolicy.yaml
nodenetworkconfigurationpolicy.nmstate.io/ens224-policy created

$ oc get nnce
NAME                                STATUS
hub-7vxwj-cnv-drhkz.ens224-policy   Available
````

Now that the NNCE is status `Available`, optionally log back into the node and take a look at the network configuration.

Woah! Look at all those interfaces on _ens224_!

{{< figure src="/images/cnv-nncp-2.png" link="/images/cnv-nncp-2.png" width="100%" caption="Node Network after NNCE">}}

> 📓 **Node Network Debugging**
>
> See [Observing node network state][9]
# Attaching a Containerized Virtual Machine to a VLAN

All the work above occurred at the cluster level by a cluster admin. Further configuration takes place within the namespaces that host the virtual machines.
## Configuring OpenShift Namespace Networking for VMs

For developers to attach CNV virtual machines to the networks plumbed above, we need to create points of attachment in the namespaces they are privileged to.

The `NetworkAttachmentDefinition` resource provides virtual machines a logical reference to the network interfaces we created previously.

```shell
$ oc api-resources --api-group k8s.cni.cncf.io
NAME                             SHORTNAMES       APIVERSION           NAMESPACED   KIND
network-attachment-definitions   net-attach-def   k8s.cni.cncf.io/v1   true         NetworkAttachmentDefinition

$ oc explain network-attachment-definition
KIND:     NetworkAttachmentDefinition
VERSION:  k8s.cni.cncf.io/v1

DESCRIPTION:
     NetworkAttachmentDefinition is a CRD schema specified by the Network
     Plumbing Working Group to express the intent for attaching pods to one or
     more logical or physical networks. More information available at:
     https://github.com/k8snetworkplumbingwg/multi-net-spec
```

> 📓 **`NetworkAttachmentDefinition`** Enabling access to _provisioning_ bridge.
>
> Enables VMs in a namespace to attach to a network using CNI.
```yaml  {linenos=inline,hl_lines=[17]}
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  annotations:
    description: Provisioning Bridge V1928
    k8s.v1.cni.cncf.io/resourceName: bridge.network.kubevirt.io/br-1928
  name: vlan-1928
  namespace: provisioning
spec:
  config: |-
    {
      "name": "vlan-1928",
      "cniVersion": "0.3.1",
      "plugins": [
        {
          "type": "cnv-bridge",
          "bridge":"br-1928",
          "vlan":1928,
          "ipam":{}
        },
        {
          "type": "cnv-tuning"
        }
      ]
    }
``` 

Let's create an attachment to the provisioning network on bridge br-1928.

```shell
$ oc new-project provisioning
$ oc create -f net-attach-def.yaml -n provisioning

$ oc get net-attach-def -n provisioning
NAME        AGE
vlan-1928   1m
```

Once the network attachment definition is available, a VM can be launch using this network on a bridged interface.
# References

* [About OpenShift virtualization][1]
* [KubeVirt.io][2]
* [NMState.io][3]
* [Machine API Operator][7]
* [MachineSet API][8]
* [Enabling CNV Nested Virtualization on KVM Hypervisors][10]

[1]: <https://docs.openshift.com/container-platform/4.10/virt/about-virt.html> "About OpenShift virtualization"
[2]: <https://kubevirt.io> "KubeVirt.io"
[3]: <https://nmstate.io/> "NMState A Declarative API for Host Network Management"
[4]: <https://kb.vmware.com/s/article/1003806> "VLAN configuration on virtual switches, physical switches, and virtual machines (1003806)"
[5]: <https://kb.vmware.com/s/article/1002934> "How promiscuous mode works at the virtual switch and portgroup levels (1002934)"
[6]: <https://docs.openshift.com/container-platform/4.10/virt/node_network/virt-updating-node-network-config.html>
[7]: <https://github.com/openshift/machine-api-operator> "Machine API Operator"
[8]: <https://docs.openshift.com/container-platform/4.10/rest_api/machine_apis/machineset-machine-openshift-io-v1beta1.html> "MachineSet API"
[9]: <https://docs.openshift.com/container-platform/4.10/virt/node_network/virt-observing-node-network-state.html> "Observing Node Network State"
[10]: <https://access.redhat.com/solutions/6692341> "Enabling Nested Virtualization on KVM Hypervisors"
[11]: <https://docs.openshift.com/container-platform/4.10/virt/virtual_machines/vm_networking/virt-attaching-vm-multiple-networks.html> "Attaching a virtual machine to multiple networks"
