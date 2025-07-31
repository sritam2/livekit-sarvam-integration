#!/usr/bin/env python3
"""
Debug script to show what the OAuth file contains and how it's read.
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow

def show_oauth_file_contents():
    """Show what's inside the OAuth credentials file."""
    print("🔍 Reading credentials_OAuthClient.json...")
    
    # Method 1: Read raw JSON
    with open('credentials_OAuthClient.json', 'r') as f:
        raw_data = json.load(f)
    
    print("\n📄 Raw JSON structure:")
    print(json.dumps(raw_data, indent=2))
    
    # Method 2: Show what InstalledAppFlow extracts
    print("\n🔧 What InstalledAppFlow extracts:")
    
    try:
        # This is how our OAuth code reads it
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials_OAuthClient.json', 
            ['https://www.googleapis.com/auth/calendar']
        )
        
        # Access the client config that flow extracted
        client_config = flow.client_config
        
        print(f"✅ Client ID: {client_config['client_id']}")
        print(f"✅ Project ID: {client_config.get('project_id', 'N/A')}")
        print(f"✅ Auth URI: {client_config['auth_uri']}")
        print(f"✅ Token URI: {client_config['token_uri']}")
        print(f"✅ Client Secret: {client_config['client_secret'][:10]}...*** (hidden)")
        print(f"✅ Redirect URIs: {client_config.get('redirect_uris', [])}")
        
        print("\n🎯 OAuth Flow Configuration:")
        # Access scopes from the flow's OAuth2 session
        scopes = ['https://www.googleapis.com/auth/calendar']  # The scopes we passed in
        print(f"   Scopes: {scopes}")
        print(f"   Flow Type: Installed App (Desktop)")
        print(f"   Ready for OAuth consent: ✅")
        
    except Exception as e:
        print(f"❌ Error reading OAuth file: {e}")

def compare_with_service_account():
    """Compare OAuth file vs Service Account file structure."""
    print("\n" + "="*60)
    print("📊 COMPARISON: OAuth vs Service Account")
    print("="*60)
    
    # OAuth structure
    print("\n🔐 OAuth 2.0 Client (credentials_OAuthClient.json):")
    print("   ├── client_id (public identifier)")
    print("   ├── client_secret (private key)")
    print("   ├── redirect_uris (where to return after auth)")
    print("   ├── auth_uri (Google's OAuth consent page)")
    print("   └── token_uri (where to get access tokens)")
    print("   ➤ REQUIRES: User consent in browser")
    print("   ➤ RESULT: User-authorized access tokens")
    
    # Service Account structure  
    print("\n🤖 Service Account (credentials.json):")
    print("   ├── client_email (service account identity)")
    print("   ├── private_key (service account's private key)")
    print("   ├── project_id (Google Cloud project)")
    print("   └── type: 'service_account'")
    print("   ➤ REQUIRES: Manual calendar sharing")
    print("   ➤ RESULT: Direct server-to-server access")

if __name__ == "__main__":
    show_oauth_file_contents()
    compare_with_service_account()