.PHONY: help

help:
	@echo "SparrowCam - Bird Feeder Observation System"
	@echo ""
	@echo "This project is organized into three packages:"
	@echo "  • local  - Local development environment"
	@echo "  • tests  - Testing suite"
	@echo "  • deploy - Deployment to target devices"
	@echo ""
	@echo "Each package has its own Makefile with available commands."
	@echo "Run 'make -C <package> help' to see package-specific options:"
	@echo ""
	@echo "  make -C local help"
	@echo "  make -C tests help"
	@echo "  make -C deploy help"
