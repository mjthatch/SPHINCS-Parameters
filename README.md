# SPHINCS-Parameters
Scripts for exploring SPHINCS+ parameter tradeoffs, computing security levels, signature sizes, and signing/verification costs.
- [security.sage](security.sage) computes the security level for FORS and PORS+FP parameter sets
- [original-sphincs-parameter-search.sage](original-sphincs-parameter-search.sage) script from https://sphincs.org/data/sphincs+-specification.pdf (updated for SageMath 9.0)
- [costs.sage](costs.sage) computes signature sizes and signing/verification times for SPHINCS+ variants
- [stateful.sage](stateful.sage) evaluates stateful alternatives (XMSS, XMSS-MT, SHRINCS/UXMSS) against the SLH-DSA-128s baseline
- [octopus_pmf.py](octopus_pmf.py) computes the PMF of the Octopus authentication set size (MIT license, from https://github.com/MehdiAbri/PORS-FP)
- [slhdsa-2to40.sage](slhdsa-2to40.sage) sweeps SLH-DSA parameter tuples and filters them by security level and signature size
- [run_experiments.py](run_experiments.py) runs the full parameter sweep and writes results to CSV
- [export_site_data.sage](export_site_data.sage) exports [site/data.json](site/data.json), the canonical dataset both site pages load (run after regenerating the sweep CSVs)
- [utils/](utils/) helper scripts for searching and visualising the parameter space
- [tests/](tests/) regression suite, run `python3 tests/test_regression.py`; diffs an independent reference model against the CSVs, both site pages (needs node), and costs.sage (when sage is available)
- [document/](document/) LaTeX source for the accompanying technical report
- [site/](site/) interactive explorer hosted on GitHub Pages, stateless parameter search over all report schemes (SPX / W+C / FORS+C / PORS+FP) with worst-case mode, shareable URL state and CSV export ([index.html](site/index.html)), and stateful scheme comparison ([stateful.html](site/stateful.html)), including the compiled [report.pdf](site/report.pdf)