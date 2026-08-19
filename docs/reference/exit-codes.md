# Exit codes

Use process status, not output text, for automation.

| Code | Name | Meaning |
|---:|---|---|
| 0 | `OK` | Request succeeded, solution exists, or no applicable known violation was found |
| 1 | `UNSATISFIABLE` | No compatible assignment exists in the active matrix domain |
| 2 | `ENVIRONMENT_BROKEN` | An installed environment or verification probe is known to be broken |
| 3 | `DETECTION_FAILED` | Required detection data could not be produced |
| 4 | `MATRIX_STALE` | Matrix health or age policy requires attention |
| 64 | `USAGE` | Invalid command syntax or user input |
| 70 | `INTERNAL` | Unexpected internal failure |
| 130 | shell convention | Interrupted by the user |

## Shell example

```bash
if rigsolve check; then
  echo "No applicable known incompatibility found"
else
  status=$?
  case "$status" in
    2) echo "Environment is known to be broken" ;;
    64) echo "Invalid rigsolve invocation" ;;
    *) echo "rigsolve failed with status $status" ;;
  esac
fi
```

Invalid argparse usage is normalized to status 64. It does not collide with the environment-broken status.
