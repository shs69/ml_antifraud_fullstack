from __future__ import annotations

import subprocess
import sys


def main():
    scenarios = [2, 3]
    quantiles = [0.999, 0.995, 0.99]

    for scenario in scenarios:
        for q in quantiles:
            print(f"\n\n=== scenario={scenario}, anomaly_normal_quantile={q} ===")
            cmd = [
                sys.executable,
                "scripts/run_unseen_scenario_v2.py",
                "--heldout-scenario",
                str(scenario),
                "--anomaly-normal-quantile",
                str(q),
            ]
            subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
