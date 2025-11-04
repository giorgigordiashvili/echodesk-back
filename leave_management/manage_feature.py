#!/usr/bin/env python
"""
Leave Management Feature Management Script

Usage:
    python manage_feature.py list-packages
    python manage_feature.py add-to-package <package_name>
    python manage_feature.py remove-from-package <package_name>
    python manage_feature.py add-to-tenant <tenant_subdomain>
    python manage_feature.py remove-from-tenant <tenant_subdomain>
    python manage_feature.py status

Examples:
    python manage_feature.py add-to-package Professional
    python manage_feature.py add-to-package Enterprise
    python manage_feature.py add-to-tenant mycompany
    python manage_feature.py status
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from django.db import transaction
from tenants.models import Package, PackageFeature, Feature, Tenant, TenantFeature


FEATURE_KEY = 'leave_management'
FEATURE_NAME = 'Leave Management'
FEATURE_DESCRIPTION = 'Employee leave and absence management system with multi-level approvals'


def get_or_create_feature():
    """Get or create the leave_management feature"""
    feature, created = Feature.objects.get_or_create(
        key=FEATURE_KEY,
        defaults={
            'name': FEATURE_NAME,
            'description': FEATURE_DESCRIPTION,
            'is_active': True
        }
    )

    if created:
        print(f"✅ Created feature: {FEATURE_NAME} ({FEATURE_KEY})")
    else:
        print(f"ℹ️  Feature already exists: {FEATURE_NAME} ({FEATURE_KEY})")

    return feature


def list_packages():
    """List all available packages"""
    packages = Package.objects.all()

    print("\n📦 Available Packages:")
    print("-" * 50)

    for package in packages:
        features = PackageFeature.objects.filter(package=package)
        has_lms = features.filter(feature__key=FEATURE_KEY).exists()

        status = "✅ HAS LMS" if has_lms else "❌ NO LMS"

        print(f"\n{package.name} - {status}")
        print(f"  Description: {package.description}")
        print(f"  Features: {features.count()}")

    print("\n" + "-" * 50)


def add_to_package(package_name):
    """Add leave_management to a package"""
    try:
        package = Package.objects.get(name=package_name)
    except Package.DoesNotExist:
        print(f"❌ Package '{package_name}' not found")
        print("\nAvailable packages:")
        for p in Package.objects.all():
            print(f"  - {p.name}")
        return

    feature = get_or_create_feature()

    package_feature, created = PackageFeature.objects.get_or_create(
        package=package,
        feature=feature
    )

    if created:
        print(f"✅ Added {FEATURE_NAME} to {package.name} package")
    else:
        print(f"ℹ️  {FEATURE_NAME} already exists in {package.name} package")


def remove_from_package(package_name):
    """Remove leave_management from a package"""
    try:
        package = Package.objects.get(name=package_name)
    except Package.DoesNotExist:
        print(f"❌ Package '{package_name}' not found")
        return

    try:
        feature = Feature.objects.get(key=FEATURE_KEY)
    except Feature.DoesNotExist:
        print(f"❌ Feature {FEATURE_KEY} not found")
        return

    try:
        package_feature = PackageFeature.objects.get(package=package, feature=feature)
        package_feature.delete()
        print(f"✅ Removed {FEATURE_NAME} from {package.name} package")
    except PackageFeature.DoesNotExist:
        print(f"ℹ️  {FEATURE_NAME} was not in {package.name} package")


def add_to_tenant(tenant_subdomain):
    """Add leave_management feature to a specific tenant"""
    try:
        tenant = Tenant.objects.get(subdomain=tenant_subdomain)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{tenant_subdomain}' not found")
        return

    feature = get_or_create_feature()

    tenant_feature, created = TenantFeature.objects.get_or_create(
        tenant=tenant,
        feature=feature
    )

    if created:
        print(f"✅ Added {FEATURE_NAME} to tenant '{tenant.name}' ({tenant_subdomain})")
    else:
        print(f"ℹ️  {FEATURE_NAME} already exists for tenant '{tenant.name}'")


def remove_from_tenant(tenant_subdomain):
    """Remove leave_management feature from a specific tenant"""
    try:
        tenant = Tenant.objects.get(subdomain=tenant_subdomain)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{tenant_subdomain}' not found")
        return

    try:
        feature = Feature.objects.get(key=FEATURE_KEY)
    except Feature.DoesNotExist:
        print(f"❌ Feature {FEATURE_KEY} not found")
        return

    try:
        tenant_feature = TenantFeature.objects.get(tenant=tenant, feature=feature)
        tenant_feature.delete()
        print(f"✅ Removed {FEATURE_NAME} from tenant '{tenant.name}'")
    except TenantFeature.DoesNotExist:
        print(f"ℹ️  {FEATURE_NAME} was not enabled for tenant '{tenant.name}'")


def show_status():
    """Show current status of leave_management feature"""
    try:
        feature = Feature.objects.get(key=FEATURE_KEY)
    except Feature.DoesNotExist:
        print(f"❌ Feature {FEATURE_KEY} not found in database")
        print("\nRun with 'add-to-package' to create the feature")
        return

    print(f"\n📊 Leave Management Feature Status")
    print("=" * 60)
    print(f"Feature Key: {feature.key}")
    print(f"Feature Name: {feature.name}")
    print(f"Active: {'✅ Yes' if feature.is_active else '❌ No'}")
    print(f"Description: {feature.description}")

    # Show packages
    print(f"\n📦 Packages with this feature:")
    print("-" * 60)
    package_features = PackageFeature.objects.filter(feature=feature).select_related('package')

    if package_features.exists():
        for pf in package_features:
            print(f"  • {pf.package.name}")
    else:
        print("  (None)")

    # Show tenants
    print(f"\n🏢 Tenants with this feature:")
    print("-" * 60)
    tenant_features = TenantFeature.objects.filter(feature=feature).select_related('tenant')

    if tenant_features.exists():
        for tf in tenant_features:
            print(f"  • {tf.tenant.name} ({tf.tenant.subdomain})")
    else:
        print("  (None)")

    print("\n" + "=" * 60)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == 'list-packages':
        list_packages()

    elif command == 'add-to-package':
        if len(sys.argv) < 3:
            print("❌ Error: Package name required")
            print("Usage: python manage_feature.py add-to-package <package_name>")
            return
        add_to_package(sys.argv[2])

    elif command == 'remove-from-package':
        if len(sys.argv) < 3:
            print("❌ Error: Package name required")
            print("Usage: python manage_feature.py remove-from-package <package_name>")
            return
        remove_from_package(sys.argv[2])

    elif command == 'add-to-tenant':
        if len(sys.argv) < 3:
            print("❌ Error: Tenant subdomain required")
            print("Usage: python manage_feature.py add-to-tenant <tenant_subdomain>")
            return
        add_to_tenant(sys.argv[2])

    elif command == 'remove-from-tenant':
        if len(sys.argv) < 3:
            print("❌ Error: Tenant subdomain required")
            print("Usage: python manage_feature.py remove-from-tenant <tenant_subdomain>")
            return
        remove_from_tenant(sys.argv[2])

    elif command == 'status':
        show_status()

    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)


if __name__ == '__main__':
    main()
