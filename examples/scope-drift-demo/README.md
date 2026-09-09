# Scope drift demo

This is a disposable public fixture for demonstrating a bounded repair request.
`component.html` is the only approved source file. `companion.txt` is a
deliberately out-of-scope file that must stay unchanged.

From the repository root, run:

~~~bash
web-ui-quality run --json --ci --require VERIFIED --file component.html examples/scope-drift-demo "修复 component.html 里的保存按钮；不要修改 companion.txt"
~~~

The command is a real source-checkout run, not a prewritten JSON example. It
records the Before state and stops when the trusted Host write receipt and
required verification evidence are missing. If an authorized Host changes
`companion.txt`, the later project-drift check must keep the result from being
reported as `VERIFIED`.

The checked-in [`actual-run.json`](actual-run.json) is the captured TaskResult
from this command. Its real result is `NOT_VERIFIED` with
`HOST_RECEIPT_REQUIRED`; it is not presented as a successful repair. The
public acceptance run in [`actual-drift-gate.json`](actual-drift-gate.json)
also exercises an unexpected baseline change and confirms that it blocks a
`VERIFIED` claim.

This fixture is for local testing only. It does not measure Browser behavior,
Host accuracy, model accuracy, or production outcomes.
