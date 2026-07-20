"""Inbound event ingestion primitives (auth providers + adapters).

This package is intentionally pure/side-effect-free: it holds NO key material,
performs NO database I/O, and does NOT touch the core proof engine. It exists so
that new integrations require only a lightweight adapter (and, optionally, a new
auth provider) rather than changes to the core platform.
"""
