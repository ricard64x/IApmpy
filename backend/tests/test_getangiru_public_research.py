"""Public research fails closed and transmits no project data."""
import json
import tempfile
import unittest

from app.services.getangiru_public_research import (
    lookup_public_cves, FEED, MAX_FEED_BYTES
)


class PublicResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache=self.tmp.name+"/public.json"
        self.calls=[]

    def fixture(self,url):
        self.calls.append(url)
        self.assertEqual(FEED,url)
        return json.dumps({
            "catalogVersion":"2026.fake-fixture",
            "dateReleased":"2026-01-01T00:00:00Z",
            "vulnerabilities":[
                {"cveID":"CVE-2024-3400","dateAdded":"2024-04-12",
                 "vendorProject":"Synthetic Supplier","product":"Synthetic Product",
                 "dueDate":"2024-05-03"}
            ]}).encode()

    def test_only_static_allowlisted_public_url(self):
        r=lookup_public_cves(["CVE-2024-3400"],self.cache,self.fixture)
        self.assertEqual(1,len(self.calls))
        self.assertEqual(FEED,self.calls[0])
        self.assertTrue(r["entries"][0]["listed_in_kev"])
        self.assertEqual(0,r["private_documents_sent"])
        self.assertEqual(0,r["model_calls"])
        # Reuse local cache, no second network request.
        r2=lookup_public_cves(["CVE-2024-3400"],self.cache,
                              lambda _: self.fail("Cache must be used"))
        self.assertEqual(r,r2)

    def test_rejects_injections_before_network(self):
        for invalid in (["https://internal.example/"],["../etc/passwd"],
                        ["CVE-2024-3400","inject"],[],["CVE-2024-3400"]*6):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                lookup_public_cves(invalid,self.cache,self.fixture)
        self.assertFalse(self.calls)

    def test_missing_catalog_entry_is_not_claimed_safe(self):
        r=lookup_public_cves(["CVE-2025-12345"],self.cache,self.fixture)
        self.assertFalse(r["entries"][0]["listed_in_kev"])
        self.assertIn("no prueba",r["interpretation"])

    def test_oversized_feed_rejected(self):
        with self.assertRaises(ValueError):
            lookup_public_cves(["CVE-2024-3400"],self.cache,
                               lambda _:b"x"*(MAX_FEED_BYTES+1))


if __name__=="__main__":
    unittest.main()
