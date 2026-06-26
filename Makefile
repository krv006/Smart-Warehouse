PYTHON = .venv/Scripts/python.exe
MANAGE = $(PYTHON) manage.py

# ──────────────────────────────────────────────────────────────────────────────
#  Asosiy buyruqlar
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo ""
	@echo "  make run          - Serverni ishga tushirish"
	@echo "  make migrate      - Migratsiyalarni qo'llash"
	@echo "  make migrations   - Yangi migratsiyalar yaratish"
	@echo "  make seed         - Fake ma'lumotlar qo'shish"
	@echo "  make seed-clear   - Bazani tozalab, fake ma'lumot qo'shish"
	@echo "  make superuser    - Superuser yaratish"
	@echo "  make shell        - Django shell"
	@echo "  make check        - Loyiha tekshiruvi"
	@echo "  make install      - Paketlarni o'rnatish"
	@echo "  make fresh        - Bazani reset + migrate + seed"
	@echo ""

# ──────────────────────────────────────────────────────────────────────────────
#  Server
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: run
run:
	$(MANAGE) runserver

.PHONY: run-plus
run-plus:
	$(MANAGE) runserver 0.0.0.0:8000

# ──────────────────────────────────────────────────────────────────────────────
#  Ma'lumotlar bazasi
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: migrate
migrate:
	$(MANAGE) migrate

.PHONY: migrations
migrations:
	$(MANAGE) makemigrations

.PHONY: superuser
superuser:
	$(MANAGE) createsuperuser

# ──────────────────────────────────────────────────────────────────────────────
#  Fake ma'lumotlar (Seed)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: seed
seed:
	@echo ">>> Fake malumotlar qo'shilmoqda..."
	$(MANAGE) seed --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40

.PHONY: seed-clear
seed-clear:
	@echo ">>> Baza tozalanib, fake malumotlar qo'shilmoqda..."
	$(MANAGE) seed --clear --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40

.PHONY: seed-small
seed-small:
	@echo ">>> Kichik hajmda fake malumotlar..."
	$(MANAGE) seed --clear --users 3 --products 10 --sales 15 --expenses 10 --clients 5 --payments 10

.PHONY: seed-big
seed-big:
	@echo ">>> Katta hajmda fake malumotlar..."
	$(MANAGE) seed --clear --users 20 --products 100 --sales 200 --expenses 150 --clients 50 --payments 120

# ──────────────────────────────────────────────────────────────────────────────
#  To'liq reset
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: fresh
fresh:
	@echo ">>> Baza o'chirib, qayta yaratilmoqda..."
	-del db.sqlite3 2>nul || rm -f db.sqlite3
	$(MANAGE) migrate
	$(MANAGE) createsuperuser --username admin --email admin@warehouse.uz --noinput || true
	$(PYTHON) -c "from apps.users.models import User; u=User.objects.get(username='admin'); u.set_password('admin123'); u.role='MANAGEMENT'; u.save()"
	$(MANAGE) seed --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40
	@echo ">>> Tayyor! admin / admin123"

# ──────────────────────────────────────────────────────────────────────────────
#  Yordamchi
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: check
check:
	$(MANAGE) check

.PHONY: shell
shell:
	$(MANAGE) shell

.PHONY: install
install:
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: static
static:
	$(MANAGE) collectstatic --noinput


mig:
	python manage.py makemigrations
	python manage.py migrate

user:
	python manage.py createsuperuser

