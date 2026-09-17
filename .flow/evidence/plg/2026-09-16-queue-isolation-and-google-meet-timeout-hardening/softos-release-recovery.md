# SoftOS release recovery (2026-09-17)

Cause: PR #306 merged to `main` without `release cut/promote/verify`.

Recovery:
- cut: `queue-isolation-meet-timeout-hardening-2026-09-17` @ backend `5fd29837`
- staging promote + Actions success: https://github.com/PLGEducation/plg-platform-backend/actions/runs/35252681291
- production promote + Actions success: https://github.com/PLGEducation/plg-platform-backend/actions/runs/35252851616
- SoftOS verify staging/production: passed
- feature status: released / next-step: release-complete
