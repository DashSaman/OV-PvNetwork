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

    def test_no_raw_persian_strings_outside_translation_calls(self):
        pattern = re.compile(r'[\u0600-\u06FF]')
        problems = []
        for path in SRC.rglob('*.jsx'):
            for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
                if not pattern.search(line):
                    continue
                if 't(' in line or 'defaultValue' in line or line.lstrip().startswith(('//', '*', '/*')):
                    continue
                problems.append(f'{path.name}:{lineno}')
        self.assertEqual([], problems, f'Raw Persian text outside translation calls: {problems[:20]}')

    def test_non_persian_catalogs_contain_no_arabic_script_values(self):
        arabic_block = re.compile(r'[\u0600-\u06FF]')
        allowed_native_names = {'language.ar', 'language.fa'}
        problems = []
        for lang in ['en', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']:
            catalog = json.loads((SRC / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key, value in catalog.items():
                if key in allowed_native_names:
                    continue
                if isinstance(value, str) and arabic_block.search(value):
                    problems.append(f'{lang}:{key}')
                elif isinstance(value, dict):
                    for sub, text in value.items():
                        if isinstance(text, str) and arabic_block.search(text):
                            problems.append(f'{lang}:{key}.{sub}')
        self.assertEqual([], problems, f'{len(problems)} Arabic-script values in non-Persian catalogs: ' + ', '.join(problems[:20]))

    def test_arabic_catalog_has_no_persian_only_characters(self):
        persian_only = re.compile(r'[\u067E\u0686\u0698\u06AF\u06A9\u06CC]')
        catalog = json.loads((SRC / 'lang' / 'ar.json').read_text(encoding='utf-8'))
        problems = []
        for key, value in catalog.items():
            if key == 'language.fa':
                continue
            if isinstance(value, str) and persian_only.search(value):
                problems.append(key)
            elif isinstance(value, dict):
                for sub, text in value.items():
                    if isinstance(text, str) and persian_only.search(text):
                        problems.append(f'{key}.{sub}')
        self.assertEqual([], problems, 'Persian-only characters leaked into the Arabic catalog: ' + ', '.join(problems[:20]))


if __name__ == '__main__':
    unittest.main()
