# Skill template

Copy to `records/` or let `record_skill` generate automatically.

## Frontmatter (general knowledge only)

```yaml
---
name: fix-crashloop-restart
version: 1.0
fingerprint: <auto>
tags: [k8s, CrashLoop]
symptom: CrashLoopBackOff
issues: [CrashLoop]
recommended_actions: [restart_pod]
risk_level: critical
verified: false
hit_count: 1
source_count: 1
created_at: <iso8601>
updated_at: <iso8601>
---
```

Do **not** put `cluster_id`, `namespace`, or `pod_name` in frontmatter.

## Body

```markdown
# Problem
<what went wrong>

# Resolution
1. <step>
2. <action>

# Evidence
Observed on:
- cluster: <cluster>
- namespace: <namespace>
- pod: <pod>
- severity: <severity>
- diagnosis_source: <source>
```
