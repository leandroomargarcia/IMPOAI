import pytest
from dotenv import load_dotenv

from ncm.parser import parse_poc, save_catalog

load_dotenv()


@pytest.fixture(scope="session")
def catalog_data():
    data = parse_poc()
    save_catalog(data)
    return data
