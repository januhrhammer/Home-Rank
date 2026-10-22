# Security policy

## Reporting a vulnerability

Please report security problems **privately**, through GitHub's
[private vulnerability reporting](https://github.com/januhrhammer/Home-Rank/security/advisories/new),
not in a public issue.

Describe the problem, how to reproduce it, and what an attacker could do with it. You'll get an
answer within a week. Once a fix is released, the advisory is published, crediting you if you
like.

## Supported versions

Home-Rank is in early development (0.x). Security fixes go into the next release only, so please
check that a problem still exists in the latest release before reporting it.

## Scope

In scope: the Home-Rank code in this repository and the Docker images published from it.

Out of scope: problems that need an attacker to already control the server or its configuration,
and setups that leave out the protections the [self-hosting guide](docs/self-hosting.md)
describes, for example `TRUST_PROXY_HEADERS=true` without a reverse proxy in front.
