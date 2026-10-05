"""Compatibility entry point for the current evidence-tier critical-path report.

The V2 implementation and its reports remain in Git at 01eb216. Old commands
must not overwrite the applied ADR-0056 decision with a superseded contract.
"""

from gen_d02_evidence_tiers_report import main

if __name__ == "__main__":
    main()
