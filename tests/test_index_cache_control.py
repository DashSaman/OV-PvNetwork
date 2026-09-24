from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IndexCacheControlContractTests(unittest.TestCase):
    def test_spa_index_is_served_with_no_cache(self):
        source = (ROOT / 'backend/app.py').read_text(encoding='utf-8')
        self.assertIn('PVNETWORK_INDEX_NO_CACHE_V1', source)
        self.assertIn('headers={"Cache-Control": "no-cache"}', source)

    def test_index_route_still_serves_the_bundled_file(self):
        source = (ROOT / 'backend/app.py').read_text(encoding='utf-8')
        self.assertIn('async def serve_react():', source)
        self.assertIn('FileResponse(', source)
        self.assertIn('index.html', source)


if __name__ == '__main__':
    unittest.main()
