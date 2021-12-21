---
title: Red Hat Advanced Cluster Management Walkthrough
date: 2021-12-21T09:00:00-08:00
asciinema: true
banner: /images/port-of-oakland.png
layout: post
tags:
 - openshift
 - RHACM
notes_url: https://docs.google.com/document/d/1veVSKoT9IE91oMjAHENNKnYSKhFDusQSRc7krTDTk_w/edit#heading=h.7i52732yar9x
---

Red Hat Advanced Cluster Management for Kubernetes, [RHACM][2], built on the Open Cluster Management [project][1], manages Kubernetes distributions like AKS, EKS, GKE, and OpenShift including the workloads they host. Read on for a demonstration of RHACM features like Cluster Hibernation, Cluster Pools, Multi-cluster application deployment and Observability.

Skip to the end for the complete [video demo][8] or take your time and stroll through a few quick GUI Free reanimations on your way there.
<!--more-->

# Advanced Cluster Management Features

## Cluster Lifecycle

RHACM enables cluster lifecycle management by leveraging the [Hive.OpenShift.io][7] API and its ClusterDeployment resource.
Once all the associated resources like the `install-config.yaml`, cloud provider secrets, and a handful of other resources are defined, the deployment can be driven by GitOps and CLI tools.

Spoiler alert! Keep an eye out for aspects of cluster lifecycle management to decouple a bit as the [multicluster engine][5] operator evolves.

**Demo: Cluster Deployment Using Kustomize**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=true >}}
  <p>OpenShift cluster deployment can be driven by GitOps and CLI tools.</p>
  {{< asciinema key="hive-clusterdeployment-20211002-1748" rows="50" font-size="smaller" poster="npt:0:22" loop=false >}}
  {{< /collapsable>}}

_Source: [Github][4]_

⭐ **Pro Tip:** 
The OpenShift install process creates a default admin user and a kubeconfig with TLS credentials. 
After cluster creation, [download the kubeconfig][6] from the CLI.

Full cluster lifecycle management is supported for OpenShift. See the [support matrix][3] for a breakdown by platform. For example, creation of an EKS cluster is not supported, but an existing EKS cluster and its workloads can be managed and monitored.

**Demo: Import EKS Cluster**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=true >}}
  <p>Importing an EKS cluster creates open-cluster-management namespaces to host an agent.</p>
  {{< asciinema key="import-eks--20210825-1422" rows="20" font-size="smaller" poster="npt:0:35" loop=false >}}
  {{< /collapsable>}}

## Cluster Pools

Not only one cluster at a time, but entire pools of clusters can be deployed and made available for checkout by developers or for use by transient workloads. When these clusters are not in use they are [hibernated][9] to minimize cloud provider cost. Couple this with Single Node OpenShift and it becomes much quicker and cheaper to playground an application. Clusters are not reused after checkout, so you can be sure there won't be "highlighting on the pages" from the last _borrower_. 📓

**Demo: Cluster Pool Deployment Using Kustomize**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Deploying a ClusterPool results in a namespace for each deployed cluster. Clusters are hibernated once deployed.</p>
  {{< asciinema key="deploy-clusterpool-aws-edge-20210826-1414" rows="20" font-size="smaller" poster="npt:1:01" loop=false >}}
  {{</collapsable>}}

## Multicluster Observability

ACM brings a single pane of glass to your entire cluster fleet. ACM enables search and discovery of resources across all managed clusters simultaneously.

<!-- {{< figure src="/images/RHACM-ObservabilityArch.png#floatright" link="/images/RHACM-ObservabilityArch.png" width="60%" >}} -->

In addition to this comprehensive inventory, the ACM observability add-on will [aggregate metrics and logs][12] from your managed clusters enabling centralized dashboards and alerting.

## Application Lifecycle

Applications can be deployed to multiple clusters through "channels" referencing Helm charts, git repos, or container images. Subscription to the channels is automated by PlacementRules that targets labels that have been applied to cluster deployments. Refer to the [video demo](#video-demo) for greater coverage.

**Demo: Uniform Multicluster Application Deployment**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=true >}}
  <p>Deploying application to AWS, Azure, and vSphere with no code changes.</p>
  {{< asciinema key="dev-pacman-deploy-20211007-1316" rows="20" font-size="smaller" poster="npt:0:09" loop=true >}}
  {{</collapsable>}}

⭐ **Pro Tip:** Test out your existing applications in a [Free OpenShift Developer Sandbox][15]

## Governance Risk and Compliance

Not included in the demo is proper treatment of the Governance and Compliance features of RHACM. These enable centralized policy enforcement for infrastructure, applications, and security. This [blog post][14] goes into the subject at depth.

## ClusterSets and Submariner

The clusters managed by RHACM can be grouped into ClusterSets which allow for grouping of clusters for purposes like role based access control and inter-cluster networking with [Submariner][11].

##  Ansible and ArgoCD Integration

The applications inventories known to OpenShift GitOps or ArgoCD on managed clusters are discovered by the RHACM hub cluster and can be leveraged in automations.

Finally, Ansible automations can be associated with cluster lifecycle events and policy violations to drive infrastructure operations for resources that may exist outside of Kubernetes.

# Video Demo

All that preamble was just a little context for the following. This video was recorded for a [BrightTALK][13] a couple of months go. It will hopefully provide you a clearer picture of just some of RHACMs capabilities.

**Demo: Overview of RHACM obeservability and appplication & cluster lifecycle features.**
> {{< collapsable prompt="📺 YouTube Video" collapse=false >}}
  <p>This video was part of Red Hat's <a href="https://www.brighttalk.com/webcast/15137/515127">BrightTALK Show and Tell</a> summer  2021 webinar series.</p>
  {{% youtube rS9IatJBRP8 %}}
  {{</collapsable>}}

# References

* [Demo Source][4]
* [Red Hat Advanced Cluster Management for Kubernetes][2]
* [Hive API][7]
* [Multicluster Engine][5]
* [Red Hat Advanced Cluster Management for Kubernetes 2.4 Support Matrix][3]
* [Recover Kubeconfig from RHACM Created Cluster][6]
* [Observatorium.io][12]
* [Open-Cluster-Management.io][1]
* [Submariner Blog Post][10]
* [Submariner.io][11]
* [BrightTALK Application portability and multicluster management][13]
* [Implement Policy-based Governance Using Configuration Management of RHACM][14]
* [OpenShift Developer Sandbox][15]

[1]: https://open-cluster-management.io/ "Open Cluster Management"
[2]: https://www.redhat.com/en/technologies/management/advanced-cluster-management "Red Hat Advanced Cluster Management for Kubernetes"
[3]: https://access.redhat.com/articles/6218901 "Red Hat Advanced Cluster Management for Kubernetes 2.4 Support Matrix"
[4]: https://github.com/dlbewley/demo-acm "ACM Demo Source"
[5]: https://github.com/open-cluster-management/mce-docs "Multicluster Engine"
[6]: {{< ref "/blog/RHACM-Recover-Created-Cluster-Credentials-and-Kubeconfig.md" >}} "Recover Kubeconfig from RHACM Created Cluster"
[7]: https://github.com/openshift/hive "Hive"
[8]: https://www.youtube.com/watch?v=rS9IatJBRP8 "YouTube Red Hat Advanced Cluster Management Demos"
[9]: https://github.com/open-cluster-management/hibernate-cronjob "Cluster Hibernate Cronjob"
[10]: https://cloud.redhat.com/blog/connecting-managed-clusters-with-submariner-in-red-hat-advanced-cluster-management-for-kubernetes "Submariner Blog Post"
[11]: https://submariner.io/ "Submariner"
[12]: https://github.com/observatorium/observatorium "Observatorium"
[13]: https://www.brighttalk.com/webcast/15137/515127 "BrightTALK Application portability and multicluster management"
[14]: https://cloud.redhat.com/blog/implement-policy-based-governance-using-configuration-management-of-red-hat-advanced-cluster-management-for-kubernetes "Implement Policy-based Governance Using Configuration Management of RHACM"
[15]: https://www.redhat.com/en/technologies/cloud-computing/openshift/try-it "OpenShift Developer Sandbox"
[16]: https://docs.openshift.com/container-platform/4.9/installing/installing_sno/install-sno-preparing-to-install-sno.html "Single Node OpenShift"