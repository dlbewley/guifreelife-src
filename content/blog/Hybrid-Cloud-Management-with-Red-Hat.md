---
title: Hybrid Cloud Management With Red Hat
date: 2022-09-19
asciinema: true
banner: /images/port-of-oakland-night.png
layout: post
tags:
 - hybrid-cloud
 - openshift
 - RHACM
 - RHACS
 - webinar
notes_url: https://docs.google.com/document/d/1xvXiDdRqrWoma5Zb52H3YRkT0wCNpVj3Oj_8FX6X4FE/edit#
description: Demo of Red Hat Advanced Cluster Management management of AWS EKS and the automated deployment of Red Hat Advanced Cluster Security by policy.
---

Whether workloads are in the datacenter, in the cloud, or even in multiple clouds, OpenShift provides a consistent experience. And the Hybrid Cloud Console is your entry point for Red Hat cloud services to enable the most effective use of each environment. This video demo walks through the provisioning of [ROSA][18] and using Red Hat Advanced Cluster Management with EKS. Finally, [RHACM][2] policies are deployed to ensure automatic application of Red Hat Advanced Cluster Security.

<!--more-->

> :notebook: _Check out the 2021 [RHACM][10] and [RHACS][11] walkthroughs._

_So what does the demo cover?_

# Hybrid Cloud Management

The Red Hat [Hybrid Cloud Console][1] is the gateway to cloud services and tools for managing hybrid cloud environments and supporting services like Ansible Automation Platform, RHEL image building, and [Application and Data Services][14] like Data Science, Streams for Apache Kafka, and API Management and much more. Read more about it [here][19].

The [OpenShift Cluster Manager][9] centralizes cluster metrics and alerts relayed through telemetry that enables Insights recommendations for cluster management.  This is also a great place to find information on the latest versions of OpenShift including links to the release notes and downloads for command line tools. Here you may also review your support cases and subscription allocations over time.

# Red Hat OpenShift Service on AWS 

Red Hat OpenShift Service on AWS ([ROSA][18]) allows you to draw down on negotiated spending commitments with AWS. Experienced Red Hat site reliability engineers manage the platform while your developers focus on what matters; your workloads.

> ⭐ **Pro Tip:** Get started right in the AWS console! Just search for "OpenShift".

# Red Hat Advanced Cluster Management

[RHACM][2] manages cluster and application life cycles, applies consistent governance, and enables observation of your entire Kubernetes fleet.
Not only OpenShift, but clusters still based on technologies like AKS, EKS, and GKE benefit from advanced cluster management as well. More details [here][3].

RHACM enables search and discovery of resources across all managed clusters simultaneously, and it [aggregates metrics and logs][12] from your managed clusters enabling centralized dashboards and alerting. The demo illustrates an example EKS cluster managed by RHACM with, cluster metrics aggregated to a single pane of glass.

**Demo: Deployment EKS and Kube Metrics Server**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=true >}}
  <p>EKS with Metrics Server Deployment</p>
  {{< asciinema key="deploy-eks-and-metrics-20220531" rows="50" font-size="smaller" poster="npt:0:27" loop=false >}}
  {{< /collapsable>}}

# Red Hat Advanced Cluster Security

Red Hat Advanced Cluster Security ([RHACS][7]) can be automatically deployed to ensure developers can take advantage of DevSecOps on any cluster in your fleet. The demo will apply [Open Cluster Management][5] governance policies [from git][4] to enable a GitOps approach to policy enforcement. The policies deployed will provision RHACS on managed clusters without any interaction. 

Also see [RHACS in action][11] in this previous video demonstration.

# Video Demo

Finally, check out the demo!

**Demo: ROSA Deploy and configure, RHACM import of EKS, and automated RHACS deployment**
> {{< collapsable prompt="📺 YouTube Video" collapse=false >}}
  <p>This video was part of Red Hat's <a href="https://red.ht/openshiftshowandtell2022">OpenShift Show and Tell</a> summer 2022 webinar series.</p>
  {{% youtube YTJFwGoeyb4 %}}
  {{</collapsable>}}

⭐ **Pro Tip:** You can kick the tires in a [Free OpenShift Developer Sandbox][15]

# References

* [Demo Source][4]
* [Open Cluster Management][5]
* [OpenShift Cluster Manager][9]
* [OpenShift Developer Sandbox][15]
* [Red Hat Advanced Cluster Management for Kubernetes 2.5 Support Matrix][3]
* [Red Hat Advanced Cluster Management for Kubernetes][2]
* [Red Hat Advanced Cluster Security for Kubernetes][7]
* [Red Hat Application and Data Services][14]
* [Red Hat Hybrid Cloud Console][19]
* [Red Hat Observability Service][12]
* [Red Hat OpenShift Service on AWS][18]
* [RHACM Walkthrough 2021][10]
* [RHACS Walkthrough 2021][11]
* [BrightTALK Application portability and multicluster management][13]

[1]: https://console.redhat.com "Red Hat Hybrid Cloud Console"
[2]: https://www.redhat.com/en/technologies/management/advanced-cluster-management "Red Hat Advanced Cluster Management for Kubernetes"
[3]: https://access.redhat.com/articles/6663461 "Red Hat Advanced Cluster Management for Kubernetes 2.5 Support Matrix"
[4]: https://github.com/dlbewley/demo-acm "ACM Demo Source"
[5]: https://open-cluster-management.io "Open Cluster Management"
[7]: https://www.redhat.com/en/technologies/cloud-computing/openshift/advanced-cluster-security-kubernetes "Red Hat Advanced Cluster Security for Kubernetes"
[8]: https://www.youtube.com/watch?v=YTJFwGoeyb4 "YouTube Red Hat ROSA, Hybrid Cloud and Advanced Cluster Management Demos"
[9]: https://console.redhat.com/openshift/overview "OpenShift Cluster Manager"
[10]: {{< ref "/blog/Red-Hat-Advanced-Cluster-Management-Walkthrough.md" >}} "RHACM Walkthrough 2021"
[11]: {{< ref "/blog/Red-Hat-Advanced-Cluster-Security-Walkthrough.md" >}} "RHACS Walkthrough 2021"
[12]: https://github.com/rhobs/configuration "Red Hat Observability Service"
[13]: https://www.brighttalk.com/webcast/15137/515127 "BrightTALK Application portability and multicluster management"
[14]: https://console.redhat.com/application-services/overview "Red Hat Application and Data Services"
[15]: https://www.redhat.com/en/technologies/cloud-computing/openshift/try-it "OpenShift Developer Sandbox"
[16]: https://docs.openshift.com/container-platform/4.9/installing/installing_sno/install-sno-preparing-to-install-sno.html "Single Node OpenShift"
[17]: https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml "Kube Metrics-Server Deployment"
[18]: https://www.redhat.com/en/technologies/cloud-computing/openshift/aws "Red Hat OpenShift Service on AWS"
[19]: https://access.redhat.com/products/red-hat-hybrid-cloud-console "Hybrid Cloud Console Product Page"

