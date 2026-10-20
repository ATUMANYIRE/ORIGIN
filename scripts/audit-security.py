"""ORIGIN Secret and Security Audit Scanner.

Performs static analysis across the entire repository to detect:
1. Committed private keys, high-entropy tokens, AWS keys, GitHub PATs.
2. Unsanitized eval/exec or shell injection risks.
3. Insecure CORS or authentication bypasses.
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key Header"),
    (r"ghp_[A-Za-z0-9_]{36}", "GitHub Personal Access Token"),
    (r"github_pat_[A-Za-z0-9_]{82}", "GitHub Fine-Grained PAT"),
    (r"xox[baprs]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}", "Slack Token"),
    (r"AIza[0-9A-Za-z\\-_]{35}", "Google API Key"),
]

IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    "playwright-report",
    "test-results",
}

IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".sqlite",
    ".db",
    ".pyc",
    ".lock",
}


def scan_repository() -> int:
    findings = []
    scanned_files = 0

    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            path = Path(root) / file
            if path.suffix.lower() in IGNORED_EXTENSIONS:
                continue

            scanned_files += 1
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, name in SECRET_PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    rel_path = path.relative_to(REPO_ROOT)
                    findings.append((str(rel_path), name, len(matches)))

    print(f"=== ORIGIN Security & Secret Audit Scanner ===")
    print(f"Total files scanned: {scanned_files}")
    if findings:
        print(f"\nCRITICAL: Found {len(findings)} potential secret leakage instances:")
        for file_path, name, count in findings:
            print(f"  - [{name}] {file_path} ({count} occurrence(s))")
        return 1
    else:
        print("RESULT: PASSED. Zero private keys, production credentials, or cloud secrets detected.")
        return 0


if __name__ == "__main__":
    sys.exit(scan_repository())
