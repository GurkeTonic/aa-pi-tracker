appname = aa-pi-tracker
package = aa_pi_tracker

# Default goal
.DEFAULT_GOAL := help

# Help
.PHONY: help
help:
	@echo ""
	@echo "$(appname) Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make [command]"
	@echo ""
	@echo "Commands:"
	@echo "  translations            Create or update translation files (en base, de)"
	@echo "  compile_translations    Compile translation files (.po -> .mo)"
	@echo "  build_test              Build the package"
	@echo ""

# Translation files — source language is English; translated to German.
# Run from inside the package dir so locale/ lands in $(package)/locale/.
.PHONY: translations
translations:
	@echo "Creating or updating translation files"
	@cd $(package) && django-admin makemessages \
		-l de \
		--keep-pot \
		--no-location \
		--ignore 'build/*'

# Compile translation files
.PHONY: compile_translations
compile_translations:
	@echo "Compiling translation files"
	@cd $(package) && django-admin compilemessages -l de

# Build the package
.PHONY: build_test
build_test:
	@echo "Building the package"
	@python -m build
