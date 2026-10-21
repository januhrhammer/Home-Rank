# 3. User accounts and passwords

Date: 2026-10-21

## Status

Accepted

## Context

Home-Rank is self-hosted for one person, a family or a club. An admin creates the accounts; there
is no public sign-up and the app sends no email. A password is the only login factor. If the
database ever leaks, for example through a backup, the stored password hashes must be expensive to
crack.

## Decision

- **Custom user model from the first migration.** `accounts.User` extends Django's `AbstractUser`
  without changes for now. Replacing the user model after the first migration is notoriously
  hard; adding fields to our own model is easy.
- **Log in with a username.** Email is optional and not unique. Nothing depends on it: there is
  no sign-up and no password-reset email.
- **Hash passwords with Argon2id**, using Django's `Argon2PasswordHasher` with its default
  parameters (100 MiB memory, 2 passes, 8 lanes). Django's default, PBKDF2, is expensive only in
  CPU time and needs almost no memory per guess, so attackers can run thousands of guesses in
  parallel on GPUs. Argon2id is memory-hard: every guess needs 100 MiB, which removes most of
  that advantage. It is the variant recommended by RFC 9106 and by OWASP. Django doesn't use it
  by default only because it needs the `argon2-cffi` library.
- **Password rules:** Django's four validators (minimum length, common passwords, entirely
  numeric, similarity to the username). The minimum length is 15 characters, as NIST SP
  800-63B-4 requires when a password is the only factor. No composition rules such as "must
  contain a digit", which NIST advises against. Long passphrases are the intended style.

## Consequences

- `argon2-cffi` is a runtime dependency. It ships prebuilt packages for amd64 and arm64.
- Checking a password briefly takes 100 MiB of RAM (about 20 ms on a desktop, longer on a
  Raspberry Pi). Login rate limiting is therefore required, so that a flood of login attempts
  cannot exhaust memory.
- Forgotten passwords are reset by an admin (Django admin or `manage.py changepassword`), not by
  email.
- Tests hash with fast MD5 for speed; one test checks that the real settings produce Argon2id
  hashes.
- If the hashing algorithm ever changes, Argon2 stays in `PASSWORD_HASHERS` behind the new one,
  so existing hashes keep working and are upgraded at each user's next login.
