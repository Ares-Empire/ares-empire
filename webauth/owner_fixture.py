"""Made-up owner file for isolated tests; never reads the machine's owner file."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from webauth import owner

DETAILS = {"name": "Erika Musterfrau", "street": "Musterstraße 1", "city": "12345 Musterstadt",
           "email": "owner@example.org"}


class OwnerTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.owner_file = Path(directory) / "owner.json"
        self.owner_file.write_text(json.dumps(DETAILS), encoding="utf-8")
        self.enterContext(patch.dict(os.environ, {"ARES_OWNER_FILE": str(self.owner_file)}))
        owner.get_owner.cache_clear()
        self.addCleanup(owner.get_owner.cache_clear)
