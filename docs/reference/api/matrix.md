# Matrix API

The matrix API validates, indexes, queries, merges, serializes, and updates compatibility facts.

## Load and query

```{eval-rst}
.. autofunction:: rigsolve.matrix.load_bundled

.. autofunction:: rigsolve.matrix.load_matrix

.. autoclass:: rigsolve.matrix.MatrixStore

.. autoclass:: rigsolve.matrix.MatrixStats
```

`MatrixStore` is immutable. Query methods return tuples, and `data` exposes the validated frozen `MatrixData` value.

## Serialize and merge

```{eval-rst}
.. autofunction:: rigsolve.matrix.dump_matrix

.. autofunction:: rigsolve.matrix.save_matrix

.. autofunction:: rigsolve.matrix.merge_matrices

.. autofunction:: rigsolve.matrix.validate_matrix

.. autofunction:: rigsolve.matrix.matrix_from_mapping
```

## Updates

```{eval-rst}
.. autofunction:: rigsolve.matrix.fetch_update

.. autofunction:: rigsolve.matrix.load_with_cached_update

.. autoclass:: rigsolve.matrix.MatrixUpdateResult

.. autoclass:: rigsolve.matrix.MatrixUpdateError
```

## Provenance and evidence

```{eval-rst}
.. autoclass:: rigsolve.matrix.Source

.. autoclass:: rigsolve.matrix.VerificationTier

.. autoclass:: rigsolve.matrix.ProvenanceError
```

## Fact models

```{eval-rst}
.. autoclass:: rigsolve.matrix.MatrixMetadata

.. autoclass:: rigsolve.matrix.MatrixData

.. autoclass:: rigsolve.matrix.WheelFact

.. autoclass:: rigsolve.matrix.TorchBuildFact

.. autoclass:: rigsolve.matrix.TestedAgainstFact

.. autoclass:: rigsolve.matrix.DriverConstraintFact

.. autoclass:: rigsolve.matrix.CouplingFact

.. autoclass:: rigsolve.matrix.KnownBrokenFact

.. autoclass:: rigsolve.matrix.ArchitectureConstraintFact

.. autoclass:: rigsolve.matrix.SourceBuildFact
```

Each constructor performs field-level validation. `validate_matrix` adds cross-fact checks. See {doc}`../../matrix-schema` for the serialized TOML contract.
