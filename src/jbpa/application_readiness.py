"""Read-only checks of vendor-expanded Axis and its local conversion service."""

import stat
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApplicationReadinessProbe:
    def __init__(self, root="/opt/jitterbit/tomcat", opener=None):
        self.root = Path(root).resolve()
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def __call__(self):
        result = {"status": "NOT_READY", "readOnly": True}
        try:
            war = self.root / "webapps/axis.war"
            app = self.root / "webapps/axis"
            if war.is_symlink() or app.is_symlink():
                raise ValueError("unsafe path")
            with zipfile.ZipFile(war) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                if (
                    not entries
                    or len(entries) > 10000
                    or sum(entry.file_size for entry in entries) > 1024**3
                    or len({entry.filename for entry in entries}) != len(entries)
                ):
                    raise ValueError("archive bounds")
                missing = mismatched = 0
                for entry in entries:
                    relative = Path(entry.filename)
                    if (
                        relative.is_absolute()
                        or ".." in relative.parts
                        or stat.S_ISLNK(entry.external_attr >> 16)
                    ):
                        raise ValueError("unsafe entry")
                    target = app / relative
                    if any(path.is_symlink() for path in [target, *target.parents]):
                        raise ValueError("unsafe expansion")
                    if not target.is_file():
                        missing += 1
                        continue
                    if target.stat().st_size != entry.file_size:
                        mismatched += 1
                        continue
                    crc = 0
                    with target.open("rb") as handle:
                        for block in iter(lambda: handle.read(1048576), b""):
                            crc = zlib.crc32(block, crc)
                    mismatched += crc != entry.CRC
                result.update(
                    expectedFiles=len(entries), missingFiles=missing, contentMismatches=mismatched
                )
                if missing or mismatched:
                    result["reason"] = "AXIS_EXPANSION_INCOMPLETE"
                    return result
            tree = ET.parse(self.root / "conf/server.xml")
            ports = [
                int(node.get("port"))
                for node in tree.iter("Connector")
                if "HTTP" in node.get("protocol", "HTTP")
                and node.get("SSLEnabled", "false").lower() != "true"
                and node.get("port", "").isdigit()
                and 0 < int(node.get("port")) < 65536
            ]
            if len(set(ports)) != 1:
                result["reason"] = "HTTP_CONNECTOR_UNQUALIFIED"
                return result
            url = f"http://127.0.0.1:{ports[0]}/axis/soap-services/JsonEngine?wsdl"
            with self.opener.open(url, timeout=5) as response:
                body = response.read(262145)
                result["httpStatus"] = response.status
                if len(body) > 262144 or response.status != 200:
                    result["reason"] = "AXIS_WSDL_UNAVAILABLE"
                    return result
                wsdl = ET.fromstring(body)
                operations = [
                    node.get("name") for node in wsdl.iter() if node.tag.endswith("}operation")
                ]
                if not wsdl.tag.endswith("}definitions") or "xmlToJson" not in operations:
                    result["reason"] = "AXIS_CONVERSION_SERVICE_UNCONFIRMED"
                    return result
            result.update(status="READY", reason=None, conversionServicePublished=True)
        except urllib.error.HTTPError as exc:
            result.update(reason="AXIS_HTTP_ERROR", httpStatus=exc.code)
        except (
            OSError,
            ValueError,
            zipfile.BadZipFile,
            ET.ParseError,
            urllib.error.URLError,
            TimeoutError,
        ):
            result["reason"] = "AXIS_EVIDENCE_UNAVAILABLE"
        return result
