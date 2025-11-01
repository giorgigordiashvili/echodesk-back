# EchoDesk Ecommerce Website Generator - Implementation Plan

## Overview
Allow EchoDesk users to generate ecommerce websites with CRM integration directly from EchoDesk.

---

## Architecture

### Option A: Subdomain per Store
- Each store gets: `{store-name}.echodesk.shop`
- Use Vercel/Netlify API to deploy generated sites
- Single codebase, multi-tenant configuration via environment variables

### Option B: Single Multi-tenant Frontend (RECOMMENDED)
- One Next.js app handles all stores: `echodesk.shop`
- Route by subdomain or path: `echodesk.shop/{store-name}`
- Fetch store config from API based on domain/slug
- **Benefit**: No deployment complexity, instant updates

---

## Database Models

### StorefrontTemplate Model
```python
class StorefrontTemplate(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=50, choices=[
        ('minimal', 'Minimal'),
        ('modern', 'Modern'),
        ('classic', 'Classic'),
        ('luxury', 'Luxury'),
    ])

    # Design Configuration
    theme_config = models.JSONField(default=dict)  # {primaryColor, secondaryColor, fontFamily, buttonStyle}

    # Layout Configuration
    layout_config = models.JSONField(default=dict)  # {headerType, productGrid, showSidebar}

    # Feature Toggles
    features = models.JSONField(default=dict)  # {showReviews, showRelatedProducts, enableWishlist, showStockCount}

    # Content
    products = models.JSONField(default=list)  # Product array
    logo_url = models.CharField(max_length=500, blank=True)
    domain_slug = models.CharField(max_length=100, unique=True)  # for subdomain

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### CustomDomain Model
```python
class CustomDomain(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    storefront = models.ForeignKey(StorefrontTemplate, on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, unique=True)  # "shop.example.com"

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending DNS Verification'),
        ('verified', 'DNS Verified'),
        ('active', 'Active & SSL Enabled'),
        ('failed', 'Verification Failed')
    ], default='pending')

    ssl_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending SSL'),
        ('issued', 'SSL Issued'),
        ('active', 'SSL Active')
    ], default='pending')

    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Product Model
```python
class Product(models.Model):
    storefront = models.ForeignKey(StorefrontTemplate, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.CharField(max_length=500)
    stock_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sku = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## Template System

### Pre-built Templates (4 Options)

**1. Minimal Template**
- Clean, white space design
- Simple product cards
- Top navigation bar
- 2-3 column grid

**2. Modern Template**
- Bold colors and gradients
- Large hero images
- Animated transitions
- 3-4 column grid

**3. Classic Template**
- Traditional ecommerce layout
- Detailed product descriptions
- Category sidebar
- Breadcrumb navigation

**4. Luxury Template**
- High-end aesthetic
- Elegant typography
- Large, high-quality product images
- Minimal UI elements

### Theme Configuration
```typescript
theme: {
  primaryColor: string       // Main brand color
  secondaryColor: string     // Accent color
  fontFamily: string         // 'Inter' | 'Playfair' | 'Roboto' | etc.
  buttonStyle: string        // 'rounded' | 'sharp' | 'pill'
}
```

### Layout Configuration
```typescript
layout: {
  headerType: string         // 'centered' | 'split' | 'minimal'
  productGrid: string        // '2-column' | '3-column' | '4-column'
  showSidebar: boolean       // Category sidebar
  footerStyle: string        // 'minimal' | 'detailed'
}
```

### Feature Toggles
```typescript
features: {
  showReviews: boolean
  showRelatedProducts: boolean
  enableWishlist: boolean
  showStockCount: boolean
  enableSearch: boolean
  showBreadcrumbs: boolean
}
```

---

## Configuration Wizard (5 Steps)

### Step 1: Choose Template
- Display 4 template previews with screenshots
- User clicks to select template type
- Show template features

### Step 2: Customize Design
- Color pickers for primary/secondary colors
- Logo upload (drag & drop)
- Font family dropdown
- Button style selector
- Live preview on right side

### Step 3: Add Products
- Add products via form (name, price, description, image)
- CSV import option for bulk upload
- Manage inventory and stock
- Set product categories

### Step 4: Setup Payment
- Connect Bank of Georgia merchant account
- Configure shipping zones and costs
- Set currency and tax settings

### Step 5: Domain Setup
- Choose subdomain: `{their-choice}.echodesk.shop`
- Or add custom domain with DNS instructions
- Preview final site

---

## CRM Integration

### Data Flow
```
Customer Places Order on Storefront
        ↓
Webhook to EchoDesk API
        ↓
Creates:
  1. Client in CRM (with contact info)
  2. Ticket for Order Tracking
  3. Order record with line items
        ↓
EchoDesk Dashboard shows:
  - Order as Ticket
  - Customer Profile
  - Purchase History
```

### Webhook Events
```python
# Webhook payload from storefront → EchoDesk
{
  "event": "order.created",
  "storefront_id": 123,
  "order": {
    "id": "ORD-001",
    "customer": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+995555123456"
    },
    "items": [
      {
        "product_id": 1,
        "name": "Product Name",
        "quantity": 2,
        "price": 50.00
      }
    ],
    "total": 100.00,
    "status": "pending"
  }
}
```

### Auto-Create CRM Entry
```python
def handle_order_webhook(payload):
    # 1. Create or get Client
    client, created = Client.objects.get_or_create(
        email=payload['order']['customer']['email'],
        defaults={
            'name': payload['order']['customer']['name'],
            'phone': payload['order']['customer']['phone'],
            'source': 'ecommerce'
        }
    )

    # 2. Create Ticket for order
    ticket = Ticket.objects.create(
        title=f"Order {payload['order']['id']}",
        description=format_order_details(payload['order']),
        client=client,
        ticket_type='order',
        status='open',
        priority='normal'
    )

    # 3. Create Order record
    order = Order.objects.create(
        ticket=ticket,
        order_id=payload['order']['id'],
        items=payload['order']['items'],
        total=payload['order']['total'],
        status='pending'
    )

    return order
```

---

## Custom Domain Setup

### DNS Configuration Instructions (User Side)

**Option A: CNAME (Subdomain)**
```
shop.theirsite.com → CNAME → proxy.echodesk.shop
```

**Option B: A Record (Root Domain)**
```
theirsite.com → A → YOUR_SERVER_IP
```

### DNS Verification Service
```python
import dns.resolver

def verify_domain(domain: str) -> bool:
    """Check if domain points to our server"""
    try:
        # Check CNAME
        answers = dns.resolver.resolve(domain, 'CNAME')
        for rdata in answers:
            if 'proxy.echodesk.shop' in str(rdata.target):
                return True

        # Check A record
        answers = dns.resolver.resolve(domain, 'A')
        for rdata in answers:
            if str(rdata) == 'YOUR_SERVER_IP':
                return True
    except:
        return False

    return False
```

### Auto SSL with Caddy (RECOMMENDED)

**Caddyfile Dynamic Generation**
```python
def add_to_caddy(domain: str, storefront_slug: str):
    """Add domain to Caddy configuration"""
    caddy_config = f"""
{domain} {{
    reverse_proxy localhost:3000 {{
        header_up Host {{host}}
        header_up X-Custom-Domain {domain}
        header_up X-Storefront-Slug {storefront_slug}
    }}
}}
"""

    # Append to Caddyfile
    with open('/etc/caddy/Caddyfile', 'a') as f:
        f.write(caddy_config)

    # Reload Caddy (zero downtime)
    os.system('caddy reload --config /etc/caddy/Caddyfile')
```

### User Flow

**Step 1: Add Domain**
```
User inputs: shop.example.com
→ Backend saves as 'pending'
→ Shows DNS instructions modal
```

**Step 2: DNS Instructions UI**
```html
<div class="dns-instructions">
  <h3>Add this DNS record to your domain provider:</h3>
  <table>
    <tr>
      <td>Type:</td>
      <td><code>CNAME</code></td>
    </tr>
    <tr>
      <td>Name:</td>
      <td><code>shop</code> (or <code>@</code> for root)</td>
    </tr>
    <tr>
      <td>Value:</td>
      <td><code>proxy.echodesk.shop</code></td>
    </tr>
    <tr>
      <td>TTL:</td>
      <td><code>3600</code></td>
    </tr>
  </table>
  <button>Verify DNS</button>
</div>
```

**Step 3: Verification & SSL**
```
User clicks "Verify DNS"
→ Backend runs verify_domain()
→ If valid:
    - Status = 'verified'
    - Add to Caddy config
    - Caddy auto-generates SSL cert
    - Status = 'active'
→ If invalid:
    - Show error message
    - Allow retry
```

### API Endpoints

```python
# Add custom domain
@api_view(['POST'])
def add_custom_domain(request):
    domain = request.data['domain']
    storefront_id = request.data['storefront_id']

    # Validate domain format
    if not is_valid_domain(domain):
        return Response({'error': 'Invalid domain'}, status=400)

    # Save as pending
    custom_domain = CustomDomain.objects.create(
        tenant=request.user.tenant,
        storefront_id=storefront_id,
        domain=domain,
        status='pending'
    )

    return Response({
        'status': 'pending',
        'instructions': {
            'type': 'CNAME',
            'name': extract_subdomain(domain),
            'value': 'proxy.echodesk.shop',
            'ttl': 3600
        }
    })

# Verify domain
@api_view(['POST'])
def verify_domain(request, domain_id):
    custom_domain = CustomDomain.objects.get(id=domain_id)

    if verify_domain_dns(custom_domain.domain):
        custom_domain.status = 'verified'
        custom_domain.verified_at = timezone.now()
        custom_domain.save()

        # Add to Caddy for SSL
        add_to_caddy(custom_domain.domain, custom_domain.storefront.domain_slug)

        # Update SSL status
        custom_domain.ssl_status = 'issued'
        custom_domain.save()

        return Response({'status': 'success', 'message': 'Domain verified and SSL enabled'})

    return Response({'status': 'failed', 'error': 'DNS not configured correctly'}, status=400)
```

---

## Frontend Routing (Next.js Middleware)

### Request Routing by Domain
```typescript
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  const hostname = request.headers.get('host') || ''

  // Check if it's a custom domain
  const customDomain = await getStorefrontByDomain(hostname)

  if (customDomain) {
    // Rewrite to storefront page with domain's slug
    const url = request.nextUrl.clone()
    url.pathname = `/store/${customDomain.slug}${request.nextUrl.pathname}`

    return NextResponse.rewrite(url)
  }

  // Check if it's an echodesk.shop subdomain
  if (hostname.endsWith('.echodesk.shop')) {
    const subdomain = hostname.split('.')[0]
    const storefront = await getStorefrontBySlug(subdomain)

    if (storefront) {
      const url = request.nextUrl.clone()
      url.pathname = `/store/${storefront.slug}${request.nextUrl.pathname}`
      return NextResponse.rewrite(url)
    }
  }

  // Default routing for EchoDesk dashboard
  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
}
```

### Dynamic Template Rendering
```typescript
// app/store/[slug]/page.tsx
export default async function StorefrontPage({ params }: { params: { slug: string } }) {
  const storefront = await getStorefront(params.slug)

  // Apply theme as CSS variables
  const themeStyles = {
    '--primary': storefront.theme_config.primaryColor,
    '--secondary': storefront.theme_config.secondaryColor,
    '--font-family': storefront.theme_config.fontFamily,
  }

  // Render template based on type
  const TemplateComponent = getTemplateComponent(storefront.template_type)

  return (
    <div style={themeStyles}>
      <TemplateComponent
        config={storefront}
        products={storefront.products}
      />
    </div>
  )
}

function getTemplateComponent(type: string) {
  switch(type) {
    case 'minimal':
      return MinimalTemplate
    case 'modern':
      return ModernTemplate
    case 'classic':
      return ClassicTemplate
    case 'luxury':
      return LuxuryTemplate
    default:
      return MinimalTemplate
  }
}
```

---

## Implementation Phases

### Phase 1: Core Template System
- [ ] Create database models (StorefrontTemplate, Product)
- [ ] Build 4 pre-designed templates (Minimal, Modern, Classic, Luxury)
- [ ] Create configuration wizard (5 steps)
- [ ] Implement live preview during customization

### Phase 2: Product Management
- [ ] Product CRUD operations
- [ ] CSV import for bulk products
- [ ] Image upload and management
- [ ] Inventory tracking

### Phase 3: Subdomain Routing
- [ ] Next.js middleware for subdomain detection
- [ ] Dynamic template rendering
- [ ] Slug uniqueness validation

### Phase 4: Custom Domain Support
- [ ] DNS verification service
- [ ] Caddy integration for auto SSL
- [ ] User instructions UI
- [ ] Domain status dashboard

### Phase 5: CRM Integration
- [ ] Order webhook handler
- [ ] Auto-create Client from order
- [ ] Auto-create Ticket for order tracking
- [ ] Order dashboard in EchoDesk

### Phase 6: Payment Integration
- [ ] BOG payment integration per storefront
- [ ] Checkout flow
- [ ] Order confirmation emails
- [ ] Payment status sync with CRM

---

## Tech Stack Summary

### Backend
- Django REST Framework for APIs
- PostgreSQL for data storage
- Celery for background tasks (DNS verification, SSL setup)
- dnspython for DNS resolution

### Frontend
- Next.js 15 for storefront + dashboard
- Tailwind CSS for styling
- React Hook Form for configuration wizard
- Radix UI for components

### Infrastructure
- Caddy for reverse proxy + auto SSL
- DigitalOcean/AWS for hosting
- Cloudflare for DNS management (optional)

### Payment
- Bank of Georgia payment gateway

---

## Benefits

1. **No Deployment Complexity**: Single Next.js app handles all stores
2. **Instant Updates**: User changes reflected immediately (no rebuild)
3. **Easy Custom Domains**: Caddy handles SSL automatically
4. **Built-in CRM**: Every order becomes a ticket, every customer a client
5. **Flexible Templates**: Multiple designs with full customization
6. **Scalable**: Can handle hundreds of stores on one app

---

## Future Enhancements

- [ ] Advanced analytics (sales, traffic, conversion)
- [ ] Email marketing integration
- [ ] Multi-language support
- [ ] Mobile app for order management
- [ ] Advanced SEO tools
- [ ] Social media integration
- [ ] Abandoned cart recovery
- [ ] Customer reviews and ratings
- [ ] Discount codes and promotions
- [ ] Inventory alerts and automation
