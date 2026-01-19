import pytest
from fastapi.testclient import TestClient
import json

def test_create_account(client, sample_account_data):
    """Test POST /accounts endpoint"""
    response = client.post("/api/v1/accounts/", json=sample_account_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["user_id"] == sample_account_data["user_id"]
    assert data["account_type"] == sample_account_data["account_type"]
    assert data["currency"] == sample_account_data["currency"]
    assert data["status"] == "active"
    assert data["balance"] == 0.0
    assert "id" in data

def test_create_account_invalid_data(client):
    """Test POST /accounts with invalid data"""
    invalid_data = {
        "user_id": "test",
        "account_type": "invalid_type",  # Invalid
        "currency": "USD"
    }
    
    response = client.post("/api/v1/accounts/", json=invalid_data)
    assert response.status_code == 400

def test_get_account(client, sample_account_data):
    """Test GET /accounts/{account_id} endpoint"""
    # First create an account
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    # Then retrieve it
    response = client.get(f"/api/v1/accounts/{account_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == account_id
    assert data["user_id"] == sample_account_data["user_id"]
    assert data["balance"] == 0.0

def test_get_nonexistent_account(client):
    """Test GET /accounts/{account_id} with non-existent account"""
    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    response = client.get(f"/api/v1/accounts/{fake_id}")
    
    assert response.status_code == 404

def test_get_account_invalid_uuid(client):
    """Test GET /accounts/{account_id} with invalid UUID"""
    response = client.get("/api/v1/accounts/invalid-uuid")
    assert response.status_code == 400

def test_get_account_ledger(client, sample_account_data):
    """Test GET /accounts/{account_id}/ledger endpoint"""
    # Create account
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    # Make a deposit to create ledger entry
    deposit_data = {
        "account_id": account_id,
        "amount": 100.00,
        "currency": "USD",
        "description": "Test deposit"
    }
    client.post("/api/v1/deposits", json=deposit_data)
    
    # Get ledger
    response = client.get(f"/api/v1/accounts/{account_id}/ledger")
    
    assert response.status_code == 200
    ledger = response.json()
    
    assert isinstance(ledger, list)
    assert len(ledger) == 1
    assert ledger[0]["account_id"] == account_id
    assert ledger[0]["entry_type"] == "credit"
    assert ledger[0]["amount"] == 100.00

def test_execute_transfer_success(client, sample_account_data):
    """Test POST /transfers endpoint - successful transfer"""
    # Create source account
    source_account = sample_account_data.copy()
    source_account["user_id"] = "sender_123"
    create_source = client.post("/api/v1/accounts/", json=source_account)
    source_account_id = create_source.json()["id"]
    
    # Create destination account
    dest_account = sample_account_data.copy()
    dest_account["user_id"] = "receiver_456"
    create_dest = client.post("/api/v1/accounts/", json=dest_account)
    dest_account_id = create_dest.json()["id"]
    
    # Deposit money to source account
    deposit_data = {
        "account_id": source_account_id,
        "amount": 500.00,
        "currency": "USD"
    }
    client.post("/api/v1/deposits", json=deposit_data)
    
    # Execute transfer
    transfer_data = {
        "source_account_id": source_account_id,
        "destination_account_id": dest_account_id,
        "amount": 200.50,
        "currency": "USD",
        "description": "Test transfer payment"
    }
    
    response = client.post("/api/v1/transfers/", json=transfer_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["type"] == "transfer"
    assert data["status"] == "completed"
    assert data["amount"] == 200.50
    assert data["currency"] == "USD"
    
    # Verify balances
    source_response = client.get(f"/api/v1/accounts/{source_account_id}")
    dest_response = client.get(f"/api/v1/accounts/{dest_account_id}")
    
    assert source_response.json()["balance"] == 299.50  # 500 - 200.50
    assert dest_response.json()["balance"] == 200.50

def test_execute_transfer_insufficient_funds(client, sample_account_data):
    """Test POST /transfers with insufficient funds"""
    # Create accounts
    source_account = sample_account_data.copy()
    source_account["user_id"] = "poor_sender"
    create_source = client.post("/api/v1/accounts/", json=source_account)
    source_account_id = create_source.json()["id"]
    
    dest_account = sample_account_data.copy()
    dest_account["user_id"] = "rich_receiver"
    create_dest = client.post("/api/v1/accounts/", json=dest_account)
    dest_account_id = create_dest.json()["id"]
    
    # Try to transfer without funds
    transfer_data = {
        "source_account_id": source_account_id,
        "destination_account_id": dest_account_id,
        "amount": 100.00,
        "currency": "USD"
    }
    
    response = client.post("/api/v1/transfers/", json=transfer_data)
    
    assert response.status_code == 422  # Unprocessable Entity
    assert "Insufficient funds" in response.json()["detail"]

def test_execute_transfer_same_account(client, sample_account_data):
    """Test POST /transfers to same account"""
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    transfer_data = {
        "source_account_id": account_id,
        "destination_account_id": account_id,  # Same account
        "amount": 100.00,
        "currency": "USD"
    }
    
    response = client.post("/api/v1/transfers/", json=transfer_data)
    
    assert response.status_code == 400
    assert "cannot be the same" in response.json()["detail"].lower()

def test_execute_deposit(client, sample_account_data):
    """Test POST /deposits endpoint"""
    # Create account
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    # Execute deposit
    deposit_data = {
        "account_id": account_id,
        "amount": 750.25,
        "currency": "USD",
        "description": "Salary deposit"
    }
    
    response = client.post("/api/v1/deposits", json=deposit_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["type"] == "deposit"
    assert data["status"] == "completed"
    assert data["amount"] == 750.25
    
    # Verify balance
    account_response = client.get(f"/api/v1/accounts/{account_id}")
    assert account_response.json()["balance"] == 750.25

def test_execute_deposit_invalid_account(client):
    """Test POST /deposits with invalid account"""
    fake_id = "123e4567-e89b-12d3-a456-426614174000"
    
    deposit_data = {
        "account_id": fake_id,
        "amount": 100.00,
        "currency": "USD"
    }
    
    response = client.post("/api/v1/deposits", json=deposit_data)
    assert response.status_code == 400

def test_execute_withdrawal_success(client, sample_account_data):
    """Test POST /withdrawals endpoint - successful withdrawal"""
    # Create account
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    # First deposit money
    deposit_data = {
        "account_id": account_id,
        "amount": 1000.00,
        "currency": "USD"
    }
    client.post("/api/v1/deposits", json=deposit_data)
    
    # Then withdraw
    withdrawal_data = {
        "account_id": account_id,
        "amount": 350.75,
        "currency": "USD",
        "description": "ATM withdrawal"
    }
    
    response = client.post("/api/v1/withdrawals", json=withdrawal_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["type"] == "withdrawal"
    assert data["status"] == "completed"
    assert data["amount"] == 350.75
    
    # Verify balance
    account_response = client.get(f"/api/v1/accounts/{account_id}")
    assert account_response.json()["balance"] == 649.25  # 1000 - 350.75

def test_execute_withdrawal_insufficient_funds(client, sample_account_data):
    """Test POST /withdrawals with insufficient funds"""
    create_response = client.post("/api/v1/accounts/", json=sample_account_data)
    account_id = create_response.json()["id"]
    
    withdrawal_data = {
        "account_id": account_id,
        "amount": 100.00,
        "currency": "USD"
    }
    
    response = client.post("/api/v1/withdrawals", json=withdrawal_data)
    
    assert response.status_code == 422  # Unprocessable Entity
    assert "Insufficient funds" in response.json()["detail"]

def test_get_user_accounts(client, sample_account_data):
    """Test GET /accounts/user/{user_id}/accounts endpoint"""
    user_id = "multi_account_user"
    
    # Create multiple accounts for same user
    for i in range(3):
        account_data = sample_account_data.copy()
        account_data["user_id"] = user_id
        account_data["account_type"] = ["checking", "savings", "business"][i]
        client.post("/api/v1/accounts/", json=account_data)
    
    # Get user accounts
    response = client.get(f"/api/v1/accounts/user/{user_id}/accounts")
    
    assert response.status_code == 200
    accounts = response.json()
    
    assert len(accounts) == 3
    assert all(acc["user_id"] == user_id for acc in accounts)
    account_types = [acc["account_type"] for acc in accounts]
    assert "checking" in account_types
    assert "savings" in account_types
    assert "business" in account_types

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_api_documentation(client):
    """Test API documentation endpoints"""
    response = client.get("/docs")
    assert response.status_code == 200
    
    response = client.get("/redoc")
    assert response.status_code == 200

def test_concurrent_api_requests(client, sample_account_data):
    """Test concurrent API requests"""
    import threading
    import time
    
    # Create account with initial balance
    account_data = sample_account_data.copy()
    create_response = client.post("/api/v1/accounts/", json=account_data)
    account_id = create_response.json()["id"]
    
    # Initial deposit
    client.post("/api/v1/deposits", json={
        "account_id": account_id,
        "amount": 1000.00,
        "currency": "USD"
    })
    
    results = []
    
    def make_withdrawal(amount):
        try:
            response = client.post("/api/v1/withdrawals", json={
                "account_id": account_id,
                "amount": amount,
                "currency": "USD"
            })
            results.append((amount, response.status_code))
        except Exception as e:
            results.append((amount, str(e)))
    
    # Create concurrent withdrawal requests
    threads = []
    amounts = [100.00, 200.00, 300.00, 400.00]  # Total: 1000
    
    for amount in amounts:
        thread = threading.Thread(target=make_withdrawal, args=(amount,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Check that not all succeeded (should have some failures due to insufficient funds)
    status_codes = [result[1] for result in results]
    
    # Some should be 201 (success), some should be 422 (insufficient funds)
    assert 201 in status_codes
    assert 422 in status_codes
    
    # Verify final balance is not negative
    account_response = client.get(f"/api/v1/accounts/{account_id}")
    final_balance = account_response.json()["balance"]
    assert final_balance >= 0
