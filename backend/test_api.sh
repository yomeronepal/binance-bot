#!/bin/bash

echo "Testing Health Check..."
curl -s http://localhost:8000/api/health/
echo -e "\n"

echo "Testing User Registration..."
curl -s -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  --data-binary @- << EOF
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "TestPass123!",
  "password2": "TestPass123!"
}
EOF
echo -e "\n"

echo "Testing User Login..."
curl -s -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  --data-binary @- << EOF
{
  "username": "testuser",
  "password": "TestPass123!"
}
EOF
echo -e "\n"
