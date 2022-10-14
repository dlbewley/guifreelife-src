---
title: "Autoscaling OpenShift Workloads With Custom Prometheus Metrics"
date: 2022-10-13
draft: true
banner: /images/openshift-keda-autoscaling-sequence.png
layout: post
asciinema: true
tags:
 - kubernetes
 - openshift
 - prometheus
 - OCP4
 - monitoring
---

Kubernetes enables the automated scaling of applications to meet workload demands. Historically only memory and CPU consumption could be considered in scaling decisions. Now scaling can be based on nearly anything using custom metrics. Read on to learn how the Openshift Custom Metric Autoscaler Operator and KEDA allows you to scale based on the dimensions that are important to your business.

<!--more-->

# Understanding OpenShift Monitoring

OpenShift includes monitoring and alerting out of the box. Batteries included.

Metrics are continuously collected and evaluated against dozens of predefined rules that identify potential issues. Metrics are also stored for review in graphical dashboards enabling troubleshooting and proactive capacity analysis.

All of the metrics can also be queried using ad hoc PromQL syntax in the console at _Observe -> Metrics_.

{{< figure src="/images/keda-dashboard-metrics.png" link="/images/keda-dashboard-metrics.png"  caption="OpenShift Metrics Queries" width="100%">}}

> **:star: Pro Tip:** Red Hat Advanced Cluster Management aggregates metrics from all your clusters to a single pane of glass. See posts with the [RHACM tag]({{< ref "/tags/RHACM" >}})

**What is monitored?**

Prometheus is the engine driving the metrics collection.
These metrics are collected or "scraped" from Targets which can be found in the console at _Observe -> Targets_.

These targets are defined using `ServiceMonitor` resources. For example there are ServiceMonitors for [Kube State Metrics][15]:

```bash
$ oc get servicemonitor/kube-state-metrics -n openshift-monitoring -o yaml | yq e '.spec.selector' -
matchLabels:
  app.kubernetes.io/component: exporter
  app.kubernetes.io/name: kube-state-metrics
  app.kubernetes.io/part-of: openshift-monitoring

$ oc get services -l app.kubernetes.io/component=exporter -A
NAMESPACE              NAME                 TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)            AGE
openshift-monitoring   kube-state-metrics   ClusterIP   None         <none>        8443/TCP,9443/TCP  6d
openshift-monitoring   node-exporter        ClusterIP   None         <none>        9100/TCP           6d
```

And there are ServiceMonitors that ship with add-on operators like OpenShift Data Foundation:

```bash
$ oc get servicemonitors -n openshift-storage
NAME                                              AGE
noobaa-mgmt-service-monitor                       6d
ocs-metrics-exporter                              6d
odf-operator-controller-manager-metrics-monitor   6d
rook-ceph-mgr                                     6d
s3-service-monitor                                6d
```

**Demo:** Listing the ServiceMonitors that define the Prometheus targets
> {{< collapsable prompt="📺 ASCII Screencast" collapse=true >}}
  <p>OpenShift monitors dozens of Prometheus targets defined through ServiceMonitors</p>
  {{< asciinema key="servicemonitor-keda-20221013_1456" rows="35" font-size="smaller" poster="npt:0:06" loop=false >}}
  {{< /collapsable>}}

# Understanding Horizontal Pod Autoscaling

[Horizontal pod autoscaling][14] (HPA) has been a feature since the earliest days of OpenShift. Traditionally, it has only been possible usable with CPU and memory consumption metrics.

When the CPU load of a pod reached an identified threshold, the Deployment or StatefulSet that created the pod was resized to add more pod replicas. When the load receeded, the resource was scaled down and the extra pods were terminated.

Today, using the OpenShift [Custom Metrics Autoscaler operator][5], we can create our own custom metrics and arbitrary PromQL queries can drive HPA.

The Custom Metrics Autoscaler operator is based on the upstream [Kubernetes Event Driven Autoscaling][2] project. KEDA makes it possible to trigger an autoscaling on a [number of event sources][4] or "Scalers" in the KEDA vernacular. We will use the [Prometheus scaler][15].

> **:star: Pro Tip:** This may remind you of [OpenShift Serverless][17], but the use case differs. KEDA, for example will only permit you to scale as low as 1 pod. See [Knative versus KEDA][12]

# Prerequisites

## Enabling OpenShift User Workload Monitoring

To begin monitoring of our own custom application we must first [enable user workload monitoring][13] in OpenShift.

Easy peasy.

> **Demo:** Enabling user workload monitoring
>
>  ⭐ **Pro Tip:** Use the [yq tool](https://github.com/mikefarah/yq) to do it with 2 commands

```bash
$ oc extract configmap/cluster-monitoring-config \
  -n openshift-monitoring --to=- \
  | yq eval '.enableUserWorkload = true' - > config.yaml

$ oc set data configmap/cluster-monitoring-config \
  --from-file=config.yaml -n openshift-monitoring
```

## Installing OpenShift Custom Metrics Autoscaler Operator

Next, we must install the OpenShift [Custom Metrics Autoscaler operator][5] which is built on the [KEDA][2] project. In addition to installing the operator, a `KedaController` operand must be created which will result in the deployment of pods to the openshift-keda namespace.

> **Demo:** Deploying and [configuring KEDA](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/operator) using kustomize:

```bash
$ oc apply -k operator
    namespace/openshift-keda created
    kedacontroller.keda.sh/keda created
    operatorgroup.operators.coreos.com/openshift-keda created
    subscription.operators.coreos.com/openshift-custom-metrics-autoscaler-operator created

# checking the status of KEDA
$ oc logs -f -n openshift-keda -l app=keda-operator
```
# Using Custom Metrics Autoscaling

Let's walk through an example using two applications. One will be the metered app called "prometheus-example-monitor" which exists only to provide a metric. Imagine this metric describes an amount of work piled up in a queue. The second application called "static app" actually performs the work, and it will autoscale based on the metric advertised by the metered app.

## Enabling Custom Metrics in our Application

Prometheus expects applications to provide a `/metrics` endpoint which returns data in a format it understands.  I will make use of an existing example application. See the [Prometheus docs](https://prometheus.io/docs/prometheus/latest/getting_started/) to instrument your application. We'll use a contrived example app here.

> **Demo:** Deploying an [example metered application](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/custom-metric-app) using kustomize:

```bash
$ oc apply -k custom-metric-app
    namespace/keda-test created
    service/prometheus-example-app created
    deployment.apps/prometheus-example-app created
    servicemonitor.monitoring.coreos.com/prometheus-example-monitor created
    route.route.openshift.io/prometheus-example-app created
```

> :warning: **Warning:**  Creation of a ServiceMonitor is privileged, so unless you are an admin you may have to request one of the following roles such as `monitoring-edit`.

Monitoring ClusterRoles:

* `monitoring-rules-view` grants read access to PrometheusRule custom resources for a project.
* `monitoring-rules-edit` grants create, modify, and deleting PrometheusRule custom resources for a project.
* `monitoring-edit` grants `monitoring-rules-edit` plus create new scrape targets for services or pods. With this role, you can also create, modify, and delete ServiceMonitor and PodMonitor resources.

## Understanding ServiceMonitors

> {{< figure src="/images/openshift-keda-autoscaling-sequence-1.png" link="/images/openshift-keda-autoscaling-sequence-1.png"  caption="Exposing Custom Prometheus Metrics" width="100%">}}

The OpenShift-monitoring operator automates the configuration of Prometheus. A `ServiceMonitor` resource tells Prometheus to target a Service and grab any metrics that are exported by that service.

Imagine a case where a metered-app is regularly checking a topic in Kafka to determine the length of a queue of work. We don't care to scale this application, but we want to use its knowledge to scale another app.

Using a `ServiceMontior` ([example](https://github.com/dlbewley/demo-custom-metric-autoscaling/blob/main/custom-metric-app/servicemonitor.yaml)) we tell Prometheus to connect to a service and scrape the metrics available at `/metrics`. This is what is known as a Target in Prometheus-speak.

> :warning: **Warning:** Be sure to name the port in the Service definition and reference the name not the number in the ServiceMonitor definition! Symptoms include no Target nor metrics visible in Prometheus.

Example `ServiceMonitor` resource for the metered app

```yaml  {hl_lines=[10,11]}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  labels:
    k8s-app: prometheus-example-monitor
  name: prometheus-example-monitor
spec:
  endpoints:
  - interval: 30s
    # use port name NOT port number
    port: web
    scheme: http
  selector:
    matchLabels:
      app: prometheus-example-app
```
## Deploying A Scaled Application

> **Demo:** Deploying an [example scaled application](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/scaled-app) using kustomize:

```bash
$ oc apply -k scaled-app
    namespace/keda-test unchanged
    serviceaccount/thanos unchanged
    role.rbac.authorization.k8s.io/thanos-metrics-reader unchanged
    rolebinding.rbac.authorization.k8s.io/thanos-metrics-reader unchanged
    secret/thanos-token unchanged
    service/static-app configured
    deployment.apps/static-app configured
    buildconfig.build.openshift.io/static-app configured
    imagestream.image.openshift.io/static-app configured
    scaledobject.keda.sh/static-app configured
    triggerauthentication.keda.sh/keda-trigger-auth-prometheus unchanged
    route.route.openshift.io/static-app configured
```

Notice that we did not create a HorizontalPodAutoscaler, but one was created automatically using the information in the ScaledObject resource:

```bash
$ oc get hpa
NAME                  REFERENCE               TARGETS     MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-static-app   Deployment/static-app   0/5 (avg)   1         10        1          14d
```

## Understanding Thanos

OpenShift workload monitoring actually introduces a second Prometheus instance distinct from the platform instance. KEDA will we need an intermediatary to speak to when looking up metrics. This is where Thanos fits in. The KEDA operator will be looking up metrics values by asking the Thanos-querier for them. You may think of it as a proxy to Prometheus.

The conversation with Thanos must be authenticated, and it is the `TriggerAuthentication` resource that supplies the credentials. Those credentials are the CA cert and token associated with the Thanos service account.

```yaml {hl_lines=[4]}
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: keda-trigger-auth-prometheus
spec:
  secretTargetRef:
  - parameter: bearerToken
    name: thanos-token
    key: token
  - parameter: ca
    name: thanos-token
    key: ca.crt
```

> {{< figure src="/images/openshift-keda-autoscaling-sequence-2.png" link="/images/openshift-keda-autoscaling-sequence-2.png"  caption="Using Prometheus Metrics for KEDA Autoscaling" width="100%">}}

## Understanding Scaled Objects

But what metric will be queried and what will it be used for? That is defined by the `ScaledObject` resource. Given an "object" which can be scaled, the KEDA will use the ScaledObject resource to create and program a HorizontalPodAutoscaler to be controlled by values found for the metrics are interested in.

> :notebook: Notice that the trigger contains a reference on line 35 to the `TriggerAuthentication` defined above.

```yaml {linenos=inline,hl_lines=[34,35]}
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: scaled-app
spec:
  scaleTargetRef:
    api: apps/v1
    name: static-app
    kind: Deployment
  cooldownPeriod:  200
  maxReplicaCount: 10
  minReplicaCount: 1
  pollingInterval: 30
  advanced:
    restoreToOriginalReplicaCount: false
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
          - type: Percent
            value: 100
            periodSeconds: 15
  triggers:
    - type: prometheus
      metadata:
        namespace: keda-test
        serverAddress: https://thanos-querier.openshift-monitoring.svc.cluster.local:9092
        metricName: http_requests_total
        # 'job' corresponds to the 'app' label value on deployment
        query: sum(rate(http_requests_total{job="prometheus-example-app"}[1m]))
        threshold: '5'
        authModes: "bearer"
      authenticationRef:
        name: keda-trigger-auth-prometheus
```

# Demo

oc create -f load.yaml
# Summary

_So, what did we just learn? TL;DR_

* **OpenShift provides platform and workload monitoring out of the box**

  Batteries included. The platform ships with Prometheus configured to comprehensively monitor the platform and graph the results. User workload monitoring is enabled with a flip of the switch.

* **Developers can add thier own metrics to be monitored**

  Developers can add the Prometheus client libraries to their application, define a ServiceMonitor, and Prometheus will begin scraping them.

* **Custom metrics can be used in autoscaling triggers**

  With the addition of the [CMA operator][5], a ScaledObject can program a Autoscaler to resize an application using knowledge gained from any metric. You are no longer limited to scaling only using CPU and memory thresholds!

# References

{{< figure src="/images/openshift-keda-autoscaling-sequence.png" link="/images/openshift-keda-autoscaling-sequence.png"  caption="Custom Metric Autoscaling Sequence Diagram" width="75%">}}

* [Custom Metrics Autoscaler on OpenShift][11] - Red Hat Blog
* [Example Demo][3] - GitHub
* [Automatically scaling pods based on custom metrics][1] - OpenShift Docs
* [Enabling monitoring for user-defined projects][7] - OpenShift Docs
* [Managing metrics][19] - OpenShift Docs
* [Custom Metrics Autoscaler Operator][5] - GitHub
* [KEDA.sh][2]
* [KEDA Prometheus Scaler][15]
* [Knative versus KEDA][12]
* [List of KEDA Scaler Sources][4]
* [Custom Metrics Autoscaling Demo][3]
* [Prometheus.io][6]
* [Beginners Guide to Prometheus Operator][10]
* [Horizontal Pod Autoscaling][14]

[1]: <https://docs.openshift.com/container-platform/4.11/nodes/pods/nodes-pods-autoscaling-custom.html> "Automatically scaling pods based on custom metrics"
[2]: <https://keda.sh> "KEDA.sh"
[3]: <https://github.com/dlbewley/demo-custom-metric-autoscaling> "Custom Metrics Autoscaling Demo"
[4]: <https://keda.sh/docs/latest/scalers/> "KEDA Scalers"
[5]: <https://github.com/openshift/custom-metrics-autoscaler-operator> "Custom Metrics Autoscaler Operator"
[6]: <https://prometheus.io> "Prometheus"
[7]: <https://docs.openshift.com/container-platform/4.11/monitoring/enabling-monitoring-for-user-defined-projects.html> "Enabling monitoring for user-defined projects"
[8]: <https://github.com/rhobs/prometheus-example-app> "Example Go App With Prometheus Metrics"
[9]: <https://issues.redhat.com/browse/OCPPLAN-7962> "Integrate KEDA with OpenShift"
[10]: <https://blog.container-solutions.com/prometheus-operator-beginners-guide> "Beginners Guide to Prometheus Operator"
[11]: <https://cloud.redhat.com/blog/custom-metrics-autoscaler-on-openshift> "Blog"
[12]: <https://access.redhat.com/articles/6636281> "Knative versus KEDA"
[13]: <https://docs.openshift.com/container-platform/4.11/monitoring/enabling-monitoring-for-user-defined-projects.html> "Enabling user workload monitoring in OpenShift"
[14]: <https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/> "Horizontal Pod Autoscaling"
[15]: <https://keda.sh/docs/2.8/scalers/prometheus/> "KEDA Prometheus Scaler"
[16]: <https://github.com/kubernetes/kube-state-metrics> "Kube State Metrics"
[17]: <https://www.redhat.com/en/technologies/cloud-computing/openshift/serverless> "OpenShift Serverless"
[18]: <https://access.redhat.com/articles/6718611> "Example Autoscaling for RGW in ODF via HPA using KEDA"
[19]: <https://docs.openshift.com/container-platform/4.11/monitoring/managing-metrics.html> "Managing metrics"
[20]: <https://access.redhat.com/articles/6675491> "Enabling TLS in ServiceMonitor metrics collection"
