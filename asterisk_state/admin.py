"""Intentionally empty — asterisk_state is schema-only.

The sync layer writes these rows; exposing them in Django admin would give
operators a footgun (editing an endpoint out-of-band desyncs the tenant's
product models). Use the admin actions on ``Trunk``/``Queue``/etc. instead.
"""
