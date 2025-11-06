from rest_framework.authtoken.models import Token
from tenant_schemas.utils import schema_context

token_key = "64bbd86339a45cdd95e3a5c54076db289c63b73a"
tenant_schema = "groot"

print(f"\n{'='*60}")
print(f"Testing Admin Token: {token_key}")
print(f"Tenant Schema: {tenant_schema}")
print(f"{'='*60}\n")

with schema_context(tenant_schema):
    try:
        token_obj = Token.objects.select_related('user').get(key=token_key)
        user = token_obj.user
        print(f"✅ SUCCESS: Admin token is valid!")
        print(f"   User ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.first_name} {user.last_name}")
        print(f"   Is Active: {user.is_active}")
        print(f"   Is Staff: {user.is_staff}")
        print(f"   Is Superuser: {user.is_superuser}")
    except Token.DoesNotExist:
        print(f"❌ FAILED: Token not found in {tenant_schema} schema")
    except Exception as e:
        print(f"❌ ERROR: {e}")

print(f"\n{'='*60}\n")
