# Changelog

## [0.8.0](https://github.com/januhrhammer/Home-Rank/compare/v0.7.0...v0.8.0) (2026-10-23)


### Features

* **ui:** add a favicon ([#69](https://github.com/januhrhammer/Home-Rank/issues/69)) ([4cb1a58](https://github.com/januhrhammer/Home-Rank/commit/4cb1a58cc1cbcdb9ef32af36ea77fb78ed2e5fb5))
* **ui:** fit the game list on phones ([#73](https://github.com/januhrhammer/Home-Rank/issues/73)) ([1e8876c](https://github.com/januhrhammer/Home-Rank/commit/1e8876cc1d2cc9fec704b374c2f378d7a0bd5d20))
* **ui:** fold the header into a menu on phones ([#72](https://github.com/januhrhammer/Home-Rank/issues/72)) ([1d34c6a](https://github.com/januhrhammer/Home-Rank/commit/1d34c6acbf5b60fa4a6443f42a11656060bbfdab))
* **ui:** type moves into the repertoire editor ([#77](https://github.com/januhrhammer/Home-Rank/issues/77)) ([7b2196b](https://github.com/januhrhammer/Home-Rank/commit/7b2196b1d4392ea9bbe62a27d4f098db596d6b44))


### Bug Fixes

* **auth:** keep a login that overtakes a check of who is logged in ([#83](https://github.com/januhrhammer/Home-Rank/issues/83)) ([7f16d37](https://github.com/januhrhammer/Home-Rank/commit/7f16d37762a5d6af5ddf4fad9944796fe4122caa))
* **release:** attach .env.example as env.example ([#70](https://github.com/januhrhammer/Home-Rank/issues/70)) ([3b348bf](https://github.com/januhrhammer/Home-Rank/commit/3b348bf621bbe063defe47bb6e0d80d554238e35))
* **ui:** keep the board's letters and the database table on phones ([#74](https://github.com/januhrhammer/Home-Rank/issues/74)) ([7d9dfe7](https://github.com/januhrhammer/Home-Rank/commit/7d9dfe7b76236f2d7ddb1fa18b6ea05e770fcc7c))
* **ui:** show a puzzle's game date as the game list does ([#81](https://github.com/januhrhammer/Home-Rank/issues/81)) ([df495f6](https://github.com/januhrhammer/Home-Rank/commit/df495f6614990a388bb14e75df9cf2040f8a1c0c))
* **ui:** show keyboard focus in dropdowns and calm the board ([#76](https://github.com/januhrhammer/Home-Rank/issues/76)) ([58dc7e8](https://github.com/januhrhammer/Home-Rank/commit/58dc7e836465a1317c5365e4d0232198331ab3b7))


### Performance Improvements

* **ui:** download each page when it is first shown ([#79](https://github.com/januhrhammer/Home-Rank/issues/79)) ([e6c6f39](https://github.com/januhrhammer/Home-Rank/commit/e6c6f3944a1ecfe5cc84f4ddd8b75f37b19cb366))

## [0.7.0](https://github.com/januhrhammer/Home-Rank/compare/v0.6.0...v0.7.0) (2026-10-23)


### Features

* **repertoire:** build repertoires move by move or from PGN ([#63](https://github.com/januhrhammer/Home-Rank/issues/63)) ([3f9250c](https://github.com/januhrhammer/Home-Rank/commit/3f9250ce61ad5ddd18429a065af343920da7a6eb))
* **repertoire:** seed from games, gap report, drills and the API ([#64](https://github.com/januhrhammer/Home-Rank/issues/64)) ([3dabb60](https://github.com/januhrhammer/Home-Rank/commit/3dabb6051ff4505524e4a708d268f6d34bb398db))
* **repertoire:** store repertoires as moves keyed by position ([#61](https://github.com/januhrhammer/Home-Rank/issues/61)) ([0be5a77](https://github.com/januhrhammer/Home-Rank/commit/0be5a7771e2022d178b146285f51bc2de0260370))
* **ui:** build repertoires on the board ([#65](https://github.com/januhrhammer/Home-Rank/issues/65)) ([1e96594](https://github.com/januhrhammer/Home-Rank/commit/1e96594cb962e809e5c8bc3270f632a9ca8977ae))
* **ui:** drill repertoires and see where my games left them ([#66](https://github.com/januhrhammer/Home-Rank/issues/66)) ([80c205d](https://github.com/januhrhammer/Home-Rank/commit/80c205d6e4a4e2e7d30f0bf88952ec11db4ec6f6))

## [0.6.0](https://github.com/januhrhammer/Home-Rank/compare/v0.5.0...v0.6.0) (2026-10-23)


### Features

* **api:** browse reference databases and explore positions ([#58](https://github.com/januhrhammer/Home-Rank/issues/58)) ([169e928](https://github.com/januhrhammer/Home-Rank/commit/169e928617cf07a15d5931bfff106434094ac9c9))
* **chesslib:** stream compressed PGN and pack games for reference databases ([#53](https://github.com/januhrhammer/Home-Rank/issues/53)) ([e60fdee](https://github.com/januhrhammer/Home-Rank/commit/e60fdeeaae2c2335f0696227e065e26e0446c895))
* **explorer:** search positions and explore moves in my games and reference databases ([#57](https://github.com/januhrhammer/Home-Rank/issues/57)) ([2304a5f](https://github.com/januhrhammer/Home-Rank/commit/2304a5f501b4a2ef6b5254eea0536a32136d9c60))
* **reference:** add reference databases with partitioned, compact storage ([#55](https://github.com/januhrhammer/Home-Rank/issues/55)) ([8328b3f](https://github.com/januhrhammer/Home-Rank/commit/8328b3fcb4833c5e36d4db4f7a28172503127066))
* **reference:** import large PGN files with a pool of processes ([#56](https://github.com/januhrhammer/Home-Rank/issues/56)) ([f0b2c51](https://github.com/januhrhammer/Home-Rank/commit/f0b2c518ab23a7435b53e87d528f4bb679d8910e))
* **ui:** explore openings, find positions and browse reference databases ([#59](https://github.com/januhrhammer/Home-Rank/issues/59)) ([cd148e8](https://github.com/januhrhammer/Home-Rank/commit/cd148e87285bf66f99590f24da213e61514b1287))


### Performance Improvements

* **explorer:** meet the 200 ms target with 100,000 personal games ([#60](https://github.com/januhrhammer/Home-Rank/issues/60)) ([7f9d655](https://github.com/januhrhammer/Home-Rank/commit/7f9d65563e7277e99cb0eaf105d18a76fb2583ad))

## [0.5.0](https://github.com/januhrhammer/Home-Rank/compare/v0.4.0...v0.5.0) (2026-10-23)


### Features

* **api:** train puzzles: next due, reviews, list and statistics ([#50](https://github.com/januhrhammer/Home-Rank/issues/50)) ([f0da872](https://github.com/januhrhammer/Home-Rank/commit/f0da872e0f1339818a7df6df7bdb5e32cbafee67))
* **engine:** find puzzles in analysed games ([#46](https://github.com/januhrhammer/Home-Rank/issues/46)) ([89e308b](https://github.com/januhrhammer/Home-Rank/commit/89e308b804758a289414fcd859390f0bc2964a3e))
* **engine:** tag mating puzzles "mate" as well as "mateInN" ([#51](https://github.com/januhrhammer/Home-Rank/issues/51)) ([fe0fd2b](https://github.com/januhrhammer/Home-Rank/commit/fe0fd2b4157513d6c7c5cd2ffc61352b1936567b))
* **training:** add puzzles and spaced-repetition cards ([#48](https://github.com/januhrhammer/Home-Rank/issues/48)) ([6e6da8d](https://github.com/januhrhammer/Home-Rank/commit/6e6da8d5c8904b33f1b0ab62591cf11ddda0b146))
* **training:** find puzzles in analysed games and schedule them with FSRS ([#49](https://github.com/januhrhammer/Home-Rank/issues/49)) ([f1d5ac0](https://github.com/januhrhammer/Home-Rank/commit/f1d5ac0ce3df2c3d66bed59e87b7c617a37e6b3f))

## [0.4.0](https://github.com/januhrhammer/Home-Rank/compare/v0.3.0...v0.4.0) (2026-10-23)


### Features

* **analysis:** add the analysis app's data ([#40](https://github.com/januhrhammer/Home-Rank/issues/40)) ([b715766](https://github.com/januhrhammer/Home-Rank/commit/b7157661c09f0ea64743fe673c96ee866a8f95d6))
* **analysis:** analyse games in the background with Stockfish ([#41](https://github.com/januhrhammer/Home-Rank/issues/41)) ([42f50e9](https://github.com/januhrhammer/Home-Rank/commit/42f50e9fd306231950556f7d9a73aa0da22096e8))
* **analysis:** analyse new games automatically, optionally only at night ([#42](https://github.com/januhrhammer/Home-Rank/issues/42)) ([024b368](https://github.com/januhrhammer/Home-Rank/commit/024b368de03a08c036f85ae8ca9e2e8fbc6bc0f5))
* **api:** start analyses and read a game's analysis ([#43](https://github.com/januhrhammer/Home-Rank/issues/43)) ([d3f500d](https://github.com/januhrhammer/Home-Rank/commit/d3f500d7759c8d62edd057fb5c8974b252371730))
* **docker:** bundle Stockfish in the image, CI and dev setup ([#37](https://github.com/januhrhammer/Home-Rank/issues/37)) ([4ef9686](https://github.com/januhrhammer/Home-Rank/commit/4ef9686cd2a6021dfa32442df10d75fdda4b8607))
* **engine:** analyse games and score moves like Lichess ([#39](https://github.com/januhrhammer/Home-Rank/issues/39)) ([e5e7984](https://github.com/januhrhammer/Home-Rank/commit/e5e798483c0b8ef93a4b86994f8b0344d66b9800))
* **ui:** show Stockfish's analysis in the game viewer ([#44](https://github.com/januhrhammer/Home-Rank/issues/44)) ([5e0e131](https://github.com/januhrhammer/Home-Rank/commit/5e0e1318ba3f131b20548d5d1a471d697c3b1e30))

## [0.3.0](https://github.com/januhrhammer/Home-Rank/compare/v0.2.0...v0.3.0) (2026-10-23)


### Features

* **api:** link Lichess and Chess.com accounts and sync them ([#33](https://github.com/januhrhammer/Home-Rank/issues/33)) ([e268fbf](https://github.com/januhrhammer/Home-Rank/commit/e268fbf4fd0ca4e2cdaf82eb50d97f93fb012634))
* **sync:** add linked accounts and sync runs ([#28](https://github.com/januhrhammer/Home-Rank/issues/28)) ([267095e](https://github.com/januhrhammer/Home-Rank/commit/267095eb6aa82c9bdc59ea5b4e4247d2aea2406b))
* **sync:** fetch games from Lichess and Chess.com ([#30](https://github.com/januhrhammer/Home-Rank/issues/30)) ([83023ca](https://github.com/januhrhammer/Home-Rank/commit/83023cab3c3f78792f4a2ae9df9f1d1c3d161a4a))
* **sync:** link accounts and sync their games in the background ([#32](https://github.com/januhrhammer/Home-Rank/issues/32)) ([1f605ad](https://github.com/januhrhammer/Home-Rank/commit/1f605ad04c69e1465804e58bc67ac4e55a4e4f8d))
* **sync:** sync linked accounts on a schedule ([#34](https://github.com/januhrhammer/Home-Rank/issues/34)) ([9c0dd8a](https://github.com/januhrhammer/Home-Rank/commit/9c0dd8a55e913e8aea821009bdee35e59c8fd234))
* **ui:** link Lichess and Chess.com accounts on the import page ([#35](https://github.com/januhrhammer/Home-Rank/issues/35)) ([da529ac](https://github.com/januhrhammer/Home-Rank/commit/da529ac985e326c5042002cd4ead18ce5707264d))

## [0.2.0](https://github.com/januhrhammer/Home-Rank/compare/v0.1.0...v0.2.0) (2026-10-22)


### Features

* **chesslib:** extract game data, fingerprints and positions ([#10](https://github.com/januhrhammer/Home-Rank/issues/10)) ([7661316](https://github.com/januhrhammer/Home-Rank/commit/7661316c3dd90895a0478a43fa63e2303c0508cd))
* **chesslib:** read pgn files one game at a time ([#8](https://github.com/januhrhammer/Home-Rank/issues/8)) ([2a7c9df](https://github.com/januhrhammer/Home-Rank/commit/2a7c9df7b034234e53a7be674beb81bcb8c9c9b9))
* **games:** add the game database models ([#11](https://github.com/januhrhammer/Home-Rank/issues/11)) ([d1d8bbd](https://github.com/januhrhammer/Home-Rank/commit/d1d8bbd6ab663e7b1e972d2738a7f44be95afa2f))
* **games:** import pgn files in a background job ([#12](https://github.com/januhrhammer/Home-Rank/issues/12)) ([34f4c04](https://github.com/januhrhammer/Home-Rank/commit/34f4c04a67cc6b6a1ec411819859c076060dcb42))
* **games:** list games with filters and sorting ([#14](https://github.com/januhrhammer/Home-Rank/issues/14)) ([ecee863](https://github.com/januhrhammer/Home-Rank/commit/ecee8639f4c7986ddb181febd5a94afc5116a240))
* **games:** manage collections and tags ([#17](https://github.com/januhrhammer/Home-Rank/issues/17)) ([e963283](https://github.com/januhrhammer/Home-Rank/commit/e9632836cac596297e65a4fc3837e69bf1bbba0d))
* **games:** show a game and export pgn ([#16](https://github.com/januhrhammer/Home-Rank/issues/16)) ([0765edd](https://github.com/januhrhammer/Home-Rank/commit/0765eddc94abe42ad964c55ff2235df5533b516a))
* **games:** upload pgn files through the api ([#13](https://github.com/januhrhammer/Home-Rank/issues/13)) ([9bf897d](https://github.com/januhrhammer/Home-Rank/commit/9bf897ddaf48818535e3f3c2ed775a2e29a55e79))
* let users set their player names, updating all their games ([#27](https://github.com/januhrhammer/Home-Rank/issues/27)) ([f61cb82](https://github.com/januhrhammer/Home-Rank/commit/f61cb827d1fd48b9e5aa0db752405566b44bb4f1))
* **ui:** act on several games at once ([#23](https://github.com/januhrhammer/Home-Rank/issues/23)) ([1081134](https://github.com/januhrhammer/Home-Rank/commit/10811344aa977c5d867d36abb98ec6a8909f256a))
* **ui:** add a page for collections and tags ([#22](https://github.com/januhrhammer/Home-Rank/issues/22)) ([a892e7c](https://github.com/januhrhammer/Home-Rank/commit/a892e7cece16c7d7b1215545eee997a126d6ef5e))
* **ui:** add the game list ([#19](https://github.com/januhrhammer/Home-Rank/issues/19)) ([ec9b22c](https://github.com/januhrhammer/Home-Rank/commit/ec9b22cd47f41941196c87828bf9a82a9433fd6c))
* **ui:** add the game viewer ([#20](https://github.com/januhrhammer/Home-Rank/issues/20)) ([a617b24](https://github.com/januhrhammer/Home-Rank/commit/a617b245017e8f1851b8ed69fee95546fc66fc4e))
* **ui:** add the import page ([#18](https://github.com/januhrhammer/Home-Rank/issues/18)) ([d4bef3d](https://github.com/januhrhammer/Home-Rank/commit/d4bef3dc957cb314c0506a9cb5f11265c8106942))
* **ui:** give the app the look of a chess book ([#25](https://github.com/januhrhammer/Home-Rank/issues/25)) ([3d8d92a](https://github.com/januhrhammer/Home-Rank/commit/3d8d92a509a91ae476c38f2df66224e73f91fd42))
* **ui:** tag games and add them to collections ([#21](https://github.com/januhrhammer/Home-Rank/issues/21)) ([fb80346](https://github.com/januhrhammer/Home-Rank/commit/fb803466a803e4d4598c560497dd6cfe44512bd5))
* **ui:** typeset the move list like a chess book, with figurines ([#26](https://github.com/januhrhammer/Home-Rank/issues/26)) ([0d525bd](https://github.com/januhrhammer/Home-Rank/commit/0d525bdadbc08e426b8783b16ec7d131cba5daac))

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
