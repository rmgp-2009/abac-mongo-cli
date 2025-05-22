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


#def configure_abac_logging(log_file="abac.log"):
 #   logger = logging.getLogger("py_abac")
 #   logger.setLevel(logging.DEBUG)
 #   fh = logging.FileHandler(log_file, encoding="utf-8")
 #   fh.setLevel(logging.DEBUG)
 #   fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
 #   fh.setFormatter(fmt)
 #   if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
 #       logger.addHandler(fh)
    
    # 3) Logger do PDP explicitamente
 #   pdp_logger = logging.getLogger("py_abac.pdp")
 #   pdp_logger.setLevel(logging.DEBUG)
 #   if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file
 #              for h in pdp_logger.handlers):
 #       pdp_logger.addHandler(fh)
 #   pdp_logger.propagate = False
 #   print(logging.root.manager.loggerDict.keys())


def configure_abac_logging(log_file="abac.log"):
    """
   Configure the py_abac logger to write INFO+ events to a file.
    """
    # Isto limpa quaisquer handlers já registados
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    # Configura o root logger para gravar tudo (DEBUG+) apenas em file
    logging.basicConfig(
        level    = logging.DEBUG,
        filename = log_file,
        filemode = "a",   # "w" para sobrescrever, "a" para acrescentar
        format   = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Puxa também o logger do py_abac e do PDP para DEBUG
    logging.getLogger("py_abac").setLevel(logging.DEBUG)
    logging.getLogger("py_abac.pdp").setLevel(logging.DEBUG)

def load_policies(storage, policies_dir="policies"):
    """
    Load all .json policy files from policies_dir into the MongoStorage.
    """
    base = os.getcwd()
    for path in glob.glob(os.path.join(base, policies_dir, "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                policy_json = json.load(f)
                storage.add(Policy.from_json(policy_json))
                print(f"  ✔ Loaded {policy_json.get('uid')}")
        except Exception as exc:
            # Ignore duplicates or invalid files
            # print(f"Falhou {path}: {exc}")
            print(f"  ⚠ Skipping {os.path.basename(path)}: {exc}")
            pass

def initialize_pdp(client, db_name="Northwind", policies_dir="policies"):
    """
    Set up the Mongo-backed storage for ABAC policies, apply migrations,
    load policies, configure logging, and return a PDP instance.
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

def build_request(subject_id, subject_attrs,
                  resource_id, resource_attrs,
                  action_id, action_attrs,
                  context):
    """
    Create a Request object to evaluate against the PDP.
    """
    subject  = {"id": subject_id,  "attributes": subject_attrs}
    resource = {"id": resource_id, "attributes": resource_attrs}
    action   = {"id": action_id,   "attributes": action_attrs}
    return Request(subject, resource, action, context)
