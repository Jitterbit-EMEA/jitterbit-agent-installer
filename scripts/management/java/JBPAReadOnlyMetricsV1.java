import java.lang.instrument.Instrumentation;
import java.lang.management.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.management.*;

/** Bounded local attach snapshot. No transformations, GC, thread dumps, server or remote JMX. */
public final class JBPAReadOnlyMetricsV1 {
    private static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"")
            .replace("\n", "\\n").replace("\r", "\\r") + "\"";
    }
    public static void agentmain(String output, Instrumentation unused) throws Exception {
        Path path = Paths.get(output).toAbsolutePath().normalize();
        if (!path.toString().startsWith("/var/tmp/jbpa-noport-") ||
            !path.getFileName().toString().matches("metrics-[0-9]+-[a-f0-9]+\\.json"))
            throw new IllegalArgumentException("Invalid diagnostic output path");
        MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
        ThreadMXBean threads = ManagementFactory.getThreadMXBean();
        MemoryUsage heap = memory.getHeapMemoryUsage();
        MemoryUsage nonheap = memory.getNonHeapMemoryUsage();
        long[] deadlocks = threads.findDeadlockedThreads();
        StringBuilder b = new StringBuilder();
        b.append("{\"pid\":").append(ProcessHandle.current().pid());
        b.append(",\"uptimeMs\":").append(ManagementFactory.getRuntimeMXBean().getUptime());
        b.append(",\"heapUsedBytes\":").append(heap.getUsed());
        b.append(",\"heapCommittedBytes\":").append(heap.getCommitted());
        b.append(",\"heapMaxBytes\":").append(heap.getMax());
        b.append(",\"nonheapUsedBytes\":").append(nonheap.getUsed());
        b.append(",\"liveThreads\":").append(threads.getThreadCount());
        b.append(",\"daemonThreads\":").append(threads.getDaemonThreadCount());
        b.append(",\"peakThreads\":").append(threads.getPeakThreadCount());
        b.append(",\"deadlockedThreads\":").append(deadlocks == null ? 0 : deadlocks.length);
        b.append(",\"gc\":[");
        boolean first = true;
        for (GarbageCollectorMXBean gc : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (!first) b.append(','); first = false;
            b.append("{\"name\":").append(quote(gc.getName()));
            b.append(",\"count\":").append(gc.getCollectionCount());
            b.append(",\"timeMs\":").append(gc.getCollectionTime()).append('}');
        }
        b.append("],\"tomcat\":["); first = true;
        List<MBeanServer> servers = MBeanServerFactory.findMBeanServer(null);
        String[] types = {"ThreadPool", "GlobalRequestProcessor", "Manager"};
        String[][] attrs = {
            {"currentThreadCount", "currentThreadsBusy", "maxThreads", "connectionCount", "maxConnections", "keepAliveCount"},
            {"requestCount", "errorCount", "bytesReceived", "bytesSent", "processingTime", "maxTime"},
            {"activeSessions", "sessionCounter", "expiredSessions", "rejectedSessions", "maxActive"}
        };
        int records = 0;
        for (int si = 0; si < servers.size(); si++) {
            MBeanServer server = servers.get(si);
            for (int ti = 0; ti < types.length; ti++) {
                Set<ObjectName> names = new TreeSet<>(server.queryNames(new ObjectName("*:type=" + types[ti] + ",*"), null));
                for (ObjectName name : names) {
                    if (++records > 100) break;
                    if (!first) b.append(','); first = false;
                    String connector = name.getKeyProperty("name");
                    b.append("{\"type\":").append(quote(types[ti]));
                    b.append(",\"serverIndex\":").append(si);
                    b.append(",\"connector\":").append(quote(connector == null ? "" : connector));
                    b.append(",\"attributes\":{"); boolean afirst = true;
                    for (String attr : attrs[ti]) {
                        try {
                            Object value = server.getAttribute(name, attr);
                            if (!(value instanceof Number)) continue;
                            if (!afirst) b.append(','); afirst = false;
                            b.append(quote(attr)).append(':').append(((Number)value).longValue());
                        } catch (Exception ignored) { }
                    }
                    b.append("}}");
                }
            }
        }
        b.append("],\"tomcatTruncated\":").append(records > 100).append('}');
        byte[] bytes = b.toString().getBytes(StandardCharsets.UTF_8);
        if (bytes.length > 65536) throw new IllegalStateException("Diagnostic output cap");
        Files.write(path, bytes, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }
}
