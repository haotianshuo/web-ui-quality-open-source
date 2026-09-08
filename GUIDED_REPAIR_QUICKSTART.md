> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Guided Repair Quickstart — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0; the Trust Kernel identity is 4.2.3.


## Scenario

> “订单页面手机上坏了。这个项目本来就很多历史报错；不要动登录逻辑。其他几个页面好像也有类似问题。”

### 1. Check readiness

```bash
python -B scripts/run_runtime.py doctor
```

### 2. Optional explicit authentication

```bash
python -B scripts/run_runtime.py auth legacy-admin ./storage-state.json \
  --allow-origin https://staging.example.com
```

### 3. Describe the task once

```bash
python -B scripts/run_runtime.py run . \
  "修复订单页移动端错位，不要动登录逻辑；如果多个页面是同一个共享组件导致，优先修根因" \
  --url https://staging.example.com/orders \
  --auth-profile legacy-admin
```

Runtime automatically anchors Goal/Protected Scope, routes the intent, seals the project baseline, gathers bounded evidence, maps findings to source, assigns a Risk Tier, creates a Change Budget, prepares a Patch Candidate, creates Host-gated project-tool plans and records resumable state. Runtime does not grant itself write permission. If the candidate exceeds its Change Budget, normal patch continuation stops until the user/Host explicitly widens scope and a new bound plan is created.

### 4. Host applies the patch

An integrated Host first submits the exact Patch Candidate and obtains the immutable V3 Host Apply Binding. The external Host then reviews/applies only that bound candidate and returns a Receipt Protocol v3 receipt. The Host-side HMAC secret is supplied through `WUQ_HOST_RECEIPT_HMAC_KEY`; Runtime does not create or persist that secret and cannot self-authorize the write. Required project tools are executed by the Host under the recorded binary/argv/cwd/network/resource/filesystem conditions.

For standalone integration use `--expert-json` only when you actually need Host binding artifacts. `--host-patch-candidate` binds a candidate before apply; the subsequent After run uses `--host-write-receipt`. A legacy receipt can be read for migration/diagnostics but cannot produce a new 4.2+ `VERIFIED`.

### 5. Verify the exact repair run

```bash
python -B scripts/run_runtime.py run . "验证刚才的修复" \
  --after-url https://staging.example.com/orders \
  --host-write-receipt ./host-write-receipt.json \
  --host-tool-result ./tsc-result.json
```

Repeat `--host-tool-result` for additional required plans.

### 6. Read TaskResult / Human Task Report

Normal output keeps protocol details out of the default view and shows four human areas only:

```text
结果：已完成并验证
改了什么：2 个目标文件
验证了什么：目标页面和本次修改已验证；未覆盖整个仓库
下一步：无需操作
...
```

A globally partial repository is never rendered as whole-project verification.

For machine use:

```bash
python -B scripts/run_runtime.py run . "验证刚才的修复" \
  --after-url https://staging.example.com/orders \
  --host-write-receipt ./host-write-receipt.json \
  --host-tool-result ./tsc-result.json \
  --ci
```

CI exit codes remain: `0 VERIFIED`, `2 REVIEW_REQUIRED`, `3 NOT_VERIFIED`, `4 FAIL`, `5 CLI/system error`.

### 7. Inspection is also human-first

```bash
python -B scripts/run_runtime.py run . "先别改，只看看这个页面"
```

This produces an Inspection Task Report with `changes = NONE`; it does not send ordinary users to `--expert-json`.

### 8. Review / revert scope

After a verified Host write, expert/machine state can include a repair-scope revert plan. The plan only identifies files and Before/After hashes; Host/Git/IDE must restore the actual content. It is never a whole-project rollback claim.

### 9. Resume

Say:

```text
继续上次任务
```

Resume restores workflow state, never write authority.


## Bundled vs installed entry

The canonical bundled-plugin examples above use `python -B scripts/run_runtime.py`. After installing the Python package, the equivalent console entry is `web-ui-quality ...`; both dispatch to the same Runtime contract.
