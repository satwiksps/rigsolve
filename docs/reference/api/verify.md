# Verification API

```{eval-rst}
.. autofunction:: rigsolve.verify.verify_packages

.. autoclass:: rigsolve.verify.SmokeResult

.. autoclass:: rigsolve.verify.VerificationTier
```

Verification runs child interpreters. A successful result describes only the recorded package, environment, and probe. It must not be generalized to untested artifacts or GPU architectures.
