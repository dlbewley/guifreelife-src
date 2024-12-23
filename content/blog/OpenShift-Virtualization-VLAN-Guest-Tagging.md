---
title: "OpenShift Virtualization VLAN Guest Tagging"
date: 2024-12-22
banner: /images/vgt-trunk.jpeg
layout: post
mermaid: false
asciinema: true
draft: true
tags:
  - networking
  - openshift
  - kubernetes
  - virtualization
description: Some workloads require the use of VLAN tagged interfaces in virtual machines. VMware terms this feature VGT. OpenShift Virtualization supports this feature using traditional Linux Bridge interfaces. This post details and demonstrates an implementation.
---

Some workloads require the use of VLAN interfaces in virtual machines. VMware terms this feature "Virtual Guest Tagging" or "VLAN Guest Tagging" while OpenStack calls it "VLAN-aware instances". OpenShift Virtualization can support this feature using traditional Linux Bridge interfaces.

<!--more-->

# OVS Bridge and Linux Bridge

OpenShift networking uses the [OVN-Kubernetes][4] CNI which includes support for a `localnet` topology layered upon an OVS Bridge. See this [previous post][9] on OVN. While OVN is the most featureful and recommended interface, it does [not yet support][7] VLAN tags through a localnet attachment.

Fortunately this can be accomplished using a Linux Bridge interface. 
An alternative solution would be to use an SR-IOV capable NIC which can support QinQ.

## Define the Linux Bridge

It's important to note that a host NIC can not be assigned to both an OVS Bridge and a Linux Bridge at the same time, so a dedicated host NIC will be required for this feature.

Create a Linux bridge called `br-trunk` on a dedicated NIC called ens256.

>  📓 **`NodeNetworkConfigurationPolicy` to create Linux Bridge `br-trunk`**
>  If ens256 is not in every host you'll need to add add a NodeSelector. 
>  [ref](https://github.com/dlbewley/demo-virt/blob/main/demos/vgt/components/br-trunk/linux-bridge/nncp.yaml)

{{< collapsable prompt="br-trunk nncp.yaml" collapse=false md=true >}}
```yaml {linenos=inline,hl_lines=[17,21,29]}
---
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: br-trunk
spec:
  desiredState:
    interfaces:
      - name: ens256
        ipv4:
          enabled: false
        ipv6:
          enabled: false
        state: up
        type: ethernet

      - name: br-trunk
        description: |-
          A dedicated OVS bridge with ens256 as a port
          allowing all VLANs and untagged traffic.
        type: linux-bridge
        state: up
        bridge:
          options:
            stp:
              enabled: false
          port:
            - name: ens256
              vlan: {}
```
{{< /collapsable >}}

Now create a network attachment definition called `trunk` in the demo-vgt namespace. It will be a cnv-bridge type and reference the `br-trunk` interface just created above.

>  📓 **`NetworkAttachmentDefinition` to form a an 802.1q trunk from a Linux Bridge to VM**
>  [ref](https://github.com/dlbewley/demo-virt/blob/main/demos/vgt/components/trunk/linux-bridge/nad.yaml)

{{< collapsable prompt="trunk nad.yaml" collapse=false md=true >}}
```yaml {linenos=inline,hl_lines=[17,21,29]}
---
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  annotations:
    description: 802.1q Trunk Connection
  name: trunk
  namespace: demo-vgt
spec:
  # the name below is the name of a cluster-scoped "network"
  # omitting vlanId on Linux Bridge results in all VLANs passed
  # omitting vlan on OVS Bridge results in only VLAN 0 passing
  config: |-
    {
      "cniVersion": "0.4.0",
      "name": "trunk",
      "type": "cnv-bridge",
      "macspoof": false,
      "bridge": "br-trunk",
      "netAttachDefName": "demo-vgt/trunk",
      "vlanId": {},
      "ipam": {}
    }
```
{{< /collapsable >}}

# Demo VLAN Guest Tagging

**Demo ([source][6]): 802.1q trunk to a VM using linux-bridge on the host and cnv-bridge type NetworkAttachmentDefinition**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Setup, test, and cleanup. </p>
  {{< asciinema key="vgt-linux-br-20241222" rows="40" font-size="smaller" poster="npt:0:35" loop=false >}}
  {{< /collapsable>}}

# Summary

OVS Bridging + `localnet` topology is the recommended way to attach a OpenShift Virtualization VM guest to a provider VLAN. (Stand by for User Defined Networks feature!) However, when there is a need to pass VLAN tags all the way through to the VM guest your options become special SR-IOV hardware or a Linux Bridge. You just saw how to implement the linux bridge solution.

# References

* [Demo Source][6]
* [Container Network Interface Specification][2]
* [OVN-Kubernetes CNI Plugin][3] - github.com
* [OVN-Kubernetes][4]
* [RFE Support Trunking on OVN-K8s Localnet][7]
* [Linux Bridge][8]
* [GUI Free Life OVN Inspection][9] post
* [OpenStack VLAN Aware Instances][10]

[2]: <https://github.com/containernetworking/cni/blob/spec-v0.4.0/SPEC.md> "CNI v0.4.0 Specification"
[3]: <https://github.com/ovn-org/ovn-kubernetes> "OVN-Kubernetes CNI Plugin"
[4]: <https://ovn-kubernetes.io/> "OVN-Kubernetes"
[6]: <https://github.com/dlbewley/demo-virt/tree/main/demos/vgt> "Demo Source"
[7]: <https://issues.redhat.com/browse/RFE-6831> "RFE Support Trunking on OVN-K8s Localnet"
[8]: <https://developers.redhat.com/articles/2022/04/06/introduction-linux-bridging-commands-and-features> "Linux Bridge"
[9]: {{< ref "/blog/Open-Virtual-Network-Inspection-on-OpenShift.md" >}} "Open Virtual Network Inspection on OpenShift" 
[10]: <https://docs.redhat.com/en/documentation/red_hat_openstack_services_on_openshift/18.0/html/managing_networking_resources/vlan-aware-instances_rhoso-mngnet#vlan-aware-instances_rhoso-mngnet> "OpenStack VLAN Aware Instances"