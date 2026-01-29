"""Ollama orchestrator for conversational banking."""
import httpx
import asyncio
import json
import logging
import re
import random
from typing import Optional, Dict, Any, List
from config import get_settings
from models import PayeeCategory


def simulate_bill_breakdown(amount: float) -> Dict[str, int]:
    """
    Simulates ATM device counting bills. Generates realistic denomination breakdown.
    Mimics how a real ATM would count deposited cash.
    
    Args:
        amount: Total amount in dollars
    
    Returns:
        Dictionary with bill counts per denomination
    """
    result = {
        "bills_100": 0,
        "bills_50": 0,
        "bills_20": 0,
        "bills_10": 0,
        "bills_5": 0,
        "bills_1": 0,
        "coins_amount": 0.0,
    }
    
    if amount <= 0:
        return result
    
    remaining = int(amount)
    
    # Realistic distribution: prefer larger bills (70% in $100s)
    if remaining >= 100:
        hundreds_amount = int(remaining * 0.7)
        hundreds_amount = (hundreds_amount // 100) * 100
        result["bills_100"] = hundreds_amount // 100
        remaining -= hundreds_amount
    
    # Distribute remainder across smaller denominations
    if remaining >= 50:
        fifties = random.randint(0, remaining // 50)
        result["bills_50"] = fifties
        remaining -= fifties * 50
    
    if remaining >= 20:
        twenties = remaining // 20
        result["bills_20"] = twenties
        remaining -= twenties * 20
    
    if remaining >= 10:
        tens = remaining // 10
        result["bills_10"] = tens
        remaining -= tens * 10
    
    if remaining >= 5:
        fives = remaining // 5
        result["bills_5"] = fives
        remaining -= fives * 5
    
    if remaining > 0:
        result["bills_1"] = remaining
    
    return result

settings = get_settings()

class OllamaOrchestrator:
    """Handles LLM interactions with Ollama for conversational banking."""
    
    def __init__(self):
        self.api_url = settings.ollama_api_url
        self.model = settings.ollama_model
        self.retry_attempts = settings.ollama_retry_attempts
        self.retry_backoff = settings.ollama_retry_backoff_seconds
        logging.info("OllamaOrchestrator initialized with model: %s, api_url: %s", self.model, self.api_url)

    # --- Intent Validation Helper ---
    @staticmethod
    def validate_intent(intent: dict) -> list[str]:
        op = intent.get("operation")
        errors: list[str] = []

        if op == "BALANCE_INQUIRY":
            if not intent.get("account_id") and not intent.get("account_type"):
                errors.append("account_id or account_type is required")

        elif op == "WITHDRAW":
            if not intent.get("account_id"):
                errors.append("account_id is required")
            if intent.get("amount") in (None, 0):
                errors.append("amount is required")

        elif op == "CASH_DEPOSIT":
            # just ensure we know the target account; denominations/total validated later
            if not intent.get("account_id"):
                errors.append("account_id is required")

        elif op == "CHECK_DEPOSIT":
            if not intent.get("account_id"):
                errors.append("account_id is required")
            # Don't validate amount here - let CHECK_DEPOSIT operation logic handle it
            # This allows proper conversational flow to ask for amount
            # check_number, check_date, payer_name will be auto-generated if not provided

        elif op == "TRANSFER":
            # Skip validation - TRANSFER handler will ask for missing fields conversationally
            pass

        elif op == "CHANGE_PIN":
            if not intent.get("account_id"):
                errors.append("account_id (or card id) is required")

        elif op in ("DEPOSIT", "PAYMENT"):
            errors.append("operation not yet implemented")

        else:
            errors.append("unknown operation")

        return errors

    async def retry_ollama_request(self, prompt: str, tools: Optional[List[Dict]] = None) -> Optional[Dict[str, Any]]:
        """Make a request to Ollama with retry logic."""
        logging.info("[retry_ollama_request] Called with prompt: %s", prompt[:100])
        for attempt in range(self.retry_attempts):
            try:
                logging.info("[retry_ollama_request] Attempt %d", attempt + 1)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                    if tools:
                        payload["tools"] = tools
                    logging.debug("[retry_ollama_request] Payload: %s", json.dumps(payload)[:200])
                    response = await client.post(
                        f"{self.api_url}/api/generate",
                        json=payload
                    )
                    response.raise_for_status()
                    logging.info("[retry_ollama_request] Success on attempt %d", attempt + 1)
                    return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logging.warning("[retry_ollama_request] Error on attempt %d: %s", attempt + 1, str(e))
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff * (2 ** attempt)
                    logging.info("[retry_ollama_request] Retrying after %d seconds", wait_time)
                    await asyncio.sleep(wait_time)
                else:
                    logging.error("[retry_ollama_request] All attempts failed.")
                    return None
        return None
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for ATM intent extraction."""
        logging.info("[get_system_prompt] Called.")

        return """
    You are FlowPilot ATM's intent parser.

    Your ONLY job is to convert the user's natural language into a single JSON object
    describing the requested ATM operation.

    Return exactly ONE JSON object and NO extra text. The JSON MUST use this schema:

    {
    "operation": "WITHDRAW | DEPOSIT | TRANSFER | PAYMENT | BALANCE_INQUIRY | CASH_DEPOSIT | CHECK_DEPOSIT | CHANGE_PIN",
    "account_id": number or null,
    "source_account_id": number or null,
    "destination_account_id": number or null,
    "account_type": "CHECKING | SAVINGS | null",
    "amount": number or null,
    "currency": "USD" or other 3-letter currency code or null,
    "source_account_type": "CHECKING | SAVINGS | null",
    "destination_account_type": "CHECKING | SAVINGS | null",
    "is_external": boolean or null,
    "check_number": string or null,
    "pin_change": {
        "old_pin": string or null,
        "new_pin": string or null
    } or null,
    "raw_text": "copy of the original user prompt"
    }

    Mapping rules:

    - BALANCE_INQUIRY:
    - Use operation = "BALANCE_INQUIRY" for any request to show balances or account info,
        e.g. "show my balance", "get my account info", "how much do I have".
    - CRITICAL: Only set account_type if the user EXPLICITLY mentions the account type.
    - If the user EXPLICITLY mentions "checking", "savings", "money market", "high yield savings",
        "health savings", "HSA", "student checking", "business checking", or similar, map them into:
        - account_type = "SAVINGS" for all savings-family products
        - account_type = "CHECKING" for all checking-family products.
    - If the user just says "my account" or "account" without specifying a type, set account_type = null.
    - account_id can be null if not given; the backend will resolve it.
    - amount should be null.

    - WITHDRAW:
    - Use operation = "WITHDRAW" for cash withdrawals, e.g.
        "withdraw 100", "take out 50 from savings", "get 20 dollars from checking".
    - Extract amount as a number and currency if mentioned.
    - CRITICAL: Only set account_type if the user EXPLICITLY mentions the account type.
    - Map product names to account_type the same way:
        - "savings", "money market", "high yield savings", "health savings", "HSA" -> "SAVINGS"
        - "checking", "student checking", "business checking", etc. -> "CHECKING".
    - If the user just says "my account" or "account" without specifying a type, set account_type = null.
    - account_id can be null; backend will map account_type to a concrete id.

    - CASH_DEPOSIT:
    - Use operation = "CASH_DEPOSIT" ONLY for depositing physical cash money (bills and coins), e.g.
        "deposit 200 in cash into savings", "deposit cash", "insert bills", "deposit 100 dollars cash", "cash deposit".
    - IMPORTANT: If the user says "cash", "bills", "coins", or "dollar bills", use CASH_DEPOSIT, NOT "DEPOSIT".
    - Do NOT use CASH_DEPOSIT for checks/cheques - those use CHECK_DEPOSIT.
    - CRITICAL: Only set account_type if the user EXPLICITLY mentions the account type.
    - If the user says "into my checking" or "into savings", set the appropriate account_type.
    - If the user just says "my account" or "account" without specifying a type, set account_type = null.
    - Extract amount, currency when possible.
    - account_id may be null if not specified.
    - If amount is not specified, set it to null so the backend can collect it.

    - CHECK_DEPOSIT:
    - Use operation = "CHECK_DEPOSIT" for depositing checks or cheques (a paper payment instrument), e.g.
        "deposit this check", "check deposit", "add my paycheck", "deposit a cheque",
        "cheque deposit into my account", "deposit a check", "deposit my check", "cheque deposit".
    - CRITICAL DISTINCTION: The words "check" or "cheque" refer to a paper bank check (payment instrument),
        NOT "checking account". "Deposit a check" or "Deposit a cheque" means CHECK_DEPOSIT.
    - DO NOT confuse "check" (the payment instrument) with "checking account".
    - CRITICAL: Only set account_type if the user EXPLICITLY mentions the account type.
    - If the user says "into my checking" or "into savings", set the appropriate account_type.
    - If the user just says "my account" or "account" without specifying a type, set account_type = null.
    - Keywords for CHECK_DEPOSIT: "check", "cheque", "paycheck", "check number"
    - Keywords for CASH_DEPOSIT: "cash", "bills", "coins", "dollar bills"
    - If a check number appears, put it in check_number, else null.
    - amount may be null if not spoken - set it to null if not provided.
    - account_id may be null if not specified.

    - TRANSFER:
    - Use operation = "TRANSFER" when moving money between accounts, e.g.
        "transfer 300 from checking to savings",
        "move 50 to my savings account",
        "send 100 to my external bank account".
    - Extract amount and currency.
    - CRITICAL: Only set source_account_type and destination_account_type if the user EXPLICITLY mentions them.
    - For internal transfers (between the customer's own accounts):
        - Set source_account_type and destination_account_type based on phrases like
            "from checking", "to savings", etc.
        - If the user just says "from my account" without specifying type, set source_account_type = null.
        - If the user just says "to my account" without specifying type, set destination_account_type = null.
    - If the user clearly indicates an external bank (e.g. "to another bank",
        "to my account at XYZ bank"), set is_external = true.
    - account_id / source_account_id / destination_account_id may be null; backend resolves them.

    - DEPOSIT and PAYMENT:
    - Only use "DEPOSIT" for generic deposit flows that are not clearly cash or check.
    - Use "PAYMENT" for bill payments or similar, e.g. "pay my electricity bill".
    - If unsure whether it's PAYMENT or TRANSFER to an internal account, prefer TRANSFER
        for moving between customer-owned accounts, and PAYMENT for paying merchants/billers.

    - CHANGE_PIN:
    - Use operation = "CHANGE_PIN" when the user wants to change or reset their PIN,
        e.g. "change my PIN", "update my ATM PIN".
    - Do NOT invent actual PIN numbers.
    - If the user explicitly says old and new PINs in the text, you may fill pin_change,
        otherwise set old_pin and new_pin to null and let the UI collect them securely.

    General rules:

    - ALWAYS respond with a SINGLE JSON object and NO extra explanation.
    - If some field is unknown, set it to null (or false for is_external when appropriate).
    - Do NOT guess account_id values. Only fill account_id / source_account_id /
    destination_account_id if the user explicitly gives an id or account number.
    - Prefer using account_type / source_account_type / destination_account_type
    based on natural language like "checking", "savings", etc.
    - If the user mentions multiple possible actions, choose the PRIMARY action they
    clearly want (for example, if they say "before withdrawing, show me my balance",
    treat that as WITHDRAW; the backend can still do a balance check first).
    """

    async def get_intent_from_llm(self, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Call Ollama to get a JSON intent for the given user message.
        Expects the model to return a single JSON object as text.
        """
        system_prompt = self.get_system_prompt()
        full_prompt = f"{system_prompt}\n\nUSER: {user_message}\nINTENT_JSON:"

        logging.info("[get_intent_from_llm] Sending prompt (truncated): %s", full_prompt[:200])

        response = await self.retry_ollama_request(full_prompt)
        if not response:
            logging.error("[get_intent_from_llm] No response from Ollama.")
            return None

        # Ollama /api/generate returns a JSON with a 'response' field that is the text.
        raw = response.get("response", "")
        logging.info("[get_intent_from_llm] Raw model response: %s", raw[:200])

        # Extract first JSON object from the text
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                logging.error("[get_intent_from_llm] No JSON object found in response.")
                return None
            json_str = raw[start : end + 1]
            intent = json.loads(json_str)
            logging.info("[get_intent_from_llm] Parsed intent: %s", intent)
            return intent
        except json.JSONDecodeError as e:
            logging.error("[get_intent_from_llm] JSON decode error: %s", str(e))
            return None

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Define available tools that map to backend API endpoints."""
        logging.info("[get_available_tools] Called.")
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
    
    @staticmethod
    def pick_account_id_for_type(canonical_type: str, accounts: list[dict]) -> int | None:
        if not canonical_type:
            return None
        ct = canonical_type.upper()
        logging.info("[pick_account_id_for_type] Looking for type=%s in accounts=%s", ct, accounts)
        matches = [a for a in accounts if (a.get("type") or "").upper() == ct]
        logging.info("[pick_account_id_for_type] Matches: %s", matches)
        if len(matches) == 1:
            return matches[0]["id"]
        return None



    async def extract_transaction_intent(self, message: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        logging.info("[extract_transaction_intent] Called with message: %s", message)

        # 1. Call LLM to get high-level intent JSON
        intent = await self.get_intent_from_llm(message)

        if not intent:
            logging.info("[extract_transaction_intent] LLM returned no intent.")
            return None

        op = intent.get("operation")
        
        # Normalize generic "DEPOSIT" to "CASH_DEPOSIT" if user mentioned cash
        message_lower = message.lower()
        if op == "DEPOSIT" and any(keyword in message_lower for keyword in ["cash", "bills", "coins", "dollar bills"]):
            intent["operation"] = "CASH_DEPOSIT"
            op = "CASH_DEPOSIT"
            logging.info("[extract_transaction_intent] Normalized DEPOSIT to CASH_DEPOSIT based on keywords in message")
        
        # Normalize "CASH_DEPOSIT" to "CHECK_DEPOSIT" if user mentioned check/cheque
        if op == "CASH_DEPOSIT" and any(keyword in message_lower for keyword in ["check", "cheque", "paycheck"]):
            intent["operation"] = "CHECK_DEPOSIT"
            op = "CHECK_DEPOSIT"
            logging.info("[extract_transaction_intent] Corrected CASH_DEPOSIT to CHECK_DEPOSIT based on keywords in message")
        
        # Normalize generic "DEPOSIT" to "CHECK_DEPOSIT" if user mentioned check/cheque
        if op == "DEPOSIT" and any(keyword in message_lower for keyword in ["check", "cheque", "paycheck"]):
            intent["operation"] = "CHECK_DEPOSIT"
            op = "CHECK_DEPOSIT"
            logging.info("[extract_transaction_intent] Normalized DEPOSIT to CHECK_DEPOSIT based on keywords in message")
        
        acct_type = intent.get("account_type")
        src_type = intent.get("source_account_type")
        dst_type = intent.get("destination_account_type")
        logging.info("[extract_transaction_intent] Initial intent: %s", intent)
        logging.info("[extract_transaction_intent] Accounts available: %s", accounts)
        logging.info("[extract_transaction_intent] Operation: %s, acct_type: %s, src_type: %s, dst_type: %s", op, acct_type, src_type, dst_type)

        # DO NOT auto-map account_type to account_id here
        # Let process_conversation handle account selection with proper user prompts
        # This ensures users are always asked to confirm their account selection

        logging.info("[extract_transaction_intent] Final intent: %s", intent)
        return intent


    # Add this new function for clarification
    def check_missing_fields(intent: str, extracted_data: dict, customer_accounts: list, payees: list = []) -> dict:
        logging.info("[check_missing_fields] Called with intent: %s, extracted_data: %s", intent, extracted_data)
        """
        Check if all required fields are present for the transaction intent.
        Returns dict with clarification_needed flag and missing fields list.
        """
        required_fields = {
            "WITHDRAW": ["account_id", "amount"],
            "CASH_DEPOSIT": ["account_id", "bills_100", "bills_50", "bills_20", "bills_10", "bills_5", "bills_1","total"],
            "CHECK_DEPOSIT": ["account_id", "amount"],  # check details auto-generated by device
            "TRANSFER": ["from_account_id", "to_account_id", "amount"],
            "BILL_PAYMENT": ["from_account_id", "payee_id", "amount"],
            "PIN_CHANGE": ["account_id", "old_pin", "new_pin"], 
            "BALANCE_INQUIRY": ["account_id"]
        }
        
        required = required_fields.get(intent, [])
        missing = [field for field in required if field not in extracted_data or extracted_data[field] is None]
        
        if missing:
            logging.info("[check_missing_fields] Missing fields: %s", missing)
            # Generate clarifying question
            questions = {
                "account_id": "Which account would you like to use?",
                "from_account_id": "Which account would you like to transfer from?",
                "to_account_id": "Which account would you like to transfer to?",
                "amount": "How much would you like to process?",
                "check_number": "What is the check number?",
                "check_date": "What is the date on the check?",
                "payer_name": "Who is the check from?",
                "payee_id": "Which payee would you like to pay?",
                "bills_100": "How many bills of each denomination are you depositing?",
                "bills_50": "How many bills of each denomination are you depositing?",
                "bills_20": "How many bills of each denomination are you depositing?",
                "bills_10": "How many bills of each denomination are you depositing?",
                "bills_5": "How many bills of each denomination are you depositing?",
                "bills_1": "How many bills of each denomination are you depositing?",
                "total": "What is the total amount you are depositing?",
                "old_pin": "What is your current PIN?",
                "new_pin": "What would you like your new PIN to be?"

            }
            
            question = questions.get(missing[0], f"I need more information about {missing[0]}.")
            
            return {
                "clarification_needed": True,
                "missing_fields": missing,
                "question": question
            }
        
        logging.info("[check_missing_fields] All required fields present.")
        return {"clarification_needed": False}

    #"""Process a conversational message and return response with potential tool calls."""
    async def process_conversation(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
        session_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        logging.info("[process_conversation] Called with message: %s", message)

        accounts = session_context.get("accounts", [])
        logging.info("[process_conversation] Session accounts: %s", accounts)

        # ----------------------------------------------------------------------
        # A) Handle follow-up responses
        # ----------------------------------------------------------------------
        
        # A1) Handle "Use account id: 123"
        account_id_match = re.match(r"Use account id: (\d+)", message.strip(), re.IGNORECASE)
        if account_id_match:
            selected_id = int(account_id_match.group(1))
            logging.info("[process_conversation] Follow-up selection: account_id=%s", selected_id)

            last_intent = session_context.get("pending_intent")
            if not last_intent:
                last_user_msg = None
                for msg in reversed(conversation_history):
                    if msg["sender"] == "USER":
                        last_user_msg = msg["content"]
                        break
                if last_user_msg:
                    last_intent = await self.extract_transaction_intent(last_user_msg, accounts)

            if not last_intent:
                logging.warning("[process_conversation] No previous intent found for follow-up.")
                return {
                    "success": False,
                    "message": "I could not find the previous transaction. Please say it again.",
                    "error": "NO_PREVIOUS_INTENT",
                }

            # Patch account_id and fall through to normal handling
            if last_intent.get("operation") == "TRANSFER":
                # For TRANSFER: determine if this is source or destination account
                if not last_intent.get("from_account_id") and not last_intent.get("source_account_id"):
                    last_intent["from_account_id"] = selected_id
                    last_intent["source_account_id"] = selected_id
                    logging.info("[process_conversation] TRANSFER: Patched source account_id=%s", selected_id)
                elif not last_intent.get("to_account_id") and not last_intent.get("destination_account_id"):
                    last_intent["to_account_id"] = selected_id
                    last_intent["destination_account_id"] = selected_id
                    logging.info("[process_conversation] TRANSFER: Patched destination account_id=%s", selected_id)
                else:
                    last_intent["from_account_id"] = selected_id
                    last_intent["source_account_id"] = selected_id
            else:
                last_intent["account_id"] = selected_id
            logging.info("[process_conversation] Patched account_id into pending intent: %s", last_intent)

            intent = last_intent
            session_context["pending_intent"] = intent
            
        # A2) Handle numeric responses for check deposit flow
        elif session_context.get("pending_intent", {}).get("operation") == "CHECK_DEPOSIT":
            last_intent = session_context.get("pending_intent")
            check_collection_state = last_intent.get("_check_collection_state", {})
            
            logging.info("[process_conversation] A2: CHECK_DEPOSIT numeric handler - last_intent=%s, check_collection_state=%s", last_intent, check_collection_state)
            
            # Try to parse numeric response
            try:
                numeric_value = float(message.strip().replace("$", "").replace(",", ""))
                logging.info("[process_conversation] A2: Parsed numeric value: %s", numeric_value)
                
                # Check if we're collecting number of checks
                if not check_collection_state.get("num_checks"):
                    num_checks = int(numeric_value)
                    if num_checks <= 0 or num_checks > 50:
                        logging.warning("[process_conversation] A2: Invalid num_checks: %s", num_checks)
                        return {
                            "success": False,
                            "message": "Please enter a valid number of checks (1-50).",
                            "error": "INVALID_NUMBER",
                        }
                    
                    check_collection_state["num_checks"] = num_checks
                    check_collection_state["checks"] = []
                    last_intent["_check_collection_state"] = check_collection_state
                    logging.info(f"[process_conversation] A2: num_checks set to {num_checks}, account_id={last_intent.get('account_id')}")
                    
                    intent = last_intent
                    session_context["pending_intent"] = intent
                    
                # Check if we're collecting check amounts
                elif len(check_collection_state.get("checks", [])) < check_collection_state.get("num_checks", 0):
                    if numeric_value <= 0:
                        logging.warning("[process_conversation] A2: Invalid check amount: %s", numeric_value)
                        return {
                            "success": False,
                            "message": "Please enter a valid check amount greater than $0.",
                            "error": "INVALID_AMOUNT",
                        }
                    
                    # Generate check details with the provided amount
                    import random
                    from datetime import datetime
                    
                    check_number = f"CHK{random.randint(100000, 999999)}"
                    payer_names = [
                        "ABC Corporation", "XYZ Industries", "John Smith",
                        "Jane Doe", "Global Services LLC", "Tech Solutions Inc."
                    ]
                    payer_name = random.choice(payer_names)
                    check_date = datetime.utcnow().strftime("%Y-%m-%d")
                    
                    new_check = {
                        "check_number": check_number,
                        "check_date": check_date,
                        "payer_name": payer_name,
                        "amount": numeric_value
                    }
                    
                    check_collection_state["checks"].append(new_check)
                    last_intent["_check_collection_state"] = check_collection_state
                    logging.info(f"[process_conversation] A2: added check {len(check_collection_state['checks'])}/{check_collection_state['num_checks']}, account_id={last_intent.get('account_id')}")
                    
                    intent = last_intent
                    session_context["pending_intent"] = intent
                else:
                    # All checks collected, proceed normally
                    logging.info("[process_conversation] A2: All checks collected, proceeding to flow_steps")
                    intent = last_intent
                    
            except (ValueError, AttributeError) as e:
                # Not a numeric response - but we have a pending CHECK_DEPOSIT, so ask user to provide just the number
                logging.warning("[process_conversation] A2: Not a numeric response (error: %s), asking user for numeric input only", str(e))
                
                check_collection_state = last_intent.get("_check_collection_state", {})
                if not check_collection_state.get("num_checks"):
                    # Still collecting number of checks
                    return {
                        "success": False,
                        "message": "Please enter just the number of checks (e.g., '3').",
                        "error": "INVALID_FORMAT",
                    }
                else:
                    # Collecting check amounts
                    check_index = len(check_collection_state.get("checks", [])) + 1
                    return {
                        "success": False,
                        "message": f"Please enter just the amount for check #{check_index} (e.g., '150.50').",
                        "error": "INVALID_FORMAT",
                    }
        else:
            # ------------------------------------------------------------------
            # B) First-turn: extract intent from LLM
            # ------------------------------------------------------------------
            intent = await self.extract_transaction_intent(message, accounts)
            logging.info("[process_conversation] Extracted intent: %s", intent)
            session_context["pending_intent"] = intent

        # ----------------------------------------------------------------------
        # C) Intent handling
        # ----------------------------------------------------------------------
        if intent:
            errors = self.validate_intent(intent)

            # ---------------------- C1) Validation errors ---------------------
            if errors:
                # Ambiguous / missing account_id: clarification with options
                if (
                    "account_id is required" in errors
                    or "account_id or account_type is required" in errors
                ):
                    acct_type = intent.get("account_type")
                    candidates = accounts
                    if acct_type:
                        candidates = [
                            acc
                            for acc in accounts
                            if (acc.get("type") or "").upper() == acct_type.upper()
                        ]

                    if candidates:
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in candidates
                        ]
                        clarifying_question = (
                            f"I see multiple {acct_type.lower() if acct_type else ''} accounts. "
                            f"Which one should I use?"
                        )
                        logging.info(
                            "[process_conversation] Account ambiguity, asking user to choose. options=%s",
                            options,
                        )
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": clarifying_question,
                            "options": options,
                            "missing_fields": errors,
                            "error": "MISSING_FIELDS",
                        }

                    clarifying_question = "Which account should I use?"
                    logging.info(
                        "[process_conversation] Account ambiguity, but no candidates found."
                    )
                    return {
                        "success": False,
                        "clarification_needed": True,
                        "question": clarifying_question,
                        "options": [],
                        "missing_fields": errors,
                        "error": "MISSING_FIELDS",
                    }

                # Generic clarification
                clarifying_question = None
                field_map = {
                    "account_id": "Which account should I use?",
                    "account_type": "What type of account?",
                    "amount": "How much should I process?",
                    "source_account_id": "Which account should I transfer from?",
                    "destination_account_id": "Which account should I transfer to?",
                    "is_external": "Is this an external transfer?",
                    "check_number": "What is the check number?",
                    "account_id or account_type is required": "Which account or account type should I use?",
                }
                for err in errors:
                    for key, question in field_map.items():
                        if key in err:
                            clarifying_question = question
                            break
                    if clarifying_question:
                        break
                if not clarifying_question:
                    clarifying_question = f"Missing required information: {errors[0]}"

                logging.info("[process_conversation] Validation failed: %s", errors)
                return {
                    "success": False,
                    "clarification_needed": False,
                    "question": clarifying_question,
                    "options": [],
                    "missing_fields": errors,
                    "error": "MISSING_FIELDS",
                }

            # ---------------------- C2) No validation errors -----------------
            op = intent["operation"]
            amt = intent.get("amount")
            acct_id = intent.get("account_id")
            src_id = intent.get("source_account_id")
            dst_id = intent.get("destination_account_id")

            # ---------------------- BALANCE_INQUIRY --------------------------
            if op == "BALANCE_INQUIRY":
                # If account_id is missing, ask for clarification
                if not acct_id:
                    # If there is only one account, auto-select it
                    if len(accounts) == 1:
                        intent["account_id"] = accounts[0]["id"]
                        acct_id = accounts[0]["id"]
                    else:
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in accounts
                        ]
                        clarifying_question = "Which account would you like to check the balance for?"
                        logging.info("[process_conversation] BALANCE_INQUIRY missing account_id, asking for clarification. options=%s", options)
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": clarifying_question,
                            "options": options,
                            "missing_fields": ["account_id is required"],
                            "error": "MISSING_FIELDS",
                        }

                # If account_id is present, show the balance for that account only
                acc = next((a for a in accounts if a["id"] == acct_id), None)
                if acc:
                    balance_info = f"{acc.get('account_name') or acc['type']}: ${acc['balance']:.2f}"
                    human_msg = f"Here is your account balance:\n{balance_info}"
                    logging.info("[process_conversation] BALANCE_INQUIRY -> AccountInfo for account_id %s.", acct_id)
                    return {
                        "success": True,
                        "message": human_msg,
                        "transaction_intent": intent,
                        "flow_steps": [
                            {
                                "step": "account_info",  # AccountInfo.tsx
                                "data": {
                                    "mode": "BALANCE",
                                    "accounts": [
                                        {
                                            "id": acc["id"],
                                            "account_name": acc.get("account_name") or acc["type"],
                                            "type": acc.get("type"),
                                            "balance": float(acc["balance"]),
                                            "currency": acc["currency"],
                                        }
                                    ],
                                },
                            },
                        ],
                        "error": None,
                    }
                else:
                    logging.warning("[process_conversation] BALANCE_INQUIRY: account_id %s not found in accounts.", acct_id)
                    return {
                        "success": False,
                        "message": "Account not found.",
                        "error": "ACCOUNT_NOT_FOUND",
                    }

            # --------------------------- WITHDRAW -----------------------------
            if op == "WITHDRAW":
                # Check for missing account_id first
                if not acct_id:
                    # Filter accounts by type if account_type is specified
                    acct_type = intent.get("account_type")
                    candidates = accounts
                    if acct_type:
                        candidates = [
                            acc for acc in accounts 
                            if (acc.get("type") or "").upper() == acct_type.upper()
                        ]
                    
                    if len(candidates) == 1:
                        # Auto-select if only one matching account
                        intent["account_id"] = candidates[0]["id"]
                        acct_id = candidates[0]["id"]
                    elif len(candidates) > 1:
                        # Multiple matching accounts - ask user to choose
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in candidates
                        ]
                        logging.info("[process_conversation] WITHDRAW missing account_id, asking for clarification.")
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": "Which account would you like to withdraw from?",
                            "options": options,
                            "missing_fields": ["account_id is required"],
                            "error": "MISSING_FIELDS",
                        }
                    else:
                        # No matching accounts
                        logging.error("[process_conversation] WITHDRAW: no matching accounts found for type %s", acct_type)
                        return {
                            "success": False,
                            "message": f"No {acct_type.lower() if acct_type else ''} accounts found.",
                            "error": "NO_MATCHING_ACCOUNTS",
                        }
                
                # Then check for missing amount
                if not amt or amt == 0:
                    logging.warning(
                        "[process_conversation] WITHDRAW intent missing amount after account selected."
                    )
                    return {
                        "success": False,
                        "clarification_needed": False,
                        "question": "How much would you like to withdraw?",
                        "options": [],
                        "missing_fields": ["amount is required"],
                        "error": "MISSING_FIELDS",
                    }

                acc = next((a for a in accounts if a["id"] == acct_id), None)
                acc_label = acc.get("account_name") if acc else "your account"

                human_msg = (
                    f"I'll help you withdraw ${amt:.2f} from {acc_label}. "
                    "Please review and confirm on the screen."
                )

                logging.info(
                    "[process_conversation] WITHDRAW -> AccountSelection -> WithdrawalAmount -> "
                    "WithdrawalDenomination -> WithdrawalConfirm."
                )

                return {
                    "success": True,
                    "message": human_msg,
                    "transaction_intent": intent,
                    "flow_steps": [
                        {
                            # AccountSelection.tsx
                            "step": "account_selection",
                            "data": {
                                "mode": "WITHDRAW",
                                "preselected_account_id": acct_id,
                            },
                        },
                        {
                            # WithdrawalAmount.tsx
                            "step": "withdrawal_amount",
                            "data": {
                                "amount": float(amt),
                            },
                        },
                        {
                            # WithdrawalDenomination.tsx
                            "step": "withdrawal_denomination",
                            "data": {
                                # optional: denominations suggestion
                            },
                        },
                        {
                            # WithdrawalConfirm.tsx (automation stops here; user confirms)
                            "step": "withdrawal_confirm",
                            "data": {},
                        },
                    ],
                    "error": None,
                }

            # ---------------- Other operations: keep your existing text logic ---
            human_msg = "I'll help you with that transaction. Please review the details on the screen."

            if op == "CASH_DEPOSIT":
                # Check for missing account_id first
                if not acct_id:
                    # Filter accounts by type if account_type is specified
                    acct_type = intent.get("account_type")
                    candidates = accounts
                    if acct_type:
                        candidates = [
                            acc for acc in accounts 
                            if (acc.get("type") or "").upper() == acct_type.upper()
                        ]
                    
                    if len(candidates) == 1:
                        # Auto-select if only one matching account
                        intent["account_id"] = candidates[0]["id"]
                        acct_id = candidates[0]["id"]
                    elif len(candidates) > 1:
                        # Multiple matching accounts - ask user to choose
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in candidates
                        ]
                        logging.info("[process_conversation] CASH_DEPOSIT missing account_id, asking for clarification.")
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": "Which account would you like to deposit cash into?",
                            "options": options,
                            "missing_fields": ["account_id is required"],
                            "error": "MISSING_FIELDS",
                        }
                    else:
                        # No matching accounts
                        logging.error("[process_conversation] CASH_DEPOSIT: no matching accounts found for type %s", acct_type)
                        return {
                            "success": False,
                            "message": f"No {acct_type.lower() if acct_type else ''} accounts found.",
                            "error": "NO_MATCHING_ACCOUNTS",
                        }
                
                # For cash deposit, amount is not required upfront (user will insert bills)
                if acct_id:
                    acc = next((a for a in accounts if a["id"] == acct_id), None)
                    acc_label = acc.get("account_name") if acc else "your account"
                    if amt:
                        human_msg = (
                            f"I'll help you deposit ${amt:.2f} in cash into {acc_label}. "
                            "Please insert the notes and confirm on the screen."
                        )
                    else:
                        human_msg = (
                            f"I'll help you deposit cash into {acc_label}. "
                            "Please insert the notes and confirm on the screen."
                        )
                    
                    # Simulate device counting bills if amount is provided
                    simulated_denominations = None
                    if amt and amt > 0:
                        simulated_denominations = simulate_bill_breakdown(amt)
                        logging.info(f"[CASH_DEPOSIT] Simulated bill breakdown for ${amt}: {simulated_denominations}")
                    
                    return {
                        "success": True,
                        "message": human_msg,
                        "transaction_intent": intent,
                        "flow_steps": [
                            {
                                "step": "account_selection",
                                "data": {
                                    "mode": "CASH_DEPOSIT",
                                    "preselected_account_id": acct_id,
                                },
                            },
                            {
                                "step": "deposit_type_selection",
                                "data": {
                                    "account_id": acct_id,
                                    "mode": "CASH_DEPOSIT",
                                    "preselected_type": "cash",
                                },
                            },
                            {
                                "step": "cash_deposit_screen",
                                "data": {
                                    "account_id": acct_id,
                                    "denominations": simulated_denominations,
                                },
                            },
                            {
                                "step": "cash_deposit_review",
                                "data": {
                                    "account_id": acct_id,
                                },
                            },
                            {
                                "step": "cash_deposit_confirmation",
                                "data": {
                                    "account_id": acct_id,
                                },
                            },
                        ],
                        "error": None,
                    }

            elif op == "CHECK_DEPOSIT":
                logging.info("[process_conversation] CHECK_DEPOSIT handler: acct_id=%s, intent=%s", acct_id, intent)
                
                # Check for missing account_id first
                if not acct_id:
                    logging.info("[process_conversation] CHECK_DEPOSIT: no account_id, asking user to select")
                    # Filter accounts by type if account_type is specified
                    acct_type = intent.get("account_type")
                    candidates = accounts
                    if acct_type:
                        candidates = [
                            acc for acc in accounts 
                            if (acc.get("type") or "").upper() == acct_type.upper()
                        ]
                        logging.info("[process_conversation] CHECK_DEPOSIT: filtered %d candidates for type %s", len(candidates), acct_type)
                    else:
                        logging.info("[process_conversation] CHECK_DEPOSIT: no account_type filter, using all %d accounts", len(accounts))
                    
                    # Always ask user to choose - no auto-selection
                    if len(candidates) > 0:
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in candidates
                        ]
                        question = f"Which account would you like to deposit the check into?"
                        logging.info("[process_conversation] CHECK_DEPOSIT: asking for account selection with %d options", len(options))
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": question,
                            "options": options,
                            "missing_fields": ["account_id is required"],
                            "error": "MISSING_FIELDS",
                            "_pending_intent": intent,
                        }
                    else:
                        # No matching accounts found
                        logging.error("[process_conversation] CHECK_DEPOSIT: no matching accounts found for type %s", acct_type)
                        return {
                            "success": False,
                            "message": f"No {acct_type.lower() if acct_type else ''} accounts found.",
                            "error": "NO_MATCHING_ACCOUNTS",
                        }
                
                # Conversational flow: Ask for number of checks and amounts
                acc = next((a for a in accounts if a["id"] == acct_id), None)
                acc_label = acc.get("account_name") if acc else "your account"
                logging.info("[process_conversation] CHECK_DEPOSIT: found account %s (id=%s)", acc_label, acct_id)
                
                # Check if we're collecting check information conversationally
                check_collection_state = intent.get("_check_collection_state", {})
                logging.info("[process_conversation] CHECK_DEPOSIT: check_collection_state=%s", check_collection_state)
                
                if not check_collection_state.get("num_checks"):
                    # Step 1: Ask for number of checks
                    logging.info("[process_conversation] CHECK_DEPOSIT: asking for number of checks (acct_id=%s, acc_label=%s)", acct_id, acc_label)
                    
                    # CRITICAL: Ensure account_id is preserved in the pending intent
                    if not intent.get("account_id"):
                        logging.error("[process_conversation] CHECK_DEPOSIT: account_id is MISSING in intent when asking for num_checks!")
                        intent["account_id"] = acct_id
                    
                    return {
                        "success": False,
                        "clarification_needed": True,
                        "question": f"How many checks would you like to deposit into {acc_label}?",
                        "options": [],
                        "missing_fields": ["number_of_checks"],
                        "error": "MISSING_FIELDS",
                        "_pending_intent": intent,  # Store intent for next iteration
                    }
                
                num_checks = check_collection_state.get("num_checks")
                collected_checks = check_collection_state.get("checks", [])
                
                # Step 2: Collect amount for each check
                if len(collected_checks) < num_checks:
                    check_index = len(collected_checks) + 1
                    logging.info(f"[process_conversation] CHECK_DEPOSIT: asking for amount of check {check_index}/{num_checks}, acct_id={acct_id}")
                    
                    # CRITICAL: Ensure account_id is preserved in the pending intent
                    if not intent.get("account_id"):
                        logging.error("[process_conversation] CHECK_DEPOSIT: account_id is MISSING in intent when asking for check amount!")
                        intent["account_id"] = acct_id
                    
                    return {
                        "success": False,
                        "clarification_needed": True,
                        "question": f"What is the amount of check #{check_index}?",
                        "options": [],
                        "missing_fields": [f"check_{check_index}_amount"],
                        "error": "MISSING_FIELDS",
                        "_pending_intent": intent,  # Store intent for next iteration
                    }
                
                # All checks collected - proceed to UI flow with pre-populated checks
                logging.info(f"[process_conversation] CHECK_DEPOSIT: {num_checks} checks collected, proceeding to flow_steps")
                logging.info(f"[process_conversation] CHECK_DEPOSIT: collected_checks data: {collected_checks}")
                logging.info(f"[process_conversation] CHECK_DEPOSIT: account_id: {acct_id}")
                total_amount = sum(check["amount"] for check in collected_checks)
                human_msg = (
                    f"I'll help you deposit {num_checks} check{'s' if num_checks > 1 else ''} "
                    f"(total ${total_amount:.2f}) into {acc_label}. "
                    "Please review the details on the screen."
                )

                return {
                    "success": True,
                    "message": human_msg,
                    "transaction_intent": intent,
                    "flow_steps": [
                        {
                            "step": "deposit_type_selection",
                            "data": {
                                "preselected_type": "check",
                                "account_id": acct_id,
                            },
                        },
                        {
                            "step": "check_deposit_screen",
                            "data": {
                                "account_id": acct_id,
                                "checks": collected_checks,  # Pre-populate with collected checks
                            },
                        },
                        {
                            "step": "check_deposit_review",
                            "data": {},
                        },
                        {
                            "step": "check_deposit_confirmation",
                            "data": {},
                        },
                    ],
                    "error": None,
                }

            elif op == "TRANSFER":
                # Try to resolve source account from source_account_type if not already set
                if not src_id:
                    src_type = intent.get("source_account_type")
                    if src_type:
                        src_id = self.pick_account_id_for_type(src_type, accounts)
                        if src_id:
                            intent["source_account_id"] = src_id
                            intent["from_account_id"] = src_id
                            logging.info("[process_conversation] TRANSFER: resolved source_account_type '%s' to account_id %s", src_type, src_id)
                
                # Try to resolve destination account from destination_account_type if not already set
                if not dst_id:
                    dst_type = intent.get("destination_account_type")
                    if dst_type:
                        # For destination, exclude source account
                        dst_candidates = [a for a in accounts if a["id"] != src_id] if src_id else accounts
                        dst_id = self.pick_account_id_for_type(dst_type, dst_candidates)
                        if dst_id:
                            intent["destination_account_id"] = dst_id
                            intent["to_account_id"] = dst_id
                            logging.info("[process_conversation] TRANSFER: resolved destination_account_type '%s' to account_id %s", dst_type, dst_id)
                
                # Check for missing source account
                if not src_id:
                    if len(accounts) == 1:
                        intent["source_account_id"] = accounts[0]["id"]
                        intent["from_account_id"] = accounts[0]["id"]
                        src_id = accounts[0]["id"]
                    else:
                        # Filter by source account type if specified
                        src_type = intent.get("source_account_type")
                        candidates = accounts
                        if src_type:
                            src_type_upper = src_type.upper()
                            candidates = [a for a in accounts if (a.get("type") or "").upper() == src_type_upper]
                            if not candidates:
                                logging.warning("[process_conversation] TRANSFER: no accounts match source_account_type=%s, using all accounts", src_type)
                                candidates = accounts
                        
                        options = [
                            {
                                "id": acc["id"],
                                "account_name": acc.get("account_name") or acc["type"],
                                "type": acc.get("type"),
                                "balance": acc.get("balance"),
                                "currency": acc.get("currency"),
                            }
                            for acc in candidates
                        ]
                        logging.warning("[process_conversation] TRANSFER: missing source_account_id, asking for clarification.")
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": "Which account would you like to transfer from?",
                            "options": options,
                            "missing_fields": ["from_account_id is required"],
                            "error": "MISSING_FIELDS",
                            "_pending_intent": intent,
                        }

                # Check for missing destination account
                if not dst_id and not intent.get("is_external"):
                    # Filter by destination account type if specified
                    dst_type = intent.get("destination_account_type")
                    candidates = [a for a in accounts if a["id"] != src_id]  # Exclude source account
                    
                    if dst_type and candidates:
                        dst_type_upper = dst_type.upper()
                        typed_candidates = [a for a in candidates if (a.get("type") or "").upper() == dst_type_upper]
                        if typed_candidates:
                            candidates = typed_candidates
                        else:
                            logging.warning("[process_conversation] TRANSFER: no accounts match destination_account_type=%s, using all remaining accounts", dst_type)
                    
                    destination_options = [
                        {
                            "id": acc["id"],
                            "account_name": acc.get("account_name") or acc["type"],
                            "type": acc.get("type"),
                            "balance": acc.get("balance"),
                            "currency": acc.get("currency"),
                        }
                        for acc in candidates
                    ]
                    if destination_options:
                        logging.warning("[process_conversation] TRANSFER: missing destination_account_id, asking for clarification.")
                        return {
                            "success": False,
                            "clarification_needed": True,
                            "question": "Which account would you like to transfer to?",
                            "options": destination_options,
                            "missing_fields": ["to_account_id is required"],
                            "error": "MISSING_FIELDS",
                            "_pending_intent": intent,
                        }
                    else:
                        logging.warning("[process_conversation] TRANSFER: no destination accounts available.")
                        return {
                            "success": False,
                            "clarification_needed": False,
                            "question": "You only have one account. Cannot transfer to the same account.",
                            "options": [],
                            "missing_fields": ["to_account_id is required"],
                            "error": "MISSING_FIELDS",
                        }

                # Check for missing amount
                if not amt or amt == 0:
                    logging.warning("[process_conversation] TRANSFER: missing amount.")
                    return {
                        "success": False,
                        "clarification_needed": False,
                        "question": "How much would you like to transfer?",
                        "options": [],
                        "missing_fields": ["amount is required"],
                        "error": "MISSING_FIELDS",
                    }

                src = next((a for a in accounts if a["id"] == src_id), None)
                dst = next((a for a in accounts if a["id"] == dst_id), None) if dst_id else None
                src_label = src.get("account_name") if src else "your source account"
                is_external = intent.get("is_external", False)
                if is_external:
                    dst_label = "your external account"
                else:
                    dst_label = dst.get("account_name") if dst else "your destination account"

                human_msg = (
                    f"I'll help you transfer ${amt:.2f} from {src_label} to {dst_label}. "
                    "Please review and confirm on the screen."
                )

                logging.info("[process_conversation] TRANSFER -> flow_steps (is_external=%s)", is_external)
                return {
                    "success": True,
                    "message": human_msg,
                    "transaction_intent": intent,
                    "flow_steps": [
                        {
                            "step": "transfer_to_account",
                            "data": {
                                "preselected_account_id": dst_id,
                                "is_external": is_external,
                            },
                        },
                        {
                            "step": "transfer_from_account",
                            "data": {
                                "preselected_account_id": src_id,
                            },
                        },
                        {
                            "step": "transfer_amount",
                            "data": {
                                "amount": float(amt),
                            },
                        },
                        {
                            "step": "transfer_review",
                            "data": {},
                        },
                        {
                            "step": "transfer_confirmation",
                            "data": {},
                        },
                    ],
                    "error": None,
                }

            elif op == "CHANGE_PIN":
                human_msg = (
                    "I'll help you change your PIN. "
                    "Please follow the instructions on the screen to enter your old and new PIN securely."
                )

            logging.info("[process_conversation] Returning structured intent without flow_steps.")
            return {
                "success": True,
                "message": human_msg,
                "transaction_intent": intent,
                "flow_steps": [],
                "error": None,
            }

        # ----------------------------------------------------------------------
        # D) No intent detected → fallback to generic LLM response
        # ----------------------------------------------------------------------
        prompt = f"{self.get_system_prompt()}\n\n"
        for msg in conversation_history[-5:]:
            prompt += f"{msg['sender']}: {msg['content']}\n"
        prompt += f"USER: {message}\nASSISTANT: "

        logging.info("[process_conversation] Fallback to Ollama LLM with prompt.")
        response = await self.retry_ollama_request(prompt, self.get_available_tools())
        if not response:
            logging.error("[process_conversation] LLM unavailable.")
            return {
                "error": "LLM_UNAVAILABLE",
                "message": "Conversational mode unavailable. Please use Traditional ATM.",
                "success": False,
            }

        logging.info("[process_conversation] LLM response received.")
        return {
            "success": True,
            "message": response.get("response", ""),
            "tool_calls": response.get("tool_calls", []),
            "error": None,
        }


# Global orchestrator instance
orchestrator = OllamaOrchestrator()
