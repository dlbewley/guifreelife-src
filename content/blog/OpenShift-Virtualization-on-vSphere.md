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

OpenShift Virtualization builds upon [Kubevirt][2] and provides a container native home for your virtual machine workloads. While only bare metal is officially supported, it is possible to experiment in a lab using nested virtualization. This post will walk through the basics of enabling OpenShift Virtualization on top of a vSphere IPI deployment.
<!--more-->

# Understanding OpenShift Virtualization

As you begin porting applications to container native infrastructure you may begin to appreciate the niceties ...

# Configuring vSphere Networking

In your vSphere cluster you likely already have several networks plumbed to your Hosts for running Guests on.  It is likely you may to attach your container virtual machines to this same network. Virtual Switch Tagging (VST) and Virtual Guest Tagging (VGT) enables the ability to carry a VLAN tag all the way from the physical switch through the vSwitch to the Guest.

* Add a PortGroup to the distributed vSwitch

Follow the [VMware documentation][4] to configure your distributed vSwitch by adding a PortGroup to carry all the VLANs you would like to be present in the OpenShift Virtualization environment.
Configure the portgroup to have vlan type 'VLAN trunking' and specify the VLANs to carry, or just include all of them.

> **:warning: IMPORTANT** Enable promiscuous mode
> Switches imporove network efficiency by learning where MAC addresses are and not sending traffic where it isn't needed. Because our virtual machines will be using MAC address that vSphere does not know about you will see failures such as no response to DHCP requests unless you [modify the security settings of the PortGroup][5]. 

⭐ **TODO Double check promiscuity after testing.**


> {{< figure src="/images/cnv-trunkpg-1.png" link="/images/cnv-trunkpg-1.png"  caption="TrunkPG Port Group" width="100%">}}

Now we can create Guests with a 2nd network interface card that attached to this port group and they will have receive an an 802.1Q trunk.

# Customizing the OpenShift Node Template

Lest you be confused let me clearly describe the end state. A virtual machine in a container on a virtual machine on a physical ESXi host. For this to work, our Guest (OpenShift Node) running in vSphere needs to know how to "do virtualization". It all starts with a template.

* Clone the Existing RHCOS Template as a VM

Clone the "_\*rhcos_" template to a virtual machine so that it is possible to make edits. Give the VM a name that matches the template with "_-cnv_" on the end. So _hub-7vxwj-rhcos_ becomes _hub-7vxwj-rhcos-cnv_.

* Edit the VM Settings

This VM is temporary. Don't boot it. We just want to make some changes to it that aren't possible to do with a static template.

>**Make These Changes**
> * Enable these CPU features: Hardware virtualization, IOMMU, Performance counters
> * Add a 2nd NIC attached to the `TrunkPG` portgroup
>
> {{< figure src="/images/cnv-cpu-1.png" link="/images/cnv-cpu-1.png"  caption="CNV Node Template with Customizations" width="100%">}}

## Convert the Customized VM to a New Template

Once these changes have been made, right click and convert this VM to a template. Keep the same `hub-7vxwj-rhcos-cnv` name.

# Create a Machineset for Hypervisors

How do we tell OpenShift to use this template? 

* Create a `MachineSet` for CNV nodes using the template just created.

Based on the existing worker machineset we will create a new one that is CNV specific.
Notice we are using "cnv" because Container Native Virtualization is a reference to OpenShift Virtualization.


>  **`MachineSet` For Workers With Virtualization**
> 
>  Notice that line 44 refers to the virtual machine template `hub-7vxwj-rhcos-cnv` that we created above.
  ```yaml  {linenos=inline,hl_lines=[9,17,24,40,44]}
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
        metadata: {}
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
              - networkName: TrunkPG
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


# OpenShift Virtualization Networking

Install OpenShift Virtualization (also known as CNV) using the web UI or GitOps and [this repo](https://github.com/redhat-cop/gitops-catalog/tree/main/virtualization-operator).

Once CNV is installed and a `Hyperconverged` resource has been created the [nmstate.io][3] API group will become available.

```shell
$ oc api-resources --api-group nmstate.io
NAME                                 SHORTNAMES   APIVERSION           NAMESPACED   KIND
nodenetworkconfigurationenactments   nnce         nmstate.io/v1beta1   false        NodeNetworkConfigurationEnactment
nodenetworkconfigurationpolicies     nncp         nmstate.io/v1beta1   false        NodeNetworkConfigurationPolicy
nodenetworkstates                    nns          nmstate.io/v1beta1   false        NodeNetworkState
```

With this API we can create a `NodeNetworkConfigurationPolicy` that will be used to configure the 2nd NIC for us in a way that will present each VLAN as a bridge.

* Create a Node Network Configuration Policy

If we want to use all the VLANs we are trunking to this nodes, we need to tell OpenShift how to configure the network.

First, log in to the node using `oc debug node` or ssh. And look at the current network settings.

Notice that the 2nd NIC (ens224) exists, but it has no useful configuration.

{{< figure src="/images/cnv-nncp-1.png" link="/images/cnv-nncp-1.png" width="100%" caption="Node Network before NNCP">}}


> **`NodeNetworkConfigurationPolicy` For Workers With Virtualization**
>
> Notice on line 7 we are checking for a label that will be automatically created when a CPU with virtualization is found to exist in the node.

```yaml  {linenos=inline,hl_lines=[7]}
apiVersion: nmstate.io/v1beta1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: ens224-policy
spec:
  nodeSelector:
    cpu-feature.node.kubevirt.io/hypervisor: "true"
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

After creation of the NodeNetworkConfigurationPolicy, a NodeNetworkConfigurationEnablement will be created for each node that satisfies the node selector in the policy.

```shell
$ oc get nodes -l cpu-feature.node.kubevirt.io/hypervisor="true"
NAME                  STATUS   ROLES    AGE   VERSION
hub-7vxwj-cnv-gjlvj   Ready    worker   40m   v1.22.3+b93fd35

$ oc create -f nodenetworkconfigurationpolicy.yaml
nodenetworkconfigurationpolicy.nmstate.io/ens224-policy created

$ oc get nnce
NAME                                STATUS
hub-7vxwj-cnv-gjlvj.ens224-policy   Available
````

Now that the NNCE is status Available, log back into the node, and take a look at the network now. Woah! Look at all those interfaces.

{{< figure src="/images/cnv-nncp-2.png" link="/images/cnv-nncp-2.png" width="100%" caption="Node Network after NNCP">}}

## Namespace Level Networking for VMs

All the work above occurred at the cluster level by a cluster admin. Now for users to place CNV Guests on them we must work at the project or namespace leve.

The `NetworkAttachmentDefinition` resource so that virtual machines have a logical reference to the network interfaces we created previously.

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

> **NetworkAttachmentDefinition**
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
$ oc create -f net-attach-def.yaml
```

# Attaching a Virtual Machine to a VLAN

We covered a lot of ground. Let's save the creation of a CNV virtual machine for a later post.

# References

* [About OpenShift virtualization][1]

[1]: <https://docs.openshift.com/container-platform/4.10/virt/about-virt.html> "About OpenShift virtualization"
[2]: <kubevirt>
[3]: <https://nmstate.io/> "NMState A Declarative API for Host Network Management"
[4]: <https://kb.vmware.com/s/article/1003806> "VLAN configuration on virtual switches, physical switches, and virtual machines (1003806)"
[5]: <https://kb.vmware.com/s/article/1002934> "How promiscuous mode works at the virtual switch and portgroup levels (1002934)"
[6]: <https://docs.openshift.com/container-platform/4.10/virt/node_network/virt-updating-node-network-config.html>
