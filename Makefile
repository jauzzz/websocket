run:
	@gunicorn ws:app --bind 0.0.0.0:8200 --worker-class aiohttp.worker.GunicornUVLoopWebWorker -e SIMPLE_SETTINGS=ws.settings.production

dev.run:
	@gunicorn ws:app --bind 0.0.0.0:8200 --worker-class aiohttp.worker.GunicornUVLoopWebWorker -e SIMPLE_SETTINGS=ws.settings.development

dev.worker:
	@gunicorn --workers=8 --worker-connections=6000 --backlog=8192 ws:app --bind 0.0.0.0:8200 --worker-class aiohttp.worker.GunicornUVLoopWebWorker -e SIMPLE_SETTINGS=ws.settings.development

requirements-test:
	@pip install -r requirements/test.txt

requirements-dev:
	@pip install -r requirements/dev.txt

test:
	@SIMPLE_SETTINGS=ws.settings.test py.test websocket

test-matching:
	@SIMPLE_SETTINGS=ws.settings.test pytest -rxs -k${Q} websocket

test-coverage:
	@SIMPLE_SETTINGS=ws.settings.test pytest --cov=websocket websocket --cov-report term-missing

lint:
	@flake8
	@isort --check

detect-outdated-dependencies:
	@sh -c 'output=$$(pip list --outdated); echo "$$output"; test -z "$$output"'

release-patch: ## Create patch release
	SIMPLE_SETTINGS=ws.settings.test bump2version patch --dry-run --no-tag --no-commit --list | grep new_version= | sed -e 's/new_version=//' | xargs -n 1 towncrier --yes --version
	git commit -am 'Update CHANGELOG'
	bump2version patch

release-minor: ## Create minor release
	SIMPLE_SETTINGS=ws.settings.test bump2version minor --dry-run --no-tag --no-commit --list | grep new_version= | sed -e 's/new_version=//' | xargs -n 1 towncrier --yes --version
	git commit -am 'Update CHANGELOG'
	bump2version minor

release-major: ## Create major release
	SIMPLE_SETTINGS=ws.settings.test bump2version major --dry-run --no-tag --no-commit --list | grep new_version= | sed -e 's/new_version=//' | xargs -n 1 towncrier --yes --version
	git commit -am 'Update CHANGELOG'
	bump2version major

%.logs: ## Container log
	docker-compose -f docker-compose.yml logs -f $*

%-shell: ## Container shell
	docker-compose -f docker-compose.yml exec $* sh

up:
	docker-compose -f docker-compose.yml up -d --build

down:
	docker-compose -f docker-compose.yml down -v
	
scale:
	docker-compose -f docker-compose.yml scale socketio=2

ulimit:
	sudo sysctl -w kern.maxfiles=1048600 && sudo sysctl -w kern.maxfilesperproc=1048576
