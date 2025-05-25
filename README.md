# ABAC-Mongo CLI

A Python CLI tool providing Attribute-Based Access Control (ABAC) on top of MongoDB.

## Features

- Login as `ordersManager` or `admin`
- Interactive menu with arrow-key editing and history
- Py-ABAC policy enforcement for every operation
- Detailed logging of policy decisions and MongoDB actions
- Automatic loading of all JSON policies in `policies/`

## Installation

1. **Clone the repo**
```bash
git clone https://github.com/rmgp-2009/abac-mongo-cli.git abac-mongo
cd abac-mongo
```

2. Create and activate a virtual environment (optional but recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install Dependencies in editable mode:
```bash
pip install -e .
```
This will install:
- pymongo
- py-abac[mongo]
- prompt_toolkit

## Usage

Run the CLI either via the installed script:
```bash
abac-mongo
```
Or directly with Python:
```bash
python3 -m abac_mongo_cli.main
```

You will be prompted to:
1. Enter your ID (or type admin for the super-user).
2. If you log in as an ordersManager, you'll be asked:
    - "Are you chief? [y/N]"
    - "Your IP address:"
3. Then you'll see a menu to:
    1. Find documents
    2. Insert document
    3. Update documents
    4. Delete documents
    5. View Policies (Admin)
    6. Delete Policy (Admin)
    0. Exit

For each operation you enter:
- Collection name (e.g. Orders, orders_status)
- A single-line JSON payload for filter, document, or update spec

## Policies

All ABAC policies live as JSON files in the `policies/` directory.
- You can **add**, **remove**, or **edit** any `*.json` there to suit your organization's rules. 
- On startup the CLI will load every JSON policy it finds.
- **NOTE: The policies should follow the Policy Language defined by Py-ABAC https://py-abac.readthedocs.io/en/latest/policy_language.html**.

## Logs

- `abac.log` - detailed traced of every policy load and ABAC decision (INFO+).
- `cli.log` - records of each login and MongoDB action initiated by a user.
Both files are generated in the directory where you run `abac-mongo`.

## MongoDB Login

The MongoDB connection in this tool is **hard-coded** for a local super-user and the default MongoDB connection.
- **You must change this configuration based on your needs**.

## Tailoring to Your Environment

The CLI, its menu prompts, example collections and logic flow, is build around Northwind databased and the author's personal needs.
- **Database name**, collection names and field names may differe in your setup.
- **Login logic** in `main.py` (roles, attributes, MongoDB connection) should be adapted to your organization's user management or authentication system.

## License & Maintenance

- **License:** MIT License (see `LICENSE` file)
- **Maintenance:** This code is provided "as is" and will **not** be actively maintained. Use at your own risk.

## Third Party Notices

This project depends on the following libraries:
- **Py-ABAC** (Apache 2.0)
- **prompt_toolkit** (BSD 3-Clause)

For the full text of each license, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
