#!/usr/bin/env python3

import requests
import json
import uuid
import re
import os
import random
from typing import Dict, Optional, Any, List

class TwitchSender:
    def __init__(self, token: str = None, integrity_token: str = None):
        self.base_url = "https://gql.twitch.tv/gql"
        self.session = requests.Session()
        self.token = token
        self.headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'de-DE',
            'Authorization': f'OAuth {token}',
            'Client-Id': 'kd1unb4b3q4t58fwlpcbzcbnm76a8fp',
            'Client-Version': '2bdd5859-f9bd-44a3-b05c-9e7d44598294',
            'Connection': 'keep-alive',
            'Content-Type': 'text/plain;charset=UTF-8',
            'Host': 'gql.twitch.tv',
            'Origin': 'https://www.twitch.tv',
            'Priority': 'u=0',
            'Referer': 'https://www.twitch.tv/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'TE': 'trailers',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Device-Id': 'gt9TuP8Tr8b6672DX11HwIq1xI8VHuYq'
        }
        self.query_hash = "0435464292cf380ed4b3d905e4edcb73078362e82c06367a5b2181c76c822fa2"
        
    def generate_nonce(self) -> str:
        return str(uuid.uuid4()).replace('-', '')
    
    def get_channel_id(self, username: str) -> Optional[str]:
        try:
            query = """
            query GetUser($login: String!) {
                user(login: $login) {
                    id
                    login
                    displayName
                }
            }
            """
            
            payload = {
                "query": query,
                "variables": {"login": username.lower()}
            }
            
            response = self.session.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if 'data' in response_data and 'user' in response_data['data'] and response_data['data']['user']:
                    user_id = response_data['data']['user']['id']
                    return str(user_id)
        except Exception:
            pass
        
        return None
    
    def send_message(self, channel_id: str, message: str) -> Dict[str, Any]:
        payload = {
            "operationName": "sendChatMessage",
            "variables": {
                "input": {
                    "channelID": channel_id,
                    "message": message,
                    "nonce": self.generate_nonce(),
                    "replyParentMessageID": None
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.query_hash
                }
            }
        }
        
        try:
            payload_string = json.dumps(payload)
            
            response = self.session.post(
                self.base_url,
                headers=self.headers,
                data=payload_string
            )
            
            response.raise_for_status()
            
            response_text = response.text
            content_encoding = response.headers.get('content-encoding', '').lower()
            
            if content_encoding in ['br', 'brotli']:
                try:
                    import brotli
                    decompressed_data = brotli.decompress(response.content)
                    response_text = decompressed_data.decode('utf-8')
                except:
                    pass
            elif content_encoding == 'gzip':
                try:
                    import gzip
                    decompressed_data = gzip.decompress(response.content)
                    response_text = decompressed_data.decode('utf-8')
                except:
                    pass
            
            try:
                response_data = json.loads(response_text)
                
                # check for response
                message_success = False
                error_message = None
                
                if isinstance(response_data, dict):
                    # errors
                    if 'errors' in response_data and response_data['errors']:
                        error_messages = [error.get('message', 'Unknown error') for error in response_data['errors']]
                        error_message = '; '.join(error_messages)
                    # success
                    elif 'data' in response_data:
                        send_message_data = response_data['data'].get('sendChatMessage', {})
                        if isinstance(send_message_data, dict):
                            if 'messageID' in send_message_data and send_message_data['messageID']:
                                message_success = True
                            elif 'error' in send_message_data and send_message_data['error'] is not None:
                                error_message = send_message_data['error'].get('message', 'Unknown message error')
                            else:
                                error_message = f"Message failed - Response: {json.dumps(send_message_data)}"
                        else:
                            error_message = f"sendChatMessage is not a dict: {send_message_data}"
                    else:
                        error_message = f"No data field in response: {response_data}"
                else:
                    error_message = f"Response is not a dict: {response_data}"
                
                return {
                    'success': message_success,
                    'status_code': response.status_code,
                    'data': response_data,
                    'error': error_message
                }
                
            except (ValueError, json.JSONDecodeError) as e:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'data': {'raw_response': response_text},
                    'error': f'Failed to parse response: {str(e)}'
                }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }

def read_tokens_from_file(file_path: str) -> List[tuple]:
    """Read tokens from a file, one token per line. Format: token | integrity"""
    tokens = []
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines and comments
                        parts = line.split('|')
                        token = parts[0].strip()
                        integrity = parts[1].strip() if len(parts) > 1 else None
                        
                        if token.startswith('OAuth '):
                            token = token[6:]
                        tokens.append((token, integrity))
        else:
            print(f"Token file '{file_path}' not found.")
    except Exception as e:
        print(f"Error reading token file: {e}")
    
    return tokens

def main():
    username = input("Username: ").strip()
    message = input("Message: ").strip()
    token_file = input("Token file path (default: Phone verified tokens.txt): ").strip()
    
    if not token_file:
        token_file = "phone_verified_tokens.txt"
    
    # token thing
    tokens = read_tokens_from_file(token_file)
    
    if not tokens:
        print(f"No valid tokens found in '{token_file}'")
        return
    
    print(f"Found {len(tokens)} tokens")
    print("Getting channel ID...")
    
    # Get channel ID using first token
    first_token, first_integrity = tokens[0]
    first_sender = TwitchSender(first_token, first_integrity)
    channel_id = first_sender.get_channel_id(username)
    
    if channel_id:
        print(f"Channel ID: {channel_id}")
        
        # send
        for i, (token, integrity) in enumerate(tokens, 1):
            sender = TwitchSender(token, integrity)
            result = sender.send_message(channel_id, message)
            
            if result['success']:
                status = "SUCCESS"
                colors = ['\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[97m']
                reset_color = '\033[0m'
                random_color = random.choice(colors)
                status_code = result.get('status_code', 'N/A')
                response_data = result.get('data', {})
                print(f"[{random_color}{status}{reset_color}] [{i}/{len(tokens)}] User: {token[:10]}... sent message to {username} | {{'raw_response': 'Status {status_code}'}}")
            else:
                status = "FAILED"
                error_info = result.get('error', 'Unknown error')
                status_code = result.get('status_code', 'N/A')
                print(f"[{status}] [{i}/{len(tokens)}] User: {token[:10]}... failed to send message to {username} Status {status_code} - {error_info}")
            
            # delay(change if you want)
            import time
            time.sleep(0.1)
    else:
        print("Could not find channel ID")

if __name__ == "__main__":
    main()
