.PHONY: tag push

version := $(shell python3 -c "import app; print(app.__version__);")

tag:
	git tag v${version}

push:
	git push
	git push origin v${version}


generate-client:
	openapi-python-client update --path ./docs/references/upstream-apis/Marzban-API.json --config openapi-generator-config.yaml


