# Apache, JVM and Tomcat visibility without added services or ports

Validated 12 October 2026 on JBLAB-PA-AUTOMATION, native PA 12.10.1.1 and its bundled Java 25 runtime. This is a version-scoped QA method, not general certification for every agent/runtime/container.

## Apache

The installed configuration already exposes `/server-status` with `Require local` on the existing listener **46908**. Use `http://127.0.0.1:46908/server-status?auto` through SSH. No listener, module, configuration directive or reload was added. The earlier gap resulted from not discovering this existing endpoint, rather than the absence of Apache status support.

The collector returns busy/idle workers, scoreboard and available cumulative accesses/bytes/uptime. Capture before/after for counter deltas; the status probe itself contributes a request. Do not equate configured MaxRequestWorkers with actual busy workers or assume Apache handles every operation/Axis request.

## Both JVMs and Tomcat

This runtime has no jcmd/jstat executables and no jdk.attach/compiler modules, but supports its built-in HotSpot local attach channel and instrumentation. The temporary `JBPAReadOnlyMetricsV1` helper reads:

- Actual heap used/committed/max and non-heap used.
- Live/daemon/peak threads and deadlocked-thread count, without thread dumps.
- Per-collector GC counts and elapsed collection-time counters; no forced collection.
- Existing Tomcat ThreadPool, GlobalRequestProcessor and Manager numeric MBean attributes across the registered local MBean servers.

The helper creates no remote/local JMX/RMI server, HTTP exporter, TCP/UDP socket, scheduler or background monitoring thread. It modifies no MBean attribute and requests no class redefinition/retransformation. It executes on demand and returns. The JVM's built-in attach mechanism may create its private UNIX-domain socket/Attach Listener thread; this is not an added network port or OS service. The helper class remains loaded until normal JVM shutdown, while staged files are removed after collection. Do not claim the class was unloaded or restart solely to remove it.

Attach is explicitly opt-in. `local-jvm-attach.py` validates the PA account, Java process, caught SIGQUIT handler, same PID namespace and private socket ownership/permissions, then drops to the JVM account. It sends one bounded load request, not arbitrary diagnostic commands. Fail closed on unsupported namespaces, disabled attachment/loading, stale markers or rejected helper execution. Do not change JVM security flags to force attachment.

Sources: [OpenJDK 25 Linux attach implementation](https://raw.githubusercontent.com/openjdk/jdk/jdk-25-ga/src/jdk.attach/linux/classes/sun/tools/attach/VirtualMachineImpl.java), [Java instrumentation specification](https://docs.oracle.com/en/java/javase/25/docs/api/java.instrument/java/lang/instrument/package-summary.html). No OpenJDK code is bundled in the helper.

## Build, integrity and staging

Source: `scripts/management/java/JBPAReadOnlyMetricsV1.java`; local protocol client: `scripts/management/local-jvm-attach.py`. The one-off compiler was Eclipse ECJ 4.38, downloaded from the official archive and SHA-512 verified against its published checksum list. It was run temporarily with the existing Java runtime, targeting Java 17 bytecode. No JDK/package was installed, and no third-party compiler executes inside the PA JVM.

Compiler source: `https://archive.eclipse.org/eclipse/downloads/drops4/R-4.38-202512010920/ecj-4.38.jar`; checksum list: `https://archive.eclipse.org/eclipse/downloads/drops4/R-4.38-202512010920/checksum/eclipse-4.38-SUMSSHA512`. Recorded evidence: `output/estate-health/noport-visibility-2026-10-12/compiler-provenance.json`.

The stage is a dedicated `/var/tmp/jbpa-noport-*` directory. The helper JAR has an Agent-Class manifest with class-redefinition/retransformation disabled, and its SHA-256 is checked before collection. Diagnostic output is restricted to numeric counters and bounded standard component labels; credentials, system properties, command lines, request payloads and thread stacks are not exported. Temporary compiler/source/class/JAR/client/output files are removed after the diagnostic window.

Management profile selects `apacheUrl`, `localJvmProbeJar`, `localJvmHelper` and `localJvmProbeSha256`. These are administrator-owned configuration, not arbitrary MCP tool arguments. A future release should build/pin the tiny helper artifact once, stage it under verified customer policy and clean up per target; current preparation is a controlled QA workflow, not an implemented customer deployment route.

## Collector and interpretation

`collect-estate-node.py` reads the helper before/after its host sample and projects qualified counters into the existing JVM/Tomcat metric family, retaining PID/start-time identity. Inspect each JVM separately; a single configured JAVA_OPTS value does not establish every JVM's effective heap. Tomcat metrics are expected only from JVMs hosting Tomcat; absence on the log-shipper JVM is not a Tomcat failure.

Use GC counter deltas over actual observation times; a reset is not negative GC activity. Collection time is not a precise stop-the-world pause histogram or process CPU. Tomcat processingTime/requestCount deltas provide a mean server processing time, not p95/p99. maxTime is a cumulative maximum and must not be claimed as a new slow request. HTTP errorCount does not encompass business failures returned in HTTP 200.

The health collector records TCP/UDP listening endpoints before/after. The initial two-JVM probe verified an unchanged listener set. Ports 8099/9404 were not enabled, no PA services were installed, and no service restart/configuration change was performed. Apache/JVM/Tomcat visibility can therefore close independently of native metrics-service enablement. Native metrics shipping remains a separate choice.

Health responses can still be partial because of cloud-roster reconciliation, unclassified Support Tools service output, history or unsupported sources. Closing these three gaps does not qualify peak sizing, fleet completeness or every runtime measurement.

## Repeatable preparation

An authorized private profile may select a pinned management-side `localJvmProbeArtifact` and SHA-256. The collector copies the helper JAR/client into a private per-target stage, verifies digests, sets controlled ownership, performs the check and removes the stage in finally. The qualified QA profile is `secrets/qa-health-profile.json` (ignored by Git). Automatic Apache discovery reads an already configured localhost status location; it never enables one. Collection transport supports bounded gzip/base64 so busy operation metadata cannot exceed the old 1 MiB SSH cap simply through repetition; decoded captures remain capped at 20 MiB.
