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

    def test_register(self, email, password, name):
        """Test user registration"""
        success, response = self.run_test(
            "User Registration",
            "POST",
            "api/register",
            200,
            data={"email": email, "password": password, "name": name}
        )
        if success and 'token' in response and 'user' in response:
            if email == self.test_email:
                self.token = response['token']
                self.user_id = response['user']['id']
                self.invite_code = response['user']['invite_code']
            else:
                self.partner_token = response['token']
                self.partner_id = response['user']['id']
                self.partner_invite_code = response['user']['invite_code']
            return True
        return False

    def test_login(self, email, password):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "api/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'token' in response and 'user' in response:
            if email == self.test_email:
                self.token = response['token']
                self.user_id = response['user']['id']
                self.invite_code = response['user']['invite_code']
            else:
                self.partner_token = response['token']
                self.partner_id = response['user']['id']
                self.partner_invite_code = response['user']['invite_code']
            return True
        return False

    def test_get_profile(self):
        """Test getting user profile"""
        success, response = self.run_test(
            "Get User Profile",
            "GET",
            "api/me",
            200
        )
        return success

    def test_create_journal_entry(self, content, date, mood=None, token=None):
        """Test creating a journal entry"""
        success, response = self.run_test(
            "Create Journal Entry",
            "POST",
            "api/journal",
            200,
            data={"content": content, "date": date, "mood": mood},
            token=token
        )
        return success

    def test_create_mood_entry(self, mood, date):
        """Test creating a mood entry"""
        success, response = self.run_test(
            "Create Mood Entry",
            "POST",
            "api/mood",
            200,
            data={"mood": mood, "date": date}
        )
        return success

    def test_invite_partner(self, invite_code, token=None):
        """Test inviting a partner"""
        success, response = self.run_test(
            "Invite Partner",
            "POST",
            "api/invite-partner",
            200,
            data={"invite_code": invite_code},
            token=token
        )
        return success

    def test_get_calendar(self, month):
        """Test getting calendar data"""
        success, response = self.run_test(
            "Get Calendar Data",
            "GET",
            f"api/calendar/{month}",
            200
        )
        return success, response

    def test_generate_reflection(self, date):
        """Test generating an AI reflection"""
        success, response = self.run_test(
            "Generate AI Reflection",
            "POST",
            f"api/generate-reflection/{date}",
            200
        )
        return success, response

    def test_get_stats(self):
        """Test getting user stats"""
        success, response = self.run_test(
            "Get User Stats",
            "GET",
            "api/stats",
            200
        )
        return success, response

def main():
    # Get the backend URL from the frontend .env file
    backend_url = "https://6d305d83-b091-4c21-a014-6164b09ac846.preview.emergentagent.com"
    
    # Setup
    tester = QueBellaAPITester(backend_url)
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    current_month = datetime.now().strftime('%Y-%m')
    
    print(f"\n🚀 Starting Que Bella API Tests with backend URL: {backend_url}")
    
    # Test user registration
    if not tester.test_register(tester.test_email, tester.test_password, tester.test_name):
        print("❌ User registration failed, stopping tests")
        return 1
    
    # Test user login
    if not tester.test_login(tester.test_email, tester.test_password):
        print("❌ User login failed, stopping tests")
        return 1
    
    # Test getting user profile
    if not tester.test_get_profile():
        print("❌ Get user profile failed")
        return 1
    
    # Test creating journal entry
    if not tester.test_create_journal_entry("This is a test journal entry for today.", today, "Happy"):
        print("❌ Create journal entry failed")
        return 1
    
    # Test creating mood entry
    if not tester.test_create_mood_entry("Excited", today):
        print("❌ Create mood entry failed")
        return 1
    
    # Test getting calendar data
    success, calendar_data = tester.test_get_calendar(current_month)
    if not success:
        print("❌ Get calendar data failed")
        return 1
    
    # Test getting stats
    success, stats = tester.test_get_stats()
    if not success:
        print("❌ Get stats failed")
        return 1
    
    # Register partner user
    if not tester.test_register(tester.partner_email, tester.partner_password, tester.partner_name):
        print("❌ Partner registration failed")
        return 1
    
    # Test partner linking
    if not tester.test_invite_partner(tester.partner_invite_code):
        print("❌ Partner invitation failed")
        return 1
    
    # Create partner journal entry for the same day
    if not tester.test_create_journal_entry("This is a partner's journal entry for today.", today, "Loved", token=tester.partner_token):
        print("❌ Create partner journal entry failed")
        return 1
    
    # Test generating AI reflection
    success, reflection = tester.test_generate_reflection(today)
    if not success:
        print("❌ Generate AI reflection failed")
        return 1
    
    # Test getting updated calendar data
    success, updated_calendar = tester.test_get_calendar(current_month)
    if not success:
        print("❌ Get updated calendar data failed")
        return 1
    
    # Test getting updated stats
    success, updated_stats = tester.test_get_stats()
    if not success:
        print("❌ Get updated stats failed")
        return 1
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
