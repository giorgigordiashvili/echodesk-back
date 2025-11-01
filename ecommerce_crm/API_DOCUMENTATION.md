# E-commerce CRM API Documentation

## Base URL
All endpoints are prefixed with `/api/ecommerce/`

## Product Endpoints

### List Products
```
GET /api/ecommerce/products/
```
**Query Parameters:**
- `status` - Filter by status (draft, active, inactive, out_of_stock)
- `product_type` - Filter by product type ID
- `product_type_key` - Filter by product type key
- `category` - Filter by category ID
- `category_slug` - Filter by category slug
- `is_featured` - Filter featured products (true/false)
- `min_price` - Minimum price filter
- `max_price` - Maximum price filter
- `search` - Search by SKU, slug, or name
- `in_stock` - Filter in-stock products (true/false)
- `low_stock` - Filter low stock products (true/false)
- `ordering` - Sort by fields (e.g., price, -created_at, quantity)
- `language` - Response language code (en, ka, ru)

### Create Product
```
POST /api/ecommerce/products/
Content-Type: application/json

{
  "sku": "PROD-001",
  "slug": "sample-product",
  "name": {"en": "Sample Product", "ka": "ნიმუში პროდუქტი"},
  "description": {"en": "Description", "ka": "აღწერა"},
  "short_description": {"en": "Short desc", "ka": "მოკლე აღწერა"},
  "product_type": 1,
  "category": 1,
  "price": "99.99",
  "compare_at_price": "149.99",
  "cost_price": "50.00",
  "track_inventory": true,
  "quantity": 100,
  "low_stock_threshold": 10,
  "status": "active",
  "is_featured": false,
  "attributes": [
    {
      "attribute_id": 1,
      "value_text": "Blue"
    },
    {
      "attribute_id": 2,
      "value_number": 42
    }
  ]
}
```

### Get Product Detail
```
GET /api/ecommerce/products/{id}/
```

### Update Product
```
PUT /api/ecommerce/products/{id}/
PATCH /api/ecommerce/products/{id}/
```

### Delete Product
```
DELETE /api/ecommerce/products/{id}/
```

### Add Image to Product
```
POST /api/ecommerce/products/{id}/add_image/
Content-Type: multipart/form-data

{
  "image": <file>,
  "alt_text": {"en": "Product image", "ka": "პროდუქტის სურათი"},
  "sort_order": 0
}
```

### Remove Image from Product
```
DELETE /api/ecommerce/products/{id}/remove_image/{image_id}/
```

### Update Product Attributes
```
POST /api/ecommerce/products/{id}/update_attributes/

{
  "attributes": [
    {
      "attribute_id": 1,
      "value_text": "Red"
    }
  ]
}
```

### Get Featured Products
```
GET /api/ecommerce/products/featured/
```

### Get Low Stock Products
```
GET /api/ecommerce/products/low_stock/
```

## Product Type Endpoints

### List Product Types
```
GET /api/ecommerce/types/
```

### Create Product Type
```
POST /api/ecommerce/types/

{
  "name": {"en": "Electronics", "ka": "ელექტრონიკა"},
  "key": "electronics",
  "description": {"en": "Electronic devices", "ka": "ელექტრონული მოწყობილობები"},
  "icon": "📱",
  "sort_order": 0,
  "is_active": true
}
```

### Get Product Type Detail
```
GET /api/ecommerce/types/{id}/
```

### Update Product Type
```
PUT /api/ecommerce/types/{id}/
PATCH /api/ecommerce/types/{id}/
```

### Delete Product Type
```
DELETE /api/ecommerce/types/{id}/
```

## Category Endpoints

### List Categories
```
GET /api/ecommerce/categories/
```

### Get Category Tree
```
GET /api/ecommerce/categories/tree/
```

### Create Category
```
POST /api/ecommerce/categories/

{
  "name": {"en": "Electronics", "ka": "ელექტრონიკა"},
  "description": {"en": "Electronic products", "ka": "ელექტრონული პროდუქტები"},
  "slug": "electronics",
  "parent": null,
  "sort_order": 0,
  "is_active": true
}
```

### Get Category Detail
```
GET /api/ecommerce/categories/{id}/
```

### Update Category
```
PUT /api/ecommerce/categories/{id}/
PATCH /api/ecommerce/categories/{id}/
```

### Delete Category
```
DELETE /api/ecommerce/categories/{id}/
```

## Attribute Endpoints

### List Attributes
```
GET /api/ecommerce/attributes/
```

### Create Attribute
```
POST /api/ecommerce/attributes/

{
  "name": {"en": "Color", "ka": "ფერი"},
  "key": "color",
  "attribute_type": "select",
  "options": [
    {"en": "Red", "ka": "წითელი", "value": "red"},
    {"en": "Blue", "ka": "ლურჯი", "value": "blue"}
  ],
  "is_required": false,
  "is_variant_attribute": true,
  "is_filterable": true,
  "sort_order": 0,
  "is_active": true
}
```

### Get Attribute Detail
```
GET /api/ecommerce/attributes/{id}/
```

### Update Attribute
```
PUT /api/ecommerce/attributes/{id}/
PATCH /api/ecommerce/attributes/{id}/
```

### Delete Attribute
```
DELETE /api/ecommerce/attributes/{id}/
```

## Product Variant Endpoints

### List Variants
```
GET /api/ecommerce/variants/
```

### Create Variant
```
POST /api/ecommerce/variants/

{
  "product": 1,
  "sku": "PROD-001-BLUE-L",
  "name": {"en": "Blue - Large", "ka": "ლურჯი - დიდი"},
  "price": "109.99",
  "quantity": 50,
  "is_active": true,
  "sort_order": 0
}
```

## Image Endpoints

### List Product Images
```
GET /api/ecommerce/images/?product={product_id}
```

### Create Image
```
POST /api/ecommerce/images/
Content-Type: multipart/form-data

{
  "product": 1,
  "image": <file>,
  "alt_text": {"en": "Product image"},
  "sort_order": 0
}
```

### Update Image
```
PUT /api/ecommerce/images/{id}/
PATCH /api/ecommerce/images/{id}/
```

### Delete Image
```
DELETE /api/ecommerce/images/{id}/
```

## Response Codes

- `200 OK` - Success
- `201 Created` - Resource created successfully
- `204 No Content` - Resource deleted successfully
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Multilanguage Support

All multilanguage fields accept a JSON object with language codes as keys:

```json
{
  "en": "English text",
  "ka": "ქართული ტექსტი",
  "ru": "Русский текст"
}
```

Supported language codes: `en`, `ka`, `ru`
