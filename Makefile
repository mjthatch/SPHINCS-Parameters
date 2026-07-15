# Single entrypoint for regenerating every derived artifact.
#
#   make generate   — everything below, in dependency order
#   make sweeps     — the two parameter sweeps -> utils/*.csv        (sage)
#   make derived    — thresholds + extremes from the sweep CSVs      (python)
#   make data       — site/data.json for both site pages             (sage)
#   make figures    — report figures from the generated data         (python)
#   make test       — regression suite (validates artifacts <-> model)
#   make clean-generated

SAGE   ?= sage
PYTHON ?= python3

UTILS  := utils
IMAGES := document/content/images

CSV_CAPPED  := $(UTILS)/all_size_capped_candidates.csv
CSV_UNBOUND := $(UTILS)/all_unbound_candidates.csv

.PHONY: generate sweeps derived data figures test clean-generated

generate: sweeps derived data figures test

sweeps:
	$(SAGE) slhdsa-2to40.sage --max-size 7856 > /dev/null
	mv candidates.csv $(CSV_CAPPED)
	$(SAGE) slhdsa-2to40.sage --max-size 99999999 > /dev/null
	mv candidates.csv $(CSV_UNBOUND)

derived:
	cd $(UTILS) && $(PYTHON) min_mult_search.py
	$(PYTHON) $(UTILS)/extremes_summary.py

data:
	$(SAGE) export_site_data.sage

figures:
	cd $(IMAGES) && $(PYTHON) ../../../$(UTILS)/sieve_search_draw.py \
	    --input ../../../$(CSV_UNBOUND) --weights 1,1,1,1,1 --suffix _1
	cd $(IMAGES) && $(PYTHON) ../../../$(UTILS)/sieve_search_draw.py \
	    --input ../../../$(CSV_UNBOUND) --weights 5,1,1.5,2,1 --suffix _2
	cd $(UTILS) && $(PYTHON) venn_diagram_draw.py
	mv $(UTILS)/euler_custom_minimax.png $(IMAGES)/concentric_diagram.png
	cd $(IMAGES) && $(PYTHON) ../../../$(UTILS)/plot_concept_scatter.py
	mv $(IMAGES)/conceptual_bounded_zones_origin_vector.png $(IMAGES)/scatter_plot.png

test:
	$(PYTHON) tests/test_regression.py

clean-generated:
	rm -f $(CSV_CAPPED) $(CSV_UNBOUND)
	rm -f $(UTILS)/global_X_thresholds.csv $(UTILS)/master_extremes_summary.csv
	rm -f site/data.json site/report.pdf
	rm -f $(IMAGES)/sieve_step*.png $(IMAGES)/concentric_diagram.png $(IMAGES)/scatter_plot.png
