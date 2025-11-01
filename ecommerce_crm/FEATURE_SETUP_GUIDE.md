# E-commerce CRM Feature Setup Guide

## Overview
This guide explains how to add the `ecommerce_crm` feature to subscription packages so tenants can access the product management system.

## Feature Information
- **Feature Key**: `ecommerce_crm`
- **Feature Name**: E-commerce CRM
- **Icon**: 🛍️
- **Category**: Core
- **Pricing**:
  - Per User: 15 GEL/month
  - Unlimited Users: 150 GEL/month

## Method 1: Django Admin (Recommended for Single Package)

### Step 1: Access Django Admin
1. Navigate to: `https://api.echodesk.ge/admin/`
2. Login with superuser credentials

### Step 2: Add Feature to Package
1. Go to **Tenants** → **Package Features**
2. Click **"Add Package Feature"**
3. Fill in the form:
   - **Package**: Select target package (e.g., Professional, Enterprise)
   - **Feature**: Select "E-commerce CRM"
   - **Is Active**: ✅ Check this box
4. Click **"Save"**

### Step 3: Verify Feature is Added
1. Go to **Tenants** → **Packages**
2. Click on the package you modified
3. Scroll to "Package Features" section
4. Verify "E-commerce CRM" is listed

### Step 4: Grant to Specific Tenant (Optional)
If you want to give a tenant access without changing their package:

1. Go to **Tenants** → **Tenant Features**
2. Click **"Add Tenant Feature"**
3. Fill in:
   - **Tenant**: Select the tenant
   - **Feature**: Select "E-commerce CRM"
   - **Is Active**: ✅ Check this box
4. Click **"Save"**

## Method 2: Django Shell (For Bulk Operations)

```python
# SSH into your server and run:
python3 manage.py shell

# Import required models
from tenants.models import Package, Feature, PackageFeature, Tenant, TenantFeature

# Get the ecommerce feature
ecommerce_feature = Feature.objects.get(key='ecommerce_crm')

# --- Option A: Add to a single package ---
professional = Package.objects.get(name='Professional')
PackageFeature.objects.create(
    package=professional,
    feature=ecommerce_feature,
    is_active=True
)

# --- Option B: Add to multiple packages ---
package_names = ['Professional', 'Enterprise', 'Business']
for pkg_name in package_names:
    try:
        package = Package.objects.get(name=pkg_name)
        pf, created = PackageFeature.objects.get_or_create(
            package=package,
            feature=ecommerce_feature,
            defaults={'is_active': True}
        )
        if created:
            print(f"✅ Added ecommerce_crm to {pkg_name}")
        else:
            print(f"ℹ️  {pkg_name} already has ecommerce_crm")
    except Package.DoesNotExist:
        print(f"⚠️  Package '{pkg_name}' not found")

# --- Option C: Grant directly to a tenant ---
tenant = Tenant.objects.get(schema_name='groot')
TenantFeature.objects.get_or_create(
    tenant=tenant,
    feature=ecommerce_feature,
    defaults={'is_active': True}
)
print(f"✅ Granted ecommerce_crm to tenant 'groot'")
```

## Method 3: SQL Query (Advanced)

```sql
-- First, get the feature ID
SELECT id, key, name FROM tenants_feature WHERE key = 'ecommerce_crm';
-- Note the ID (let's say it's 10)

-- Get package IDs
SELECT id, name FROM tenants_package;
-- Note the IDs of packages you want to add the feature to

-- Add feature to package (replace 1 with package ID, 10 with feature ID)
INSERT INTO tenants_packagefeature (package_id, feature_id, is_active, created_at, updated_at)
VALUES (1, 10, true, NOW(), NOW())
ON CONFLICT (package_id, feature_id) DO UPDATE SET is_active = true;

-- Verify
SELECT p.name as package_name, f.name as feature_name, pf.is_active
FROM tenants_packagefeature pf
JOIN tenants_package p ON pf.package_id = p.id
JOIN tenants_feature f ON pf.feature_id = f.id
WHERE f.key = 'ecommerce_crm';
```

## Method 4: Data Migration (Automated)

Create a migration to automatically add the feature to packages:

```bash
cd echodesk-back
python3 manage.py makemigrations tenants --empty --name add_ecommerce_to_packages
```

Edit the migration file (see next section for code).

## Verification Steps

### 1. Check Package Has Feature
```python
from tenants.models import Package, Feature

package = Package.objects.get(name='Professional')
ecommerce = Feature.objects.get(key='ecommerce_crm')

has_feature = package.features.filter(id=ecommerce.id).exists()
print(f"Professional has ecommerce_crm: {has_feature}")
```

### 2. Check User Can See Feature
```python
from users.models import User

user = User.objects.get(email='user@example.com')
feature_keys = user.feature_keys  # This is populated from their tenant's subscription

print(f"User feature keys: {feature_keys}")
print(f"Has ecommerce_crm: {'ecommerce_crm' in feature_keys}")
```

### 3. Frontend Verification
1. Login as a user with the feature
2. Check the sidebar - you should see "Products" (🛍️)
3. Navigate to `/products`
4. You should see the product management interface

## Package Configuration Examples

### Starter Package (No E-commerce)
```python
starter = Package.objects.get(name='Starter')
# Don't add ecommerce_crm - this is a basic package
```

### Professional Package (With E-commerce)
```python
professional = Package.objects.get(name='Professional')
ecommerce = Feature.objects.get(key='ecommerce_crm')

PackageFeature.objects.get_or_create(
    package=professional,
    feature=ecommerce,
    defaults={'is_active': True}
)
```

### Enterprise Package (All Features)
```python
enterprise = Package.objects.get(name='Enterprise')

# Add all features including ecommerce
all_features = Feature.objects.filter(is_active=True)
for feature in all_features:
    PackageFeature.objects.get_or_create(
        package=enterprise,
        feature=feature,
        defaults={'is_active': True}
    )
```

## Troubleshooting

### Feature Not Showing in Sidebar
1. **Check user's feature_keys**:
   ```python
   user = User.objects.get(email='user@example.com')
   print(user.feature_keys)
   ```

2. **Check tenant subscription**:
   ```python
   from tenants.models import TenantSubscription

   tenant = user.tenant
   subscription = TenantSubscription.objects.get(tenant=tenant, is_active=True)
   print(f"Package: {subscription.package.name}")
   print(f"Package features: {list(subscription.package.features.values_list('key', flat=True))}")
   ```

3. **Check tenant features**:
   ```python
   tenant_features = tenant.tenant_features.filter(is_active=True)
   print(f"Direct tenant features: {list(tenant_features.values_list('feature__key', flat=True))}")
   ```

### Feature Shows But Can't Access
- Check that the feature is marked as `is_active=True` in both:
  - PackageFeature
  - Feature itself
  - TenantFeature (if using direct tenant assignment)

### Need to Remove Feature
```python
# From package
PackageFeature.objects.filter(
    package__name='Starter',
    feature__key='ecommerce_crm'
).delete()

# From specific tenant
TenantFeature.objects.filter(
    tenant__schema_name='groot',
    feature__key='ecommerce_crm'
).delete()
```

## Best Practices

1. **Add to Packages, Not Individual Tenants**:
   - Use PackageFeature for consistency
   - Only use TenantFeature for special cases/trials

2. **Test Before Production**:
   - Test on a development tenant first
   - Verify frontend shows the feature correctly
   - Test API endpoints work

3. **Document Package Features**:
   - Keep track of which packages include which features
   - Update your pricing page to reflect new features

4. **Migration Strategy**:
   - Create migrations for permanent changes
   - Makes deployment repeatable across environments

## Related Files
- Backend Models: `/tenants/models.py`, `/tenants/feature_models.py`
- Frontend Permission Check: `/src/services/permissionService.ts`
- Navigation Config: `/src/config/navigationConfig.ts`
- Feature Migration: `/tenants/migrations/0019_add_ecommerce_crm_feature.py`
