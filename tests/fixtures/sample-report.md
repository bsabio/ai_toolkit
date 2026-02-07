# Sprint 12 Retrospective Report

**Team:** Platform Engineering  
**Sprint:** 12 (Jan 20 – Feb 2, 2026)  
**Author:** Sample Author  

## Summary

Sprint 12 delivered 3 of 5 planned features. Velocity was 34 story points against a target of 42. Two items were deferred due to dependency on the auth service migration.

## Completed

- [x] API rate limiting middleware (8 pts)
- [x] Dashboard metrics export CSV (5 pts)
- [x] Database connection pooling upgrade (13 pts)

## Deferred

- [ ] SSO integration for enterprise tier (8 pts) — blocked on auth service
- [ ] Webhook retry with exponential backoff (8 pts) — moved to Sprint 13

## Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Velocity | 42 pts | 34 pts | ⚠️ Below |
| Bug escape rate | <2% | 1.5% | ✅ Pass |
| PR review time | <4h | 3.2h | ✅ Pass |
| Deploy frequency | 3/week | 4/week | ✅ Pass |

## Retrospective Notes

### What went well
- Connection pooling upgrade was smooth — great job by the DBA team
- New PR template reduced review iterations

### What needs improvement
- Sprint planning did not account for auth service dependency
- Stand-ups are running too long (avg 22 min, target 15 min)

### Action Items
1. Add dependency check to sprint planning template
2. Timebox stand-ups to 15 minutes with hard cutoff
3. Schedule mid-sprint check-in for blocked items
