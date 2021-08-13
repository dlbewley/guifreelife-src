---
title: Recovering kubeconfig for a Cluster Created with RHACM
banner: /img/banners/banner-22.jpg
date: 2021-08-13
layout: post
tags:
  - openshift
  - RHACM
  - hybrid-cloud
---

[Red Hat Advanced Cluster Management for Kubernetes][1] and it's upstream [Open Cluster Management][2] automate cluster lifecycle management from creation, configuration, upgrade, and destruction.

If a cluster is created by RHACM you may need to download the kubeadmin password and the kubeconfig. This is easily accomplished by browsing to the RHACM cluster overview, but how do you do the same from the CLI?

# ClusterDeployment

The creation of a cluster starts with a ClusterDeployment which will be interpreted by [Hive][3]. Subsequently associated kubeconfig and kuebadmincreds secrets will be generated holding the values we are looking for.

# Script

Use this script to extract the kubeconfig and kubeadmin credentials of a managed cluster that was deployed by RHACM.

{{< gist dlbewley f57eb2bb5b69d2db0df7b171329a68cc >}}


[1]: https://access.redhat.com/products/red-hat-advanced-cluster-management-for-kubernetes/ "RHACM"
[2]: https://open-cluster-management.io/ "OCM"
[3]: https://github.com/openshift/hive "Hive"