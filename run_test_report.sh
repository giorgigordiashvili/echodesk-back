#!/bin/bash

echo "========================================"
echo "   COMPREHENSIVE TEST REPORT"
echo "========================================"
echo ""

echo "1. TICKETS MODEL TESTS (42 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_models --verbosity=0 2>&1 | tail -3
echo ""

echo "2. TICKETS API TESTS (29 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_api --verbosity=0 2>&1 | tail -3
echo ""

echo "3. ECOMMERCE MODEL TESTS (25 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_models --verbosity=0 2>&1 | tail -3
echo ""

echo "4. ECOMMERCE API TESTS (15 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_api --verbosity=0 2>&1 | tail -3
echo ""

echo "5. ECOMMERCE AUTH TESTS (12 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_authentication --verbosity=0 2>&1 | tail -3
echo ""

echo "6. ECOMMERCE EMAIL TESTS (10 tests)"
echo "-----------------------------------"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_email --verbosity=0 2>&1 | tail -3
echo ""

echo "========================================"
echo "   OVERALL SUMMARY"
echo "========================================"
python3 manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests tickets.tests --verbosity=0 2>&1 | tail -5
echo ""
echo "========================================"
