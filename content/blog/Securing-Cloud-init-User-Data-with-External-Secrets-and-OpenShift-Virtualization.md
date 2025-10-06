---
title: "Securing Cloud-init User Data with External Secrets and OpenShift Virtualization"
date: 2025-10-06
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
description: Learn how to securely manage cloud-init user data in OpenShift Virtualization using External Secrets Operator and 1Password, keeping sensitive information out of git repositories.
---

Storing Kubernetes resources in git for automated deployment promotes consistency, resilency, and accountability, but commiting secrets to git is risky and should be avoided. Use the External Secrets Operator to securely store cloud-init and other data, and sleep soundly!

<!--more-->

# Securing Cloud-init User Data

As described in [this post][1] the cloud-init `userData` script for a [OpenShift Virtualization][15] virtual machine may contain privileged information like activation keys for your RHEL subscription.

```yaml
rh_subscription:
  org: 00000000
  activation-key: EXAMPLE
  enable-repo:
    - 'rhel-9-for-x86_64-baseos-rpms'
    - 'rhel-9-for-x86_64-appstream-rpms'
```

These example userData scripts for VMs: [client][10], [ldap][9], and [nfs][8] have placeholders which make them safe to place in a public repository.

Most of the data isn't sensitive, and keeping the scripts in git makes for easier testing and debugging. But how can we safely manage the actual secret to be used by cloud-init if it is not commited to git?

# The External Secrets Operator

The [External Secrets Operator][3] solves this issue for us by understanding how to look into secure vaults from "[providers][4]" like AWS Secrets Manager, HashiCorp Vault, or 1Password.

Once your data is within a secure vault, you will create an `ExternalSecret` resource, which is safe to commit to git. When you apply these resources to the cluster, the ESO will use the information in the ExternalSecret to create a Kubernetes `Secret` resource, securely downloading, and inserting the sensitive data into it.

## 1Password Provider for ESO

Using [1Password](https://1password.com) can be handy in a homelab or development environment, particularly if you already use 1Password to manage credentials in your browser. You Don't have to deploy any infrastructure or have an AWS account to use it. Be aware there is more than one 1Password integration and you should select the 1Password-SDK External Secrets Operator provider.

## Installing the External Secrets Operator

Make sure to install a version of the External Secrets Operator (ESO) that supports the 1password-sdk provider, which was introduced in version 0.17. The older 1password-connect provider is now deprecated. If the operator has been updated to version 0.17 or later by the time you read this, you may be able to use the operator directly instead of installing via the Helm chart.

Install latest upstream ESO using Helm.

```bash
$ helm repo add external-secrets https://charts.external-secrets.io

$ oc new-project external-secrets

$ helm install external-secrets \
   external-secrets/external-secrets \
   -n external-secrets
```

# Configuring 1Password

Use the command line to setup 1Password. Grab the 1Password CLI command `op` from https://developer.1password.com/ or use `brew`.

```bash
$ brew install 1password-cli
```

Create a dedicated vault in 1Password for use by the ESO, so there is no chance of your personal data sloshing around in your Kubernetes environment.

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

Place this token in a secret called _onepassword-connect-token_ which allows ESO to authenticate to 1Password.

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

Now, we can take the example userData files and modify them to contain the sensitive data we want. In this case, the organization ID and activation key required for our subscription.

Edit the checked out copy of the `{VM}/base/scripts/userData` scripts, and insert the configuration that should not be stored in git.

At this point, the copies in your working directory may now look like the following. Be certain not to commit these changes to git!

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

Now that 1Password is ready, it's time to tell the ESO about it.

Create a `ClusterSecretStore` associated to the 1password-sdk provider. This will be referenced by `ExternalSecret` resources created later, and it will use the secret token we just created to look up data in the vault.

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

## Reading Secret Data from the Vault

Create an `externalsecret.yaml` for each VM.
Here are examples for each of the VMs [client][11], [ldap][12], and [nfs][13].

Notice below that we set the refreshInterval to 0 so that the ESO is not continually checking 1Password for changes to this secret. Remember this secret is only used once, when the VM boots for the first time.

 If you do not disable this refresh, then it is likely that you will become rate limited.

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
      name: cloudinitdisk-client # this will be the name of the created secret
      creationPolicy: Owner
  data:
  - secretKey: "userData" # this will be a field in the secret
      remoteRef:
      # 1password-entry-name and property
      key: "demo autofs client/userData"
  ```
  {{< /collapsable >}}

This `ExternalSecret` will retrieve the data at "demo autofs client/userData" create a Secret named `cloudinitdisk-client`.


# Updating the VM Deployment

Now we must update [the kustomization.yaml][14] file that deploys the virtual machine. It should create the `ExternalSecret` and patch the VM to mount the subsequently created `Secret` holding the sensitive version of the cloud-init script.

As a reference, we can still let Kustomize generate a sample secret from our "clean" userData in git.

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

# Booting the VM

Finally, deploy the Virtual Machine using [Kustomize][6] via the `oc apply -k` command.

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

After a moment, the `ExternalSecret` status should be _SecretSynced_ and we can see that the resulting `cloudinitdisk-client` secret has been created.

```bash
$ oc get externalsecrets -n demo-client
NAME                   STORETYPE            STORE           REFRESH INTERVAL   STATUS         READY
cloudinitdisk-client   ClusterSecretStore   1password-sdk   0                  SecretSynced   True

$ oc get secrets -l demo=client -n demo-client
NAME                          TYPE     DATA   AGE
cloudinitdisk-client          Opaque   1      98s   # Created by ESO
cloudinitdisk-client-sample   Opaque   1      2m20s # Generated by Kustomize
```

Once the VM boots we can login and examine the user data imported from the secret, and confirm the information from the vault is indeed there!

```bash
[root@client ~]# grep -A2 subscription /var/lib/cloud/instance/user-data.txt
rh_subscription:
  org: 12345678
  activation-key: secret-key4me
```

# Summary

By leveraging the [External Secrets Operator][3] and [Kustomize][6] we _safely_ deployed fully provisioned Virtual Machines to OpenShift using a single command.
We used 1Password for it's ubiquity and ease of setup, but this pattern can be adapted for other secret backends and VM configurations, providing a robust solution for secret management in [OpenShift Virtualization][15] environments.

# References

* [Demo Github Repo][5]
* [Client userData External Secret][2]
* [External Secrets Operator][3]
* [1Password-SDK ESO Provider][4]
* [1Password Create Item Docs][7]
* [Kustomize][6]
* [OpenShift Virtualization][15]

<!-- "/blog/Deploying-LDAP-AutoFS-with-OpenShift-Virtualization.md" -->
[1]: {{< ref "/coming-soon.md" >}}  "Deploying-LDAP-AutoFS-with-OpenShift-Virtualization"
[2]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/externalsecret.yaml> "Client userData External Secret"
[3]: <https://external-secrets.io/latest/> "External Secrets Operator"
[4]: <https://external-secrets.io/latest/provider/1password-sdk/> "1Password ESO Provider"
[5]: <https://github.com/dlbewley/demo-autofs/> "Demo Github Repo"
[6]: <https://kustomize.io/> "Kustomize"
[7]: <https://developer.1password.com/docs/cli/item-create/> "1Password Create Item Docs"
[8]: <https://github.com/dlbewley/demo-autofs/blob/main/nfs/base/scripts/userData> "NFS VM cloud-init"
[9]: <https://github.com/dlbewley/demo-autofs/blob/main/ldap/base/scripts/userData> "LDAP VM cloud-init"
[10]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/scripts/userData> "Client VM cloud-init"
[11]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/externalsecret.yaml> "Client VM ExternalSecret"
[12]: <https://github.com/dlbewley/demo-autofs/blob/main/ldap/base/externalsecret.yaml> "LDAP VM ExternalSecret"
[13]: <https://github.com/dlbewley/demo-autofs/blob/main/nfs/base/externalsecret.yaml> "NFS VM ExternalSecret"
[14]: <https://github.com/dlbewley/demo-autofs/blob/main/client/base/kustomization.yaml> "Client VM Kustomization"
[15]: <https://www.redhat.com/en/technologies/cloud-computing/openshift/virtualization> "OpenShift Virtualization"