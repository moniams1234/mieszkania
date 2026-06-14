import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['DB_PATH'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'offers.db')
    with app.test_client() as c:
        yield c

def test_index_returns_200(client):
    r = client.get('/')
    assert r.status_code == 200

def test_index_contains_offers_json(client):
    r = client.get('/')
    assert b'offersData' in r.data

def test_index_contains_all_cities(client):
    r = client.get('/')
    assert b'Gdansk' in r.data
    assert b'Warszawa' in r.data
    assert b'Wroclaw' in r.data
