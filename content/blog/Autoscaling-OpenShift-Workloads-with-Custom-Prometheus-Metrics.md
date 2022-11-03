---
title: "Autoscaling OpenShift Workloads With Custom Prometheus Metrics"
date: 2022-11-03
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

Kubernetes enables the automated scaling of applications to meet workload demands. Historically only memory and CPU consumption could be considered in scaling decisions, but the OpenShift Custom Metrics Autoscaler operator and KEDA remove that limitation. Read on to learn how OpenShift enables auto scaling based on the metrics that are important to your business.

<!--more-->

# Understanding OpenShift Monitoring

OpenShift includes monitoring and alerting out of the box. Batteries included.

Metrics are continuously collected and evaluated against dozens of predefined rules that identify potential issues. Metrics are also stored for review in graphical dashboards enabling troubleshooting and proactive capacity analysis. 

All of these metrics can be queried using Prometheus PromQL syntax in the console at _Observe -> Metrics_.

{{< figure src="/images/keda-dashboard-metrics.png" link="/images/keda-dashboard-metrics.png"  caption="OpenShift Metrics Queries" width="100%">}}

> **:star: Pro Tip:** Red Hat Advanced Cluster Management aggregates metrics from all your clusters to a single pane of glass. See blog posts with the [RHACM tag]({{< ref "/tags/RHACM" >}})

**What is monitored?**

All metrics are collected or "scraped" from Targets which can be found in the console at _Observe -> Targets_.  These targets are defined using `ServiceMonitor` resources.

For example there are ServiceMonitors for [Kube State Metrics][15]:

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

[Horizontal pod autoscaling][14] (HPA) has been a feature since the earliest days of OpenShift, but scaling was triggered only by CPU and memory consumption metrics. When the average CPU load of pods in an application reached an identified threshold the Deployment or StatefulSet that created the pod was resized to add more pod replicas. When the load receded, the application was scaled down and the extra pods were terminated.

Unfortunately, those simplistic metrics may not tell the whole story for your application.

The OpenShift [Custom Metrics Autoscaler operator][5] (CMA) enables you to create your own custom metrics and tailored PromQL queries for scaling. CMA is based on the upstream [Kubernetes Event Driven Autoscaling][2] project which makes it possible to trigger on a [number of event sources][4] or "Scalers" in the KEDA vernacular. We will use the [Prometheus scaler][15].

> **:star: Pro Tip:** This may remind you of [OpenShift Serverless][17], but the use case differs. KEDA, for example, will only permit you to scale as low as 1 pod. See [Knative versus KEDA][12]

# Prerequisites

## Enabling OpenShift User Workload Monitoring

To begin monitoring our own custom application we must first [enable user workload monitoring][13] in OpenShift.

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

> **Demo:** Deploying and [configuring KEDA](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/operator) using Kustomize:

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

Let's walk through an example using two applications. One will be the metered app called "prometheus-example-app" which exists only to provide a metric. Imagine this metric describes an amount of work piled up in a queue. The second application called "static-app" actually performs the work, and it will autoscale based on the metric advertised by the metered app.

## Enabling Custom Metrics in our Application

Prometheus expects applications to provide a `/metrics` endpoint which returns data in a format it understands. See the [Prometheus docs](https://prometheus.io/docs/prometheus/latest/getting_started/) to get started with instrumenting your application. We'll use a contrived [example app][8] here.

> :warning: **Apply the Appropriate Monitoring ClusterRole:** Creation of a `ServiceMonitor` is privileged, so unless you are a cluster admin you may have to request one of the following roles such as `monitoring-edit`.

* `monitoring-rules-view` grants read access to PrometheusRule custom resources for a project.
* `monitoring-rules-edit` grants create, modify, and deleting PrometheusRule custom resources for a project.
* `monitoring-edit` grants `monitoring-rules-edit` plus grants creation of new scrape targets for services or pods. This cluster role is needed to create, modify, and delete ServiceMonitor and PodMonitor resources.


> **Demo:** [Deploying](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/custom-metric-app)  an example metered application using Kustomize:

```bash  {hl_lines=[5]}
$ oc apply -k custom-metric-app
    namespace/keda-test created
    service/prometheus-example-app created
    deployment.apps/prometheus-example-app created
    servicemonitor.monitoring.coreos.com/prometheus-example-monitor created
    route.route.openshift.io/prometheus-example-app created
```

## Understanding ServiceMonitors

> {{< figure src="/images/openshift-keda-autoscaling-sequence-1.png" link="/images/openshift-keda-autoscaling-sequence-1.png"  caption="Exposing Custom Prometheus Metrics" width="100%">}}

The OpenShift-monitoring operator automates the configuration of Prometheus using the ServiceMonitor resource to target matching Services and scrape any metrics that are exported at `/metrics`.

Imagine a case where a metered-app is regularly checking a topic in Kafka to determine the length of a queue of work. We don't care to scale _this_ application, but we want to use its _knowledge_ to scale another app.

> :warning: **Warning:** Be sure to name the port in the Service definition and reference this name and not the number in the ServiceMonitor definition! Symptoms include no Target nor metrics visible in Prometheus.

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

Another app exists to perform work based on that example work queue. It performs tasks in parallel, so it can benefit from scaling out horizontally. 

> **Demo:** Deploying an [example scaled application](https://github.com/dlbewley/demo-custom-metric-autoscaling/tree/main/scaled-app) using kustomize:

```bash  {hl_lines=[11]}
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

Notice that we did not create a HorizontalPodAutoscaler above, but one was created automatically using the information in the ScaledObject resource:

```bash
$ oc get hpa
NAME                  REFERENCE               TARGETS     MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-static-app   Deployment/static-app   0/5 (avg)   1         10        1          14d
```
## Understanding ScaledObjects

Now that a custom metric is being collected, and an app exists which can benefit from the knowledge in this metric to scale more effectively, the two can be joined together using a `ScaledObject` resource.

Given the inputs of:

* an object, such as a Deployment or Statefulset, which can be scaled (line 9)
* a trigger of type Prometheus that identifies the relevant metric (line 31)
* and authentication credentials to query metrics (line 35)

...the operator will use the ScaledObject resource to create and program a `HorizontalPodAutoscaler` that will be triggered by the results of the Prometheus metrics query.


```yaml {linenos=inline,hl_lines=[8,9,31,34,35]}
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

> :notebook: Notice that the trigger contains a reference on line 35 to the `TriggerAuthentication` resource.
## Understanding Thanos

OpenShift workload monitoring actually introduces a second Prometheus instance distinct from the platform instance, so an intermediary will be used when looking up metrics. This is where Thanos fits in. The CMA or KEDA operator will be looking up metrics values by asking the Thanos-querier for them. You may think of it as a proxy to Prometheus.

The conversation with Thanos must be authenticated, and it is the `TriggerAuthentication` resource that supplies the credentials. Those credentials are the CA cert and token associated with the _thanos_ service account created by our application deployment.

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


# Demo

We have all the pieces on the table, so let's put them together and see an example.

For this demo we won't use the Kafka example mentioned, but we will [increase the load](https://github.com/dlbewley/demo-custom-metric-autoscaling/blob/main/load.yaml) on the "[prometheus-example-app](#enabling-custom-metrics-in-our-application)" which is acting as our metered-app.

As the rate of HTTP hits to the metered-app increase, the HPA will be triggered and cause the "[static-app](#deploying-a-scaled-application)" to scale out.

Below is a graph of the query, defined by the ScaledOjbect, captured during this demo.

{{< figure src="/images/openshift-keda-autoscaling-demo-metric.png" link="/images/openshift-keda-autoscaling-demo-metric.png"  caption="Custom Metric Graph with Load Generator" width="75%">}}

**Demo:** Autoscaling one application based on the metrics of another. (_output has been sped up_)
> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Scale app "static-app" based on the rate of hits counted in the app "prometheus-example-app"</p>
  {{< asciinema key="scale-keda-20221102_1548" rows="45" font-size="smaller" poster="npt:2:00" loop=false >}}
  {{< /collapsable>}}

# Summary

_So, what did we just learn? TL;DR_

* **OpenShift provides platform and workload monitoring out of the box**

  Batteries included. The platform ships with Prometheus configured to comprehensively monitor the platform and graph the results.

* **Developers can add their own metrics to be monitored**

  Developers can add the Prometheus client libraries to their application, define a ServiceMonitor, and Prometheus will begin scraping them.

* **Custom metrics can be used in auto scaling triggers**

  With the addition of the [OpenShift Custom Metrics Autoscaling operator][5], a ScaledObject can program an Autoscaler to resize an application using any metric. You can now scale your application using intelligent metrics that are important to your business!

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