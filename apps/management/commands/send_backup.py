import os
import shutil
import subprocess
import tempfile
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.models import TelegramSettings


class Command(BaseCommand):
    help = "DB backup qilib Telegram guruhiga yuboradi (PostgreSQL va SQLite)"

    def handle(self, *args, **options):
        config = TelegramSettings.objects.filter(is_active=True).first()
        if not config:
            self.stderr.write("Telegram sozlamasi topilmadi yoki faol emas.")
            return

        db = settings.DATABASES['default']
        engine = db['ENGINE']
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")

        with tempfile.TemporaryDirectory() as tmpdir:
            if engine == 'django.db.backends.postgresql':
                filepath, db_name = self._dump_postgres(db, tmpdir, date_str)
            elif engine == 'django.db.backends.sqlite3':
                filepath, db_name = self._dump_sqlite(db, tmpdir, date_str)
            else:
                self.stderr.write(f"Qo'llab-quvvatlanmaydigan DB: {engine}")
                return

            if filepath is None:
                return

            file_size = os.path.getsize(filepath)
            size_mb = round(file_size / 1024 / 1024, 2)
            filename = os.path.basename(filepath)

            caption = (
                f"📦 *Smart Warehouse — Kunlik Backup*\n\n"
                f"📅 Sana: `{date_str}`\n"
                f"🗄 DB: `{db_name}`\n"
                f"⚙️ Tur: `{'PostgreSQL' if 'postgresql' in engine else 'SQLite'}`\n"
                f"📊 Hajm: `{size_mb} MB`\n"
                f"✅ Holat: Muvaffaqiyatli"
            )

            with open(filepath, 'rb') as f:
                resp = requests.post(
                    f"https://api.telegram.org/bot{config.bot_token}/sendDocument",
                    data={'chat_id': config.chat_id, 'caption': caption, 'parse_mode': 'Markdown'},
                    files={'document': (filename, f, 'application/octet-stream')},
                    timeout=60,
                )

            if resp.ok:
                self.stdout.write(self.style.SUCCESS(f"Backup yuborildi: {filename} ({size_mb} MB)"))
            else:
                self.stderr.write(f"Telegram xatosi: {resp.text}")

    def _dump_postgres(self, db, tmpdir, date_str):
        filepath = os.path.join(tmpdir, f"backup_{date_str}.sql")
        db_name = db.get('NAME', 'warehouse')

        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        result = subprocess.run(
            [
                'pg_dump',
                '-h', db.get('HOST', 'localhost'),
                '-p', str(db.get('PORT', '5432')),
                '-U', db.get('USER', 'postgres'),
                '-d', db_name,
                '-f', filepath,
            ],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            self.stderr.write(f"pg_dump xatosi: {result.stderr}")
            return None, None

        return filepath, db_name

    def _dump_sqlite(self, db, tmpdir, date_str):
        src = db['NAME']
        if not os.path.exists(src):
            self.stderr.write(f"SQLite fayl topilmadi: {src}")
            return None, None
        db_name = os.path.basename(src)
        filename = f"backup_{date_str}.sqlite3"
        filepath = os.path.join(tmpdir, filename)
        shutil.copy2(src, filepath)
        return filepath, db_name
