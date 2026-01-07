"""Ollama orchestrator for conversational banking."""
import httpx
import asyncio
import json
from typing import Optional, Dict, Any, List
from config import get_settings

settings = get_settings()


class OllamaOrchestrator:
    """Handles LLM interactions with Ollama for conversational banking."""
    
    def __init__(self):
        self.api_url = settings.ollama_api_url
        self.model = settings.ollama_model
        self.retry_attempts = settings.ollama_retry_attempts
        self.retry_backoff = settings.ollama_retry_backoff_seconds
    
    async def retry_ollama_request(self, prompt: str, tools: Optional[List[Dict]] = None) -> Optional[Dict[str, Any]]:
        """Make a request to Ollama with retry logic."""
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                    
                    if tools:
                        payload["tools"] = tools
                    
                    response = await client.post(
                        f"{self.api_url}/api/generate",
                        json=payload
                    )
                    response.raise_for_status()
                    return response.json()
            
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                else:
                    return None
        
        return None
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for ATM banking rules."""
        return """You are a helpful ATM banking assistant. Follow these rules strictly:

1. Never hallucinate or make up account balances - always use the provided tools to get real data
2. Always confirm transaction details before executing
3. Require PIN confirmation for withdrawals and transfers
4. Provide clear, concise responses
5. If you need information, ask clarifying questions
6. Summarize the transaction before executing
7. Handle errors gracefully and provide specific error messages

Available operations:
- Balance inquiry
- Withdraw money
- Deposit money
- Transfer between accounts
- Generate receipts

Always be professional, secure, and accurate."""
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools that map to backend API endpoints."""
        return [
            {
                "name": "get_accounts",
                "description": "Get list of customer accounts with balances",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_account_details",
                "description": "Get detailed information for a specific account including recent transactions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The account ID to get details for"
                        }
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "create_transaction_intent",
                "description": "Create an intent for a transaction (withdraw, deposit, transfer)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["WITHDRAW", "DEPOSIT", "TRANSFER"],
                            "description": "The type of operation"
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money"
                        },
                        "from_account_id": {
                            "type": "integer",
                            "description": "Source account ID (for withdraws and transfers)"
                        },
                        "to_account_id": {
                            "type": "integer",
                            "description": "Destination account ID (for deposits and transfers)"
                        }
                    },
                    "required": ["operation", "amount"]
                }
            },
            {
                "name": "execute_transaction",
                "description": "Execute a confirmed transaction intent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent_id": {
                            "type": "integer",
                            "description": "The intent ID to execute"
                        }
                    },
                    "required": ["intent_id"]
                }
            }
        ]
    
    def extract_transaction_intent(self, message: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        """Extract transaction intent from user message using simple pattern matching."""
        message_lower = message.lower()
        
        # Extract operation
        operation = None
        if 'withdraw' in message_lower:
            operation = 'WITHDRAW'
        elif 'deposit' in message_lower:
            operation = 'DEPOSIT'
        elif 'transfer' in message_lower:
            operation = 'TRANSFER'
        elif 'balance' in message_lower or 'check' in message_lower:
            return {'operation': 'BALANCE_INQUIRY', 'flow_steps': []}
        
        if not operation:
            return None
        
        # Extract amount
        import re
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', message)
        amount = float(amount_match.group(1)) if amount_match else None
        
        # If amount is missing, ask for it
        if not amount:
            return {
                'operation': operation,
                'needs_clarification': True,
                'missing_field': 'amount',
                'message': f"How much would you like to {operation.lower()}?"
            }
        
        # Extract account type - improved logic to correctly identify user's intent
        from_account = None
        to_account = None
        
        # First pass: check for explicitly mentioned account types
        for acc in accounts:
            acc_type = acc['type'].lower()
            
            if operation in ['WITHDRAW', 'TRANSFER']:
                # Look for explicit mentions like "from checking", "checking account", "withdraw from checking"
                if (f'from {acc_type}' in message_lower or 
                    f'{acc_type} account' in message_lower or
                    (operation == 'WITHDRAW' and acc_type in message_lower)):
                    from_account = acc
                    break  # Found explicit mention, stop looking
                    
        # If no explicit source account found, use checking as default for withdraw/transfer
        if operation in ['WITHDRAW', 'TRANSFER'] and not from_account:
            for acc in accounts:
                if acc['type'].lower() == 'checking':
                    from_account = acc
                    break
        
        # Handle destination account for transfers
        if operation == 'TRANSFER':
            for acc in accounts:
                acc_type = acc['type'].lower()
                # Look for "to savings", "to checking", etc.
                if f'to {acc_type}' in message_lower:
                    to_account = acc
                    break
            # Default to the other account if not specified
            if not to_account:
                for acc in accounts:
                    if acc['id'] != (from_account.get('id') if from_account else None):
                        to_account = acc
                        break
                    
        # Handle deposits
        if operation == 'DEPOSIT':
            for acc in accounts:
                acc_type = acc['type'].lower()
                if acc_type in message_lower:
                    to_account = acc
                    break
            if not to_account:
                to_account = accounts[0] if accounts else None
        
        # Validate balance for withdrawals and transfers
        if operation == 'WITHDRAW' and from_account:
            if amount > from_account['balance']:
                return {
                    'operation': operation,
                    'error': True,
                    'message': f"Insufficient funds. Your {from_account['type']} account balance is ${from_account['balance']:.2f}."
                }
        
        if operation == 'TRANSFER' and from_account:
            if amount > from_account['balance']:
                return {
                    'operation': operation,
                    'error': True,
                    'message': f"Insufficient funds. Your {from_account['type']} account balance is ${from_account['balance']:.2f}."
                }
        
        # Build flow steps
        flow_steps = []
        
        if operation == 'WITHDRAW':
            flow_steps = [
                {'step': 'select_account', 'data': {'account_id': from_account['id'] if from_account else None}},
                {'step': 'enter_amount', 'data': {'amount': amount}},
                {'step': 'confirm', 'data': {'operation': operation}},
                {'step': 'receipt', 'data': {}}
            ]
        elif operation == 'DEPOSIT':
            flow_steps = [
                {'step': 'select_account', 'data': {'account_id': to_account['id'] if to_account else None}},
                {'step': 'enter_amount', 'data': {'amount': amount}},
                {'step': 'confirm', 'data': {'operation': operation}},
                {'step': 'receipt', 'data': {}}
            ]
        elif operation == 'TRANSFER':
            flow_steps = [
                {'step': 'select_from_account', 'data': {'account_id': from_account['id'] if from_account else None}},
                {'step': 'select_to_account', 'data': {'account_id': to_account['id'] if to_account else None}},
                {'step': 'enter_amount', 'data': {'amount': amount}},
                {'step': 'confirm', 'data': {'operation': operation}},
                {'step': 'receipt', 'data': {}}
            ]
        
        return {
            'operation': operation,
            'amount': amount,
            'from_account_id': from_account['id'] if from_account else None,
            'to_account_id': to_account['id'] if to_account else None,
            'flow_steps': flow_steps
        }
    
    async def process_conversation(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
        session_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a conversational message and return response with potential tool calls."""
        # Extract transaction intent from message
        accounts = session_context.get('accounts', [])
        intent = self.extract_transaction_intent(message, accounts)
        
        if intent and intent['operation'] == 'BALANCE_INQUIRY':
            # Return account summary
            balance_info = "\n".join([
                f"{acc['type']}: ${acc['balance']:.2f}"
                for acc in accounts
            ])
            return {
                "success": True,
                "message": f"Here are your account balances:\n{balance_info}",
                "flow_steps": [],
                "error": None
            }
        
        # Check if clarification is needed
        if intent and intent.get('needs_clarification'):
            return {
                "success": True,
                "message": intent['message'],
                "flow_steps": [],
                "error": None
            }
        
        # Check for errors (like insufficient funds)
        if intent and intent.get('error'):
            return {
                "success": True,
                "message": intent['message'],
                "flow_steps": [],
                "error": None
            }
        
        if intent and intent['flow_steps']:
            # Return structured flow for UI to render
            return {
                "success": True,
                "message": f"I'll help you with that {intent['operation'].lower()}. Please review the details on the screen.",
                "transaction_intent": intent,
                "flow_steps": intent['flow_steps'],
                "error": None
            }
        
        # Fallback: Try to get response from Ollama
        prompt = f"{self.get_system_prompt()}\n\n"
        for msg in conversation_history[-5:]:
            prompt += f"{msg['sender']}: {msg['content']}\n"
        prompt += f"USER: {message}\nASSISTANT: "
        
        response = await self.retry_ollama_request(prompt, self.get_available_tools())
        
        if not response:
            return {
                "error": "LLM_UNAVAILABLE",
                "message": "Conversational mode unavailable. Please use Traditional ATM.",
                "success": False
            }
        
        return {
            "success": True,
            "message": response.get("response", ""),
            "tool_calls": response.get("tool_calls", []),
            "error": None
        }


# Global orchestrator instance
orchestrator = OllamaOrchestrator()
