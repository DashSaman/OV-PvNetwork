from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'frontend' / 'src'
LANGS = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']

T_CALL = re.compile(r"\bt\(\s*['\"]([a-zA-Z0-9_.]+)['\"]")


def collect_used_keys():
    used = set()
    for path in SRC.rglob('*.jsx'):
        used.update(T_CALL.findall(path.read_text(encoding='utf-8')))
    for path in SRC.rglob('*.js'):
        if path.name == 'i18n.js':
            continue
        used.update(T_CALL.findall(path.read_text(encoding='utf-8')))
    return used


def resolve(catalog, key):
    if key in catalog:
        return catalog[key]
    node = catalog
    for part in key.split('.'):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


class I18nCatalogParityTests(unittest.TestCase):
    def test_every_used_key_resolves_in_every_language(self):
        used = collect_used_keys()
        self.assertGreater(len(used), 400, 'translation usage scan unexpectedly small')
        problems = []
        for lang in LANGS:
            catalog = json.loads((SRC / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key in sorted(used):
                if resolve(catalog, key) is None:
                    problems.append(f'{lang}: {key}')
        self.assertEqual([], problems, f'{len(problems)} used keys missing from language catalogs: ' + ', '.join(problems[:20]))

    def test_direction_key_matches_script_direction(self):
        for lang in LANGS:
            catalog = json.loads((SRC / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            self.assertEqual('rtl' if lang in ('fa', 'ar') else 'ltr', catalog.get('direction'), lang)


if __name__ == '__main__':
    unittest.main()
