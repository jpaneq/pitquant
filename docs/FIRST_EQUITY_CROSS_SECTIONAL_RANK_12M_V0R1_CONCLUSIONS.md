# Conclusions — V0R1

The TRAIN availability revision is deterministic and structurally justified: only val_pe_own_pct is excluded, preserving the frozen dataset and every observation.

The first real fit failed the unchanged defined-inner-IC requirement. A manifest description/count bug was also recorded and corrected in a separate immutable metadata revision. No valid final signal classification or F3 conclusion exists.

Iteration 3 has been consumed by a real fit. Do not silently rerun, discard a candidate, reduce min_child_weight, change normalization or weaken the IC guard. Human review is required before any new fit. Holdout/OOT remain sealed.
