---
name: php-core
description: Use when implementing or reviewing PHP code in this SoftOS workspace, especially Composer dependency, PHPUnit, runtime, or container changes.
---

# PHP Core

Resolve the repository app root before running PHP or Composer. Respect the PHP version and extensions declared by that repository; do not infer an upgrade from the workspace image.

Use the committed Composer lockfile and prefer `composer install` over `composer update`. Run repository commands through `flow repo exec` and keep generated dependencies out of version control.

For `plg-platform-backend`, the app root is `src/`. Use `composer --working-dir=src ...` from the repo root, and run PHPUnit with `src/vendor/bin/phpunit -c src/phpunit.xml`.

Do not alter migrations, production environment files, dependency versions, or deployment behavior unless the active spec targets them explicitly.
