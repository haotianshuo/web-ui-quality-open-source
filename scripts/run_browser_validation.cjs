#!/usr/bin/env node
"use strict";

// Source-tree compatibility entry. The actual runner is package data so a
// clean Python wheel and a Codex plugin archive use the same implementation.
require("../runtime/python/web_ui_quality/browser_runner.cjs");
