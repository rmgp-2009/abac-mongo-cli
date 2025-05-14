#!/usr/bin/env python3
"""
Northwind ABAC CLI
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
cli_logger = logging.getLogger("northwind_cli")
cli_logger.setLevel(logging.INFO)
cli_fh = logging.FileHandler("cli.log", encoding="utf-8")
cli_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
cli_fh.setFormatter(cli_fmt)
if not any(isinstance(h, logging.FileHandler) for h in cli_logger.handlers):
    cli_logger.addHandler(cli_fh)

# shared history file for all prompts
history = FileHistory(".northwind_history")

def banner():
    # --------------------------------
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
    

def shell():
    print(banner())
    subject_id = prompt("Enter your ID (or 'admin'): ", history=history).strip()

    # Determine role and attributes
    if subject_id.lower() == "admin":
        role = "admin"
        subject_attrs = {"role": role}
        user_ip = None
    else:
        role = "ordersManager"
        subject_attrs = {"role": role}
        is_chief = prompt("Are you chief? [y/N]: ", history=history).strip().lower() in ("y", "yes")
        subject_attrs["isChief"] = is_chief
        user_ip = prompt("Your IP address: ", history=history).strip()

    # Log the login event
    cli_logger.info(f"Login: user='{subject_id}' role='{role}' attrs={subject_attrs}")

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

    # Initialize ABAC PDP (loads policies + configures logging)
    pdp = initialize_pdp(client, db_name=DB_NAME)

    # Menu-driven loop
    while True:
        print("\nSelect action:")
        print(" 1) Find documents")
        print(" 2) Insert document")
        print(" 3) Update documents")
        print(" 4) Delete documents")
        print(" 5) Exit")
        choice = prompt("> ", history=history).strip()

        if choice == "5":
            cli_logger.info(f"Exit: user='{subject_id}'")
            print("👋 Goodbye!")
            break

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
                #cli_logger.info(f"Executing find by user='{subject_id}' on '{collection}' filter={payload}")
                #for doc in col.find(payload, limit=20):
                #    print(json.dumps(doc, default=str, indent=2))
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
