---
title: Storing OpenShift Credentials with 1Password
date: 2023-06-09
layout: post
banner: /img/banners/mushroom-moss.jpg
tags:
 - openshift
 - OCP4
 - security
 - draft
description: How to securely manage credentials for multiple Kubernets clusters using 1Password
---

If you find yourself frequently rebuilding OpenShift clusters and potentially reusing cluster names, you may find it challanging to manage the credentials consistently and securely. Here is a solution using [1Password][2].

<!--more-->

When you interact with a kubernetes cluster, the `kubectl` or `oc` client will read and store configuration details in a file. The default location of that file will be `$HOME/.kube/config`, but it can be redefined using a `KUBECONFIG` environment variable.

# Kubeconfig Data

The [kubeconfig contains the CA certificates][1] used to validate communication with a cluster. If you rebuild a cluster these certificates will change and you'll no longer have the proper certificate. During installation OpenShift will create a client certificate used to authenticate a default admin user which is stored here, and at the end of installation the CA for the ingress controller is also appended. And finally, if you change namespaces or log into another cluster, these details will be appended to your kubeconfig as a new "context" as well.

For all of these reasons, I prefer to keep a clean and distinct kubeconfig for each cluster I interact with.

In addition to the kubeconfig, OpenShift generates a password for a user named `kubeadmin`. These credentials are useful for initial interaction with the cluster via the web browser. If a cluster is long lived these credentials are typically replaced and deleted as a best practice, but having them readily available in 1Password can be very helpful.

How can you quickly and easily get your kubeconfig and kubeadmin credentials stored in 1Password?

# Storing Kubernetes Credentials in 1Password

Store or update kubeconfig credentials in 1Password with the following script.

> :notebook: _There's a bug here. When updating an existing entry. The kubadmin password will be repeated. Do you know why?_

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 ocp21p >}}

# Reading Kubernetes Credentials from 1Password
Once credentials are stored in 1Password you can refer to them in an env file like the following.

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 ".env" >}}

# Organizing Kubeconfigs for Multiple Clusters

You may accumulate a few clusters over time. By creating a unique directory for each and a unique env file you may arrive at something like this:

```shell
$ tree -L 1 ~/.kube/ocp
/Users/dale/.kube/ocp
├── aws
├── demo
├── gcp
├── hub
├── hub-aws
├── hyper
├── rhpds
└── rosa
```

Select one of the above clusters by sourcing the corresponding env file like this.

```bash
$ source ~/.kube/ocp/hub/.env
$ echo $KUBECONFIG
/Users/dale/.kube/ocp/hub/kubeconfig
$ oc whoami
system:admin
```



[1]: {{< ref "/blog/Extracting-CA-Certs-From-Kubeconfig.md" >}} "Extracting CA Certs From Kubeconfig"
[2]: <https://developer.1password.com/docs/cli/get-started/> "Get started with 1Password CLI"
[3]: <https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/> "Organizing Cluster Access Using kubeconfig Files"
[4]: {{< ref "/blog/RHACM-Recover-Created-Cluster-Credentials-and-Kubeconfig.md" >}} "RHACM-Recover-Created-Cluster-Credentials-and-Kubeconfig"
