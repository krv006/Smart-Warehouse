import os
import subprocess
import tempfile
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.models import TelegramSettings


class Command(BaseCommand):
    help = "PostgreSQL backup qilib Telegram guruhiga yuboradi"

    def handle(self, *args, **options):
        config = TelegramSettings.objects.filter(is_active=True).first()
        if not config:
            self.stderr.write("Telegram sozlamasi topilmadi yoki faol emas.")
            return

        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.postgresql':
            self.stderr.write("Faqat PostgreSQL uchun ishlaydi.")
            return

        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"backup_{date_str}.sql"

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, filename)

            env = os.environ.copy()
            env['PGPASSWORD'] = db.get('PASSWORD', '')

            result = subprocess.run(
                [
                    'pg_dump',
                    '-h', db.get('HOST', 'localhost'),
                    '-p', str(db.get('PORT', '5432')),
                    '-U', db.get('USER', 'postgres'),
                    '-d', db.get('NAME', 'warehouse'),
                    '-f', filepath,
                ],
                env=env,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.stderr.write(f"pg_dump xatosi: {result.stderr}")
                return

            file_size = os.path.getsize(filepath)
            size_mb = round(file_size / 1024 / 1024, 2)

            caption = (
                f"📦 *Smart Warehouse — Kunlik Backup*\n\n"
                f"📅 Sana: `{date_str}`\n"
                f"🗄 DB: `{db.get('NAME', 'warehouse')}`\n"
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
