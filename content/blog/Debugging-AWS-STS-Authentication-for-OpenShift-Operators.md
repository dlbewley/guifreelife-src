---
title: "Debugging AWS STS Authentication for OpenShift Operators"
date: 2022-03-10
banner: /images/debug-sts-banner.jpg
layout: post
tags:
 - AWS
 - openshift
 - OCP4
 - operators
 - debugging
banner-credits: https://library.techsmith.com/camtasia/assets/asset/seg/1825355300_2e0192bb-1246-41e2-8801-2e8beaff3a0f
---

OpenShift supports granular AWS permissions for pods running cluster operators or even user applications. This enhances security by providing only the necessary privileges and nothing more. This post explores debugging authN and authZ of pods attempting to use fine grained IAM roles in combination with AWS secure token service.
<!--more-->

# What is STS Authentication?

First some background on what [Secure Token Service (STS)][8] is, and why it is a best practice.

The typical method of programmatic authentication to AWS uses long lived [credentials][9] in the form of any `aws_access_key_id` and an associated `aws_secret_access_key`. If those 2 items were to be accidentally leaked, it's game over for your AWS bill. 

STS adds an ephemeral third factor in `aws_session_token`. This token will expire after a period of time, so it must be regenerated on a regular basis. In this case, these tokens are validated and refreshed by interacting with an OpenID Connect [Identity Provider][10] created for use by OpenShift.

OpenShift [projects][12] these 3 factors into a pod which may then use them to authenticate and assume an IAM role appropriately authorized for the relevant AWS services.

> :notebook: **OpenShift STS Authentication Process**
> {{< figure
  src="/images/sts-authn-flow.png"
  width="100%"
  link="https://docs.openshift.com/container-platform/latest/authentication/managing_cloud_provider_credentials/cco-mode-sts.html"
  attrlink="https://docs.openshift.com/container-platform/latest/authentication/managing_cloud_provider_credentials/cco-mode-sts.html"
  attr="STS authentication flow"
>}}

Let's explore this more deeply by looking an example where this process may not be working properly.

# Degraded Ingress Cluster Operator

Multiple operators interact with STS to assume fine grained roles, but we'll focus on the [Ingress operator][13].

In this example, the Ingress cluster operator status is _Degraded_. The last message indicates the controller could not find the wildcard DNS (`*.apps`) entry in Route53. Normally the Ingress operator will be the device to create this record, but it can't even search for it for some reason.

```
$ oc get co ingress
NAME                                       VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
ingress                                              False       True          True       18h     ...\n\n

 The "default" ingress controller reports Available=False: IngressControllerUnavailable: One or more status conditions indicate unavailable: DNSReady=False (NoZones: The record isn't present in any zones.)
```

# Debugging Operator STS Authentication

The Ingress operator needs to authenticate to interact with Route53 service. To do so it seeks to assume a role that was provisioned by the [cloud-credential-operator][7], `ccoctl`, or [by hand][5]. 

This role is named in a secret along with the location of a secret token signed by a key trused by the OpenID Connect Provider you configured in AWS IAM.

Start by describing the cluster operator (`oc describe co ingress`) but more importantly, check the logs of the ingress operator pod.

```bash
$ oc logs -n openshift-ingress-operator deployment/ingress-operator -c ingress-operator
```

>  2022-02-25T17:08:36.019Z        ERROR   operator.init.controller-runtime.manager.controller.dns_controller      controller/controller.go:253    Reconciler error        {"name": "default-wildcard", "namespace": "openshift-ingress-operator", "error":
>         failed to create DNS provider: failed to create AWS DNS manager: failed to validate aws provider service endpoints: [failed to list route53 hosted zones: **WebIdentityErr: failed to retrieve credentials caused by: InvalidIdentityToken: Couldn't retrieve verification key from your identity provider,  please reference AssumeRoleWithWebIdentity documentation for requirements**
>         status code: 400, request id: 6aa3127f-e9b8-44e1-87e6-a739746f0370, ...

It appears the token was not verified.

# Mapping the Operator to a Role

**Is STS authentication and "assume role with web identity" working?**

The ingress operator pod should be assuming a unique role from AWS that is more fine grained than the instance profile used by the node. In this way the pod has only the premissions it requires to interact with Route53 and ELB APIs.

> :notebook: **Try to reproduce this failure by replicating what the pod is doing.**
>
> After copying the token you can use  the `aws sts assume-role-with-web-identity` command to test with.

First, gather some details from the pod's context. Spefically the role to be assumed, and the token to authenticate with.

## Cloud-credentials Secret

The `cloud-credentials` secret holds the [ARN][14] of the role which the pod should assume once authenticated, and the location of the token used to authenticate with. That token will be [automatically][12] available.

> ```bash
> $ oc -n openshift-ingress-operator extract secret/cloud-credentials --to=-
> # credentials
> [default]
> role_arn = arn:aws:iam::1234567890:role/ocp-oidc-openshift-ingress-operator-cloud-credentials
> web_identity_token_file = /var/run/secrets/openshift/serviceaccount/token
> ```
> 
> **Role ARN**
> 
> The `role_arn` refers to the IAM role which may have been created by the `cloud-crendential-operator` or other means.
> 
> Save this value to `$ROLE_ARN`.
> 
> **JWT Token**
> 
> The `web_identity_token_file` identifies the projected volume mount holding the JWT used to authenticate.
> 
> Download a copy of this file and save the path to `$TOKEN`

## Viewing the Contents of the Role

Before moving on let's pause and understand a bit more about the IAM role the operator seeks to assume.

The definition of the IAM role used by an operator will be derived from the `CredentialsRequest` resources bundled with the operator.

```bash
$ RELEASE_IMAGE=quay.io/openshift-release-dev/ocp-release:4.9.21-x86_64
$ mkdir -p credrequests
$ oc adm release extract \
    --credentials-requests --cloud=aws \
    --to=credrequests/ $RELEASE_IMAGE

$ cat credrequests/0000_50_cluster-ingress-operator_00-ingress-credentials-request.yaml
```
```yaml
apiVersion: cloudcredential.openshift.io/v1
kind: CredentialsRequest
metadata:
  annotations:
    include.release.openshift.io/ibm-cloud-managed: "true"
    include.release.openshift.io/self-managed-high-availability: "true"
    include.release.openshift.io/single-node-developer: "true"
  labels:
    controller-tools.k8s.io: "1.0"
  name: openshift-ingress
  namespace: openshift-cloud-credential-operator
spec:
  providerSpec:
    apiVersion: cloudcredential.openshift.io/v1
    kind: AWSProviderSpec
    statementEntries:
    - action:
      - elasticloadbalancing:DescribeLoadBalancers
      - route53:ListHostedZones
      - route53:ChangeResourceRecordSets
      - tag:GetResources
      effect: Allow
      resource: '*'
  secretRef:
    name: cloud-credentials
    namespace: openshift-ingress-operator
  serviceAccountNames:
  - ingress-operator
```

# Examining the JSON Web Token

The [JWT][2] or JSON Web Token which contains **3 fields** delimited by a "**.**".

1. Key ID which should match the IDP Key ID. _Confirm this in the OIDC provider config_
1. Token Issuer and OpenShift service account name
1. Cryptographic Signature


Note the key ID (`kid`)

> **Field 1**
> ```bash
> $ export TOKEN=/tmp/token
> $ oc  -n openshift-ingress-operator -c ingress-operator \
>        rsh deployment/ingress-operator \
>        cat /var/run/secrets/openshift/serviceaccount/token > $TOKEN
>
> $ cat $TOKEN | awk -F. '{ print $1 }' | base64 -d | jq
> ```
> ```json
> {
>   "alg": "RS256",
>   "kid": "TrJph8YY31qgQcN_KTaQspV7dY6Uks1BynN3YsoxJ5s"
> }
> ```

In the 2nd field we want to note the audience (`aud`), the issuer (`iss`), and the service account name (`serviceaccount`) scoped by namespace.

> **Field 2**
> ```bash
> $ cat $TOKEN | awk -F. '{ print $2 }' | base64 -d | jq
> ```
> ```json
> {
>   "aud": [
>     "openshift"
>   ],
>   "exp": 1642528257,
>   "iat": 1642524657,
>   "iss": "https://ocp-oidc-oidc.s3.us-west-2.amazonaws.com",
>   "kubernetes.io": {
>     "namespace": "openshift-ingress-operator",
>     "pod": {
>       "name": "ingress-operator-5b8c4b8d8b-8kb8b",
>       "uid": "cf9ee1e6-387f-445d-b8c0-90f40ad8a174"
>     },
>     "serviceaccount": {
>       "name": "ingress-operator",
>       "uid": "38313504-2c4c-4d1b-92a9-c7db391a8a59"
>     }
>   },
>   "nbf": 1642524657,
>   "sub": "system:serviceaccount:openshift-ingress-operator:ingress-operator"
> }
> ```

> **Field 3**
> _Not relevant today._

## Verify the JWT Values

Confirm the key is recognized and the resources are publicly accessible.

**Is the Key used to generate the token recognized by the OIDC provider in AWS?**

You may verify the Key ID in the [AWS OIDC provider resource][11] with the `kid` in field 1 of the token.

## Verify OpenID Connect IDP Reachability

**Can you reach the IDP issuer's openid-configuration?**

The configuration file MUST be publicly reachable for OIDC to function as Amazon makes the call to this resource on your behalf. _This must succeed on and off VPC!_

```bash
ISSUER=$(cat $TOKEN | awk -F. '{ print $2 }' | base64 -d| jq -r .iss)
# try this from a pod and from your laptop
curl -s $ISSUER/.well-known/openid-configuration || echo "Failure"
```

**Can you reach the IDP issuer's public keys?**

The keys MUST be publicly reachable for OIDC to function as Amazon makes the call to this resource on your behalf. _This must succeed on and off VPC!_

```bash
KEYS=$(curl -s $ISSUER/.well-known/openid-configuration | jq -r .jwks_uri)
# try this from a pod and from your laptop
curl -s $KEYS || echo "Failure"
```

# Testing Authentication with the Token

Use the token to attempt to the assume the role.

**First confirm you are authenitcated to AWS normally.**

```bash
$ aws sts get-caller-identity
{
    "UserId": "AROATPFFJRK73QH4YHANK:i-07d6dbc1345299a43",
    "Account": "1234567890",
    "Arn": "arn:aws:sts::1234567890:assumed-role/managed-roles-ocp-BastionInstanceRole-X15RKXKW1US9/i-07d6dbc1345299a43"
}
```

**Can you "assume role with web identity" using this token?**

Copy the token to your a host where the aws CLI is configured and available. Then do what the pod is trying to do.

```bash
# Remember role_arn and token location here:
#  oc -n openshift-ingress-operator extract secret/cloud-credentials --to=-
echo $ROLE_ARN
arn:aws:iam::1234567890:role/ocp-oidc-cf-openshift-ingress-operator-cloud-credentials
echo $TOKEN
/tmp/token

aws sts assume-role-with-web-identity \
    --duration-seconds 900 \
    --role-session-name "assumeroletest" \
    --role-arn "$ROLE_ARN" \
    --web-identity-token "$(cat $TOKEN)"
```

You should get back a block of JSON for success

> ```json
> {
>     "Credentials": {
>         "AccessKeyId": "ASIAT...............",
>         "SecretAccessKey": "cgp/a/ziU.......",
>         "SessionToken": "IQoJb3JpZ2luX2VjE..",
>         "Expiration": "2022-02-25T22:09:33+00:00"
>     },
>     "SubjectFromWebIdentityToken": "system:serviceaccount:openshift-ingress-operator:ingress-operator",
>     "AssumedRoleUser": {
>         "AssumedRoleId": "AROATPFFJRK72IHENLQ7D:assumeroletest",
>         "Arn": "arn:aws:sts::1234567890:assumed-role/ocp-oidc-cf-openshift-ingress-operator-cloud-credentials/assumeroletest"
>     },
>     "Provider": "arn:aws:iam::1234567890:oidc-provider/ocp-oidc-oidc.s3.us-west-2.amazonaws.com",
>     "Audience": "openshift"
> }
> ```

If you see an error like this, your pod can not authenticate or isn't authorized to assume the role.

> An error occurred (InvalidIdentityToken) when calling the AssumeRoleWithWebIdentity operation: Couldn't retrieve verification key from your identity provider,  please reference AssumeRoleWithWebIdentity documentation for requirements

# Possible Failures

* Are the openid-configuration and the keys publicly reachable by https? Remember this does not HAVE to be S3. If your S3 may only be private then you could use Cloudfront to expose the bucket.
* Is the key id in the token the same as configured in the OIDC IDP?
* Is the openid-configuration pointing to the right URL for the keys?
* Is the audience in the token the same as configured in the OIDC IDP? The identity provider should have 'sts.amazonaws.com' and 'openshift' audiences.
* Was `credentialsMode` set to _manual_ at OpenShift install time?
* Does the token service account match the trust relationship on the role? Notice the namespace and service account names
> **IAM Role Trust Relationship** Note service account in the condition
> ```json
> {
>     "Version": "2012-10-17",
>     "Statement": [
>         {
>             "Effect": "Allow",
>             "Principal": {
>                 "Federated": "arn:aws:iam::1234567890:oidc-provider/ocp-oidc-oidc.s3.us-west-2.amazonaws.com"
>             },
>             "Action": "sts:AssumeRoleWithWebIdentity",
>             "Condition": {
>                 "StringEquals": {
>                     "ocp-oidc-oidc.s3.us-west-2.amazonaws.com:sub": "system:serviceaccount:openshift-ingress-operator:ingress-operator"
>                 }
>             }
>         }
>     ]
> }
> ```

# References

* [Fine Grained IAM Roles for OpenShift Applications][1] _Red Hat_
* [JSON Web Token][2] _IETF_
* [EKS Pod Identity Webhook Deep-Dive][3] _Mikesir87_
* [Cloud Credential Operator][7] _Github_
* [Configuring OpenShift Cloud Crendential Operator][6], See [v4.7 docs][5] for greater detail that is automated by `ccoctl` in later versions
* [Introducing fine-grained IAM roles for service accounts][4] _AWS_
* [IAM roles for EKS service accounts][15] _AWS_
* [Temporary security credentials in IAM][8] _AWS_
* [Managing access keys for IAM users][9] _AWS_
* [Creating OpenID Connect (OIDC) identity providers][10] _AWS_
* [Service Account Token Volume Projection][12] _Kubernetes_

[1]: <https://cloud.redhat.com/blog/fine-grained-iam-roles-for-openshift-applications> "Fine Grained IAM Roles for OpenShift Applications"
[2]: <https://datatracker.ietf.org/doc/html/rfc7519> "JSON Web Token"
[3]: <https://blog.mikesir87.io/2020/09/eks-pod-identity-webhook-deep-dive/> "EKS Pod Identity Webhook Deep-Dive"
[4]: <https://aws.amazon.com/blogs/opensource/introducing-fine-grained-iam-roles-service-accounts/> "Introducing fine-grained IAM roles for service accounts"
[5]: <https://docs.openshift.com/container-platform/4.7/authentication/managing_cloud_provider_credentials/cco-mode-sts.html> "Configuring Cloud Credential Operator with STS v4.7 docs include greater detail"
[6]: <https://docs.openshift.com/container-platform/latest/authentication/managing_cloud_provider_credentials/cco-mode-sts.html> "Configuring Cloud Credential Operator with STS"
[7]: <https://github.com/openshift/cloud-credential-operator> "Cloud Credential Operator"
[8]: <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html> "Temporary security credentials in IAM"
[9]: <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html> "Managing access keys for IAM users"
[10]: <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers.html> "Identity providers and federation"
[11]: <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html> "Creating OpenID Connect (OIDC) identity providers"
[12]: <https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#service-account-token-volume-projection> "Service Account Token Volume Projection"
[13]: <https://docs.openshift.com/container-platform/4.10/networking/ingress-operator.html> "OpenShift Container Platform Ingress Operator"
[14]: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html "Amazon Resource Name"
[15]: https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-technical-overview.html "IAM roles for service accounts"
