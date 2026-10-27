# Installation

Install only the authored validation distribution from the explicitly approved offline wheelhouse. The wheel contains a single harmless Python module plus standard wheel metadata. Its source and hash are shown before approval. No build backend, dependency index, paid service is used; no host package installation is used. The harness will also verify source/wheel tampering is rejected before Docker access, using separate disposable copies with the unchanged original approval.

```sh
python -m pip install doctor-validation-fixture==0.0.0
```

# Run the installed module check

```sh
python check_installed.py
```
