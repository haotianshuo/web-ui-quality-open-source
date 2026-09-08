# Write safety and change sets

A user request to inspect is read-only. A user request to fix allows the Host to propose a narrow change, but it does not let serialized files manufacture authority.

A trusted write approval must be:

- created by the current Host process;
- bound to the current task and conversation;
- limited to exact files and operation types;
- valid at the moment of application;
- renewed when scope expands.

The user-facing confirmation should state what will change, why, which files are in scope, what will not happen, and how the result will be retested. Internal receipt, token, fingerprint, and approval object names belong in technical logs, not the default interaction.

Dependency changes, API changes, permissions, persistence, destructive operations, publication, commit, push, and deployment require separate explicit scope.
