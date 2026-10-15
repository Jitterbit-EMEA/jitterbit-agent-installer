"""Explicit host/version QA exceptions; never production resource approval."""


def cpu_exception(config, host, logical, package_version, controlled_test):
    if (
        not controlled_test
        or host.get("os") != "ubuntu"
        or host.get("version") != "24.04"
        or host.get("cpuCount") != 2
    ):
        return False
    if logical == "12.10":
        return True  # Retain the existing scoped controlled-QA compatibility rule.
    scope = config.get("qa_policy", {}).get("scoped_cpu_exception", {})
    return bool(
        (logical, package_version) in {("12.9", "12.9.2.2"), ("12.11", "12.11.3.2")}
        and (logical != "12.11" or host.get("hostname") == "JBLAB-PA-AUTOMATION")
        and host.get("architecture") == "x86_64"
        and scope.get("hostname") == host.get("hostname")
        and scope.get("logical_version") == logical
        and scope.get("package_version") == package_version
        and scope.get("cpu_count") == 2
        and scope.get("authorization") == "EXPLICIT_USER_APPROVAL"
    )
