# Security

Do not open a public issue for a suspected vulnerability.

Use [GitHub private vulnerability reporting](https://github.com/satwiksps/rigsolve/security/advisories/new). If that channel is unavailable, follow the private fallback in the repository [security policy](https://github.com/satwiksps/rigsolve/blob/main/SECURITY.md).

Include:

- the affected rigsolve version;
- the operating system and Python version;
- a minimal reproduction;
- expected and actual behavior;
- impact and known workarounds;
- whether the report can be disclosed after a fix.

## Relevant trust boundaries

- Detection parses output from local system commands and bounded local files.
- Matrix updates accept remote data only after full schema validation and use atomic replacement.
- Plan rendering never installs packages.
- `solve --execute` invokes pip only after explicit user opt-in.
- Artifact URLs and package indexes in executable facts require HTTPS.
- Verification runs untrusted native imports in child processes, but this is crash isolation rather than a security sandbox.

Review generated plans as you would review a lockfile or installation script. Matrix provenance explains where a compatibility claim came from; it does not make an upstream artifact safe.
