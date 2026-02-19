---
title: "OVN Recon: Making OpenShift Networking Connections"
date: 2026-02-18
layout: post
banner: /images/ovn-recon.png
asciinema: false
mermaid: false
tags:
  - networking
  - openshift
  - kubernetes
  - ovn
description: OVN Recon is an OpenShift Console plugin that helps visualize relationships across physical and logical networking resources in one topology-driven view.
---

The OpenShift networking stack, including the [OVN-Kubernetes][ovn-k] CNI, [Cluster Network Operator][cno], [NMState][nmstate] operator, and [FRR-K8s][frr] is very flexible, but it may not always be obvious how the pieces fit together to form a solution.

[OVN Recon][ovn-recon] is an OpenShift Console plugin built to make the connections that help develop your mental model for understanding OpenShift networking.

<!--more-->

# The Problem

**Networking is opaque and confusing.** 😵‍💫

Networking Configuration is multilayered. Beginning with the physical network interfaces cards which may be bound together into a logical bond, or they may also be sliced into VLAN subinterfaces. Those subinterfaces or their parents may be attached to OVS bridges or maybe Linux bridges.

These bridges may be aliased through a bridge-mapping that can be referenced to attach directly to local networks or VLANs arriving over trunks. Users can even define their own networks which replace the pod network for their namespace. These networks may be advertised over BGP through VRFs. Soon a broadcast domain may span multiple clusters with EVPN. There are just a lot of solutions for problems you may not even have.

With configuration spread across multiple resources, namespaces, operators, and APIs, navigating the configuration can be confusing. Particularly without a complete mental model.

If you are new to OpenShift, you may have a pre-existing mental model from another platform and be unsure how to adapt it. Even experienced users have a challenge as the platform gains capabilities they may be carrying around old habits that have been obviated.

# How OVN Recon Helps

> 💡 **OVN Recon helps you answer questions like:**
>
> - Which physical interface does this network traverse?
> - What networks are attached to this bridge?
> - Which namespaces have access to this network?
> - Where are UDNs being used?
> - What VRFs are advertising what subnets over BGP?

OVN Recon provides a view of the overall network configuration from the perspective of a single node. Begining with the data already gathered by [NMstate][nmstate] in the [`NodeNetworkState`][nmstate-nns] resource, it maps out the physical interfaces and arranges them in columns.

Bridges and bridge mappings are added to show how they make the logical connection from network to physical interface.

It then enumerates [`ClusterUserDefinedNetworks`][udn-ocp], and peeks at the definition to list the namespaces targeted for [`NetworkAttachmentDefinition`][nad] creation.

Cluster user defined networks may also be announced to [BGP][route-ad] peers via [`RouteAdvertisements`][route-ad], and these details are shown as details on graphed VRF interfaces along with their routing tables.

{{< figure
  src="/images/ovn-recon-ss1.png"
  width="100%"
  link="/images/ovn-recon-ss1.png"
  attrlink=""
  attr="OVN Recon Screenshot"
>}}

All these graphed resources are joined by interactive connections. When you click a bridge-mapping all the upstream and downstream elements are highlighted. Clicking a resource reveals details, relationship summaries, and a link directly to the resource in the OpenShift Console.

# Installing the OVN Recon Operator

> :warning: **Experimental**
>
> OVN Recon is "vibe coded" and **not** production-ready (and possibly off-brand for this blog). Use it at your own risk.
>
> _Evaluate OVN Recon in non-production environments only._

**Yea, but how do you install it?!**

Unless and until OVN Recon is added to the community operators catalog, you can install [my `CatalogSource`][catalog] to make it available in the "Operator Hub", which has recently been rebranded as "Ecosystem / Software Catalog" in the OpenShift Console.

**Steps:**
1. Click the ➕ icon at the top right of the OpenShift Console
2. Select "Import YAML"
3. Paste in this YAML:

> {{< collapsable prompt="🐱🪵 Bewley Operators [catalogsource.yaml](https://github.com/dlbewley/ovn-recon/blob/main/manifests/catalogsource.yaml)" collapse=false md=true >}}
  ```yaml {linenos=inline}
  apiVersion: operators.coreos.com/v1alpha1
  kind: CatalogSource
  metadata:
    name: bewley-operators
    namespace: openshift-marketplace
  spec:
    sourceType: grpc
    image: quay.io/dbewley/bewley-operator-catalog:latest
    displayName: Bewley Operators
    publisher: Dale Bewley
    updateStrategy:
      registryPoll:
        interval: 1h
  ```
  {{< /collapsable >}}
4. After a few moments navigate to "Ecosystem -> Software Catalog" (or "Operator Hub" in OpenShift < 4.20)
5. Search for "OVN Recon Operator"
{{< figure
  src="/images/ovn-recon-catalog-item.png"
  link="/images/ovn-recon-catalog-item.png"
  attrlink=""
  width="25%"
  attr=" "
>}}
6. Click "install" and accept the defaults
7. After a few moments click the button to create an instance of the "ovnrecon" resource and accept the defaults
8. After a few more moments a new "OVN Recon" menu will show up within the "Networking" menu of the console.

{{< collapsable prompt="📺 **Demo:** Operator Installation Process" collapse=true >}}
{{< figure
  src="/images/ovn-recon-install.gif"
  link="/images/ovn-recon-install.gif"
  attrlink=""
  width="100%"
  attr="OVN Recon Operator Installation Animation"
>}}
{{< /collapsable >}}

## Customizing the OVN Recon Install

You can modify the created `OvnRecon` resource to do things like track the `latest` tag instead of stable releases (Not recommended unless you are me). You can also enable the experimental `ovn-collector` component which is _very much_ a work in progress, just skip it for now.

# Current Status of OVN Recon

OVN Recon is experimental. I created it to help me help others understand how CUDNs change the networking in OpenShift. I vibe coded it in programming languages I don't know well. I used a number of different IDE and agentic tools including [Antigravity][antigravity], [Beads][beads], [Codex][codex], and [Cursor][cursor]. You should keep all that in mind.

It's still churning, but I thought others may find it helpful enough that I would post this note. YMMV.

## Roadmap

**📋 Ideas and todos:**

- Improve the details and summary tabs with more useful information and links.
- Add links to helpful documentation.
- Finish adding another view to visualize OVN components like logical switches and routers.
- Since we work from the configuration results found in NNS, we are not learning what NNCPs exist and how they affect the configuration. This could be added, but they are also already covered in the official network topology plugin... I would like to add this somehow without making things too messy.
- Make the operator OpenShift version aware.
- Add it to the Community Operators catalog some day.
- Maybe add parsing of an imported NNS to just quickly get a view of the physical configuration.
- Rebase the images to UBI, and general cleanup.

# Summary

Visualizing the relationships between networking resources can be very helpful for developing a mental model of the configuration dependencies. These relationships are where most of the complexity lives.

OVN Recon focuses on those relationships to promote:

- Better shared understanding across platform and network teams
- Shorter onboarding for engineers new to OpenShift or Kubernetes networking

Give it a try and [let me know][issues] your thoughts!

# References

- **[OVN-Recon project][ovn-recon]**
- [FRR-K8s][frr]
- [NMState Operator][nmstate]
- [NodeNetworkState resource][nmstate-nns]
- [OpenShift Cluster Network Operator][cno]
- [OpenShift Networking Documentation][openshift-networking]
- [OpenShift Route Advertisements][route-ad]
- [OVN-Kubernetes CNI][ovn-k]
- [User Defined Networks in OpenShift][udn-ocp]
- [NetworkAttachmentDefinition Specification][nad]
- [Beads: A coding agent memory system][beads]
- [Cursor][cursor]
- [Google Antigravity][antigravity]
- [OpenAi Codex][codex]
- [OpenShift Virtualization Networking Talk - Red Hat One 2026][rhone-vid]

## Continue Your Learning

I'll write some more detailed networking posts in the future. In the meantime, here's a little video.
> {{< collapsable prompt="📺 YouTube Video" collapse=false >}}
  <p>This video was a prerecording of a talk I gave at an internal and partner conference called Red Hat One.</p>
  {{% youtube fg0stTOZN6g %}}
  {{</collapsable>}}


[openshift-networking]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.21#Networking "OpenShift Networking Documentation"
[nmstate-nns]: https://nmstate.io/kubernetes-nmstate/user-guide/101-reporting.html "Kubernetes NMState and NodeNetworkState"
[nmstate]: https://nmstate.io "NMState Operator"
[udn-ocp]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/multiple_networks/primary-networks "User Defined Networks in OpenShift"
[nad]: https://github.com/k8snetworkplumbingwg/multi-net-spec/blob/master/v1.3/%5Bv1.3%5D%20Kubernetes%20Network%20Custom%20Resource%20Definition%20De-facto%20Standard.pdf "NetworkAttachmentDefinition (NAD) Specification"
[route-ad]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/advanced_networking/route-advertisements "OpenShift Route Advertisements"
[ovn-k]: https://ovn-kubernetes.io/ "OVN-Kubernetes Documentation"
[ovn-recon]: https://github.com/dlbewley/ovn-recon/ "OVN-Recon"
[rhone-vid]: https://youtu.be/fg0stTOZN6g "OpenShift Virtualization Networking - Red Hat One 2026"
[beads]: https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a "Beads"
[cursor]: https://cursor.com/home "Cursor"
[antigravity]: https://antigravity.google "Google Antigravity"
[codex]: https://chatgpt.com/codex "OpenAI Codex"
[issues]: https://github.com/dlbewley/ovn-recon/issues "OVN Recon Issues"
[cno]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/networking_operators/cluster-network-operator "OpenShift Cluster Network Operator"
[frr]: https://github.com/metallb/frr-k8s "FRR-K8s"
[catalog]: https://github.com/dlbewley/ovn-recon/blob/main/manifests/catalogsource.yaml "Bewley-Operators CatalogSource"
