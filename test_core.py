import io
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from core import COLS,convert,matches,read_zip
class Tests(unittest.TestCase):
 def fixture(self):
  rows=[]
  for num,ref in [('1','A'),('2','A')]:
   for account,d,c in [('411000','120','0'),('706000','0','100'),('445710','0','20')]:
    r=dict.fromkeys(COLS,'');r.update(JournalCode='70',EcritureNum=num,PieceRef=ref,EcritureDate='2026-10-01',PieceDate='2026-10-01',CompteNum=account,Debit=d,Credit=c);rows.append(r)
  df=pd.DataFrame(rows);pdfs={'A.pdf':b'%PDF-1.4 test'}
  return df,pdfs,matches(df,pdfs)
 def test_duplicate_ref(self):
  df,p,l=self.fixture();r=convert(df,p,l)
  self.assertTrue(r['issues'].empty);self.assertEqual(len(r['df']),6)
  self.assertEqual(r['df'].PieceRef.nunique(),2)
  with zipfile.ZipFile(io.BytesIO(r['pj'])) as z:self.assertEqual(set(z.namelist()),{v+'.pdf' for v in r['df'].PieceRef})
 def test_imbalance_blocks(self):
  d,p,l=self.fixture();d.loc[0,'Debit']='121'
  self.assertNotIn('fec',convert(d,p,l))
 def test_missing_pdf(self):
  d,p,l=self.fixture();self.assertNotIn('fec',convert(d,{},l))
 def test_invalid_date(self):
  d,p,l=self.fixture();d.loc[0,'EcritureDate']='20260230';self.assertNotIn('fec',convert(d,p,l))
 def test_invalid_money(self):
  d,p,l=self.fixture();d.loc[0,'Debit']='NaN';self.assertNotIn('fec',convert(d,p,l))
 def test_zip_path(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('../bad.pdf',b'x')
  with self.assertRaises(ValueError):read_zip(b.getvalue())
if __name__=='__main__':unittest.main()
