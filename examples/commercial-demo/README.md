# Northstar CRM design-work demo

This is a functional CRM, not a screenshot fixture. Search, filters, list/detail selection, mobile detail presentation, local feedback, empty state, and safe disabled behavior are implemented in plain HTML, CSS, and JavaScript.

Run the complete 3.7 workflow:

```bash
python -B run_demo.py --browser-executable /path/to/chromium
```

The output directory must be outside this demo source. Open `design-gallery/index.html` first. It shows three independently runnable designs at desktop, tablet, and mobile sizes, their Browser results, selection reason, and direct links to each candidate.

Historical checked output is intentionally excluded from this upgraded distribution. Use separately archived regression evidence when maintaining older baselines; it is not current product output.
