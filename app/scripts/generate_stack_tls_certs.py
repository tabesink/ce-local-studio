#!/usr/bin/env python3
"""Generate local self-signed TLS material for compose.stack.tls.yml (P12-05).

Writes cert.pem + key.pem under app/.stack-tls/ (gitignored). Never prints key bytes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = APP_ROOT / ".stack-tls"


def generate(dest: Path, *, days: int = 30) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    key_path = dest / "key.pem"
    cert_path = dest / "cert.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "ce-stack-tls-local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Context Engine local"),
        ]
    )
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    print(f"OK: wrote {cert_path.name} and {key_path.name} under {dest}")
    print(f"Set CE_STACK_TLS_CERT_DIR={dest.resolve().as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)
    generate(args.dest, days=args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
