# Phase 3A evidence boundaries

This directory contains local release verification and inspection of the known external repository only. No live Azure dispatch or Ubuntu 22.04 qualification has run.

`jbpa-release.yaml` records the archive verification on the development machine, not on a guest. `azure-provisioning.yaml` records the missing inputs and absence of provisioning. `source-inspection.json` records the inspected repository and its scope.

Preflight, artifact acquisition, installation/result consumption, health, runtime contract, guest logs and end-to-end timing evidence will be created from actual execution. They are deliberately absent rather than populated with invented guest observations. No Ubuntu 22.04 contract is created before a successful live capture.

See [the Phase 3A summary](../../../docs/phase-3a-summary.md).
