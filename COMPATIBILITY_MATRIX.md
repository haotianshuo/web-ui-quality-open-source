> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Compatibility matrix

| Area | Declared support | Boundary |
| --- | --- | --- |
| Python | `>=3.10` | Run the public tests on the interpreter you intend to support. |
| Runtime dependency | Pillow `>=10,<13` | The package does not vendor Pillow. |
| Optional Browser | Playwright `>=1.50,<2` | A usable compatible browser executable is also required. |
| Public test runner | pytest `>=8,<10` | Tests cover the published self-contained contract only. |
| Operating system | Windows and other Python-capable environments are intended targets | Native Host and Browser qualification is environment-specific and not measured here. |
| AI Host | Host integration is external | No model accuracy or provider-retention claim is made. |

The exact qualification environment used during this audit is recorded outside
the public source candidate. Dependency versions and licenses must be reviewed
again when a distribution environment is changed.

