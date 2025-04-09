---
title: "Generate a Kubeconfig to Enable OpenShift Service Account Authentication"
date: 2025-04-09
banner: /images/kubeconfig.jpeg
layout: post
mermaid: false
asciinema: true
tags:
  - openshift
  - kubernetes
  - kubeconfig
  - security
description: This post demonstrates how to properly generate kubeconfig files for OpenShift ServiceAccounts, enabling secure token-based authentication and TLS connections. You will learn how to create ServiceAccounts, generate time-limited tokens, bundle CA certificates, and package everything into a distributable kubeconfig file that can be stored as a Secret for download.
---

This post demonstrates how to properly generate kubeconfig files for OpenShift ServiceAccounts, enabling secure token-based authentication and TLS connections. You will learn how to create ServiceAccounts, generate time-limited tokens, bundle CA certificates, and package everything into a distributable kubeconfig file that can be stored as a Secret for download.

<!--more-->

# Creating a Kubeconfig for OpenShift ServiceAccounts

As an admin, you can generate kubeconfig files for your users to leverage with their ServiceAccounts. Here are the detailed steps. 🚶

## Prerequisites

* 🔧  Establish some default values

```bash
export API_SERVER='api.agent.lab.bewley.net:6443'
export SERVICE_ACCOUNT='demo-sa'
export KUBECONFIG_SA="kubeconfig-$SERVICE_ACCOUNT"
export NAMESPACE='demo-kubeconfig'
export DURATION='1h'
```

* 💻 Login to the cluster as admin (See [how I manage my kubeconfigs][5])

```bash
source ~/.kube/ocp/agent/.env
echo $KUBECONFIG
/Users/dale/.kube/ocp/agent/kubeconfig

oc config current-context
default/api-agent-lab-bewley-net:6443/system:admin

oc whoami
system:admin
```

* 🔑 Gather the API CA certificate
```bash
export API_CERT=$(oc get secret  loadbalancer-serving-signer \
                    -n openshift-kube-apiserver-operator \
                    -o jsonpath='{.data.tls\.crt}' | base64 -d)
```

* 🔑 Gather the ingress CA certificate
```bash
export INGRESS_CERT=$(oc get secret router-ca \
                        -n openshift-ingress-operator \
                        -o jsonpath='{.data.tls\.crt}' | base64 -d)
```

* 🔑 save the certificates to a bundle
```bash
cat <<EOF > ca-bundle.crt
$API_CERT
$INGRESS_CERT
EOF
```

* ✅ You may use `curl` to verify the CA for API
```bash
curl --cacert ./ca-bundle.crt https://$API_SERVER/healthz 
ok%  
```

> {{< collapsable prompt="📝 **Pro Tip** Viewing CA certificate details" collapse=true md=true >}}
  You may use the `openssl x509` command to examine certificate details like expiration dates.
  ```bash
  $ echo $API_CERT | openssl x509 -noout -dates -issuer -subject
  notBefore=Mar 17 20:50:37 2025 GMT
  notAfter=Mar 15 20:50:37 2035 GMT
  issuer=OU=openshift, CN=kube-apiserver-lb-signer
  subject=OU=openshift, CN=kube-apiserver-lb-signer
  #
  $ echo $INGRESS_CERT | openssl x509 -noout -dates -issuer -subject 
  notBefore=Mar 17 21:39:50 2025 GMT
  notAfter=Mar 17 21:39:51 2027 GMT
  issuer=CN=ingress-operator@1742247591
  subject=CN=ingress-operator@1742247591
  ```
  {{< /collapsable>}}

## Creating a ServiceAccount and Token

* 🔧 Create a new project and avoied adding the new context to our current $KUBECONFIG
```bash
oc new-project $NAMESPACE\
 --display-name='Demo SA Kubeconfig Mgmt'\
 --description='See https://github.com/dlbewley/demo-kubeconfig'\
 --skip-config-write
```

* 🤖 Create a service account
```bash
oc create serviceaccount $SERVICE_ACCOUNT -n $NAMESPACE
```

> ⚠️ **Caution** _Tokens are copyable keys!_ Your cluster can be accessed just by having a copy of the token. You might consider setting an expiration date by using the `--duration` option when generating tokens.

* 🔑 Create a token for the service account that lasts for a limited duration
```bash
export TOKEN=$(oc create token -n $NAMESPACE $SERVICE_ACCOUNT --duration=$DURATION)
```

> {{< collapsable prompt="📝 **Pro Tip** If you are curious to see the JWT token contents try this:" collapse=true md=true >}}
  
  ```bash
  echo $TOKEN | cut -d '.' -f2 | base64 -d | jq                   
  {
    "aud": [
      "https://kubernetes.default.svc"
    ],
    "exp": 1744146844,
    "iat": 1744143244,
    "iss": "https://kubernetes.default.svc",
    "jti": "e4510577-5955-4eb4-9f97-dec4f0e6dc34",
    "kubernetes.io": {
      "namespace": "demo-kubeconfig",
      "serviceaccount": {
        "name": "demo-sa",
        "uid": "73a74060-e67d-4b1a-ad56-e92227732d53"
      }
    },
    "nbf": 1744143244,
    "sub": "system:serviceaccount:demo-kubeconfig:demo-sa"
  }
  TS_ISSUED=$(echo $TOKEN | cut -d '.' -f2 | base64 -d | jq '.iat')
  TS_EXPIRATION=$(echo $TOKEN | cut -d '.' -f2 | base64 -d | jq '.exp')

  # view the issued and expiry times
  date -r $TS_EXPIRATION # on MacOS
  Tue Apr  8 14:14:04 PDT 2025
  # date -d @$TS_EXPIRATION # on Linux
  ```
  {{< /collapsable>}}

## Generating a Kubeconfig

Logging into a cluster for the first time will create a kubeconfig file. By default this will be at the location defined in `~/.kube/config` or the value found in the optional $KUBECONFIG environment variable.

* 🔧 Create kubeconfig file for $SERVICE_ACCOUNT in $NAMESPACE and avoid insecure connection by referencing the CA bundle created above
```bash
oc login --server=$API_SERVER \
  --token=$TOKEN \
  --certificate-authority=./ca-bundle.crt \
  --kubeconfig=$KUBECONFIG_SA
```

* 🔑 Insert the ca-bundle.crt into the kubeconfig file
```bash
oc config set-cluster $API_SERVER --embed-certs --certificate-authority=./ca-bundle.crt \
  --server https://$API_SERVER --kubeconfig="$KUBECONFIG_SA"
```

* ✅ Verify that using the kubeconfig file works
```bash
oc whoami --kubeconfig=$KUBECONFIG_SA
system:serviceaccount:demo-kubeconfig:demo-sa

# 🔒 the service account will have limited permissions until RBAC is configured"
oc get sa --kubeconfig=$KUBECONFIG_SA
Error from server (Forbidden): serviceaccounts is forbidden:...
```

The permissions of the serviceaccount may need to be adjusted through the application of RBAC, but you can now distribute the kubeconfig.

# Storing the Generated Kubeconfig in a Secret

The kubeconfig file may now be placed into a Secret where it can be downloaded from the OpenShift console or with the `oc extract` command.

```bash
oc create secret -n $NAMESPACE generic $KUBECONFIG_SA \
   --from-file=kubeconfig=$KUBECONFIG_SA
secret/kubeconfig-demo-sa created

oc describe secrets/$KUBECONFIG_SA -n $NAMESPACE
Name:         kubeconfig-demo-sa
Namespace:    demo-kubeconfig
Labels:       <none>
Annotations:  <none>

Type:  Opaque

Data
====
kubeconfig:  5191 bytes
```

# Demo

**Demo ([source][3]): Enabling OpenShift Service Accounts to use Token Authentication in Kubeconfigs**
> {{< collapsable prompt="📺 ASCII Screencast" collapse=false >}}
  <p>Setup bridge & network attachment, create VMs, test networking, and cleanup. </p>
  {{< asciinema key="kubeconfig-agent-lab-bewley-net-20250408_1649" rows="50" font-size="smaller" poster="npt:1:35" loop=false >}}
  {{< /collapsable>}}

## References

* [How to create kubeconfig for a certain serviceaccount][1] - Red Hat KCS
* [Oc Token Creation][2] - OpenShift Documentation
* [Demo Script][3]
* [Demo Repo][4]

**See also:**
* [Storing OpenShift Credentials with 1Password][5]
* [Extracting TLS CA Certificates from Kubeconfig File][6]

[1]: <https://access.redhat.com/solutions/6998487> "Red Hat KCS"
[2]: <https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/cli_tools/openshift-cli-oc#oc-create-token> "OpenShift Token Creation Documentation"
[3]: <https://github.com/dlbewley/demo-kubeconfig/blob/main/demo-script.sh> "Demo Script"
[4]: <https://github.com/dlbewley/demo-kubeconfig/tree/main> "Demo Repo"
[5]: {{< ref "/blog/Storing-OpenShift-Credentials-with-1Password.md" >}} "Storing OpenShift Credentials with 1Password"
[6]: {{< ref "/blog/Extracting-CA-Certs-From-Kubeconfig.md" >}} "Extracting TLS CA Certs from Kubeconfig.md"