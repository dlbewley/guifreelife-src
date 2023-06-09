---
title: "Storing-OpenShift-Credentials-with-1Password"
date: 2023-06-09
layout: post
tags:
 - openshift
 - OCP4
 - security
 - draft
---

If you find your self frequently building OpenShift clusters and potentially reusing cluster names you may find it challanging to manage the credentials.

* Store or update credentials in 1Password

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 ocp21p >}}

* Read credentials from 1Password 

{{< gist dlbewley 3a862af8c68b03d7477ed847261345a7 .env >}}
