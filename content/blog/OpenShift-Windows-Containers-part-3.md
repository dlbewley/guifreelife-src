---
title: Deploying a Cross-platform Windows and Linux Application to OpenShift
banner: /images/openshift-windows-app-topology-pretty.png
date: 2021-07-10
asciinema: true
layout: post
tags:
 - openshift
 - OCP4
 - operators
 - windows
 - azure
notes_url: https://gitlab.com/dlbewley/openshift-practice/-/blob/master/azure-windows-install.adoc
---

An application can sometimes require diverse components that span technology stacks. There may be a depency on a legacy component built for Windows which may not be suitable for deployment to Linux. The good news is it may still be suitable for deployment to Kubernetes.  With a Windows node in your OpenShift cluster you can deploy cross-platform applications that can simultaneously leverage the strengths of Linux and Windows.

<!--more-->

> :notebook: _This is part 3 of a 3 part series on OpenShift support for Windows containers._
_Parts: [1][21], [2][22], 3_

# Windows and Linux Living in Harmony

{{< figure src="/images/openshift-windows-app-topology.png" link="/images/openshift-windows-app-topology.png" width="100%">}}

After [enabling support for Windows nodes][22] in OpenShift, deploying an app to both Linux and Windows is as easy as TODO

# Deploying the NetCandy Store Cross-platform Application

We will deploy a sample application called [NetCandy Store][5] using a Helm chart. 

As input we will have to provide a few parameters including the Windows node name and the ssh key used by our operator. Let's define some environmental variables for later reference.

We will use the same [ssh key we gave]({{< ref "/blog/OpenShift-Windows-Containers-part-2.md#providing-an-ssh-private-key" >}}) to the Windows Machine Config Operator as it is already trusted by the node. We need this for the image pre-pull job described below.

``` bash
$ export WSSH_KEY=$(\
  oc get secret cloud-private-key -n openshift-windows-machine-config-operator \
  -o jsonpath='{.data.private-key\.pem}')
```

We also need to find the name of the Windows node to provide that as a Helm value.

``` bash
$ export WIN_NODE=$(\
  oc get nodes -l kubernetes.io/os=windows \
  -o jsonpath='{.items[0].metadata.name}')
```

In this case the cluster is on Azure, and our Windows node administrator is called `capi` rather than the default `administrator`. Define another environmental variable for the ssh user.

``` bash
$ export WSSH_USER='capi'
```

Those are all the values we need for the Helm chart.
Let's create a namespace with a descriptive name to install to.

``` bash
$ oc new-project --display-name="Net Candy Store" netcandystore
```

Next we will download the application <http://people.redhat.com/chernand/netcandystore-1.0.1.tgz> to `$CLUSTER_DIR/day2`, and finally install it using the Helm chart inside the tarball.

``` bash
$ curl -o $CLUSTER_DIR/day2/netcandystore-1.0.1.tgz \
  http://people.redhat.com/chernand/netcandystore-1.0.1.tgz

$ helm install ncs \
  --namespace netcandystore \
  --timeout=1200s \
  --set ssh.username=${WSSH_USER:-administrator} \
  --set ssh.hostkey=${WSSH_KEY} \
  --set ssh.hostname=${WIN_NODE} \
  $CLUSTER_DIR/day2/netcandystore-1.0.1.tgz
```

We can list the chart to see it has been installed in our _netcandystore_ namespace.

```
$ helm ls --namespace netcandystore
NAME    NAMESPACE       REVISION        UPDATED                                 STATUS          CHART                   APP VERSION
ncs     netcandystore   1               2021-05-24 15:10:29.909948 -0700 PDT    deployed        netcandystore-1.0.1     3.1
```

> 📺  **Watch Demo:** Deploying NetcandyStore app with Helm
> {{< asciinema key="az-win-app-deploy" rows="30" poster="npt:0:33" loop="false" >}}

## Speeding Up Application Launch by Pre-pulling Images

As windows containers are large, this Helm Chart defines a job to pre-pull the netcandystore image. You can see it took nearly 10 minutes for this job to run in this instance.

```
$ oc get job/netcandystore-prepull-image
NAME                          COMPLETIONS   DURATION   AGE
netcandystore-prepull-image   1/1           9m43s      90m
```

That 10 minute process is something you want to be done _before_ trying to launch your application. Ideally this would execute ahead of time on every node where the app might run.

Here is a look at that job definition. You can see in the `command` defnition it will ssh to the Windows node and issue a `docker pull` of the container image.

```
$ oc get job netcandystore-prepull-image -o yaml | yq e '.spec.template.spec.containers[]' -
command:
  - /bin/bash
  - -c
  - |
    ssh ${SSHOPTS} -i /tmp/ssh/private-key.pem ${SSHUSR}@${SSHHOST} docker pull ${NCIMAGE}
env:
  - name: NCIMAGE
    value: quay.io/donschenck/netcandystore:2021mar8.1
  - name: SSHOPTS
    value: -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
  - name: SSHUSR
    value: capi
  - name: SSHHOST
    value: winworker-g7tsk
image: quay.io/redhatworkshops/winc-ssh:latest
imagePullPolicy: Always
name: prepull-image
resources: {}
terminationMessagePath: /dev/termination-log
terminationMessagePolicy: File
volumeMounts:
  - mountPath: /tmp/ssh
    name: sshkey
    readOnly: true
```

The application is comprised of 3 services. A MSSQL pod running on Linux will provide the database for the GetCategories service also running on Linux, and finally the NetcandyStore service that provides the front end of the application will run on Windows.

```
$ oc get services -n netcandystore
NAME            TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
getcategories   ClusterIP   172.30.104.36   <none>        8080/TCP   90m
mssql           ClusterIP   172.30.78.137   <none>        1433/TCP   90m
netcandystore   ClusterIP   172.30.154.13   <none>        80/TCP     90m

$ oc get pods -n netcandystore \
    --field-selector=status.phase=Running  \
    -o custom-columns=NAME:.metadata.name,IP:.status.podIP,NODE:.spec.nodeName
NAME                             IP             NODE
getcategories-58b98fbd48-bsc8z   10.128.2.139   win-tmk9g-worker-westus-x4gc6
mssql-1-tsrjx                    10.131.0.27    win-tmk9g-worker-westus-wq4hg
netcandystore-5b989b4bdd-x4pt9   10.132.0.2     winworker-g7tsk
```

By describing the netcandystore pod running on Windows, you may notice that the `Container ID` begins with _docker_ rather than _cri-o_ and that the `Node-Selector` targetting _beta.kubernetes.io/os=windows_.

```
$ oc describe pod netcandystore-5b989b4bdd-x4pt9
Name:         netcandystore-5b989b4bdd-x4pt9
Namespace:    netcandystore
Priority:     0
Node:         winworker-g7tsk/10.0.32.6
Start Time:   Mon, 24 May 2021 15:20:14 -0700
Labels:       app=netcandystore
              app.kubernetes.io/instance=ncs
              app.kubernetes.io/name=netcandystore
              pod-template-hash=5b989b4bdd
Annotations:  openshift.io/scc: restricted
Status:       Running
IP:           10.132.0.2
IPs:
  IP:           10.132.0.2
Controlled By:  ReplicaSet/netcandystore-5b989b4bdd
Containers:
  netcandystore:
    Container ID:   docker://3ae2156a70ed58a1f4dcb7fe2953741ff25a84e3b15c2f77b30a5f9fc44c2d3e
    Image:          quay.io/donschenck/netcandystore:2021mar8.1
    Image ID:       docker-pullable://quay.io/donschenck/netcandystore@sha256:e321ff7c51509b4b0ded21415cff7fb760ddee06359354b9fa879a7402f016cc
    Port:           <none>
    Host Port:      <none>
    State:          Running
      Started:      Mon, 24 May 2021 15:20:51 -0700
    Ready:          True
    Restart Count:  0
    Environment:
      categoriesMicroserviceURL:  http://getcategories:8080/categories
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from default-token-nsd48 (ro)
Conditions:
  Type              Status
  Initialized       True
  Ready             True
  ContainersReady   True
  PodScheduled      True
Volumes:
  default-token-nsd48:
    Type:        Secret (a volume populated by a Secret)
    SecretName:  default-token-nsd48
    Optional:    false
QoS Class:       BestEffort
Node-Selectors:  beta.kubernetes.io/os=windows
Tolerations:     node.kubernetes.io/not-ready:NoExecute op=Exists for 300s
                 node.kubernetes.io/unreachable:NoExecute op=Exists for 300s
                 os=Windows:NoSchedule
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  75m   default-scheduler  Successfully assigned netcandystore/netcandystore-5b989b4bdd-x4pt9 to winworker-g7tsk
  Normal  Pulling    74m   kubelet            Pulling image "quay.io/donschenck/netcandystore:2021mar8.1"
  Normal  Pulled     74m   kubelet            Successfully pulled image "quay.io/donschenck/netcandystore:2021mar8.1" in 937.999ms
  Normal  Created    74m   kubelet            Created container netcandystore
  Normal  Started    74m   kubelet            Started container netcandystore
```

## Exploring Containers Running on a Windows Node

In [part 2 of this series][22] we used ssh to login to the Windows node. Let's do that again.

Begin by finding the IP address of the Windows node.

``` bash
$ oc get nodes -l kubernetes.io/os=windows -o wide
NAME              STATUS   ROLES    AGE     VERSION                       INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION    CONTAINER-RUNTIME
winworker-g7tsk   Ready    worker   5h18m   v1.20.0-1030+cac2421340a449   10.0.32.6     <none>        Windows Server 2019 Datacenter   10.0.17763.1935   docker://19.3.14
```

Then after openning a remote shell to [the bastion pod]({{< ref "/blog/OpenShift-Windows-Containers-part-2.md#deploying-a-bastion-pod-as-an-ssh-client">}}), we can secure shell to the Windows node at _10.0.32.6_. This bastion pod includes a `/usr/local/bin/sshmd.sh` script to simplify the ssh command.

> :notebook: **Azure Difference**
> 
> Remember our Windows image on Azure uses _capi_ rather than _administrator_, so provide that username when ssh'ing into the node.

``` bash
$ oc rsh -n openshift-windows-machine-config-operator deployment/winc-ssh

sh-4.4$ sshcmd.sh 10.0.32.6 capi
Could not create directory '/.ssh'.
Warning: Permanently added '10.0.32.6' (ECDSA) to the list of known hosts.
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

PS C:\Users\capi>
```

Now we can use the docker command to see what containers are running locally.

```bash
PS C:\Users\capi> docker ps -a
CONTAINER ID        IMAGE                                          COMMAND                   CREATED             STATUS              PORTS               NAMES
3ae2156a70ed        quay.io/donschenck/netcandystore               "C:\\ServiceMonitor.e…"   2 hours ago         Up 2 hours                              k8s_netcandystore_netcandystore-5b989b4bdd-x4pt9_netcandystore_49c2f119-5ce8-4a75-aeee-5be53ac748c1_0
3c5ee98c833c        mcr.microsoft.com/oss/kubernetes/pause:1.3.0   "cmd /S /C pauseloop…"    2 hours ago         Up 2 hours                              k8s_POD_netcandystore-5b989b4bdd-x4pt9_netcandystore_49c2f119-5ce8-4a75-aeee-5be53ac748c1_0
```

By the way, I mentioned those images are large, but how big are they? Large. They are large.

``` bash
PS C:\Users\capi> docker images
REPOSITORY                               TAG              IMAGE ID          CREATED             SIZE
mcr.microsoft.com/windows/servercore     ltsc2019         3a7f23e29bd7      2 weeks ago         5.28GB
mcr.microsoft.com/windows                1809             08b77c4924fc      2 weeks ago         14.3GB
mcr.microsoft.com/windows/nanoserver     1809             ad675c9cb2d5      2 weeks ago         252MB
quay.io/donschenck/netcandystore         2021mar8.1       7e8c294b169d      2 months ago        8.09GB
mcr.microsoft.com/oss/kubernetes/pause   1.3.0            e2b9b3d368da      15 months ago       256MB
```

## Exploring the OpenShift Developer Topology View

Before we leave the CLI, let's take apply some metadata that will enable the developer view of the OpenShift console to provide some visual context.
By applying [particular labels][3] and [annotations][6] to our deployment resources we can enhance the visual representation of our application in the [topology view][7].

``` bash
# this pod is on windows
$ oc label deployment/netcandystore \
  app.kubernetes.io/name=windows --overwrite

# it connects to a microservice
$ oc annotate deployment/netcandystore \
  app.openshift.io/connects-to='[{"apiVersion":"apps/v1","kind":"Deployment","name":"getcategories"}]'

# skipping this, but FYI
#app.openshift.io/vcs-uri=<github-url>
#app.kubernetes.io/part-of=<appname>

# this pod is .Net core on linux
$ oc label deployment/getcategories \
  app.kubernetes.io/name=dotnet --overwrite

# it connects to a database
$ oc annotate deployment/getcategories \
  app.openshift.io/connects-to='[{"apiVersion":"apps.openshift.io/v1","kind":"DeploymentConfig","name":"mssql"}]'

# this database is MS SQL
$ oc label deploymentconfig/mssql \
  app.kubernetes.io/name=mssql --overwrite
```

Here is the effect of those labels within the Topology View of Deployed App

{{< figure src="/images/openshift-windows-app-topology-pretty.png" link="/images/openshift-windows-app-topology-pretty.png" width="100%">}}

And finally, here is the finished product. The Netcandy Store front end application.

{{< figure src="/images/openshift-windows-app-netcandy.png" link="/images/openshift-windows-app-netcandy.png" width="100%">}}

## Summary

OpenShift offers support for legacy Windows applications that may be suitable for containerization. Through a hybrid network configuration a dn specialized machine configuration operator both Linux and Windows workloads 
and flexible runtime support

### References

* [NetCandy Store Helm Chart][5]
* [OpenShift Tech Topic: Windows Containers][4] 
* [Kubernetes Recommended Labels][3]
* [OpenShift Application Topology View][7]
* [Windows Containers Quickstart Workshop][8]

[1]: https://gitlab.com/dlbewley/openshift-practice/-/blob/master/azure-windows-install.adoc "Detailed Notes"
[2]: https://github.com/giofontana/ocp-windows-image-prepare "Ansible playbook to prepare Windows OS image for OpenShift (using Packer)"
[3]: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/ "Kubernetes Recommended Labels"
[4]: https://www.openshift.com/learn/topics/windows-containers "Windows Containers Tech Topic"
[5]: https://github.com/redhat-developer-demos/helm-repo/tree/main/stable/netcandystore "NetCandy Store Helm Chart"
[6]: https://docs.openshift.com/container-platform/4.7/applications/application_life_cycle_management/odc-viewing-application-composition-using-topology-view.html#odc-labels-and-annotations-used-for-topology-view_viewing-application-composition-using-topology-view "Topology Labels and Annotations"
[7]: https://docs.openshift.com/container-platform/4.7/applications/application_life_cycle_management/odc-viewing-application-composition-using-topology-view.html "OpenShift Application Topology View"
[8]: https://github.com/RedHatWorkshops/windows-containers-quickstart "Windows Containers Quickstart Workshop"
Guide: <http://people.redhat.com/chernand/windows-containers-quickstart/ns-deploy/>


[21]: {{< ref "/blog/OpenShift-Windows-Containers-part-1.md" >}} "Windows Containers Part 1"
[22]: {{< ref "/blog/OpenShift-Windows-Containers-part-2.md" >}} "Windows Containers Part 2"
[23]: {{< ref "/blog/OpenShift-Windows-Containers-part-3.md" >}} "Windows Containers Part 3"