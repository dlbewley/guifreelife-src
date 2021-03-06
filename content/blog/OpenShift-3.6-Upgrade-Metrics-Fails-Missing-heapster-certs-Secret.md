---
title: OpenShift 3.6 Upgrade Metrics Fails Missing heapster-certs Secret
banner: /img/banners/banner-7.jpg
date: 2017-10-13
layout: post
tags:
 - openshift
 - OCP3
 - troubleshooting
---

After your upgrade to OpenShift v3.6 did the [deployment of cluster metrics](https://docs.openshift.com/container-platform/3.6/install_config/cluster_metrics.html) wind up with empty graphs? Check if the heapster pod failed to start due to a missing secret called `heapster-certs` in the `openshift-infra` namespace.

# Problem #

**Heapster pod is failing to start**

```bash
$ oc get pods
NAME                         READY     STATUS              RESTARTS   AGE
hawkular-cassandra-1-l1f3s   1/1       Running             0          9m
hawkular-metrics-rdl07       1/1       Running             0          9m
heapster-cfpcj               0/1       ContainerCreating   0          3m
```

**Check what volumes it is attempting to mount**

```bash
$ oc volume rc/heapster
replicationcontrollers/heapster
  secret/heapster-secrets as heapster-secrets
    mounted at /secrets
  secret/hawkular-metrics-account as hawkular-metrics-account
    mounted at /hawkular-account
  secret/hawkular-metrics-certs as hawkular-metrics-certs
    mounted at /hawkular-metrics-certs
  secret/heapster-certs as heapster-certs
    mounted at /heapster-certs
```

**Check for the existence of the heapster-certs secret**

```bash
$ oc get secrets heapster-certs
Error from server (NotFound): secrets "heapster-certs" not found
```

# Solution #

Maybe you, like I, overlooked a [v3.3 tech preview feature](https://docs.openshift.com/container-platform/3.3/release_notes/ocp_3_3_release_notes.html#ocp-33-technology-preview) called [service serving certificates](https://docs.openshift.com/container-platform/3.3/dev_guide/secrets.html#service-serving-certificate-secrets). You missed that this became mandatory in v3.6 because it is [not yet](https://bugzilla.redhat.com/show_bug.cgi?id=1501994) in the release notes. See also [this bug](https://bugzilla.redhat.com/show_bug.cgi?id=1500981).

However, even if you have `/etc/origin/master/service-signer.crt` in my case it was not visible because of [this commit](https://github.com/openshift/openshift-ansible/commit/3e5d38caf39d53c917a78542a04ebb6a109e7e6f) to the v3.3 upgrade playbook had a typo placing `servicesServingCert` instead of `serviceServingCert` in `/etc/origin/master/master-config.yaml`. e.g.

```yaml
controllerConfig:
  serviceServingCert:
    signer:
      certFile: service-signer.crt
      keyFile: service-signer.key
```

And now it has been fixed in [PR 5765](https://github.com/openshift/openshift-ansible/pull/5765)
