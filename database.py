"""SQLAlchemy database engine, session, and base model."""

import logging
import socket
import struct
from urllib.parse import urlparse, parse_qs

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DNS workaround: resolve Neon's .c-4 subdomain via Google DNS (8.8.8.8)
# when the local DNS blocks it.  psycopg2 / libpq does its own DNS
# resolution (bypassing Python's socket module), so we use the `creator`
# parameter of create_engine to pass the resolved IP via `hostaddr`.
# ---------------------------------------------------------------------------


def _resolve_via_google_dns(hostname: str, dns_server: str = "8.8.8.8") -> str | None:
    """Resolve *hostname* to an IPv4 address using a raw UDP DNS query.
    Handles CNAME chains (follows them until an A record is found)."""
    try:
        txn_id = b"\xaa\xbb"
        flags = b"\x01\x00"
        counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"
        qname = b""
        for part in hostname.encode().split(b"."):
            qname += bytes([len(part)]) + part
        qname += b"\x00"
        question = qname + b"\x00\x01\x00\x01"
        packet = txn_id + flags + counts + question

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.sendto(packet, (dns_server, 53))
        resp, _ = sock.recvfrom(1024)
        sock.close()

        idx = 12
        while resp[idx] != 0:
            idx += resp[idx] + 1
        idx += 5

        ancount = struct.unpack("!H", resp[6:8])[0]
        for _ in range(ancount):
            if resp[idx] & 0xC0 == 0xC0:
                idx += 2
            else:
                while resp[idx] != 0:
                    idx += resp[idx] + 1
                idx += 1
            rtype = struct.unpack("!H", resp[idx:idx + 2])[0]
            idx += 8
            rdlen = struct.unpack("!H", resp[idx:idx + 2])[0]
            idx += 2
            if rtype == 1 and rdlen == 4:
                return socket.inet_ntoa(resp[idx:idx + 4])
            idx += rdlen
    except Exception as exc:
        logger.warning("Google-DNS resolution for %s failed: %s", hostname, exc)
    return None


def _build_engine(db_url: str):
    """Build a SQLAlchemy engine.  When the DB hostname can't be resolved
    locally, resolve it via Google DNS and create a custom psycopg2
    connection creator that passes the IP via ``hostaddr``."""

    if "sqlite" in db_url:
        return create_engine(db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True)

    parsed = urlparse(db_url)
    host = parsed.hostname

    # Check whether local DNS works
    needs_workaround = False
    if host:
        try:
            socket.getaddrinfo(host, parsed.port or 5432, socket.AF_INET)
        except socket.gaierror:
            needs_workaround = True

    if not needs_workaround:
        logger.info("Local DNS resolved %s — using standard engine.", host)
        return create_engine(db_url, pool_pre_ping=True)

    # --- DNS workaround path ---
    resolved_ip = _resolve_via_google_dns(host)
    if not resolved_ip:
        logger.error("Could not resolve %s via Google DNS either — falling back.", host)
        return create_engine(db_url, pool_pre_ping=True)

    logger.info("DNS workaround: %s → %s (via Google DNS 8.8.8.8)", host, resolved_ip)

    # Extract connection parameters
    port = parsed.port or 5432
    user = parsed.username
    password = parsed.password
    dbname = parsed.path.lstrip("/") if parsed.path else ""
    qs = parse_qs(parsed.query)
    sslmode = qs.get("sslmode", ["require"])[0]

    def _creator():
        """Create a psycopg2 connection using hostaddr (IP) for the actual
        TCP connection while keeping host (hostname) for SSL SNI."""
        return psycopg2.connect(
            host=host,           # used for SSL certificate verification / SNI
            hostaddr=resolved_ip, # actual IP to connect to (bypasses DNS)
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            sslmode=sslmode,
        )

    return create_engine("postgresql://", creator=_creator, pool_pre_ping=True)


engine = _build_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    import models  # noqa: F401 – registers models with Base
    Base.metadata.create_all(bind=engine)


