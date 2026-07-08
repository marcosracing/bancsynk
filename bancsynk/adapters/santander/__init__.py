"""Adaptador Santander read-only (BancSynk Fase 1)."""

from bancsynk.adapters.santander.accounts import SantanderReadOnlyAdapter
from bancsynk.adapters.santander.auth import SantanderAuth

__all__ = ["SantanderAuth", "SantanderReadOnlyAdapter"]
