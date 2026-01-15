# Create a verification contribution

Start in the exact environment you want to test. The verifier imports packages and, for supported probes, runs a minimal GPU kernel.

```bash
rigsolve detect
rigsolve verify \
  --package torch \
  --package flash-attn \
  --timeout 90 \
  --contribute \
  --contribution-file rigsolve-verification.json
```

The JSON file remains local. Before sharing it:

1. Read the entire `machine` object.
2. Remove the file instead of sharing it if it contains metadata you consider sensitive.
3. Confirm the result has the expected package version and tier.
4. Remember that torch and flash-attn have real GPU probes; most other built-in probes are import-only.
5. Attach the reviewed file and reproduction commands to a [verification report](https://github.com/satwiksps/rigsolve/issues/new?template=verification.yml).

Do not manually change a failed result to a success or increase its tier. Describe unexpected probe behavior in the issue; the raw failure is useful evidence.
