# Errors and exit codes API

Expected failures inherit from `RigsolveError` and carry a stable `ExitCode`.

```{eval-rst}
.. autoclass:: rigsolve.errors.ExitCode
   :members:

.. autoclass:: rigsolve.errors.RigsolveError

.. autoclass:: rigsolve.errors.MatrixError

.. autoclass:: rigsolve.errors.MatrixValidationError

.. autoclass:: rigsolve.errors.DetectionError

.. autoclass:: rigsolve.errors.UnsatisfiableError

.. autoclass:: rigsolve.errors.BrokenEnvironmentError

.. autoclass:: rigsolve.errors.StaleMatrixError

.. autoclass:: rigsolve.errors.UserInputError
```

Library callers should catch the narrowest expected exception. The CLI converts these exceptions to their declared status codes and reserves status 70 for unexpected failures.
