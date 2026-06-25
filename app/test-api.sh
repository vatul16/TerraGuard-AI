#!/bin/bash

BASE_URL="http://localhost:3000/api"

echo "=== Testing TerraGuard API ==="
echo

echo "1. Health Check"
curl -s $BASE_URL/health | jq
echo
echo

echo "2. Get all users"
curl -s $BASE_URL/users | jq
echo
echo

echo "3. Create new user"
curl -s -X POST $BASE_URL/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice Cooper","email":"alice@example.com"}' | jq
echo
echo

echo "4. Get user by ID"
curl -s $BASE_URL/users/1 | jq
echo
echo

echo "5. Update user"
curl -s -X PUT $BASE_URL/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name":"Johnathan Doe","email":"john.doe@example.com"}' | jq
echo
echo

echo "6. Delete user"
curl -s -X DELETE $BASE_URL/users/3 | jq
echo
echo

echo "=== API Test Complete ==="