.PHONY: tag push

version := $(shell python3 -c "import app; print(app.__version__);")

tag:
	git tag v${version}

push:
	git push
	git push origin v${version}


generate-client:
	openapi-python-client update --path ./openapi.json --config openapi-generator-config.yaml


