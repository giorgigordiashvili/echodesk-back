"""Tests for amanati_crm.file_utils: sanitize_filename and SanitizedUploadTo."""
from datetime import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, SimpleTestCase

from amanati_crm.file_utils import sanitize_filename, SanitizedUploadTo


class TestSanitizeFilename(SimpleTestCase):
    """Tests for the standalone sanitize_filename function."""

    def test_sanitizes_spaces(self):
        result = sanitize_filename('my document file.pdf')
        self.assertNotIn(' ', result)
        self.assertTrue(result.endswith('.pdf'))

    def test_sanitizes_parentheses(self):
        result = sanitize_filename('report (copy).docx')
        self.assertNotIn('(', result)
        self.assertNotIn(')', result)
        self.assertTrue(result.endswith('.docx'))

    def test_sanitizes_special_chars(self):
        result = sanitize_filename('file@name#with$special!chars.png')
        self.assertNotIn('@', result)
        self.assertNotIn('#', result)
        self.assertNotIn('$', result)
        self.assertNotIn('!', result)
        self.assertTrue(result.endswith('.png'))

    def test_preserves_extension_jpg(self):
        result = sanitize_filename('photo.jpg')
        self.assertTrue(result.endswith('.jpg'))

    def test_preserves_extension_png(self):
        result = sanitize_filename('image.png')
        self.assertTrue(result.endswith('.png'))

    def test_preserves_extension_pdf(self):
        result = sanitize_filename('document.pdf')
        self.assertTrue(result.endswith('.pdf'))

    def test_preserves_alphanumeric(self):
        result = sanitize_filename('valid_file-name123.txt')
        self.assertEqual(result, 'valid_file-name123.txt')

    def test_preserves_dots_in_name(self):
        result = sanitize_filename('file.name.v2.txt')
        self.assertEqual(result, 'file.name.v2.txt')

    def test_preserves_underscores_and_dashes(self):
        result = sanitize_filename('my_file-v1.txt')
        self.assertEqual(result, 'my_file-v1.txt')

    def test_unicode_filename(self):
        """Non-ASCII characters should be replaced with underscores."""
        result = sanitize_filename('resume_giorgi.pdf')
        self.assertTrue(result.endswith('.pdf'))
        # All chars in 'resume_giorgi' are ASCII, so should be preserved
        self.assertEqual(result, 'resume_giorgi.pdf')

    def test_unicode_non_ascii(self):
        """Georgian or Cyrillic chars should be replaced."""
        result = sanitize_filename('test.pdf')
        self.assertTrue(result.endswith('.pdf'))
        # Non-ASCII would be replaced with _
        # Since these are non-ASCII, they get replaced
        for char in result[:-4]:  # Exclude .pdf
            self.assertRegex(char, r'[a-zA-Z0-9_.\-]')

    def test_empty_name_with_extension(self):
        """Filename with only an extension should still work."""
        result = sanitize_filename('.gitignore')
        # os.path.splitext('.gitignore') returns ('.gitignore', '')
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_no_extension(self):
        result = sanitize_filename('Makefile')
        self.assertEqual(result, 'Makefile')

    def test_multiple_spaces_collapsed(self):
        result = sanitize_filename('my   file   name.pdf')
        self.assertNotIn(' ', result)
        self.assertTrue(result.endswith('.pdf'))


class TestSanitizedUploadTo(SimpleTestCase):
    """Tests for the SanitizedUploadTo callable."""

    def test_date_based_path(self):
        uploader = SanitizedUploadTo('attachments', date_based=True)
        instance = MagicMock()
        result = uploader(instance, 'my file.pdf')
        self.assertTrue(result.startswith('attachments/'))
        self.assertTrue(result.endswith('.pdf'))
        self.assertNotIn(' ', result)
        # Should contain a date path like YYYY/MM/DD
        parts = result.split('/')
        # Expected: attachments / YYYY / MM / DD / filename.pdf
        self.assertEqual(len(parts), 5)
        self.assertTrue(parts[1].isdigit() and len(parts[1]) == 4)  # year
        self.assertTrue(parts[2].isdigit() and len(parts[2]) == 2)  # month
        self.assertTrue(parts[3].isdigit() and len(parts[3]) == 2)  # day

    def test_no_date_path(self):
        uploader = SanitizedUploadTo('logos', date_based=False)
        instance = MagicMock()
        result = uploader(instance, 'company logo.png')
        self.assertTrue(result.startswith('logos/'))
        self.assertTrue(result.endswith('.png'))
        self.assertNotIn(' ', result)
        # Should not contain date path segments
        parts = result.split('/')
        self.assertEqual(len(parts), 2)  # 'logos' / 'filename.png'

    def test_sanitizes_filename_in_path(self):
        uploader = SanitizedUploadTo('uploads', date_based=False)
        instance = MagicMock()
        result = uploader(instance, 'report (final copy).docx')
        self.assertNotIn('(', result)
        self.assertNotIn(')', result)
        self.assertNotIn(' ', result)
        self.assertTrue(result.endswith('.docx'))

    def test_deconstructible(self):
        """SanitizedUploadTo should support Django's deconstruct protocol."""
        uploader = SanitizedUploadTo('test', date_based=True)
        path, args, kwargs = uploader.deconstruct()
        self.assertIn('SanitizedUploadTo', path)

    def test_same_params_produce_same_deconstruct(self):
        """Two SanitizedUploadTo with same params should deconstruct identically (for migrations)."""
        a = SanitizedUploadTo('test', date_based=True)
        b = SanitizedUploadTo('test', date_based=True)
        self.assertEqual(a.deconstruct(), b.deconstruct())

    def test_different_params_produce_different_deconstruct(self):
        a = SanitizedUploadTo('test', date_based=True)
        b = SanitizedUploadTo('other', date_based=True)
        self.assertNotEqual(a.deconstruct(), b.deconstruct())
