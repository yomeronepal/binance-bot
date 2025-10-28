#!/usr/bin/env python3
"""
Test script for API endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    print("=" * 50)
    print("Testing Health Check Endpoint")
    print("=" * 50)
    response = requests.get(f"{BASE_URL}/api/health/")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_user_registration():
    """Test user registration"""
    print("=" * 50)
    print("Testing User Registration")
    print("=" * 50)
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123!",
        "password2": "TestPass123!"
    }
    response = requests.post(f"{BASE_URL}/api/users/register/", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_user_login():
    """Test user login"""
    print("=" * 50)
    print("Testing User Login")
    print("=" * 50)
    data = {
        "username": "testuser",
        "password": "TestPass123!"
    }
    response = requests.post(f"{BASE_URL}/api/users/login/", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 200:
        tokens = response.json()
        return tokens
    print()
    return None

def test_user_profile(access_token):
    """Test getting user profile"""
    print("=" * 50)
    print("Testing User Profile (Protected Endpoint)")
    print("=" * 50)
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(f"{BASE_URL}/api/users/profile/", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Binance Bot API Tests")
    print("=" * 50 + "\n")

    # Test health check
    test_health_check()

    # Test registration
    test_user_registration()

    # Test login
    tokens = test_user_login()

    # Test protected endpoint if login was successful
    if tokens and 'access' in tokens:
        test_user_profile(tokens['access'])

    print("=" * 50)
    print("All tests completed!")
    print("=" * 50)
