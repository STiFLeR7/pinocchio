# Repository Governance E2E Validation Report

This report documents the end-to-end execution outcomes and audit log records generated during the failure testing suite (AP-304).

---

## 1. Validation Run Output

Running the acceptance script [verify_repository_governance.py](file:///D:/nexus/scripts/verify_repository_governance.py) produces the following outputs:

### Scenario 1: Unknown Repository
* **Action**: Try to validate command in `/unregistered/path/to/repo`.
* **Outcome**: Rejected before execution starts.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'RepositoryValidated' for task 2a723397-d29f-4151-9f5f-1f1fd66b1655
    Data: {'status': 'failed', 'working_dir': '/unregistered/path/to/repo', 'reason': 'Unknown repository'}
  ```

### Scenario 2: Blocked Runtime
* **Action**: Request `nexus` on a repo whitelisting only `["gemini", "claude"]`.
* **Outcome**: Rejected.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'RuntimeRejected' for task e992785f-63ab-4cb5-a567-f516c3adde1e
    Data: {'runtime': 'nexus', 'allowed_runtimes': ['gemini', 'claude'], 'reason': 'Runtime not allowed for repo'}
  ```

### Scenario 3: Blocked Branch
* **Action**: Run execution while the repository is on a blocked branch (`master`).
* **Outcome**: Rejected.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'BranchRejected' for task 3e02ec90-d640-460d-a38e-db62bbaa45f8
    Data: {'branch': 'master', 'blocked_branches': ['master', 'main'], 'reason': 'Branch is blocked'}
  ```

### Scenario 4: Policy Violation
* **Action**: Set task `runtime_policy="blocked"`.
* **Outcome**: Rejected.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'PolicyViolation' for task 7d52a0d8-d55b-407d-852c-149d1693c081
    Data: {'runtime_policy': 'blocked', 'expected': 'approved', 'reason': 'Policy mismatch'}
  ```

### Scenario 5: Expired or No Approval
* **Action**: Execute task lacking approval record.
* **Outcome**: Rejected.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'ExecutionBlocked' for task 6552a56c-7dc1-4436-b95a-568d2eee273c
    Data: {'reason': 'Execution lacks active approval authorization', 'status': 'no_approval'}
  ```

### Scenario 6: Repository Disabled
* **Action**: Set repository status to `"disabled"`.
* **Outcome**: Rejected.
* **Audit Entry**:
  ```
  [DB AuditLogRecord] FOUND 'RepositoryValidated' for task e26fd71b-6f74-436a-a0ad-ff40c2af5f39
    Data: {'status': 'failed', 'repository_id': '6720f51f-6d46-4efd-a8d7-bbf7b898b046', 'reason': 'Repository disabled'}
  ```

---

## 2. Integrity and Recovery Assertions

1. **Zero Execution Start**: In all 6 scenarios, execution aborts *before* the runner adapter is instantiated or shell command spawned.
2. **Audit Ledger**: The ledger correctly appends the reasons for rejection.
3. **State Consistency**: Tasks aborting due to safety violations safely default to cancelled or failed states, ensuring recovery sweeps do not restart them.
