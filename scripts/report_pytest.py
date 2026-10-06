"""Publish failed JUnit test details as GitHub Actions annotations."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def escape(value):
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(path):
    if not path.is_file():
        print("Pytest result file unavailable; inspect the preceding failed step.")
        return
    for case in ET.parse(path).getroot().iter("testcase"):
        for result in case:
            if result.tag not in {"failure", "error"}:
                continue
            title = escape(f"pytest: {case.get('classname')}.{case.get('name')}")
            title = title.replace(",", "%2C").replace(":", "%3A")
            message = escape(result.text or result.get("message", "Test failed"))
            print(f"::error title={title}::{message}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
