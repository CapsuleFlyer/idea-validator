# 0002. One container per module, and only M5 may reach the internet
Status: Draft
Context: The brief requires one container per module, 6+ images, and a controlled exit to the internet.
Options: (1) one monolith image, (2) one image per module, no network rules, (3) one image per module plus default-deny NetworkPolicy with an M5 exception.
Decision: Option 3. Each module has its own Dockerfile (multi-stage, non-root, tagged by commit SHA); `k8s/networkpolicy.yaml` denies all egress except DNS, intra-namespace traffic, and internet for `app=tools`.
Why: Limits damage from injected instructions and SSRF; the policy is testable (blocked from a non-M5 pod, allowed from M5).
Cost: More YAML and a CNI that enforces NetworkPolicy (Calico) instead of default kind.
AI use: Drafted by AI. TODO: check and add our measurements.
