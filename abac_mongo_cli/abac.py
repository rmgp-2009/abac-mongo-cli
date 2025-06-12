#!/usr/bin/env python3
"""
Helper module to initialize Py-ABAC PDP, apply migrations,
auto-load all policies and configure py-abac logging.
"""

import glob
import json
import os
import logging

from py_abac import PDP, Policy, Request, EvaluationAlgorithm
from py_abac.storage.mongo import MongoStorage, MongoMigrationSet
from py_abac.storage.migration import Migrator

def configure_abac_logging(log_file="abac.log"):
    """
    Configure the logging system so that all Py-ABAC events at DEBUG level
    and above are written to the specified file.
    This will:
      1. Remove any existing handlers on the root logger.
      2. Set up a FileHandler via basicConfig to capture all messages at DEBUG level and above.
      3. Explicitly set the “py_abac” and “py_abac.pdp” loggers to DEBUG.

    :param log_file: Path to the file where log entries will be appended.
    :type log_file: str
    """
    # Remove any previously registered handlers
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    # Configure the root logger to write DEBUG+ messages to log_file
    logging.basicConfig(
        level    = logging.DEBUG,
        filename = log_file,
        filemode = "a",   # "w" para sobrescrever, "a" para acrescentar
        format   = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Ensure Py-ABAC’s loggers also emit DEBUG+ into the same file
    logging.getLogger("py_abac").setLevel(logging.DEBUG)
    logging.getLogger("py_abac.pdp").setLevel(logging.DEBUG)

def load_policies(storage, policies_dir="policies"):
    """
    Load all JSON policy files from the specified directory into the MongoStorage.

    :param storage: The MongoStorage instance to which policies will be added.
    :type storage: MongoStorage
    :param policies_dir: Path to the directory containing policy JSON files.
    :type policies_dir: str
    """
    logger = logging.getLogger("py_abac")  
    base = os.getcwd()
    for path in glob.glob(os.path.join(base, policies_dir, "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                policy_json = json.load(f)
                storage.add(Policy.from_json(policy_json))
                print(f"**** Loaded {policy_json.get('uid')} ****")
        except Exception as exc:
            # Ignore duplicates or invalid files
            #print(f"!!! Skipping {os.path.basename(path)}: {exc} !!!") # Only for debug pourposes 
            logger.error(f"Skipping policy file '{os.path.basename(path)}': {exc}")
            pass

def delete_policy(client, policy_uid):
    """
    Deletes a policy from MongoStorage.

    :param storage: The MongoStorage instance to which policies will be added.
    :type storage: MongoStorage
    :param policy_uid: Policy uid
    :type policy_uid: str
    """    
    logger = logging.getLogger("py_abac")
    storage = MongoStorage(client, db_name="Northwind")
    try:
        storage.delete(policy_uid)
        print(f"**** Policy {policy_uid} deleted ****")
        print(f"**** Remember to delete the policy JSON from Policies directory ****")
    except Exception as exc:
        logger.error(f"Failed to dele policy '{policy_uid}': {exc}")
        pass

def update_policy(client, policy_name, policies_dir="policies"):
    """
    Update the ABAC policy with the given name by reloading its JSON file.

    :param client: A pymongo.MongoClient connected to the MongoDB server.
    :type client: MongoClient
    :param policy_name: Filename (without .json) of the policy to update.
    :type policy_name: _str
    :param policies_dir: Path to the directory containing policy JSON files.
    :type policies_dir: str
    """    
    logger = logging.getLogger("py_abac")
    path = os.path.join(os.getcwd(), policies_dir, f"{policy_name}.json")
    storage = MongoStorage(client, db_name="Northwind")
    try:
        with open(path, "r", encoding="utf-8") as f:
            policy_json = json.load(f)
            storage.update(Policy.from_json(policy_json))
            print(f"**** Updated {policy_json.get('uid')} ****")
    except Exception as exc:
        print(f"!!! Skipping {os.path.basename(path)}: {exc} !!!") # Only for debug pourposes 
        logger.error(f"Skipping policy file '{os.path.basename(path)}': {exc}")
        pass

def get_policies(client):
    """
    Prints all access control policies from Mongo storage in pages of 3,
    clearing the terminal between pages. Press Enter to continue.

    :param client: A pymongo.MongoClient connected to the MongoDB server.
    :type client: MongoClient
    """
    logger = logging.getLogger("py_abac")
    storage = MongoStorage(client, db_name="Northwind")
    page_size = 3
    offset = 0
    page = 1

    try:
        while True:
            policies = list(storage.get_all(limit=page_size, offset=offset))
            if not policies:
                print("\n[END OF POLICIES]")
                break

            os.system('clear' if os.name == 'posix' else 'cls')  # limpa terminal
            print(f"--- Page {page} (offset={offset}) ---\n")

            for policy in policies:
                try:
                    pretty = json.dumps(policy.to_json(), indent=3, ensure_ascii=False)
                    print(pretty)
                    print("-" * 80)
                except Exception as exc:
                    logger.error(f"Error converting policy UID={policy.uid}: {exc}")

            offset += page_size
            page += 1
            input("Press Enter to continue...")

    except Exception as exc:
        logger.error(f"Error obtaining policies: {exc}")


def initialize_pdp(client, db_name="Northwind", policies_dir="policies"):
    """
    Set up the Mongo-backed storage for ABAC policies, apply migrations,
    load all JSON policies from the given directory, configure logging,
    and return a configured PDP instance.

    :param client: A pymongo.MongoClient connected to the MongoDB server.
    :type client: MongoClient
    :param db_name: Name of the database where ABAC policies are stored.
    :type db_name: str
    :param policies_dir: Path to the directory containing policy JSON files.
    :type policies_dir: str
    :return: An initialized Policy Decision Point (PDP) ready for evaluation.
    :rtype: PDP
    """    
    # 1) configure logging for py_abac
    configure_abac_logging()

    # 2) storage + migrations
    storage = MongoStorage(client, db_name=db_name)
    Migrator(MongoMigrationSet(storage)).up()

    # 3) load all policies/*.json
    load_policies(storage, policies_dir=policies_dir)

    # 4) return the PDP
    return PDP(storage, EvaluationAlgorithm.HIGHEST_PRIORITY)

def build_request(subject_id, subject_attrs, resource_id, resource_attrs, action_id, action_attrs, context):
    """
    Create a Request object encapsulating subject, resource, action, and context for ABAC evaluation.

    :param subject_id: Unique identifier of the subject (e.g., user ID or 'admin').
    :type subject_id: str
    :param subject_attrs: Dictionary of subject attributes (e.g., role, isChief, userIP).
    :type subject_attrs: dict
    :param resource_id: Identifier of the resource (e.g., collection name or document ID).
    :type resource_id: str
    :param resource_attrs: Dictionary of resource attributes (e.g., employee_id, type).
    :type resource_attrs: dict
    :param action_id: Identifier of the action to perform (e.g., "read", "create").
    :type action_id: str
    :param action_attrs: Dictionary of action attributes (e.g., method name).
    :type action_attrs: dict
    :param context: Dictionary of contextual attributes (e.g., ip, weekday, hour).
    :type context: dict
    :return: A Py-ABAC Request object ready for policy evaluation.
    :rtype: AccessRequest
    """    
    subject  = {"id": subject_id,  "attributes": subject_attrs}
    resource = {"id": resource_id, "attributes": resource_attrs}
    action   = {"id": action_id,   "attributes": action_attrs}
    return Request(subject, resource, action, context)

