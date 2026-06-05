---
name: fix-crashloop-restart
version: 1.0
fingerprint: 5305d707b43e48f6
tags: [k8s, CrashLoop]
symptom: CrashLoopBackOff
issues: [CrashLoop]
recommended_actions: [restart_pod]
risk_level: critical
verified: false
hit_count: 3
source_count: 3
created_at: 2026-06-05T03:09:55Z
updated_at: 2026-06-05T03:09:55Z
---

# Problem
Detected issue(s): CrashLoop.
Symptom: CrashLoopBackOff.

# Resolution
1. Review container logs and recent events
2. restart_pod (dry-run in W5)

# Evidence
Observed on:
- cluster: dev-cluster
- namespace: default
- pod: crash-pod
- severity: critical
- diagnosis_source: rules_v1
