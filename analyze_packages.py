#!/usr/bin/env python3
"""
Analyze Package usage in the database before removal
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'echodesk.settings')
django.setup()

from tenants.models import Package, TenantSubscription, PaymentOrder, Invoice, PendingRegistration
from tenants.feature_models import PackageFeature

print("=" * 80)
print("PACKAGE SYSTEM ANALYSIS")
print("=" * 80)
print()

# Package counts
total_packages = Package.objects.count()
active_packages = Package.objects.filter(is_active=True).count()
print(f"📦 Total Packages: {total_packages}")
print(f"   └─ Active: {active_packages}")
print(f"   └─ Inactive: {total_packages - active_packages}")
print()

# Package by pricing model
if total_packages > 0:
    agent_based = Package.objects.filter(pricing_model='agent').count()
    crm_based = Package.objects.filter(pricing_model='crm').count()
    print(f"   Pricing Models:")
    print(f"   └─ Agent-based: {agent_based}")
    print(f"   └─ CRM-based: {crm_based}")
    print()

# PackageFeature counts
total_package_features = PackageFeature.objects.count()
print(f"🔗 Total PackageFeature Links: {total_package_features}")
print()

# Subscription analysis
total_subs = TenantSubscription.objects.count()
subs_with_package = TenantSubscription.objects.filter(package__isnull=False).count()
subs_with_pending = TenantSubscription.objects.filter(pending_package__isnull=False).count()
subs_with_features = TenantSubscription.objects.filter(selected_features__isnull=False).distinct().count()

print(f"💳 Total Subscriptions: {total_subs}")
print(f"   └─ With package: {subs_with_package}")
print(f"   └─ With pending_package: {subs_with_pending}")
print(f"   └─ With selected_features: {subs_with_features}")

# Mixed subscriptions
mixed = TenantSubscription.objects.filter(
    package__isnull=False
).filter(
    selected_features__isnull=False
).distinct().count()
print(f"   └─ Mixed (package + features): {mixed}")
print()

# Show subscriptions with pending_package
if subs_with_pending > 0:
    print(f"⚠️  SUBSCRIPTIONS WITH PENDING UPGRADES:")
    pending_subs = TenantSubscription.objects.filter(pending_package__isnull=False).select_related('tenant', 'package', 'pending_package')
    for sub in pending_subs:
        print(f"   • Tenant: {sub.tenant.schema_name}")
        print(f"     Current: {sub.package.display_name if sub.package else 'None'}")
        print(f"     Pending: {sub.pending_package.display_name}")
        print(f"     Scheduled for: {sub.upgrade_scheduled_for}")
        print()

# Payment order analysis
total_payments = PaymentOrder.objects.count()
payments_with_package = PaymentOrder.objects.filter(package__isnull=False).count()
payments_with_prev_package = PaymentOrder.objects.filter(previous_package__isnull=False).count()

print(f"💰 Total Payment Orders: {total_payments}")
print(f"   └─ With package: {payments_with_package}")
print(f"   └─ With previous_package: {payments_with_prev_package}")
print()

# Invoice analysis
total_invoices = Invoice.objects.count()
invoices_with_package = Invoice.objects.filter(package__isnull=False).count()

print(f"📄 Total Invoices: {total_invoices}")
print(f"   └─ With package: {invoices_with_package}")
print()

# Pending registration analysis
total_pending = PendingRegistration.objects.count()
pending_with_package = PendingRegistration.objects.filter(package__isnull=False).count()

print(f"⏳ Total Pending Registrations: {total_pending}")
print(f"   └─ With package: {pending_with_package}")
print()

print("=" * 80)
print("MIGRATION READINESS")
print("=" * 80)

issues = []

if subs_with_pending > 0:
    issues.append(f"❌ {subs_with_pending} subscriptions have pending_package (must be cleared)")

if subs_with_package > subs_with_features:
    pure_package = subs_with_package - mixed
    issues.append(f"⚠️  {pure_package} subscriptions are package-only (no features)")

if pending_with_package > 0:
    issues.append(f"⚠️  {pending_with_package} pending registrations reference packages")

if not issues:
    print("✅ No blocking issues found!")
else:
    for issue in issues:
        print(issue)

print()
print("=" * 80)
