#!/usr/bin/env python3
"""
Mongo ABAC CLI
- Login by entering your employee ID (or 'admin' for the admin role)
- Connects to MongoDB with hard-coded credentials (adminLocal/adminLocal)
- Enforce Py-ABAC policies stored in MongoDB
- Menu-driven CRUD operations
- Logs all login events and user actions to cli.log
- Uses prompt_toolkit.prompt() to supports the arrow clicks
"""

import sys
import json
from datetime import datetime, timezone
import logging
import re

from pymongo import MongoClient
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from abac_mongo_cli.abac import initialize_pdp, build_request

# -------------------------------------------------------------------
# MongoDB connection settings (hard-coded)
MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_USER = "adminLocal"
MONGO_PASS = "adminLocal"
DB_NAME    = "Northwind"
# -------------------------------------------------------------------

# --- Configure CLI logging -----------------------------------------
cli_logger = logging.getLogger("abac_mongo_cli")
cli_logger.setLevel(logging.INFO)
cli_fh = logging.FileHandler("cli.log", encoding="utf-8")
cli_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
cli_fh.setFormatter(cli_fmt)
if not any(isinstance(h, logging.FileHandler) for h in cli_logger.handlers):
    cli_logger.addHandler(cli_fh)

# shared history file for all prompts
history = FileHistory(".abac_mongo_history")

def banner():
    # Custom ASCII banner
    return r"""
     ________  ________  ________  ________                _____ ______   ________  ________   ________  ________     
|\   __  \|\   __  \|\   __  \|\   ____\              |\   _ \  _   \|\   __  \|\   ___  \|\   ____\|\   __  \    
\ \  \|\  \ \  \|\ /\ \  \|\  \ \  \___|  ____________\ \  \\\__\ \  \ \  \|\  \ \  \\ \  \ \  \___|\ \  \|\  \   
 \ \   __  \ \   __  \ \   __  \ \  \    |\____________\ \  \\|__| \  \ \  \\\  \ \  \\ \  \ \  \  __\ \  \\\  \  
  \ \  \ \  \ \  \|\  \ \  \ \  \ \  \___\|____________|\ \  \    \ \  \ \  \\\  \ \  \\ \  \ \  \|\  \ \  \\\  \ 
   \ \__\ \__\ \_______\ \__\ \__\ \_______\             \ \__\    \ \__\ \_______\ \__\\ \__\ \_______\ \_______\
    \|__|\|__|\|_______|\|__|\|__|\|_______|              \|__|     \|__|\|_______|\|__| \|__|\|_______|\|_______|
                                                                                                                  
                                                                                                                  
                                            ABAC-MONGO CLI v0.1.0
                        Attribute-Based Access Control for MongoDB with Py-ABAC 
                                            Rúben Pereira
    """

def main_menu():
    while True:
        subject_id = prompt("Enter your ID (or 'admin'): ", history=history).strip()
        # Determine role and attributes
        if subject_id.lower() == "admin":
            subject_attrs = {"id": "admin"}
            subject_attrs["role"] = "admin"
            subject_attrs["userIP"] = None # making subject_attrs = {'id': 'admin', 'role': 'admin', 'userIP': None}
            break
        try:
            subject_attrs = {"id": int(subject_id)}
            #subject_id = int(subject_id)
            subject_attrs["role"] = "ordersManager"
            subject_attrs["isChief"] = prompt("Are you chief? [y/N]: ", history=history).strip().lower() in ("y", "yes")
            ip_pattern = re.compile(r"^(25[0-5]|2[0-4]\d|[01]?\d?\d)(\.(25[0-5]|2[0-4]\d|[01]?\d?\d)){3}$")
            while True:
                user_ip = prompt("Your IPv4 address: ", history=history).strip()
                if ip_pattern.match(user_ip):
                    subject_attrs["userIP"] = user_ip # making subject_attrs = {'id': 1,'role': 'ordersManager', 'isChief': T/F, 'userIP': None}
                    break
                else:
                    print("Invalid IP! Enter a valid IPv4 (e.g. 192.168.0.1).")
            break
        except ValueError:
            print("Invalid input!")

    return subject_attrs       

def secundary_menu(admin):
    print("\nSelect action:")
    print(" 1) Find documents")
    print(" 2) Insert document")
    print(" 3) Update documents")
    print(" 4) Delete documents")
    if admin:
        print(" 5) Show policies")
        print(" 6) Delete policy")
    print(" 0) Exit")
    return prompt("> ", history=history).strip()

def connection(subject_id):
    # Connect to MongoDB using hard-coded credentials
    try:
        client = MongoClient(
            host=MONGO_HOST,
            port=MONGO_PORT,
            username=MONGO_USER,
            password=MONGO_PASS,
            authSource=DB_NAME
        )
        client.admin.command("ping")  # verify connectivity
    except Exception as e:
        cli_logger.error(f"MongoDB connection failed for user='{subject_id}': {e}")
        print(f"✖ Could not connect to MongoDB: {e}")
        sys.exit(1)

    print("✔ Login successful.\n")
    return client

def perform_request():
    return 0

def shell():
    print(banner())
    subject_attrs = main_menu()
    subject_id = subject_attrs["id"]
    role = subject_attrs["role"]
    user_ip = subject_attrs["userIP"]

    # Log the login event
    cli_logger.info(f"Login: user='{subject_id}' role='{role}' attrs={subject_attrs}")

    # Create DB connection and get client
    client = connection(subject_id)

    # Initialize ABAC PDP (loads policies + configures logging)
    pdp = initialize_pdp(client, db_name=DB_NAME)

    is_admin = (role == "admin")
    # Menu-driven loop
    while True:
        # Print options menu
        choice = secundary_menu(is_admin)

        if choice == "0":
            cli_logger.info(f"Exit: user='{subject_id}'")
            print("👋 Goodbye!")
            break
        elif (choice not in ("1", "2", "3", "4") and not is_admin) or (choice not in ("1", "2", "3", "4", "5", "6") and is_admin):
            print("Invalid choice! Try again!")
        else:
            if is_admin and choice == "5":
                choice = "1"
                collection = "py_abac_policies"
                raw = ""
            elif is_admin and choice == "6":
                choice = "4"
                collection = "py_abac_policies"
                raw = f'{{"_id": "{prompt("Enter policy ID: ", history=history).strip()}"}}'
                print(raw)
            else:
                collection = prompt("Collection name: ", history=history).strip()
                raw = prompt("Enter JSON payload (filter or document): ", history=history).strip()
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError as e:
                cli_logger.warning(f"Invalid JSON by user='{subject_id}': {e}")
                print(f"✖ Invalid JSON: {e}")
                continue

            action_map = {
                "1": ("read",   "find"),
                "2": ("create", "insert_one"),
                "3": ("update", "update_many"),
                "4": ("delete", "delete_many")
            }
            if choice not in action_map:
                print("✖ Invalid option.")
                continue

            abac_action, pymongo_op = action_map[choice]
            now = datetime.now(timezone.utc)
            context = {
                "ip":      user_ip,
                "weekday": now.strftime("%a"),
                "hour":    now.hour
            }

            # Build & evaluate ABAC request
            req = build_request(
                subject_id,             subject_attrs,
                resource_id=collection, resource_attrs={"type": collection.rstrip("s")},
                action_id=abac_action,  action_attrs={"method": abac_action},
                context=context
            )
            decision = pdp.is_allowed(req)
            cli_logger.info(
                f"ABAC decision: user='{subject_id}' action='{abac_action}' "
                f"resource='{collection}' payload={payload} → {'ALLOW' if decision else 'DENY'}"
            )
            if not decision:
                print("🚫 Access denied by policy.")
                continue

            # Execute the allowed operation
            col = client[DB_NAME][collection]
            try:
                if pymongo_op == "find":
                    cli_logger.info(f"Executing find by user='{subject_id}' on '{collection}' filter={payload}")
                    
                    #1 executes the find and saves the docs in a list
                    docs = list(col.find(payload))
                    count = len(docs)

                    #2 logs and prints the resume
                    cli_logger.info(
                        f"User='{subject_id}' found {count} docs in '{collection}' with filter={payload}"
                    )
                    print(f"✔ Found {count} document(s):")

                    #3 if none, ends
                    if count == 0:
                        continue

                    #4 otherwise, prints each one
                    for i, doc in enumerate(docs,1):
                        print(f"\n- Document #{i} -")
                        print(json.dumps(doc, default=str, indent=2))
                elif pymongo_op == "insert_one":
                    cli_logger.info(f"Executing insert by user='{subject_id}' on '{collection}' doc={payload}")
                    res = col.insert_one(payload)
                    print(f"✔ Inserted _id={res.inserted_id}")
                elif pymongo_op == "update_many":
                    cli_logger.info(f"Executing update by user='{subject_id}' on '{collection}' payload={payload}")
                    filt = payload.get("filter", {})
                    upd  = payload.get("update", {})
                    res  = col.update_many(filt, upd)
                    print(f"✔ Matched {res.matched_count}, modified {res.modified_count}")
                elif pymongo_op == "delete_many":
                    cli_logger.info(f"Executing delete by user='{subject_id}' on '{collection}' filter={payload}")
                    res = col.delete_many(payload)
                    print(f"✔ Deleted {res.deleted_count}")
            except Exception as e:
                cli_logger.error(
                    f"MongoDB operation error for user='{subject_id}' "
                    f"op='{pymongo_op}' on '{collection}': {e}"
                )
                print(f"✖ MongoDB error: {e}")

if __name__ == "__main__":
    try:
        shell()
    except KeyboardInterrupt:
        # Ctrl+c anywhere to end
        print("\n^C detected, exiting.")
        sys.exit(0)
