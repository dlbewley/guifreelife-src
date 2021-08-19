---
title: "Protect Gitignored but Tracked Files"
banner: /img/banners/banner-32.jpg
date: 2021-08-18
layout: post
tags:
  - git
---

Sometimes you want to put files in git that you really shouldn't be putting in git.

<!--more-->

Files like aws credentials or an htpasswd file.

``` bash
#.env.aws
aws_access_key_id=EXAMPLE
aws_secret_access_key=EXAMPLE
```

Why? Maybe you want to make it obvious what secrets need to be provided with your code and to illustrate how they should be formatted. So maybe you put them in a directory like `secrets/` with example values in them. Then you commit those examples. 

OK, so now how to make sure you don't accidentally update the values with real secrets and publish them to github?

I know! Put them in `.gitignore`! Oh wait. That doesn't actually work. Once the file is tracked, it is tracked.

As a workaround, you can use this pre-commit git hook.

{{< gist dlbewley 90fa9c31d5847633c2186eb2b35715a1 >}}

Tada! :tada: That'll do.

> :warning: **Warning** Git hooks are locally significant, so I can't vouch for the safety of your clones. YMMV
