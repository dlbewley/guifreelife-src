---
title: "Extracting TLS CA Certificates from Kubeconfig File"
banner: /img/banners/banner-buffy-xmas.png
date: 2023-03-09
layout: post
tags:
  - kubernetes
  - OCP4
  - openshift
  - ssl
  - kubeconfig
  - security
description: How to extract and split the CA certificates into individual files from an OpenShift kubeconfig.
---

OpenShift creates a number of Certificate Authorities to sign TLS certificates which secure functions including load balancing of the API and Ingress services.
Recent versions of openshift-install will place all the CA certificates in the generated `auth/kubeconfig` file. 

Here is how to extract and split those certificates into individual files which eases the process of trusting them particularly on a Mac.

<!--more-->

# Script for Extracting Certificates

This script will extract all the certificates associated with the first cluster found in `$KUBECONFIG`. You will need [yq](https://mikefarah.gitbook.io/yq/).

{{< gist dlbewley 639bc786e3eb595362bf807225570abf "ext-kubeconfig-cacerts.sh" >}}

# Example Run

Extract the TLS certs from the kubeconfig generated during an OpenShift installation.

```bash
$ export KUBECONFIG=auth/kubeconfig

$ ext-kubeconfig-cacerts.sh
x.apps.hub.lab.bewley.net
ingress-operator@1675639609
kube-apiserver-localhost-signer
kube-apiserver-service-network-signer
kube-apiserver-lb-signer

$ ls -1
ingress-operator@1675639609.pem
kube-apiserver-lb-signer.pem
kube-apiserver-localhost-signer.pem
kube-apiserver-service-network-signer.pem
kubeconfig-ca-data.pem
x.apps.hub.lab.bewley.net.pem
```

## Trusting the Certs

Now you may drag and drop these certs onto the Keychain app on your Mac, then set them to Always Trust. Or on your Linux box place them in `/etc/pki/ca-trust/source/anchors`.

* ingress-operator\@1675639609.pem
* kube-apiserver-lb-signer.pem
* kube-apiserver-localhost-signer.pem
* kube-apiserver-service-network-signer.pem
