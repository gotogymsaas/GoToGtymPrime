from collections import defaultdict
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from translations.models import FrontendTranslation


class Command(BaseCommand):
    help = "Export frontend translations to locale JSON files"

    def handle(self, *args, **options):
        locales_dir = getattr(settings, "FRONTEND_LOCALES_DIR", None)
        if locales_dir is None:
            self.stderr.write("FRONTEND_LOCALES_DIR not configured")
            return
        locales_path = Path(locales_dir)
        grouped = defaultdict(lambda: defaultdict(dict))
        for tr in FrontendTranslation.objects.all():
            grouped[tr.language_code][tr.namespace][tr.key] = tr.text
        for lang, namespaces in grouped.items():
            for namespace, data in namespaces.items():
                dir_path = locales_path / lang
                dir_path.mkdir(parents=True, exist_ok=True)
                file_path = dir_path / f"{namespace}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS("Translations exported"))
