from rest_framework import serializers
from .models import HelpCategory, HelpArticle


class HelpCategoryListSerializer(serializers.ModelSerializer):
    """Serializer for category listing"""
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    article_count = serializers.SerializerMethodField()

    class Meta:
        model = HelpCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'position', 'is_active', 'show_on_public',
            'show_in_dashboard', 'required_feature_key',
            'article_count', 'created_at', 'updated_at'
        ]

    def get_name(self, obj):
        lang = self.context.get('request', {})
        if hasattr(lang, 'query_params'):
            lang = lang.query_params.get('lang', 'en')
        else:
            lang = 'en'
        return obj.get_name(lang)

    def get_description(self, obj):
        lang = self.context.get('request', {})
        if hasattr(lang, 'query_params'):
            lang = lang.query_params.get('lang', 'en')
        else:
            lang = 'en'
        return obj.get_description(lang)

    def get_article_count(self, obj):
        return obj.articles.filter(is_active=True).count()


class HelpCategoryDetailSerializer(serializers.ModelSerializer):
    """Serializer for category detail with articles"""
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    articles = serializers.SerializerMethodField()
    article_count = serializers.SerializerMethodField()

    class Meta:
        model = HelpCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'position', 'is_active', 'show_on_public',
            'show_in_dashboard', 'required_feature_key',
            'article_count', 'articles', 'created_at', 'updated_at'
        ]

    def _get_language(self):
        request = self.context.get('request')
        if request and hasattr(request, 'query_params'):
            return request.query_params.get('lang', 'en')
        return 'en'

    def get_name(self, obj):
        return obj.get_name(self._get_language())

    def get_description(self, obj):
        return obj.get_description(self._get_language())

    def get_article_count(self, obj):
        return obj.articles.filter(is_active=True).count()

    def get_articles(self, obj):
        articles = obj.articles.filter(is_active=True)
        request = self.context.get('request')

        # Filter based on visibility
        if request and request.query_params.get('for_public') == 'true':
            articles = articles.filter(show_on_public=True)
        elif request and request.query_params.get('for_dashboard') == 'true':
            articles = articles.filter(show_in_dashboard=True)

        return HelpArticleListSerializer(articles, many=True, context=self.context).data


class HelpCategoryAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin CRUD - returns raw JSON fields"""

    class Meta:
        model = HelpCategory
        fields = '__all__'


class HelpArticleListSerializer(serializers.ModelSerializer):
    """Serializer for article listing"""
    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    category_slug = serializers.CharField(source='category.slug', read_only=True)

    class Meta:
        model = HelpArticle
        fields = [
            'id', 'title', 'slug', 'summary', 'content_type',
            'video_thumbnail', 'video_duration',
            'position', 'is_active', 'is_featured',
            'show_on_public', 'show_in_dashboard',
            'category_name', 'category_slug',
            'created_at', 'updated_at'
        ]

    def get_title(self, obj):
        lang = self._get_language()
        return obj.get_title(lang)

    def get_summary(self, obj):
        lang = self._get_language()
        return obj.get_summary(lang)

    def get_category_name(self, obj):
        lang = self._get_language()
        return obj.category.get_name(lang)

    def _get_language(self):
        request = self.context.get('request')
        if request and hasattr(request, 'query_params'):
            return request.query_params.get('lang', 'en')
        return 'en'


class HelpArticleDetailSerializer(serializers.ModelSerializer):
    """Serializer for article detail view"""
    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    guide_steps = serializers.SerializerMethodField()
    faq_items = serializers.SerializerMethodField()
    category = HelpCategoryListSerializer(read_only=True)

    class Meta:
        model = HelpArticle
        fields = [
            'id', 'title', 'slug', 'summary', 'content_type',
            'content', 'video_url', 'video_thumbnail', 'video_duration',
            'guide_steps', 'faq_items',
            'position', 'is_active', 'is_featured',
            'show_on_public', 'show_in_dashboard',
            'meta_title', 'meta_description',
            'category', 'created_at', 'updated_at', 'published_at'
        ]

    def get_title(self, obj):
        lang = self._get_language()
        return obj.get_title(lang)

    def get_summary(self, obj):
        lang = self._get_language()
        return obj.get_summary(lang)

    def get_content(self, obj):
        lang = self._get_language()
        return obj.get_content(lang)

    def get_guide_steps(self, obj):
        if not obj.guide_steps:
            return []
        lang = self._get_language()
        # Localize step titles and content
        localized_steps = []
        for step in obj.guide_steps:
            localized_step = {
                'step': step.get('step', 0),
                'title': step.get('title', {}).get(lang, step.get('title', {}).get('en', '')),
                'content': step.get('content', {}).get(lang, step.get('content', {}).get('en', '')),
                'image': step.get('image', '')
            }
            localized_steps.append(localized_step)
        return localized_steps

    def get_faq_items(self, obj):
        if not obj.faq_items:
            return []
        lang = self._get_language()
        # Localize questions and answers
        localized_items = []
        for item in obj.faq_items:
            localized_item = {
                'question': item.get('question', {}).get(lang, item.get('question', {}).get('en', '')),
                'answer': item.get('answer', {}).get(lang, item.get('answer', {}).get('en', ''))
            }
            localized_items.append(localized_item)
        return localized_items

    def _get_language(self):
        request = self.context.get('request')
        if request and hasattr(request, 'query_params'):
            return request.query_params.get('lang', 'en')
        return 'en'


class HelpArticleAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin CRUD - returns raw JSON fields"""

    class Meta:
        model = HelpArticle
        fields = '__all__'
