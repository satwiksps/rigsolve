# Inspect and update compatibility data

rigsolve ships a bundled TOML matrix for offline resolution. A validated cached update may be merged over it.

## Show coverage statistics

```console
$ rigsolve matrix stats
$ rigsolve matrix stats --json
```

Statistics include matrix version, fact-family counts, evidence levels, packages, sources, and harvest dates.

## Inspect facts

```console
$ rigsolve matrix show
$ rigsolve matrix show --package flash-attn
$ rigsolve matrix show --package torch --json
```

Human output includes the fact family, package, version, evidence level, and citation. JSON includes full serialized facts and the matrix digest.

## Fetch a validated update

```console
$ rigsolve matrix update
```

Update behavior:

1. fetch the configured HTTPS URL with conditional request metadata;
2. parse the complete TOML payload;
3. validate all fields, provenance, tiers, and cross-fact invariants;
4. merge with bundled data unless `--no-merge` is used;
5. write the cache through atomic replacement.

Normal `detect`, `solve`, `check`, and `why` commands do not fetch updates. They can use an already validated cache.

Write the result to an additional path:

```console
$ rigsolve matrix update --destination matrix.toml
```

Fetch an explicit source without merging:

```console
$ rigsolve matrix update \
    --url https://example.org/rigsolve/matrix.toml \
    --destination exact-remote.toml \
    --no-merge
```

## Use a local matrix

```console
$ rigsolve --matrix matrix.toml matrix stats
$ rigsolve --matrix matrix.toml solve --want torch
```

The global option appears before the subcommand. Invalid data fails before the requested operation runs.

## Validate and merge a contribution

```console
$ rigsolve matrix add contribution.toml --destination merged.toml
```

This validates the contribution, merges it deterministically with the active matrix, validates the result, and writes a new file. It does not modify the bundled package data.

## Matrix identity

Two identifiers serve different purposes:

- `matrix_version` is a human-readable data release label;
- `digest` is SHA-256 over deterministic serialized matrix data.

Plans record both. The digest detects any change even when a version label has been reused during development.

For the schema and fact-family contract, see {doc}`../matrix-schema`. For evidence interpretation, see {doc}`../trust-model`.
