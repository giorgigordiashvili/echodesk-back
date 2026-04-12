"""
Predefined homepage variant definitions for ecommerce storefronts.
Each variant is a collection of homepage sections that can be applied
to quickly set up a tenant's homepage layout.
"""

HOMEPAGE_VARIANTS = {
    'classic': {
        'name': 'Classic',
        'description': 'Hero banner + Featured products + Category grid',
        'sections': [
            {
                'title': {'en': 'Welcome to Our Store', 'ka': 'მოგესალმებით ჩვენს მაღაზიაში'},
                'subtitle': {'en': 'Discover amazing products', 'ka': 'აღმოაჩინეთ საოცარი პროდუქტები'},
                'section_type': 'hero_banner',
                'display_mode': 'slider',
                'position': 0,
                'settings': {'autoSlide': True, 'slideInterval': 5000, 'showArrows': True, 'showDots': True},
            },
            {
                'title': {'en': 'Featured Products', 'ka': 'რჩეული პროდუქტები'},
                'subtitle': {'en': 'Our best picks for you', 'ka': 'ჩვენი საუკეთესო შერჩევა თქვენთვის'},
                'section_type': 'featured_products',
                'display_mode': 'grid',
                'position': 1,
                'settings': {'columns': 4, 'maxItems': 8, 'showViewAll': True, 'viewAllLink': '/products?is_featured=true'},
            },
            {
                'title': {'en': 'Shop by Category', 'ka': 'იყიდეთ კატეგორიის მიხედვით'},
                'section_type': 'category_grid',
                'display_mode': 'grid',
                'position': 2,
                'settings': {'columns': 3},
            },
        ],
    },
    'modern': {
        'name': 'Modern',
        'description': 'Full-width hero + Statistics + Products + Large categories',
        'sections': [
            {
                'title': {'en': 'New Collection', 'ka': 'ახალი კოლექცია'},
                'section_type': 'hero_banner',
                'display_mode': 'single',
                'position': 0,
                'settings': {'showArrows': False, 'showDots': False},
            },
            {
                'title': {'en': 'Our Achievements', 'ka': 'ჩვენი მიღწევები'},
                'section_type': 'statistics',
                'display_mode': 'grid',
                'position': 1,
                'settings': {'columns': 4},
            },
            {
                'title': {'en': 'Featured Products', 'ka': 'რჩეული პროდუქტები'},
                'section_type': 'featured_products',
                'display_mode': 'grid',
                'position': 2,
                'settings': {'columns': 4, 'maxItems': 8},
            },
            {
                'title': {'en': 'Categories', 'ka': 'კატეგორიები'},
                'section_type': 'category_grid',
                'display_mode': 'grid',
                'position': 3,
                'settings': {'columns': 2},
            },
        ],
    },
    'minimal': {
        'name': 'Minimal',
        'description': 'Clean grid layout with featured products and categories',
        'sections': [
            {
                'title': {'en': 'Featured Products', 'ka': 'რჩეული პროდუქტები'},
                'section_type': 'featured_products',
                'display_mode': 'grid',
                'position': 0,
                'settings': {'columns': 3, 'maxItems': 6},
            },
            {
                'title': {'en': 'Categories', 'ka': 'კატეგორიები'},
                'section_type': 'category_grid',
                'display_mode': 'grid',
                'position': 1,
                'settings': {'columns': 3},
            },
        ],
    },
    'boutique': {
        'name': 'Boutique',
        'description': 'Elegant slideshow with category focus and featured slider',
        'sections': [
            {
                'title': {'en': 'Discover Our Collection', 'ka': 'აღმოაჩინეთ ჩვენი კოლექცია'},
                'section_type': 'hero_banner',
                'display_mode': 'slider',
                'position': 0,
                'settings': {'autoSlide': True, 'slideInterval': 4000, 'showArrows': True, 'showDots': True},
            },
            {
                'title': {'en': 'Shop by Category', 'ka': 'იყიდეთ კატეგორიის მიხედვით'},
                'section_type': 'category_grid',
                'display_mode': 'grid',
                'position': 1,
                'settings': {'columns': 4},
            },
            {
                'title': {'en': 'Best Sellers', 'ka': 'ბესტსელერები'},
                'section_type': 'featured_products',
                'display_mode': 'slider',
                'position': 2,
                'settings': {'columns': 1, 'maxItems': 8, 'autoSlide': True},
            },
            {
                'title': {'en': 'About Us', 'ka': 'ჩვენს შესახებ'},
                'section_type': 'custom_content',
                'display_mode': 'single',
                'position': 3,
                'settings': {},
            },
        ],
    },
    'marketplace': {
        'name': 'Marketplace',
        'description': 'Full-featured with hero, categories, products, stats, and branches',
        'sections': [
            {
                'title': {'en': 'Welcome', 'ka': 'მოგესალმებით'},
                'section_type': 'hero_banner',
                'display_mode': 'slider',
                'position': 0,
                'settings': {'autoSlide': True, 'slideInterval': 5000, 'showArrows': True, 'showDots': True},
            },
            {
                'title': {'en': 'Categories', 'ka': 'კატეგორიები'},
                'section_type': 'category_grid',
                'display_mode': 'grid',
                'position': 1,
                'settings': {'columns': 4},
            },
            {
                'title': {'en': 'Featured Products', 'ka': 'რჩეული პროდუქტები'},
                'section_type': 'featured_products',
                'display_mode': 'grid',
                'position': 2,
                'settings': {'columns': 4, 'maxItems': 8, 'showViewAll': True},
            },
            {
                'title': {'en': 'New Arrivals', 'ka': 'ახალი პროდუქტები'},
                'section_type': 'product_by_attribute',
                'display_mode': 'grid',
                'position': 3,
                'settings': {'columns': 4, 'maxItems': 8},
                'attribute_key': 'is_new',
                'attribute_value': 'true',
            },
            {
                'title': {'en': 'Our Numbers', 'ka': 'ჩვენი რიცხვები'},
                'section_type': 'statistics',
                'display_mode': 'grid',
                'position': 4,
                'settings': {'columns': 4},
            },
            {
                'title': {'en': 'Our Branches', 'ka': 'ჩვენი ფილიალები'},
                'section_type': 'branches',
                'display_mode': 'list',
                'position': 5,
                'settings': {},
            },
        ],
    },
}
