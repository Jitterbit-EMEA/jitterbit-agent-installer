# PA 12.10.1.1 artifact intake

Observed 2026-09-23 from the user-supplied vendor URL already recorded in `config/versions.yaml`.

| Check | Observation |
| --- | --- |
| Vendor response | HTTP 200, `application/octet-stream` |
| Content length | 660,897,206 bytes |
| Vendor `x-amz-meta-checksum-sha256` header | `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` |
| Locally downloaded file SHA-256 | `604bec9889c49167328b93d032bb9d8580f758eb70c3d1dd42dfda23db974ee8` |
| Debian Package | `jitterbit-agent` |
| Debian Version | `12.10.1.1` |
| Debian Architecture | `amd64` |
| Debian Depends | `odbcinst, unixodbc` |
| Maintainer scripts present | `preinst`, `postinst`, `prerm`, `postrm` |
| `preinst` silent branch | `silent_install` skips the system-requirements prompt; fresh-install behavior has not been executed |

The file was downloaded to private temporary storage and inspected without installation. The header digest and local digest match. This is vendor-channel evidence and a concrete value for review, but the catalogue remains `approval: pending` with `sha256: null` until the independent trust/approval decision is recorded. A transient later HEAD request failed DNS resolution; it does not change the completed HTTP 200 download and digest match.
