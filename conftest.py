import json

import pytest
from dotenv import load_dotenv

from ncm.parser import CATALOG_POC_PATH

load_dotenv()


@pytest.fixture(scope="session")
def catalog_data():
    return json.loads(CATALOG_POC_PATH.read_text(encoding="utf-8"))
