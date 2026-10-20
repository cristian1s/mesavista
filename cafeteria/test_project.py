"""Pruebas de integración; base de datos exclusiva para pruebas."""
import base64
import os
from pathlib import Path
import unittest
os.environ['MESAVISTA_DATA_DIR'] = str(Path(__file__).resolve().parent / 'data' / 'testing')
from fastapi.testclient import TestClient
import app


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app.app)
        cls.client.post('/api/reset')
        with app.connect() as c:
            import json
            c.execute('UPDATE settings SET config=? WHERE id=1',(json.dumps(app.default_config()),))

    def test_01_unknown_before_observation(self):
        s = self.client.get('/api/state').json()
        self.assertIsNone(s['latest'])
        self.assertTrue(all(t['status']=='unknown' for t in s['tables']))

    def test_02_uploaded_image_uses_pixels_and_exit_requires_review(self):
        image = (app.ROOT/'assets'/'scenes'/'02_dos_en_M06.png').read_bytes()
        response = self.client.post('/api/analyze-upload',json=dict(name='nombre-arbitrario.png',data=base64.b64encode(image).decode()))
        self.assertEqual(response.status_code,200,response.text)
        r = response.json()
        self.assertEqual(r['people'],2)
        self.assertEqual(r['empty_seats'],28)
        self.assertEqual(r['occupied_seats'],['M06-A','M06-B'])
        exit_result = self.client.post('/api/analyze-scene',json={'file':'00_base_vacia.png'}).json()
        self.assertEqual(exit_result['tables'][5]['status'],'review')
        self.assertTrue(any('M06 quedó' in a for a in exit_result['alerts']))
        self.assertEqual(self.client.post('/api/review/M06').status_code,200)
        self.assertEqual(self.client.get('/api/state').json()['tables'][5]['status'],'available')
        self.assertIn('nombre-arbitrario.png',self.client.get('/api/export').text)

    def test_03_reject_invalid_input_and_double_assignment(self):
        self.assertEqual(self.client.post('/api/analyze-upload',json=dict(name='bad.png',data='NOT_AN_IMAGE')).status_code,400)
        self.assertEqual(self.client.post('/api/analyze-scene',json={'file':'../app.py'}).status_code,400)
        cfg = app.default_config()
        cfg['seats'][0].update(x=.3,y=.3,rx=.01,ry=.01)
        cfg['seats'][1].update(x=.3,y=.3,rx=.01,ry=.01)
        d=[{'anchor':[.3,.3]},{'anchor':[.99,.99]}]
        occupied,waiting,unassigned=app.assign_detections(d,cfg)
        self.assertEqual(len(occupied),1)
        self.assertEqual(len(unassigned),1)
        self.assertEqual(len(waiting),0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
