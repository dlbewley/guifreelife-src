---
title: "Accessing the Ceph CLI with OpenShift Data Foundation"
banner: /images/uncovered-bumper.png
date: 2023-04-06
layout: post
tags:
  - kubernetes
  - OCP4
  - openshift
  - storage
  - troubleshooting
description: How to access the Ceph Toolbox CLI for debugging OpenShift Data Foundation
---

The Ceph Toolbox is not recommended or supported for use with OpenShift Data Foundation, but sometimes you want a client to troubleshoot with anyway.

<!--more-->

# Script for Enabling the Rook Ceph Toolbox

This script will cause the toolbox pod to be created and rsh to it enabling you to run ceph [troubleshooting commands](https://docs.ceph.com/en/quincy/rados/troubleshooting/index.html) such as the following.

* `ceph status`
* `ceph osd status`
* `ceph osd pool ls`
* `ceph df`
* `rados df`

{{< gist dlbewley ba5686b47e915d5ac7ebd37f400759b0 "ceph-toolbox.sh" >}}

> :star: **Warning**
>
> _It is important that you not attempt to make any changes on the command line!_
>
> See the documentation in the [references](#references) below for properly supported troubleshooting methods.

# Example Run


```bash
$ ./ceph-toolbox.sh
ocsinitialization.ocs.openshift.io/ocsinit patched
waiting for ceph tools pod to schedule .........pod/rook-ceph-tools-565ffdb78c-sf2bf
waiting for ceph tools pod to startup
pod/rook-ceph-tools-565ffdb78c-sf2bf condition met
sh-4.4$
sh-4.4$ ceph osd status
ID  HOST                      USED  AVAIL  WR OPS  WR DATA  RD OPS  RD DATA  STATE
 0  hub-q4jtr-store-1-5nlkv   299G   724G      1      135k      1        0   exists,up
 1  hub-q4jtr-store-2-652pc   299G   724G      0     18.3k      3      105   exists,up
 2  hub-q4jtr-store-3-mtddc   299G   724G      2     18.4k      2      241   exists,up
sh-4.4$ ^d
$
$ ./ceph-toolbox.sh off
ocsinitialization.ocs.openshift.io/ocsinit patched
removing any existing toolbox pod
pod "rook-ceph-tools-565ffdb78c-sf2bf" deleted
```

# References

* [Red Hat OpenShift Data Foundation](https://access.redhat.com/products/red-hat-openshift-data-foundation)
* [Troubleshooting Red Hat OpenShift Data Foundation](https://access.redhat.com/documentation/en-us/red_hat_openshift_data_foundation/4.12/html/troubleshooting_openshift_data_foundation/index)
