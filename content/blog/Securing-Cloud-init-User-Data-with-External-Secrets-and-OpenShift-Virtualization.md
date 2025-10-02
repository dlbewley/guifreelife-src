---
title: "Securing Cloud-init User Data with External Secrets and OpenShift Virtualization"
date: 2025-10-02
banner: /images/blog-external-secrets.png
layout: post
mermaid: true
asciinema: true
draft: true
tags:
  - draft
  - 1password
  - automation
  - security
  - openshift
  - kubernetes
  - virtualization
description: Cluster User Defined Networks and VLAN Access with OpenShift Virtualization
---

Storing Kubernetes resources in git for automated deployment promotes consistency, resilency, and accountability, while commiting secret configuration data to a repository where it may be retrieved by bad actors promotes nightmares! Use the External Secrets Operator to store cloud-init and other secret securely and sleep soundly!

<!--more-->

# Securing Cloud-init User Data

As described in [this post][1] the cloud-init `userData` script for a virtual machine may contain privileged information like activation keys for your RHEL subscription.

```yaml
rh_subscription:
  org: 00000000
  activation-key: EXAMPLE
  enable-repo:
    - 'rhel-9-for-x86_64-baseos-rpms'
    - 'rhel-9-for-x86_64-appstream-rpms'
```

These [client][10], [ldap][9], and [nfs][8] userData scripts have example placeholders which make them safe to place in a public repository. Having them here makes for easier testing and debugging.  They can be safely deployed as example secrets for reference with a `-sample` suffix for example.

But how can we safely manage the actual secret to be used used by cloud-init if it is not commited to git?

# The External Secrets Operator

The [External Secrets Operator][3] solves this issue for us by understanding how to look into a secure vault "[providers][4]" like AWS Secrets Manager, HashiCorp Vault, or 1Password.

Once your data is within a secure vault, you will create an `ExternalSecret` resources which is safe to commit to git. When you apply these resources to the cluster the ESO will use the information in the `ExternalSecret` to create a Kubernetes `Secret` resource, securely download, and insert the sensitive data into it.

## Installing the External Secrets Operator

Install a version of ESO which supports the 1password-sdk provider which was added in 0.17. The 1password-connect provider available in earlier versions is deprecated. By the time you read this, if the operator has uppdated to 0.17 or later you may be able to use the operator rather than the helm chart.

Install latest upstream ESO using Helm.

```bash
$ helm repo add external-secrets https://charts.external-secrets.io

$ oc new-project external-secrets

$ helm install external-secrets \
   external-secrets/external-secrets \
   -n external-secrets
```

## 1Password Provider for ESO

Using [1Password](https://1password.com) can be handy in a home lab if you already use 1Password. You Don't have to deploy any infrastructure or have an AWS account to use it. Be aware there is more than one 1Password provider. You want to use the 1Password-SDK External Secrets Operator provider.

# Configuring 1Password

Of course the External Secrets Operator supports many providers common to the enterprise including Hashicorp Vault for example. I am using 1Password for it's ease of setup.

Grab the 1Password CLI command `op` from https://developer.1password.com/ or use `brew`.

```bash
$ brew install 1password-cli
```

Create a dedicated vault in 1Password for use by the ESO, so there is no chance it can comingle with your personal data sloshing around in your Kubernetes.

```bash
$ op vault create eso --icon gears
```

Create a token to authenticate the ESO to access 1Password. Note that 90 days is the max lifetime allowed by 1Password.

```bash
$ TOKEN=$(
    op service-account create external-secrets-operator \
      --expires-in 90d \
      --vault eso:read_items,write_items \
    )
```

Place this token in a secret allowing ESO to authenticate to 1Password.

 ```bash
$ oc create secret generic onepassword-connect-token \
  --from-literal=token="$TOKEN" \
  -n external-secrets
```

> ⭐ **Pro Tip:**
> Test the token to confirm access to the vault items by setting the `OP_SERVICE_ACCOUNT_TOKEN` environment variable.
> ```bash
>  $ export OP_SERVICE_ACCOUNT_TOKEN=$(oc extract secret/onepassword-connect-token \
>   -n external-secrets --keys=token --to=-)
>
>  $ op item list --vault eso
>  ID                            TITLE                            VAULT            EDITED
>  yzsurcc4oxfjp7qdidonudn3ne    demo autofs ldap                 eso              22 hours ago
>  wretasduq3rkip7wn37njozghi    demo autofs nfs                  eso              22 hours ago
>  euaujb4izjftqineetzaer3x7i    demo autofs client               eso              5 days ago
>  ```

## Uploading userData to the Vault

Now, we can take the example userData files and modify them to contain the sensitive data we want. In this case the organization ID and activation key required for our subscription.

Edit the `{client,ldap,nfs}/base/scripts/userData` scripts. Insert the configuration that should not be stored in git. So the copies in your working directory may now look like the following. Be certain not to commit these changes to git!

```yaml
rh_subscription:
  org: 12345678
  activation-key: secret-key4me
  enable-repo:
    - 'rhel-9-for-x86_64-baseos-rpms'
    - 'rhel-9-for-x86_64-appstream-rpms'
```

Now [create 1Password items][7] storing the modified `userData` for each VM.

```bash
vault=eso
for vm in client ldap nfs; do
  op item create \
    --vault "$vault" \
    --category login \
    --title "demo autofs $vm" \
    --url "https://github.com/dlbewley/demo-autofs/tree/main/${vm}/base/scripts" \
    --tags demo=autofs \
    "userData[file]=${vm}/base/scripts/userData"
done
```

> 📓 If you later make changes to the userData script you can update the copy in 1Password like this.
> ```bash
> vault=eso
> for vm in client ldap nfs; do
>   op item edit \
>     --vault "$vault" \
>     --url "https://github.com/dlbewley/demo-autofs/tree/main/${vm}/base/scripts" \
>     "demo autofs $vm" \
>     "userData[file]=${vm}/base/scripts/userData"
> done
> ```

Here is a view of the 1Password vault after uploading each of our `userData` scripts.

{{< figure src="/images/securing-cloud-init-1password-vault.png" link="/images/securing-cloud-init-1password-vault.png"  caption="1Password Vault Entry" width="100%">}}

# Configuring the External Secrets Operator

Create a `ClusterSecretStore` associated to the 1password-sdk provider. This will be referenced by `ExternalSecret` resource created later, and it will use the secret token we just created to look up data in the vault.

```yaml {{linenos=inline,hl_lines=[11,12]}}
---
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: 1password-sdk
spec:
  provider:
    onepasswordSDK:
      vault: eso
      auth:
        serviceAccountSecretRef:
          name: onepassword-connect-token
          key: token
          namespace: external-secrets
```

# Updating the VM Deployment

Now we want to update [the kustomization.yaml][14] file that deploys the VM. It should create the `ExternalSecret` and adjust the virtual machine patch to mount to the generated Secret to find the cloud-init script.

As a sanity check we can still generate a sample secret from our "clean" userData in git, but we also need to apply the external secret and patch our VM to use the resulting secret produced by the ESO.

> {{< collapsable prompt="🪡 **Virtual Machine Patches**" collapse=false md=true >}}
  ```yaml {{linenos=inline,hl_lines=[26,32,49,50]}}
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: demo-client

labels:
  - includeSelectors: true
    pairs:
      demo: client
      app.kubernetes.io/instance: demo-autofs-client

components:
  - ../../components/argocd-vm-management

generatorOptions:
  disableNameSuffixHash: true

configMapGenerator:
  - name: sssd-conf
    files:
      - scripts/sssd.conf
      - scripts/homedir.conf

secretGenerator:
  - name: cloudinitdisk-client-sample
    files:
      - scripts/userData

resources:
  - namespace.yaml
  - externalsecret.yaml
  - virtualmachine.yaml

patches:
  - target:
      group: kubevirt.io
      kind: VirtualMachine
      name: .*
      version: v1
    patch: |-
      - op: replace
        path: /spec/runStrategy
        value: Always
      # add volumes for secret and configmap
      - op: replace
        path: /spec/template/spec/volumes/1/cloudInitNoCloud
        value: {
          "secretRef": {
            "name": "cloudinitdisk-client"
          }
        }
```
  {{< /collapsable >}}

### Reading Data from 1Password

Create an `{client,ldap,nfs}/base/externalsecret.yaml` for each VM.
Here are examples for each of the VMs [client][11], [ldap][12], and [nfs][13].

Notice that we set the refreshInterval to 0 so that the ESO is not continually checking 1Password for changes to this secret. If you do not disable this it is likely that you will become rate limited.

It is nonsensical to keep checking for an updated userData. Remember this is only used once. When the VM boots for the first time.

> {{< collapsable prompt="🔐 **External Secret**" collapse=false md=true >}}
  ```yaml{{linenos=inline,hl_lines=[8,13,19]}}
  ---
  apiVersion: external-secrets.io/v1
  kind: ExternalSecret
  metadata:
  name: cloudinitdisk-client
  spec:
  refreshPolicy: OnChange
  refreshInterval: "0"
  secretStoreRef:
      kind: ClusterSecretStore
      name: 1password-sdk
  target:
      name: cloudinitdisk-client # this will be the name of the secret
      creationPolicy: Owner
  data:
  - secretKey: "userData" # this will be a field in the secret
      remoteRef:
      # 1password-entry-name and property
      key: "demo autofs client/userData"
  ```
  {{< /collapsable >}}

This `ExternalSecret` will retrieve the data at "demo autofs client/userData" create a Secret named `cloudinitdisk-client`.

# Booting the VM

Deploy the Virtual Machine using Kustomize


```bash
$ oc apply -k client/overlays/localnet
namespace/demo-client created
role.rbac.authorization.k8s.io/argocd-vm-management created
rolebinding.rbac.authorization.k8s.io/argocd-vm-management created
configmap/sssd-conf created
secret/cloudinitdisk-client-sample created
externalsecret.external-secrets.io/cloudinitdisk-client created # <---
virtualmachine.kubevirt.io/client created
```

After a moment the `ExternalSecret` status should be _SecretSynced_ and we can see the resulting `cloudinitdisk-client` secret has been created.

```bash
$ oc get externalsecrets -n demo-client
NAME                   STORETYPE            STORE           REFRESH INTERVAL   STATUS         READY
cloudinitdisk-client   ClusterSecretStore   1password-sdk   0                  SecretSynced   True

$ oc get secrets -l demo=client -n demo-client
NAME                          TYPE     DATA   AGE
cloudinitdisk-client          Opaque   1      98s   # Created by ESO
cloudinitdisk-client-sample   Opaque   1      2m20s # Generated by Kustomize
```

Once the VM boots we can login and examine the user data imported from the secret, and confirm the  information from the vault is indeed there!

```bash
[root@client ~]# grep -A2 subscription /var/lib/cloud/instance/user-data.txt
rh_subscription:
  org: 12345678
  activation-key: secret-key4me
```

# References

* [Demo Github Repo][5]
* [Client userData External Secret][2]
* [External Secrets Operator][3]
* [1Password-SDK ESO Provider][4]
* [1Password Create Item Docs][7]

[1]: {{< ref "/blog/Deploying-LDAP-AutoFS-with-OpenShift-Virtualization.md" >}}  "Deploying-LDAP-AutoFS-with-OpenShift-Virtualization"
[2]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/externalsecret.yaml> "Client userData External Secret"
[3]: <https://external-secrets.io/latest/> "External Secrets Operator"
[4]: <https://external-secrets.io/latest/provider/1password-sdk/> "1Password ESO Provider"
[5]: <https://github.com/dlbewley/demo-autofs/> "Demo Github Repo"
[7]: <https://developer.1password.com/docs/cli/item-create/> "1Password Create Item Docs"
[8]: <https://github.com/dlbewley/demo-autofs/blob/main/nfs/base/scripts/userData> "NFS VM cloud-init"
[9]: <https://github.com/dlbewley/demo-autofs/blob/main/ldap/base/scripts/userData> "LDAP VM cloud-init"
[10]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/scripts/userData> "Client VM cloud-init"
[11]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/externalsecret.yaml> "Client VM ExternalSecret"
[12]: <https://github.com/dlbewley/demo-autofs/blob/main/ldap/base/externalsecret.yaml> "LDAP VM ExternalSecret"
[13]: <https://github.com/dlbewley/demo-autofs/blob/main/nfs/base/externalsecret.yaml> "NFS VM ExternalSecret"
[14]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/kustomization.yaml> "Client VM Kustomization"