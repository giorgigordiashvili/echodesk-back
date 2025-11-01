#!/usr/bin/env python
"""
E-commerce CRM Feature Management Script

Usage:
    python manage_feature.py list-packages
    python manage_feature.py add-to-package Professional
    python manage_feature.py add-to-tenant groot
    python manage_feature.py remove-from-package Starter
    python manage_feature.py status
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from tenants.models import Package, Feature, PackageFeature, Tenant, TenantFeature


def list_packages():
    """List all packages and their ecommerce_crm status"""
    print("\n📦 Packages and E-commerce CRM Status:\n")
    packages = Package.objects.all()
    ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

    for package in packages:
        has_feature = package.features.filter(id=ecommerce_feature.id).exists()
        status = "✅ HAS" if has_feature else "❌ MISSING"
        print(f"  {status} - {package.name}")


def add_to_package(package_name):
    """Add ecommerce_crm to a package"""
    try:
        package = Package.objects.get(name=package_name)
        ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

        pf, created = PackageFeature.objects.get_or_create(
            package=package,
            feature=ecommerce_feature,
            defaults={'is_active': True}
        )

        if created:
            print(f"✅ Added ecommerce_crm to '{package_name}' package")
        else:
            if not pf.is_active:
                pf.is_active = True
                pf.save()
                print(f"✅ Activated ecommerce_crm for '{package_name}' package")
            else:
                print(f"ℹ️  '{package_name}' already has ecommerce_crm")

    except Package.DoesNotExist:
        print(f"❌ Package '{package_name}' not found")
        print("\nAvailable packages:")
        for pkg in Package.objects.all():
            print(f"  - {pkg.name}")
    except Feature.DoesNotExist:
        print("❌ ecommerce_crm feature not found. Run migrations first.")


def add_to_tenant(tenant_schema):
    """Add ecommerce_crm directly to a tenant"""
    try:
        tenant = Tenant.objects.get(schema_name=tenant_schema)
        ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

        tf, created = TenantFeature.objects.get_or_create(
            tenant=tenant,
            feature=ecommerce_feature,
            defaults={'is_active': True}
        )

        if created:
            print(f"✅ Granted ecommerce_crm to tenant '{tenant_schema}'")
        else:
            if not tf.is_active:
                tf.is_active = True
                tf.save()
                print(f"✅ Activated ecommerce_crm for tenant '{tenant_schema}'")
            else:
                print(f"ℹ️  Tenant '{tenant_schema}' already has ecommerce_crm")

    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{tenant_schema}' not found")
        print("\nAvailable tenants:")
        for t in Tenant.objects.all()[:10]:
            print(f"  - {t.schema_name}")
    except Feature.DoesNotExist:
        print("❌ ecommerce_crm feature not found. Run migrations first.")


def remove_from_package(package_name):
    """Remove ecommerce_crm from a package"""
    try:
        package = Package.objects.get(name=package_name)
        ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

        deleted = PackageFeature.objects.filter(
            package=package,
            feature=ecommerce_feature
        ).delete()[0]

        if deleted > 0:
            print(f"✅ Removed ecommerce_crm from '{package_name}' package")
        else:
            print(f"ℹ️  '{package_name}' didn't have ecommerce_crm")

    except Package.DoesNotExist:
        print(f"❌ Package '{package_name}' not found")
    except Feature.DoesNotExist:
        print("❌ ecommerce_crm feature not found")


def show_status():
    """Show comprehensive status of ecommerce_crm feature"""
    try:
        ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

        print("\n📊 E-commerce CRM Feature Status:\n")
        print(f"  Feature Name: {ecommerce_feature.name}")
        print(f"  Feature Key: {ecommerce_feature.key}")
        print(f"  Category: {ecommerce_feature.category}")
        print(f"  Icon: {ecommerce_feature.icon}")
        print(f"  Active: {ecommerce_feature.is_active}")
        print(f"  Price (per user): {ecommerce_feature.price_per_user_gel} GEL")
        print(f"  Price (unlimited): {ecommerce_feature.price_unlimited_gel} GEL")

        # Packages with this feature
        packages_with_feature = Package.objects.filter(
            packagefeature__feature=ecommerce_feature,
            packagefeature__is_active=True
        )

        print(f"\n📦 Packages with E-commerce CRM:")
        if packages_with_feature.exists():
            for pkg in packages_with_feature:
                print(f"  ✅ {pkg.name}")
        else:
            print("  ❌ No packages have this feature yet")

        # Tenants with this feature
        tenants_with_feature = Tenant.objects.filter(
            tenantfeature__feature=ecommerce_feature,
            tenantfeature__is_active=True
        )

        print(f"\n👥 Tenants with Direct Access:")
        if tenants_with_feature.exists():
            for tenant in tenants_with_feature[:5]:
                print(f"  ✅ {tenant.schema_name}")
            if tenants_with_feature.count() > 5:
                print(f"  ... and {tenants_with_feature.count() - 5} more")
        else:
            print("  ❌ No tenants have direct access")

    except Feature.DoesNotExist:
        print("❌ ecommerce_crm feature not found. Run migrations first.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list-packages":
        list_packages()
    elif command == "add-to-package" and len(sys.argv) >= 3:
        add_to_package(sys.argv[2])
    elif command == "add-to-tenant" and len(sys.argv) >= 3:
        add_to_tenant(sys.argv[2])
    elif command == "remove-from-package" and len(sys.argv) >= 3:
        remove_from_package(sys.argv[2])
    elif command == "status":
        show_status()
    else:
        print(__doc__)
