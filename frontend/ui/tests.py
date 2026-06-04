from django.test import TestCase, Client
from django.urls import reverse

class BasicFrontendTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_login_page_load(self):
        """Test if the login page loads correctly."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login")

    def test_register_page_load(self):
        """Test if the register page loads correctly."""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register")
