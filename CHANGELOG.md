# Changelog

## 0.1.0 (2026-10-22)


### Features

* **accounts:** add csrf and me endpoints ([6e79e86](https://github.com/januhrhammer/Home-Rank/commit/6e79e865d02001f9d9b130a24bf6cd3702652fc9))
* **accounts:** add custom user model ([b4c79ea](https://github.com/januhrhammer/Home-Rank/commit/b4c79eaba768e77bf8e2370ee2c6ba8dbcf5533f))
* **accounts:** add login and logout endpoints ([7668b91](https://github.com/januhrhammer/Home-Rank/commit/7668b9183fb76db61e4502b7a57454da88713a65))
* **accounts:** enable the django admin ([c5d79ce](https://github.com/januhrhammer/Home-Rank/commit/c5d79ce0e3674b54fa76a0d752e6d1b2587cccfb))
* **accounts:** hash passwords with argon2id and enforce strong ones ([50b4742](https://github.com/januhrhammer/Home-Rank/commit/50b47420eda1d838fb8424ab84f0480f14cfd0fc))
* **accounts:** rate-limit logins with django-axes ([ba2e37c](https://github.com/januhrhammer/Home-Rank/commit/ba2e37caa37a56cf47a951b79064348fc977a485))
* **api:** mount django-ninja api at /api/v1 ([4c5f9d1](https://github.com/januhrhammer/Home-Rank/commit/4c5f9d1ac5e522a487e21158068511013dfece53))
* **api:** return errors as rfc 9457 problem details ([f73259b](https://github.com/januhrhammer/Home-Rank/commit/f73259be76a40beae014adc97fe421d3a03d677e))
* **board:** add a chessboard component wrapping chessground ([cdfab08](https://github.com/januhrhammer/Home-Rank/commit/cdfab0857fef0dffaf356178fdf2457bda956aaf))
* **core:** add /healthz and /readyz health checks ([f7a0962](https://github.com/januhrhammer/Home-Rank/commit/f7a0962aaaa29ebc4a4f9a7a09c29931d3a79d37))
* **core:** add database timeout and log settings for production ([9dce98e](https://github.com/januhrhammer/Home-Rank/commit/9dce98eddf15a20b66be239545d0cbf54590f021))
* **core:** configure https and reverse proxies for self-hosters ([70a727d](https://github.com/januhrhammer/Home-Rank/commit/70a727d537ea4f5d6d156e95937c120f7395d0e8))
* **core:** log through structlog, as json in production ([1c84167](https://github.com/januhrhammer/Home-Rank/commit/1c8416747e90a9f0af2a6c2bddd731c3ef50888a))
* **core:** serve the built frontend from django in production ([c48bacd](https://github.com/januhrhammer/Home-Rank/commit/c48bacd6b5e51d4af1247e3996b4356e3f60d99b))
* **ui:** add a typed api client generated from the openapi schema ([ca27947](https://github.com/januhrhammer/Home-Rank/commit/ca2794787e65d27ad3ad40175fe6d8fc0ae07d53))
* **ui:** add routing, page layout and source code link ([1ef5aec](https://github.com/januhrhammer/Home-Rank/commit/1ef5aec42e8a483bea9e0c12cfb92d6146989eb9))
* **ui:** add the login page ([885c8ce](https://github.com/januhrhammer/Home-Rank/commit/885c8ce4bcea5bd8a19b75db09e1817b87b0a646))
* **ui:** fetch the logged-in user with tanstack query ([f1c1e51](https://github.com/januhrhammer/Home-Rank/commit/f1c1e51d9011f2989bd452f729fd9df6d702c5c8))
* **ui:** protect pages behind login and add logout ([db7ccbb](https://github.com/januhrhammer/Home-Rank/commit/db7ccbb4c6aaecec9cded9696d762edc98b4c03d))
* **ui:** style with css modules and shared design tokens ([eaf1813](https://github.com/januhrhammer/Home-Rank/commit/eaf18134eb5de0963dc01e94997dc51fbcd39354))
* **worker:** delete expired sessions daily in the background ([526a826](https://github.com/januhrhammer/Home-Rank/commit/526a826529976ffe5a7d684279de34f34c1d1d79))


### Bug Fixes

* **core:** read docker secrets and empty variables correctly ([1f25355](https://github.com/januhrhammer/Home-Rank/commit/1f25355e07db9723fe4c395248a0631810e30b65))
