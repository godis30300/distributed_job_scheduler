from django.test import TestCase, Client, override_settings
from django.urls import reverse

@override_settings(DEMO_MODE=True)
class FrontendTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Mock login for protected views
        session = self.client.session
        session['token'] = 'mock-token'
        session['username'] = 'testuser'
        session.save()

    def test_login_page_load(self):
        """Test if the login page loads correctly."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login")

    def test_demo_login_post(self):
        """Test if login works in demo mode."""
        self.client.session.flush()
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'anypassword'
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(self.client.session['username'], 'testuser')
        self.assertTrue('token' in self.client.session)

    def test_demo_register_post(self):
        """Test if registration works in demo mode."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('login'))
        # Check if demo_users was updated in session
        self.assertIn('newuser', self.client.session.get('demo_users', {}))

    def test_dashboard_page_load(self):
        """Test if the dashboard page loads correctly."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Jobs")

    def test_job_list_page_load(self):
        """Test if the job list page loads correctly."""
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job List")

    def test_job_create_page_load(self):
        """Test if the job creation page loads correctly."""
        response = self.client.get(reverse('job_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Job")
        self.assertContains(response, "task_name")

    def test_job_detail_and_edit_pages_load(self):
        """Test if the job detail and edit pages load correctly using a real demo job ID."""
        # First, trigger demo data generation by visiting job list
        self.client.get(reverse('job_list'))
        
        # Get a valid job ID from the session
        demo_jobs = self.client.session.get('demo_jobs', [])
        self.assertTrue(len(demo_jobs) > 0, "Demo jobs should be initialized")
        job_id = demo_jobs[0]['id']
        
        # Test Detail page
        response = self.client.get(reverse('job_detail', args=[job_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Detail")
        
        # Test Edit page
        response = self.client.get(reverse('job_edit', args=[job_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Job")

    def test_job_runs_page_load(self):
        """Test if the job runs page loads correctly."""
        response = self.client.get(reverse('job_runs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Runs")

    def test_partial_views_load(self):
        """Test if the partial list views (used for AJAX/HTMX) load correctly."""
        # Job list partial
        response = self.client.get(reverse('job_list_partial'))
        self.assertEqual(response.status_code, 200)
        
        # Job runs partial
        response = self.client.get(reverse('job_runs_partial'))
        self.assertEqual(response.status_code, 200)

    def test_health_page_load(self):
        """Test if the health page loads correctly."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Health")

    def test_logout_behavior(self):
        """Test if logout flushes session and redirects to login."""
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('token', self.client.session)

    def test_unauthenticated_access(self):
        """Test if unauthenticated users are redirected to login."""
        self.client.session.flush()
        
        # Full pages should redirect
        redirect_urls = ['dashboard', 'job_list', 'job_create', 'job_runs']
        for url_name in redirect_urls:
            response = self.client.get(reverse(url_name))
            self.assertRedirects(response, reverse('login'))
        
        # Partial views should return empty content (200 OK)
        partial_urls = ['job_list_partial', 'job_runs_partial']
        for url_name in partial_urls:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content.decode(), '')
