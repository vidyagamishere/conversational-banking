"""Test script for new API endpoints following SampleRequest-Response format."""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"


def test_login():
    """Test 1: Login Phase"""
    print("\n" + "="*50)
    print("TEST 1: LOGIN PHASE")
    print("="*50)
    
    request_data = {
        "ClientId": "ATM123",
        "ClientRequestNumber": "REQ001",
        "ClientRequestTime": "2026-01-07T07:42:00Z",
        "ClientUniqueHardwareId": "HW987654",
        "ConsumerIdentificationData": {
            "Track2": "1234567890123456=26012010000000000000",
            "EMVTags": ["9F02", "5F2A"],
            "ManualDataType": "EMV"
        }
    }
    
    print("\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    response = requests.post(f"{BASE_URL}/auth/login", json=request_data)
    print("\nResponse Status:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def test_preferences():
    """Test 2: Preferences Phase"""
    print("\n" + "="*50)
    print("TEST 2: PREFERENCES PHASE")
    print("="*50)
    
    request_data = {
        "ClientId": "ATM123",
        "ClientRequestNumber": "REQ002",
        "ClientRequestTime": "2026-01-07T07:43:00Z",
        "ClientUniqueHardwareId": "HW987654",
        "CardPosition": "Inserted",
        "Preferences": {
            "Language": "EN",
            "EmailID": "user@example.com",
            "ReceiptPreference": "Email",
            "FastCashPreference": True
        }
    }
    
    print("\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    response = requests.post(f"{BASE_URL}/preferences", json=request_data)
    print("\nResponse Status:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def test_pin_validation():
    """Test 3: PIN Validation + Account Overview"""
    print("\n" + "="*50)
    print("TEST 3: PIN VALIDATION + ACCOUNT OVERVIEW")
    print("="*50)
    
    request_data = {
        "ClientId": "ATM123",
        "ClientRequestNumber": "REQ003",
        "EncryptedPinData": "ABCD1234XYZ",
        "EmvAuthorizeRequestData": {
            "Tag57": "value",
            "Tag5FA": "value"
        },
        "Breadcrumb": "Step3"
    }
    
    print("\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    response = requests.post(f"{BASE_URL}/auth/pin-validation", json=request_data)
    print("\nResponse Status:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def test_account_overview_finalize():
    """Test 4: Account Overview Finalization"""
    print("\n" + "="*50)
    print("TEST 4: ACCOUNT OVERVIEW FINALIZATION")
    print("="*50)
    
    request_data = {
        "ClientId": "ATM123",
        "ClientRequestNumber": "REQ004",
        "ClientRequestTime": "2026-01-07T07:44:00Z",
        "ClientUniqueHardwareId": "HW987654",
        "CardPosition": "Inserted",
        "ClientTransactionResult": "Confirmed",
        "AccountingState": "Final",
        "CardUpdateState": "NoUpdate",
        "EmvFinalizeRequestData": {
            "Tags": ["9F02", "5F2A"]
        }
    }
    
    print("\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    response = requests.post(f"{BASE_URL}/account-overview/finalize", json=request_data)
    print("\nResponse Status:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def test_withdrawal():
    """Test 5: Withdrawal Authorization"""
    print("\n" + "="*50)
    print("TEST 5: WITHDRAWAL AUTHORIZATION")
    print("="*50)
    
    request_data = {
        "ClientId": "ATM123",
        "ClientRequestNumber": "REQ005",
        "ClientRequestTime": "2026-01-07T07:45:00Z",
        "ClientUniqueHardwareId": "HW987654",
        "CardPosition": "Inserted",
        "HostTransactionNumber": "TXN123456",
        "EncryptedPinData": "ABCD1234XYZ",
        "EmvAuthorizeRequestData": {
            "Tag57": "value",
            "Tag5FA": "value"
        },
        "CardTechnology": "EMV",
        "SourceAccount": {
            "Number": "9876543210",
            "Type": "SAV",
            "Subtype": "Regular"
        },
        "RequestedAmount": 100,
        "Currency": "USD"
    }
    
    print("\nRequest:")
    print(json.dumps(request_data, indent=2))
    
    response = requests.post(f"{BASE_URL}/transactions/withdrawal/authorize", json=request_data)
    print("\nResponse Status:", response.status_code)
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.json()


def main():
    """Run all tests in sequence."""
    print("\n" + "="*80)
    print("TESTING NEW API ENDPOINTS - CONVERSATIONAL BANKING")
    print("="*80)
    
    try:
        # Test all phases in sequence
        test_login()
        test_preferences()
        test_pin_validation()
        test_account_overview_finalize()
        test_withdrawal()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*80 + "\n")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to the backend server.")
        print("Please make sure the backend is running on http://localhost:8000")
        print("Start it with: uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    main()
