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
description: Open Virtual Network is the engine behind the default CNI for OpenShift. This short post describes how to peek under the covers.
---

Intro

<!--more-->

# VLAN Guest Tagging

{{< asciinema key="vgt-linux-br-20241222" rows="40" font-size="smaller" poster="npt:0:35" loop=false >}}

# Summary

# References

* [Open Virtual Switch][5]
* [Open Virtual Network][1]
* [OVN-Kubernetes][4]
* [OVN-Kubernetes CNI Plugin][3] - github.com
* [Container Network Interface Specification][2]
* [My ovncli.sh script][6]

[2]: <https://github.com/containernetworking/cni/blob/spec-v0.4.0/SPEC.md> "CNI v0.4.0 Specification"
[3]: <https://github.com/ovn-org/ovn-kubernetes> "OVN-Kubernetes CNI Plugin"
[4]: <https://ovn-kubernetes.io/> "OVN-Kubernetes"
[5]: <https://www.openvswitch.org/> "Open Virtual Switch"
[6]: <https://github.com/dlbewley/demo-virt/tree/main/demos/vgt> "Demo Repo"
