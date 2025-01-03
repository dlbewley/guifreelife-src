---
title: "OpenShift Virtualization VLAN Guest Tagging"
date: 2025-01-02
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

Some workloads require the use of VLAN interfaces in virtual machines. VMware terms this feature "Virtual Guest Tagging" or "VLAN Guest Tagging" while OpenStack calls it "VLAN-aware instances". OpenShift Virtualization can implement this use case with traditional Linux Bridge interfaces.

<!--more-->

# Bridges and VLANs

{{< figure src="/images/openshift-virt-switch-tags.gif" title="Animation of VLAN tagged frames traversing a switch" class="pull-right" >}}

Chances are you are far too young to have ever seen a hardware bridge in the origional form. Traditionally a bridge simply existed to relay frames (_just think packets_) from one physical segment to another. A switch is an evolved bridge with more intelligence.

Switches understand which port a MAC address was seen on and can make more efficient decisions when directing frames. Additionally switches can be segmented into multiple broadcast domains though the use of VLANs.

An uplink on a switch may be passing in an 802.1q trunk which adds a tag identifying a VLAN to every frame. The tags remain on the frame until it is passed out a port which is configured as an "access port" associated with a specific VLAN.

That's normally exactly what you want, but in this case we want to create a port leading to a VM as a trunk port instead of a typical access port.
In that case the tags will remain intact when reaching a VM.


# OVS Bridge and Linux Bridge

OpenShift networking uses the [OVN-Kubernetes][4] CNI which includes support for a `localnet` topology layered upon an OVS Bridge. See this [previous post][9] on OVN. While OVN is the most featureful and recommended interface, it does [not yet support][7] VLAN tags through a localnet attachment.

Fortunately this can be accomplished using a Linux Bridge interface. A Linux Bridge has some intelligence in handling the ports attached to it like a switch.

## Creating the Linux Bridge

It's important to note that a host NIC can not be assigned to both an OVS Bridge and a Linux Bridge at the same time, so a dedicated host NIC will be required.

Here we create a Linux bridge called `br-trunk` on a dedicated NIC called `ens256`.

>  📓 **`NodeNetworkConfigurationPolicy` to create Linux Bridge `br-trunk`**
>  If ens256 is not in every host you'll need to add add a NodeSelector. 
>  [ref](https://github.com/dlbewley/demo-virt/blob/main/demos/vgt/components/br-trunk/linux-bridge/nncp.yaml)

* {{< collapsable prompt="br-trunk nncp.yaml" collapse=false md=true >}}
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

Next create a network attachment definition called `trunk` in the demo-vgt namespace. It will be a cnv-bridge type and reference the `br-trunk` interface just created above.

>  📓 **`NetworkAttachmentDefinition` to form a an 802.1q trunk from a Linux Bridge to VM**
>  [ref](https://github.com/dlbewley/demo-virt/blob/main/demos/vgt/components/trunk/linux-bridge/nad.yaml)

* {{< collapsable prompt="trunk nad.yaml" collapse=false md=true >}}
```yaml {linenos=inline,hl_lines=[17,19,21]}
---
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  annotations:
    description: 802.1q Trunk Connection
  name: trunk
  namespace: demo-vgt
spec:
  # omitting vlanId on Linux Bridge results in all VLANs passed
  # omitting vlan on OVS Bridge results in only VLAN 0 (native) passing
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

# Demos

## Host to Guest VLAN Tagging

In this demo, the provider VLAN 1924 (meaning existing outside the OpenShift cluster) is among several VLAN tags trunked to `ens256` on the OpenShift Node. You will see a VLAN interface created in the VM called `eth1.1924` which is directly attached to this physical VLAN.

**Demo ([source][6]): 802.1q trunk to a VM using linux-bridge on the host and cnv-bridge type NetworkAttachmentDefinition**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Setup bridge & network attachment, create VMs, test networking, and cleanup. </p>
  {{< asciinema key="vgt-linux-br-20241222" rows="40" font-size="smaller" poster="npt:0:35" loop=false >}}
  {{< /collapsable>}}

## Guest to Guest VLAN Tagging

When the VM NIC is attached via Linux Bridge it also becomes possible to make up arbitrary VLAN interfaces to trunk between virtual machines. In otherwords you can make up your own VLAN tags and trunk them peer-to-peer between VMs. 

This demo shows made up VLANs 222 and 333 being created from thin air and passed between 2 VMs via the same `trunk` attachment to the `br-trunk` Linux Bridge used above.

**Demo ([source][6]): 802.1q trunk between VMs using linux-bridge on the host and cnv-bridge type NetworkAttachmentDefinition**

* {{< collapsable prompt="VM network-setup.sh" collapse=true md=true >}}
```bash
# create eth1.222 and eth1.333 VLAN interfaces
# use .1 IP on first VM and .2 IP on second VM to enable ICMP test
NIC=eth1
VLAN=222

nmcli -f connection.id con show $NIC.$VLAN 2>&1 > /dev/null

if [ $? -ne 0 ]; then
  nmcli connection add type vlan \
    con-name $NIC.$VLAN \
    ifname $NIC.$VLAN \
    vlan.parent $NIC \
    vlan.id $VLAN
fi

nmcli connection modify $NIC.$VLAN \
  ipv4.route-metric 222 \
  ipv4.method static \
  ipv4.address 10.2.2.1/24

nmcli connection up $NIC.$VLAN

VLAN=333

nmcli -f connection.id con show $NIC.$VLAN 2>&1 > /dev/null

if [ $? -ne 0 ]; then
  nmcli connection add type vlan \
    con-name $NIC.$VLAN \
    ifname $NIC.$VLAN \
    vlan.parent $NIC \
    vlan.id $VLAN
fi

nmcli connection modify $NIC.$VLAN \
  ipv4.route-metric 333 \
  ipv4.method static \
  ipv4.address 10.3.3.1/24

nmcli connection up $NIC.$VLAN
```
{{< /collapsable >}}

> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Demonstrate peer to peer VLAN trunking </p>
  {{< asciinema key="vgt-linux-br-p2p-20250102" rows="40" font-size="smaller" poster="npt:0:35" loop=false >}}
  {{< /collapsable>}}


# Summary

OVS Bridging + `localnet` topology is the recommended way to attach a OpenShift Virtualization VM guest to a provider VLAN. However, when there is a need to pass VLAN tags all the way through to the VM guest your options become special SR-IOV hardware or a Linux Bridge. You just saw how to implement the linux bridge solution.

Stand by for OpenShift's User Defined Networks feature which is just around the corner. UDN will bring greater flexibility, simplicity, tenancy, and enhanced support for "bringing your own netork". However, UDN will not support VLAN tags out of the gate.

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