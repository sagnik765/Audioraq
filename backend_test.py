import requests
import sys
import json
import os
from datetime import datetime

class PodcastHubAPITester:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("AUDIORAQ_API_URL", "http://127.0.0.1:8001/api")
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.user_token = None
        self.podcaster_token = None
        self.admin_token = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
        
        # Remove Content-Type for file uploads
        if files:
            test_headers.pop('Content-Type', None)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers)
            elif method == 'POST':
                if files:
                    response = self.session.post(url, data=data, files=files, headers=test_headers)
                else:
                    response = self.session.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n" + "="*50)
        print("TESTING AUTHENTICATION ENDPOINTS")
        print("="*50)
        
        # Test user registration
        user_data = {
            "email": "testuser@test.com",
            "password": "test123",
            "name": "Test User",
            "role": "user",
            "phone": "+1234567890",
            "interests": ["technology", "science", "business"]
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=user_data
        )
        
        if success and 'access_token' in response:
            self.user_token = response['access_token']
            print(f"   User token obtained: {self.user_token[:20]}...")

        # Test podcaster registration
        podcaster_data = {
            "email": "podcaster@test.com",
            "password": "test123",
            "name": "Test Podcaster",
            "role": "podcaster",
            "phone": "+1234567891",
            "podcast_description": "A technology podcast about AI and machine learning innovations"
        }
        
        success, response = self.run_test(
            "Podcaster Registration",
            "POST",
            "auth/register",
            200,
            data=podcaster_data
        )
        
        if success and 'access_token' in response:
            self.podcaster_token = response['access_token']
            print(f"   Podcaster token obtained: {self.podcaster_token[:20]}...")

        # Test admin login
        admin_data = {
            "email": "admin@podcasthub.com",
            "password": "admin123"
        }
        
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data=admin_data
        )
        
        if success and 'access_token' in response:
            self.admin_token = response['access_token']
            print(f"   Admin token obtained: {self.admin_token[:20]}...")

        # Test /auth/me endpoint
        if self.user_token:
            self.run_test(
                "Get Current User",
                "GET",
                "auth/me",
                200,
                headers={'Authorization': f'Bearer {self.user_token}'}
            )

        # Test logout
        self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200
        )

    def test_interest_endpoints(self):
        """Test interest-related endpoints"""
        print("\n" + "="*50)
        print("TESTING INTEREST ENDPOINTS")
        print("="*50)
        
        # Test get interest options
        self.run_test(
            "Get Interest Options",
            "GET",
            "interests/options",
            200
        )

    def test_podcast_endpoints(self):
        """Test podcast-related endpoints"""
        print("\n" + "="*50)
        print("TESTING PODCAST ENDPOINTS")
        print("="*50)
        
        # Test get all podcasts
        self.run_test(
            "Get All Podcasts",
            "GET",
            "podcasts",
            200
        )

        # Test get podcasts with search
        self.run_test(
            "Search Podcasts",
            "GET",
            "podcasts?search=technology",
            200
        )

        # Test get podcasts with category filter
        self.run_test(
            "Filter Podcasts by Category",
            "GET",
            "podcasts?category=technology",
            200
        )

        # Test get categories
        self.run_test(
            "Get Categories",
            "GET",
            "categories",
            200
        )

        # Test get trending podcasts
        self.run_test(
            "Get Trending Podcasts",
            "GET",
            "trending",
            200
        )

        # Test get my podcasts (requires podcaster auth)
        if self.podcaster_token:
            self.run_test(
                "Get My Podcasts",
                "GET",
                "podcasts/my",
                200,
                headers={'Authorization': f'Bearer {self.podcaster_token}'}
            )

    def test_recommendation_endpoints(self):
        """Test recommendation endpoints"""
        print("\n" + "="*50)
        print("TESTING RECOMMENDATION ENDPOINTS")
        print("="*50)
        
        # Test get recommendations (requires user auth)
        if self.user_token:
            self.run_test(
                "Get Recommendations",
                "GET",
                "recommendations",
                200,
                headers={'Authorization': f'Bearer {self.user_token}'}
            )

    def test_upload_functionality(self):
        """Test podcast upload functionality"""
        print("\n" + "="*50)
        print("TESTING UPLOAD FUNCTIONALITY")
        print("="*50)
        
        if not self.podcaster_token:
            print("❌ Skipping upload tests - no podcaster token")
            return

        # Create a small test audio file content
        test_audio_content = b"fake audio content for testing"
        
        # Test podcast upload
        files = {
            'file': ('test_podcast.mp3', test_audio_content, 'audio/mpeg')
        }
        
        form_data = {
            'title': 'Test Podcast Episode',
            'description': 'This is a test podcast episode for API testing',
            'category': 'technology'
        }
        
        success, response = self.run_test(
            "Upload Podcast",
            "POST",
            "podcasts/upload",
            200,
            data=form_data,
            files=files,
            headers={'Authorization': f'Bearer {self.podcaster_token}'}
        )
        
        if success and 'id' in response:
            podcast_id = response['id']
            print(f"   Uploaded podcast ID: {podcast_id}")
            
            # Test get specific podcast
            self.run_test(
                "Get Specific Podcast",
                "GET",
                f"podcasts/{podcast_id}",
                200
            )
            
            # Test record view
            if self.user_token:
                self.run_test(
                    "Record Podcast View",
                    "POST",
                    f"podcasts/{podcast_id}/view",
                    200,
                    headers={'Authorization': f'Bearer {self.user_token}'}
                )

    def test_error_cases(self):
        """Test error handling"""
        print("\n" + "="*50)
        print("TESTING ERROR CASES")
        print("="*50)
        
        # Test invalid login
        self.run_test(
            "Invalid Login",
            "POST",
            "auth/login",
            401,
            data={"email": "invalid@test.com", "password": "wrongpass"}
        )

        # Test duplicate registration
        self.run_test(
            "Duplicate Registration",
            "POST",
            "auth/register",
            400,
            data={
                "email": "testuser@test.com",
                "password": "test123",
                "name": "Duplicate User",
                "role": "user"
            }
        )

        # Test unauthorized access
        self.run_test(
            "Unauthorized Access to My Podcasts",
            "GET",
            "podcasts/my",
            401
        )

        # Test non-existent podcast
        self.run_test(
            "Get Non-existent Podcast",
            "GET",
            "podcasts/non-existent-id",
            404
        )

def main():
    print("🎙️ PodcastHub API Testing Suite")
    print("=" * 60)
    
    tester = PodcastHubAPITester()
    
    # Run all test suites
    tester.test_auth_endpoints()
    tester.test_interest_endpoints()
    tester.test_podcast_endpoints()
    tester.test_recommendation_endpoints()
    tester.test_upload_functionality()
    tester.test_error_cases()
    
    # Print final results
    print("\n" + "="*60)
    print("📊 FINAL TEST RESULTS")
    print("="*60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
