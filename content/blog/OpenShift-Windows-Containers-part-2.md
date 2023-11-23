---
title: Adding a Windows Node to an OpenShift Cluster
banner: /images/view-of-the-fwd-iss-and-docked-atlantis-during-eva-1-00946b.jpg
date: 2021-06-03
layout: post
asciinema: true
tags:
 - openshift
 - OCP4
 - operators
 - windows
description: Preparing an OpenShift cluster on Azure to host Windows Kuberenetes nodes.
---

The Windows Machine Config Operator builds and configures Windows machines to act as nodes in an OpenShift cluster enabling cross platform workloads. This post will demonstrate the addition of a Windows node to an existing cluster and explore the integration of Windows and Kubernetes.

<!--more-->
> :notebook: _This is part 2 of a 3 part series on OpenShift support for Windows containers._
_Parts: [1][21], 2, [3][23]_

# Enabling Windows Workloads

[![Space shuttle Atlantis docking with International Space Station](/images/view-of-the-fwd-iss-and-docked-atlantis-during-eva-1-00946b.jpg)](https://picryl.com/media/view-of-the-fwd-iss-and-docked-atlantis-during-eva-1-00946b)

Enabling support for Windows containers on OpenShift is a "day 2" operation. Before we can proceeed we must ensure we've met the "day 1" networking prerequisites covered in [part 1][21] of this series. Be sure to start there.

With that out of the way we can begin [understanding Windows containers][4] support in OpenShift.
Unlike the Linux nodes which use the [CRI-O runtime](https://cri-o.io), Windows nodes continue to use Docker runtime (until such time as containerd is adopted). It is also important to note that unlike the automated [over the air updates][18] for CoreOS nodes, the Windows operating system is not automatically patched nor upgraded.

# Understanding Windows Container Images

Containers on Windows are less portable than on Linux. It is critical that the same OS version is used on the node and in the container image. This presents a challenge when containerizing applications and for patching nodes.

While the WMCO will configure a Windows node with the kubelet, kube-proxy, and container runtime plumbing enabling it to join the Kubernetes cluster, the upgrading or patching of the node is not automated.
The process of building and testing the machine images to address Windows patches will remain your responsibility.

This [playbook for automating the creation of a Window image][10] offers a starting point for constructing a pipeline to build and test updated Windows images for use on nodes.

# Reviewing the Day 1 Cluster

After [provisioning a cluster prepared for Windows][21] support, let's examine it. From this starting point we have only Linux based nodes and the cluster is deployed to Azure. Additonally, all the cluster operators are healthy and no extra operators have been installed yet.

``` 
$ oc get nodes -L kubernetes.io/os
NAME                            STATUS   ROLES    AGE   VERSION           OS
win-tmk9g-master-0              Ready    master   60m   v1.20.0+7d0a2b2   linux
win-tmk9g-master-1              Ready    master   60m   v1.20.0+7d0a2b2   linux
win-tmk9g-master-2              Ready    master   60m   v1.20.0+7d0a2b2   linux
win-tmk9g-worker-westus-wq4hg   Ready    worker   49m   v1.20.0+7d0a2b2   linux
win-tmk9g-worker-westus-x4gc6   Ready    worker   49m   v1.20.0+7d0a2b2   linux

$ oc describe infrastructure | grep ^Status -A -1
Status:
  API Server Internal URI:  https://api-int.win.az.tofu.org:6443
  API Server URL:           https://api.win.az.tofu.org:6443
  Etcd Discovery Domain:
  Infrastructure Name:      win-tmk9g
  Platform:                 Azure
  Platform Status:
    Azure:
      Cloud Name:                   AzurePublicCloud
      Network Resource Group Name:  win-tmk9g-rg
      Resource Group Name:          win-tmk9g-rg
    Type:                           Azure
Events:                             <none>

$ oc get clusteroperators
NAME                                       VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE
authentication                             4.7.8     True        False         False      37m
baremetal                                  4.7.8     True        False         False      58m
cloud-credential                           4.7.8     True        False         False      62m
cluster-autoscaler                         4.7.8     True        False         False      57m
config-operator                            4.7.8     True        False         False      58m
console                                    4.7.8     True        False         False      43m
csi-snapshot-controller                    4.7.8     True        False         False      57m
dns                                        4.7.8     True        False         False      56m
etcd                                       4.7.8     True        False         False      56m
image-registry                             4.7.8     True        False         False      48m
ingress                                    4.7.8     True        False         False      48m
insights                                   4.7.8     True        False         False      50m
kube-apiserver                             4.7.8     True        False         False      54m
kube-controller-manager                    4.7.8     True        False         False      55m
kube-scheduler                             4.7.8     True        False         False      55m
kube-storage-version-migrator              4.7.8     True        False         False      47m
machine-api                                4.7.8     True        False         False      46m
machine-approver                           4.7.8     True        False         False      57m
machine-config                             4.7.8     True        False         False      57m
marketplace                                4.7.8     True        False         False      56m
monitoring                                 4.7.8     True        False         False      46m
network                                    4.7.8     True        False         False      58m
node-tuning                                4.7.8     True        False         False      57m
openshift-apiserver                        4.7.8     True        False         False      50m
openshift-controller-manager               4.7.8     True        False         False      55m
openshift-samples                          4.7.8     True        False         False      49m
operator-lifecycle-manager                 4.7.8     True        False         False      57m
operator-lifecycle-manager-catalog         4.7.8     True        False         False      57m
operator-lifecycle-manager-packageserver   4.7.8     True        False         False      50m
service-ca                                 4.7.8     True        False         False      58m
storage                                    4.7.8     True        False         False      58m

$ oc get operators --all-namespaces
No resources found
```

# Installing the Windows Machine Config Operator

OpenShift uses operators to create and manage the nodes in a cluster along with managment of cluster services.
Check out my post on [Understanding Over the Air Updates][18] for some background.

Most relevant of these cluster operators are the [Machine-API][13] and [Machine-Config][14] which facilitate the creation of machines using the cloud provider API and the operating system configuration of these machines necessary to form a cluster node.
However, [enabling Windows containers][2] requires installation of an additional [Windows machine config operator][3].

Installing an operator on the CLI typically requires creation of a Namespace, an OperatorGroup, and a Subscription resource.

* Create the `Namespace` -
**[clusters/az-win/day2/base/namespace.yaml](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/namespace.yaml)**

``` yaml
$ cat <<EOF | oc create -f -
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-windows-machine-config-operator
  labels:
    openshift.io/cluster-monitoring: "true"
EOF
```

* Create the `OperatorGroup` -
**[clusters/az-win/day2/base/operatorgroup.yaml](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/operatorgroup.yaml)**

``` yaml
$ cat <<EOF | oc create -f -
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: windows-machine-config-operator
  namespace: openshift-windows-machine-config-operator
spec:
  targetNamespaces:
  - openshift-windows-machine-config-operator
EOF
```

* Create the `Subscription` -
**[clusters/az-win/day2/base/subscription.yaml](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/subscription.yaml)**

``` yaml
$ cat <<EOF | oc create -f -
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: windows-machine-config-operator
  namespace: openshift-windows-machine-config-operator
spec:
  channel: "stable" 
  installPlanApproval: "Automatic" 
  name: "windows-machine-config-operator"
  source: "redhat-operators" 
  sourceNamespace: "openshift-marketplace" 
EOF
```

After a few seconds check that the [`ClusterServiceVersion`][8] has been created. This is used to tell the [Operator Lifecycle Manager][9] how to install the operator.

```
$ oc get csv -n openshift-windows-machine-config-operator
```

> 📓 **Do you GitOps?**
>
> Assuming the `machineset.yaml` has been configured [as described]({{< ref "/blog/OpenShift-Windows-Containers-part-2.md#creating-a-windows-machineset" >}}) and asuming a [layout like this](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/) we can use a more GitOps compatible flow for the WMCO installation.
> A [Kustomize](https://kustomize.io) template can be applied with the [oc CLI](https://docs.openshift.com/container-platform/4.7/cli_reference/openshift_cli/developer-cli-commands.html) `-k` flag.

# Adding a Windows Node

Now that the WMCO factory is in place we can provide it the raw materials to build a Windows node.

## Creating a Windows MachineSet

The Machine API operator uses a `MachineSet` resource to understand exactly how to build a machine and how many to build. There is already a MachineSet for the Linux workers, so we will [create an Azure Windows MachineSet][5] to enable our Windows machines to be built.

> 📓 **Start with `0` replicas**
>
> It is important to create the MachineSet with 0 replicas for now as we fulfill some further prerequisites.

Here is an example with placeholder values.
Further details on the values to replace in this example MachineSet are [discussed in the WMCO github repo][6].

**[clusters/az-win/day2/base/machineset.yaml](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/machineset.yaml)**

``` yaml
# example MachineSet before replacing "<values>"
apiVersion: machine.openshift.io/v1beta1
kind: MachineSet
metadata:
  labels:
    machine.openshift.io/cluster-api-cluster: <infrastructureID>
  name: winworker
  namespace: openshift-machine-api
spec:
  replicas: 0
  selector:
    matchLabels:
      machine.openshift.io/cluster-api-cluster: <infrastructureID>
      machine.openshift.io/cluster-api-machineset: winworker
  template:
    metadata:
      labels:
        machine.openshift.io/cluster-api-cluster: <infrastructureID>
        machine.openshift.io/cluster-api-machine-role: worker
        machine.openshift.io/cluster-api-machine-type: worker
        machine.openshift.io/cluster-api-machineset: winworker
        machine.openshift.io/os-id: Windows
    spec:
      metadata:
        labels:
          node-role.kubernetes.io/worker: ""
      providerSpec:
        value:
          apiVersion: azureproviderconfig.openshift.io/v1beta1
          credentialsSecret:
            name: azure-cloud-credentials
            namespace: openshift-machine-api
          image:
            offer: WindowsServer
            publisher: MicrosoftWindowsServer
            resourceID: ""
            sku: 2019-Datacenter-with-Containers
            version: latest
          kind: AzureMachineProviderSpec
          location: <location>
          managedIdentity: <infrastructureID>-identity
          networkResourceGroup: <infrastructureID>-rg
          osDisk:
            diskSizeGB: 128
            managedDisk:
              storageAccountType: Premium_LRS
            osType: Windows
          publicIP: false
          resourceGroup: <infrastructureID>-rg
          subnet: <infrastructureID>-worker-subnet
          userDataSecret:
            name: windows-user-data
            namespace: openshift-machine-api
          vmSize: Standard_D2s_v3
          vnet: <infrastructureID>-vnet
          zone: "<zone>"
```


Every cluster has an infrastructure name that is a combination of the cluster name and a unique string. We will need to use this value in the Windows MachineSet.

* Capture the infrastructure ID

```bash
$ export CLUSTER_ID=$(oc get -o jsonpath='{.status.infrastructureName}{"\n"}' infrastructure cluster)
$ echo $CLUSTER_ID
win-tmk9g
```

* Create the above MachineSet after updating the placeholder values (there are no availability zones in westus region)

``` bash
$ sed \
  -e "s/<infrastructureID>/$CLUSTER_ID/" \
  -e "s/<location>/westus/" \
  -e "s/<zone>//" \
  -i.bak \
  $CLUSTER_DIR/day2/base/machineset.yaml

$ oc apply -n openshift-machine-api -f $CLUSTER_DIR/day2/base/machineset.yaml
```

## Providing an SSH Private Key

In part 1 of this series, [we generated an ssh key]({{< ref "/blog/OpenShift-Windows-Containers-part-1.md#generating-an-ssh-key" >}}) for installing OpenShift.
Now we will give this same key to the WMCO for use in configuring our Windows node.
By providing the private key, a new public key will be minted by the operator and installed on the node via user-data.

* Create a secret containing the private key that will be used to access the Windows VMs

``` bash
$ oc create secret generic cloud-private-key \
  --from-file=private-key.pem=${HOME}/.ssh/az-win \
  -n openshift-windows-machine-config-operator
```

After the ssh key is created the WMCO will generate a public key and create a `windows-user-data` secret for use by the openshift-machine-api when provisioning the machine.

```
$ oc logs -n openshift-windows-machine-config-operator \
    deployment/windows-machine-config-operator | tail -1

2021-05-24T18:26:13.851Z        INFO    secret_controller       secret not found, creating the secret   {"namespace": "openshift-windows-machine-config-operator", "name": "cloud-private-key", "name": "windows-user-data"}
```

You can extract the secret to view the contents.
Notice the authorized key file modification.

``` bash
$ oc extract secret/windows-user-data -n openshift-machine-api --to=-
# userData
<powershell>
  Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
  $firewallRuleName = "ContainerLogsPort"
  $containerLogsPort = "10250"
  New-NetFirewallRule -DisplayName $firewallRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $containerLogsPort -EdgeTraversalPolicy Allow
  Set-Service -Name sshd -StartupType ‘Automatic’
  Start-Service sshd
  $pubKeyConf = (Get-Content -path C:\ProgramData\ssh\sshd_config) -replace '#PubkeyAuthentication yes','PubkeyAuthentication yes'
  $pubKeyConf | Set-Content -Path C:\ProgramData\ssh\sshd_config
  $passwordConf = (Get-Content -path C:\ProgramData\ssh\sshd_config) -replace '#PasswordAuthentication yes','PasswordAuthentication yes'
  $passwordConf | Set-Content -Path C:\ProgramData\ssh\sshd_config
  $authorizedKeyFilePath = "$env:ProgramData\ssh\administrators_authorized_keys"
  New-Item -Force $authorizedKeyFilePath
  echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJhagYxgTRdyNVUU8w+WwISvm2Syq6Wu+GV0nz/XoP99
  "| Out-File $authorizedKeyFilePath -Encoding ascii
  $acl = Get-Acl C:\ProgramData\ssh\administrators_authorized_keys
  $acl.SetAccessRuleProtection($true, $false)
  $administratorsRule = New-Object system.security.accesscontrol.filesystemaccessrule("Administrators","FullControl","Allow")
  $systemRule = New-Object system.security.accesscontrol.filesystemaccessrule("SYSTEM","FullControl","Allow")
  $acl.SetAccessRule($administratorsRule)
  $acl.SetAccessRule($systemRule)
  $acl | Set-Acl
  Restart-Service sshd
</powershell>
<persist>true</persist>
```

> 📓 **Beware of failures creating _windows-user-data_ secret**
>
> If you see an error like: 
>  _​failed to create vm winworker-29pjk: failed to get custom script data: error getting user data secret windows-user-data in namespace openshift-machine-api: Secret "windows-user-data" not found_
>
> Check the operator logs. *Hint:* Did your ssh key have a passphrase?
>
> ```
> $ oc logs -n openshift-windows-machine-config-operator \
>   -f deployment/windows-machine-config-operator 
> $ oc get -n openshift-windows-machine-config-operator \
>   secret/windows-user-data
> ```

## Scaling up the Windows MachineSet
 
We created the MachineSet with zero replicas precisely because the windows-user-data secret did not yet exist. Now that it does we can scale up and create our Windows machine.

* Scale up the machineset

``` bash
$ oc scale machineset winworker --replicas=1
```

Eventually there will be a windows machine and it will become a node. We can use some labels to identify the operating systems.

```
$ oc get machines -n openshift-machine-api -L machine.openshift.io/os-id
NAME                            PHASE     TYPE              REGION   ZONE   AGE    OS-ID
win-77226-master-0              Running   Standard_D8s_v3   westus          3h6m
win-77226-master-1              Running   Standard_D8s_v3   westus          3h6m
win-77226-master-2              Running   Standard_D8s_v3   westus          3h6m
win-77226-worker-westus-g55j4   Running   Standard_D2s_v3   westus          3h
win-77226-worker-westus-n2kwj   Running   Standard_D2s_v3   westus          3h
win-77226-worker-westus-wv8ql   Running   Standard_D2s_v3   westus          3h
winworker-74qw4                 Running   Standard_D2s_v3   westus          76m    Windows

$ oc get nodes -L kubernetes.io/os
NAME                            STATUS   ROLES    AGE    VERSION                       OS
win-77226-master-0              Ready    master   3h3m   v1.20.0+bafe72f               linux
win-77226-master-1              Ready    master   3h3m   v1.20.0+bafe72f               linux
win-77226-master-2              Ready    master   3h3m   v1.20.0+bafe72f               linux
win-77226-worker-westus-g55j4   Ready    worker   172m   v1.20.0+bafe72f               linux
win-77226-worker-westus-n2kwj   Ready    worker   172m   v1.20.0+bafe72f               linux
win-77226-worker-westus-wv8ql   Ready    worker   172m   v1.20.0+bafe72f               linux
winworker-74qw4                 Ready    worker   61m    v1.20.0-1030+cac2421340a449   windows
```

> 📺  **Watch Demo:** Installing WMCO with Kustomize and Deploying a Windows Node
> {{< asciinema key="az-win-wmco-install" rows="30" font-size="smaller" poster="npt:1:24" loop="true" >}}

# Accessing the Windows Node via SSH

Our Windows node does not necessarily have a graphical interface, so how do we connect to it? Ssh of course, but to do that requires a bastion that can reach it. We will use a pod for this.

## Deploying a Bastion Pod as an SSH Client

* Create a Deployment to launch the bastion pod, courtesy of Christian Hernandez's [Windows Containers Quickstart Workshop][12] - 
**[clusters/az-win/day2/base/deployment.yaml](https://gitlab.com/dlbewley/openshift-practice/-/blob/master/clusters/az-win/day2/base/deployment.yaml)**

``` yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  creationTimestamp: null
  labels:
    app: winc-ssh
  name: winc-ssh
  namespace: openshift-windows-machine-config-operator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: winc-ssh
  strategy: {}
  template:
    metadata:
      creationTimestamp: null
      labels:
        app: winc-ssh
    spec:
      containers:
      - command:
        - /bin/bash
        - -c
        - |
          sleep infinity
        image: quay.io/redhatworkshops/winc-ssh:latest
        name: winc-ssh-container
        resources: {}
        volumeMounts:
          - mountPath: /tmp/ssh
            name: sshkey
            readOnly: true
      volumes:
      - name: sshkey
        secret:
          defaultMode: 256
          secretName: cloud-private-key
```

> 📓 **Pending Pod**
> If you notice that the winc-ssh pod is stuck in 'pending' state, it is likely because the pod needs to mount a secret which [wasn't created]({{< ref "/blog/OpenShift-Windows-Containers-part-2.md#providing-an-ssh-private-key" >}}) yet.

After the pod has launched we can `oc rsh` to the pod and then `ssh` to the IP address of the Windows node. It is worth mentioning that the Azure Windows image will expect you to login as user `capi` rather than `administrator`.

```
$ oc get nodes -l kubernetes.io/os=windows -o yaml | yq e '.items[].status | .addresses' -
- address: winworker-g7tsk
  type: Hostname
- address: 10.0.32.6
  type: InternalIP

$ oc rsh -n openshift-windows-machine-config-operator deployment/winc-ssh
sh-4.4$ export WIN_NODE=10.0.32.6
sh-4.4$ ssh -i /tmp/ssh/private-key.pem capi@$WIN_NODE
```

> :tv: **Watch Demo: ssh to Windows node**
> {{< asciinema key="az-win-wmco-ssh" rows="15" font-size="smaller" loop="true" poster="npt:0:12">}}

Once logged in you can interact with containers using the legacy docker runtime.

```
PS C:\Users\capi> docker network ls
NETWORK ID          NAME                DRIVER              SCOPE
16b1dbbcbc00        nat                 nat                 local
f9ad45f65cb7        none                null                local

PS C:\Users\capi> docker network inspect nat
[ {
        "Name": "nat",
        "Id": "16b1dbbcbc009975abee4bea88378cf8f3ab4062c70f31c8fcf49d1057448cd8",
        "Created": "2021-05-14T23:51:33.3446158Z",
        "Scope": "local",
        "Driver": "nat",
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "windows",
            "Options": null,
            "Config": [ {
                    "Subnet": "172.17.64.0/20",
                    "Gateway": "172.17.64.1"
                } ]
        },
        "Internal": false,
        "Attachable": false,
        "Ingress": false,
        "ConfigFrom": {
            "Network": ""
        },
        "ConfigOnly": false,
        "Containers": {},
        "Options": {
            "com.docker.network.windowsshim.hnsid": "FA662A2F-C423-41AF-90EC-26E71FB35871",
            "com.docker.network.windowsshim.networkname": "nat"
        },
        "Labels": {}
    } ]
```

🚀 Now that we have docked, all we need now is a containerized Windows application!

# Summary

OpenShift enables cloud native workflows for diverse workloads. It enhances automation, resilience, and scalability while enhancing developer productivity for legacy applications. With support for Windows nodes, everyone is invited to dock with the cluster!

After [deploying OpenShift to Azure]({{< ref "/blog/OpenShift-Windows-Containers-part-1.md" >}}) and adding a Windows node using the `WindowsMachineConfigOperator` we are ready to deploy a cross platform application.  Stay tuned for [part 3][23]!

## References

* [Understanding Windows Containers Support on OpenShift][4]
* [Enabling Windows container workloads on OpenShift][2]
* [Windows Machine Config Operator Project][3]
* [Creating a Windows MachineSet for Azure][5]
* [Azure MachineSet docs from WMCO Project][6]
* [Windows container networking][7]
* [Playbook for Creating Windows Container Images][10]
* [Video Demo: Installing a Windows Node on OpenShift][11]
* [Windows Containers Quickstart Workshop][12]
* [Machine-API Operator][13]
* [Machine-Config Operator][14]

[1]: https://gitlab.com/dlbewley/openshift-practice/-/blob/master/azure-windows-install.adoc "Working Notes"
[2]: https://docs.openshift.com/container-platform/4.7/windows_containers/enabling-windows-container-workloads.html "Enabling Windows container workloads"
[3]: https://github.com/openshift/windows-machine-config-operator "Windows Machine Config Operator"
[4]: https://docs.openshift.com/container-platform/4.7/windows_containers/understanding-windows-container-workloads.html "Understanding Windows Containers"
[5]: https://docs.openshift.com/container-platform/4.7/windows_containers/creating_windows_machinesets/creating-windows-machineset-azure.html "Creating Windows MachineSet for Azure"
[6]: https://github.com/openshift/windows-machine-config-operator/blob/master/docs/machineset-azure.md "MachineSet Azure docs from WMCO"
[7]: https://docs.microsoft.com/en-us/virtualization/windowscontainers/container-networking/architecture "Windows container networking"
[8]: https://docs.openshift.com/container-platform/4.7/rest_api/operatorhub_apis/clusterserviceversion-operators-coreos-com-v1alpha1.html "ClusterServiceVersion CR"
[9]: https://github.com/operator-framework/operator-lifecycle-manager "Operator Lifecycle Manager"
[10]: https://github.com/giofontana/ocp-windows-image-prepare "Ansible playbook to prepare Windows OS image for OpenShift (using Packer)"
[11]: https://demo.openshift.com/en/latest/installing-windows-node/ "Video Demo: Installing a Windows Node on OpenShift"
[12]: https://github.com/RedHatWorkshops/windows-containers-quickstart "Windows Containers Quickstart Workshop"
[13]: https://github.com/openshift/machine-api-operator "Machine-API Operator"
[14]: https://github.com/openshift/machine-config-operator "Machine-Config Operator"
[18]: {{< ref "/blog/Understanding-OpenShift-Over-The-Air-Updates.md" >}} "Understanding Over-The-Air Updates"
[21]: {{< ref "/blog/OpenShift-Windows-Containers-part-1.md" >}} "Windows Containers Part 1"
[22]: {{< ref "/blog/OpenShift-Windows-Containers-part-2.md" >}} "Windows Containers Part 2"
[23]: {{< ref "/blog/OpenShift-Windows-Containers-part-3.md" >}} "Windows Containers Part 3"