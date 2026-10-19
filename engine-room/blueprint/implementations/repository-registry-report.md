# Repository Registry Schema Report

This report documents the schema and fields defined for the **Repository Registry** in Nexus under AP-304.

---

## 1. Schema Definitions

The `repository_registry` table contains the following columns:

| Column Name | Database Type | Description | Default |
| --- | --- | --- | --- |
| `id` | `Uuid` (Primary Key) | Standard primary key mapping. | `uuid4` |
| `name` | `String(200)` | Unique name of the repository. | None |
| `absolute_path` | `String(1000)` | Absolute directory path on local disk. | None |
| `allowed_branches`| `JSON` | List/dict of wildcard branch patterns allowed. | Required |
| `allowed_commands`| `JSON` | List of allowed CLI commands. | Required |
| `timeout_limit` | `Integer` | Max timeout allowed for this repository. | `3600` |
| `is_active` | `Boolean` | Flag representing repository status. | `True` |
| `allowed_runtimes`| `JSON` | Whitelisted runtimes (e.g. `["gemini"]`). | `NULL` |
| `allowed_profiles`| `JSON` | Whitelisted profiles (e.g. `["coding"]`). | `NULL` |
| `blocked_branches`| `JSON` | Blocked wildcard branch patterns. | `NULL` |
| `protected_branches`| `JSON` | Protected wildcard branch patterns. | `NULL` |
| `owner` | `String(200)` | Authorized owner user IDs (comma-separated).| `NULL` |
| `status` | `String(50)` | Current status (`"active"`, `"disabled"`). | `"active"` |
| `created_at` | `DateTime` | Record creation timestamp. | `now` |
| `updated_at` | `DateTime` | Record update timestamp. | `now` |

---

## 2. Backward Compatibility Wrappers

To avoid database column rename churn across scripts, the SQLAlchemy model maps properties:
* **`repository_id`**: Property alias returning `self.id`.
* **`repository_name`**: Property alias/setter mapping to the `name` column.
* **`repository_path`**: Property alias/setter mapping to the `absolute_path` column.
