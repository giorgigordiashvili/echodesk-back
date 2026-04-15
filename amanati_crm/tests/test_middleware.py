"""Tests for amanati_crm middleware: BotBlockerMiddleware, EchoDeskTenantMiddleware."""
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.http import Http404, JsonResponse

from amanati_crm.middleware import BotBlockerMiddleware


class TestBotBlockerMiddleware(SimpleTestCase):
    """Tests for BotBlockerMiddleware which blocks suspicious requests."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = lambda request: JsonResponse({'ok': True})
        self.middleware = BotBlockerMiddleware(self.get_response)

    # ── Blocked extensions ──

    def test_blocks_php_files(self):
        request = self.factory.get('/admin.php')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_asp_files(self):
        request = self.factory.get('/page.asp')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_aspx_files(self):
        request = self.factory.get('/index.aspx')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_jsp_files(self):
        request = self.factory.get('/handler.jsp')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_cgi_files(self):
        request = self.factory.get('/script.cgi')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_exe_files(self):
        request = self.factory.get('/malware.exe')
        with self.assertRaises(Http404):
            self.middleware(request)

    # ── Blocked paths ──

    def test_blocks_wp_admin(self):
        request = self.factory.get('/wp-admin/')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_wp_login(self):
        request = self.factory.get('/wp-login.php')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_env_file(self):
        request = self.factory.get('/.env')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_git_directory(self):
        request = self.factory.get('/.git/config')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_phpmyadmin(self):
        request = self.factory.get('/phpmyadmin/')
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_shell_path(self):
        request = self.factory.get('/shell')
        with self.assertRaises(Http404):
            self.middleware(request)

    # ── /api without trailing slash ──

    def test_blocks_api_without_trailing_slash(self):
        request = self.factory.get('/api')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 404)

    def test_blocks_api_post_without_trailing_slash(self):
        request = self.factory.post('/api')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 404)

    # ── Allowed paths ──

    def test_allows_normal_api_endpoint(self):
        request = self.factory.get('/api/invoices/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_static_files(self):
        request = self.factory.get('/static/css/style.css')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_admin_page(self):
        request = self.factory.get('/admin/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_api_docs(self):
        request = self.factory.get('/api/docs/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    # ── Case insensitivity ──

    def test_blocks_php_case_insensitive(self):
        """Path is lowercased, so /Admin.PHP should be blocked."""
        request = self.factory.get('/Admin.PHP')
        # BotBlockerMiddleware lowercases the path
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_blocks_wp_admin_mixed_case(self):
        request = self.factory.get('/WP-ADMIN/')
        # Middleware lowercases: /wp-admin/ matches
        with self.assertRaises(Http404):
            self.middleware(request)


class TestRequestLoggingMiddleware(SimpleTestCase):
    """Tests for RequestLoggingMiddleware (only runs in DEBUG mode)."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=False)
    def test_no_logging_when_debug_false(self):
        """Middleware should be a passthrough when DEBUG=False."""
        from amanati_crm.middleware import RequestLoggingMiddleware
        get_response = lambda request: JsonResponse({'ok': True})
        middleware = RequestLoggingMiddleware(get_response)
        request = self.factory.get('/api/test/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_logging_active_when_debug_true(self):
        """Middleware should still return valid response when DEBUG=True."""
        from amanati_crm.middleware import RequestLoggingMiddleware
        get_response = lambda request: JsonResponse({'ok': True})
        middleware = RequestLoggingMiddleware(get_response)
        request = self.factory.get('/api/test/')
        request.META['HTTP_USER_AGENT'] = 'TestAgent'
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_get_client_ip_from_x_forwarded_for(self):
        from amanati_crm.middleware import RequestLoggingMiddleware
        middleware = RequestLoggingMiddleware(lambda r: JsonResponse({'ok': True}))
        request = self.factory.get('/api/test/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 192.168.1.1'
        ip = middleware.get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')

    @override_settings(DEBUG=True)
    def test_get_client_ip_from_remote_addr(self):
        from amanati_crm.middleware import RequestLoggingMiddleware
        middleware = RequestLoggingMiddleware(lambda r: JsonResponse({'ok': True}))
        request = self.factory.get('/api/test/')
        ip = middleware.get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

    @override_settings(DEBUG=True)
    def test_status_emoji_success(self):
        from amanati_crm.middleware import RequestLoggingMiddleware
        middleware = RequestLoggingMiddleware(lambda r: JsonResponse({'ok': True}))
        self.assertIsNotNone(middleware.get_status_emoji(200))
        self.assertIsNotNone(middleware.get_status_emoji(404))
        self.assertIsNotNone(middleware.get_status_emoji(500))
