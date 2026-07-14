.PHONY: install dev test test-quick test-stress test-protocol test-coverage \
        test-clean clean detect tui monitor mock

install:
	pip install -e .

dev:
	python3 -m venv dev/venv && \
	. dev/venv/bin/activate && \
	pip install -e ".[dev]"

# ── Test Protocol ──────────────────────────────────────────────────────────
# Core:  run this after every change
#        make test-protocol
# ────────────────────────────────────────────────────────────────────────────

test:
	python -m pytest tests/ -v --tb=short

test-quick:
	python -m pytest tests/ -v --tb=short -m "not stress"

test-stress:
	python -m pytest tests/test_stress.py -v --tb=short -x

test-protocol:
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║   ifix-ios — Test Protocol                              ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "──────────────────────────────────────────────────────────"
	@echo "  [1/4] Verificando importaciones..."
	@echo "──────────────────────────────────────────────────────────"
	python -c "from ifix_ios.app import cli; from ifix_ios.tui_app import IDeviceTUI; from ifix_ios.core.guide_agent import GuideAgent; print('  ✓ Todos los módulos importados correctamente')"
	@echo ""
	@echo "──────────────────────────────────────────────────────────"
	@echo "  [2/4] Ejecutando tests unitarios..."
	@echo "──────────────────────────────────────────────────────────"
	python -m pytest tests/ -v --tb=short -m "not stress" --junitxml=/tmp/ifix-ios-unit.xml || (echo "  ✗ Tests unitarios fallaron" ; exit 1)
	@echo ""
	@echo "──────────────────────────────────────────────────────────"
	@echo "  [3/4] Ejecutando tests de estrés..."
	@echo "──────────────────────────────────────────────────────────"
	python -m pytest tests/test_stress.py -v --tb=short -x --junitxml=/tmp/ifix-ios-stress.xml || (echo "  ✗ Tests de estrés fallaron" ; exit 1)
	@echo ""
	@echo "──────────────────────────────────────────────────────────"
	@echo "  [4/4] Limpiando entorno simulado..."
	@echo "──────────────────────────────────────────────────────────"
	-rm -rf /tmp/ifix-ios-mock-bin
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║   ✓ PROTOCOLO COMPLETADO                                ║"
	@echo "╚══════════════════════════════════════════════════════════╝"

test-coverage:
	pip install pytest-cov -q
	python -m pytest tests/ --cov=ifix_ios --cov-report=term-missing --cov-report=html:/tmp/ifix-ios-coverage

test-clean:
	-rm -rf /tmp/ifix-ios-mock-bin
	-rm -rf /tmp/ifix-ios-coverage
	-rm -f /tmp/ifix-ios-unit.xml /tmp/ifix-ios-stress.xml

# ── Development commands ────────────────────────────────────────────────────

detect:
	python -m ifix_ios detect

tui:
	python -m ifix_ios tui

monitor:
	python -m ifix_ios monitor

mock:
	python dev/mock_device.py

clean:
	rm -rf build/ dist/ *.egg-info/ __pycache__/
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
