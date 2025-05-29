---
title: "Deploying AutoFS and LDAP on OpenShift Virtualization"
date: 2025-05-29
# banner: /images/machineconfigs-butane.png
layout: post
mermaid: false
asciinema: true
draft: true
tags:
  - draft
  - automation
  - openshift
  - kubernetes
  - virtualization
description: Exploring an automated deployment of an NFS server, and LDAP server, and an autofs client on OpenShift Virtualization
---

Exploring an automated deployment of an NFS server, and LDAP server, and an autofs client on OpenShift Virtualization

<!--more-->

# Cloud-init
# Servers
## NFS
### User Dirs
### Exports
## LDAP
### LDAP Schemas
### Automount Maps
## Client
### SSSD


# Demo 

> {{< collapsable prompt="📺 **ASCII Screencast**" collapse=false >}}
  <p>Managing MachineConfig resources with Butane and Make</p>
  {{< asciinema key="machineconfig-20250529" rows="50" font-size="smaller" poster="npt:1:06" loop=true >}}
  {{</collapsable>}}

# Summary

VMs are cool

# References

* [Demo Github Repo][1]
* [Demo Recording][2]

[1]: <https://github.com/dlbewley/demo-autofs/> "Demo Github Repo"
[2]: <https://> "Asciinema Demo Recording"