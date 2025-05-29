import requests
import sys
import uuid
from datetime import datetime, timedelta

class QueBellaAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.invite_code = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
        self.test_password = "TestPass123!"
        self.test_name = "Test User"
        self.partner_email = f"partner_{uuid.uuid4().hex[:8]}@example.com"
        self.partner_password = "PartnerPass123!"
        self.partner_name = "Partner User"
        self.partner_token = None
        self.partner_id = None
        self.partner_invite_code = None

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        elif self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.text:
                    try:
                        return success, response.json()
                    except:
                        return success, response.text
                return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    try:
                        print(f"Response: {response.json()}")
                    except:
                        print(f"Response: {response.text}")
                return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test the health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        if success and response.get("status") == "healthy":
            print(f"Health check message: {response.get('message')}")
            return True
        return False

    def test_supabase_connection(self):
        """Test the Supabase connection endpoint"""
        success, response = self.run_test(
            "Supabase Connection Test",
            "GET",
            "api/test",
            200
        )
        if success and response.get("status") == "success":
            print(f"Supabase connection message: {response.get('message')}")
            return True
        return False

    def test_register(self, email, password, full_name):
        """Test user registration with Supabase Auth"""
        success, response = self.run_test(
            "User Registration",
            "POST",
            "api/register",
            200,
            data={"email": email, "password": password, "full_name": full_name}
        )
        if success and 'access_token' in response and 'user' in response:
            if email == self.test_email:
                self.token = response['access_token']
                self.user_id = response['user']['id']
                self.invite_code = response['user'].get('invite_code')
            else:
                self.partner_token = response['access_token']
                self.partner_id = response['user']['id']
                self.partner_invite_code = response['user'].get('invite_code')
            print(f"Registration message: {response.get('message')}")
            print(f"User ID: {response['user']['id']}")
            print(f"Email: {response['user']['email']}")
            return True
        return False

    def test_login(self, email, password):
        """Test user login with Supabase Auth"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "api/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response and 'user' in response:
            if email == self.test_email:
                self.token = response['access_token']
                self.user_id = response['user']['id']
                self.invite_code = response['user'].get('invite_code')
            else:
                self.partner_token = response['access_token']
                self.partner_id = response['user']['id']
                self.partner_invite_code = response['user'].get('invite_code')
            print(f"Login message: {response.get('message')}")
            print(f"User ID: {response['user']['id']}")
            print(f"Email: {response['user']['email']}")
            return True
        return False

def main():
    # Get the backend URL from the frontend .env file
    backend_url = "https://a98a75b8-b4a5-4aa7-bf3a-d704a14a3584.preview.emergentagent.com"
    
    # Setup
    tester = QueBellaAPITester(backend_url)
    
    print(f"\n🚀 Starting Que Bella API Tests with backend URL: {backend_url}")
    print(f"Testing Supabase-based backend implementation")
    
    # Test 1: Health Check
    if not tester.test_health_check():
        print("❌ Health check failed, stopping tests")
        return 1
    
    # Test 2: Supabase Connection
    if not tester.test_supabase_connection():
        print("❌ Supabase connection test failed, stopping tests")
        return 1
    
    # Test 3: User Registration (User 1)
    if not tester.test_register(tester.test_email, tester.test_password, tester.test_name):
        print("❌ User registration failed, stopping tests")
        return 1
    
    # Test 4: User Login (User 1)
    if not tester.test_login(tester.test_email, tester.test_password):
        print("❌ User login failed, stopping tests")
        return 1
    
    # Test 5: User Registration (User 2)
    if not tester.test_register(tester.partner_email, tester.partner_password, tester.partner_name):
        print("❌ Partner registration failed")
        return 1
    
    # Test 6: User Login (User 2)
    if not tester.test_login(tester.partner_email, tester.partner_password):
        print("❌ Partner login failed")
        return 1
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"\n✅ All Supabase-based backend tests passed successfully!")
    print(f"\n🔍 Summary:")
    print(f"  - Health check endpoint is working")
    print(f"  - Supabase connection is working")
    print(f"  - User registration with Supabase Auth is working")
    print(f"  - User login with Supabase Auth is working")
    print(f"  - Successfully registered and logged in two different users")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
