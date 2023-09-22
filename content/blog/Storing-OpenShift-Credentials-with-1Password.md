---
title: Storing OpenShift Credentials with 1Password
date: 2023-09-22
layout: post
banner: /img/banners/mushroom-moss.jpg
tags:
 - openshift
 - OCP4
 - security
description: How to securely manage credentials for multiple Kubernets clusters using 1Password
---

If you find yourself frequently rebuilding OpenShift clusters and potentially reusing cluster names, you may find it challanging to manage the credentials consistently and securely. Here is a solution using [1Password][2].

<!--more-->

# What's in a Kubeconfig?

When you interact with a kubernetes cluster the `kubectl` or `oc` client will read and store configuration details in a file affectionately known as "kubeconfig" located at `$HOME/.kube/config`. This file contains the CA certificates or `certificate-authority-data` used to validate communication with a cluster. The file also keeps track of the usernames and namespaces you interact with. The combination of those items forms what is known as a "context", but we can ignore that concept today.

> :star: **Pro Tip:**
> See [this post][1] for details on extracting the certificate data from a kubeconfig to enable your operating system and web browser to trust your cluster.

During installation, OpenShift will create a system _admin_ user and a _kuebadmin_ user. The _admin_ user `client-certificate-data` and `client-key-data` are stored in the kubeconfig to enable passwordless authentication.

> :notebook: Example kubeconfig file
```yaml
apiVersion: v1
kind: Config
preferences: {}
clusters:
  - name: hub
    cluster:
      server: https://api.hub.lab.bewley.net:6443
      certificate-authority-data: LS0t...o=
users:
  - name: admin
    user:
      client-certificate-data: LS0t...o=
      client-key-data: LS0t...==
contexts:
  - name: admin
    context:
      cluster: hub
      user: admin
```

The _kubeadmin_ user authenticates with a password, which is not available in the kubeconfig. As a best practice this kubeadmin user is removed, but having the kubeadmin password readily available along side the kubeconfig can be very helpful.

It is important that a kubeconfig can be easily updated or replaced, because if the CA certificates are renewed or if you rebuild the cluster the `certificate-authority-data` will be out of date, and the kubeconfig will no longer be able to verify the connection. For this reason, I maintain a distinct kubeconfig for each cluster I interact with. This is easily done by overidding the file location with the `KUBECONFIG` environment variable. 

_So, how can you quickly and easily get your kubeconfig and kubeadmin credentials stored in 1Password?_

# Storing Kubernetes Credentials in 1Password

By uploading a kubeconfig and the kubeadmin password to a 1Password vault you can always have a clean copy of this data that can be easily refreshed and shared across your systems.

The following script uses the [1Password CLI][2] to store or update the kubeconfig and kubeadmin credentials in a 1Password vault.

Start by pointing to the kubeconfig to be saved.

```bash
export KUBECONFIG=install-dir/auth/kubeconfig
```

The script will upload that file and look for a `kubeadmin-password` file in the same directory and upload that. The script will also login to the cluster to gather some other information such as the console URL, the cluster id, and creation date.

> :notebook: _There's a bug here. When updating an existing entry. The kubeadmin password will be repeated. Do you know why?_

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 ocp21p >}}

# Reading Kubernetes Credentials from 1Password

Once stored in 1Password you can read the credentials and kubeconfig by sourcing an env file written like the following. 

> :notebook: Example env file to read kubernetes credentials from 1Password

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 ".env" >}}

I keep mine organized like this with a directory per cluster.

```shell
$ find ~/.kube/ocp -name .env
/Users/dale/.kube/ocp/demo/.env
/Users/dale/.kube/ocp/validated-hub/.env
/Users/dale/.kube/ocp/gcp/.env
/Users/dale/.kube/ocp/hub-aws/.env
/Users/dale/.kube/ocp/aws/.env
/Users/dale/.kube/ocp/hyper/.env
/Users/dale/.kube/ocp/hub/.env
```

# Example Usage

Select one of the above clusters by sourcing a corresponding env file like this.

```bash
$ source ~/.kube/ocp/hub/.env
$ echo $KUBECONFIG
/Users/dale/.kube/ocp/hub/kubeconfig
$ oc whoami
system:admin
```

Now you can "kube" to your :hearts: content!

If you dedeploy the cluster, just remove the file from `~/.kube/ocp/<cluster>/kubeconfig` and repeat above to update 1Password and write out a new kubeconfig.
# Possible Improvements

There are other tools for managing kubernetes contexts but those seem to stem from putting too much information in one kubeconfig. I find this solution to be adequate for my needs.

As I mentioned there is a bug that duplicates the kubeadmin. Maybe you can fix it for me.

I suppose you could store the kubeconfig to a ramdisk instead of persisting it on the filesystem if you are extra paranoid. :shrug:
# References

* [Extracting CA Certs From Kubeconfig][1]
* [Get started with 1Password CLI][2]
* [Organizing Cluster Access Using kubeconfig Files][3]
* [Recovering a Kubeconfig for a Cluster Created with RHACM][4]

[1]: {{< ref "/blog/Extracting-CA-Certs-From-Kubeconfig.md" >}} "Extracting CA Certs From Kubeconfig"
[2]: <https://developer.1password.com/docs/cli/get-started/> "Get started with 1Password CLI"
[3]: <https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/> "Organizing Cluster Access Using kubeconfig Files"
[4]: {{< ref "/blog/RHACM-Recover-Created-Cluster-Credentials-and-Kubeconfig.md" >}} "RHACM-Recover-Created-Cluster-Credentials-and-Kubeconfig"
