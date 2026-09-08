---
name: laravel-8
description: Use for work in the existing PLG Laravel 8 application; preserves its framework version, app layout, test setup, and migration safety boundaries.
---

# Laravel 8

Treat `plg-platform-backend/src` as the Laravel application root. Preserve compatibility with `laravel/framework` 8.x and PHP 8.2 unless an approved modernization spec says otherwise.

Use Artisan and PHPUnit from the application root. Feature tests use MySQL according to `src/phpunit.xml`; do not silently replace them with SQLite when behavior depends on MySQL.

Keep schema hardening candidate-gated. Never run destructive migrations, seeders, queue workers, or production commands as an incidental validation step.

Use the public `/api/v2/auto/health` endpoint for local liveness. Keep secrets in ignored environment files or SoftOS secret providers, not tracked source.
