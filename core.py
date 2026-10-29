"""Conversion explicite, sans suppression de lignes ni équilibrage automatique."""
import csv
import io
import re
import zipfile
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import PurePosixPath
import pandas as pd

COLS = 'JournalCode JournalLib EcritureNum EcritureDate CompteNum CompteLib CompAuxNum CompAuxLib PieceRef PieceDate EcritureLib Debit Credit EcritureLet DateLet ValidDate Montantdevise Idevise'.split()
CSV_MAP = {'Code journal':'JournalCode','Numéro de séquence':'EcritureNum','Date de facturation':'EcritureDate','Code comptable':'CompteNum','Compte auxiliaire':'CompAuxNum','Client à facturer':'CompAuxLib','Numéro de facture':'PieceRef','Description':'EcritureLib','Débit':'Debit','Crédit':'Credit'}

def decode(b):
    for encoding in ('utf-8-sig','cp1252'):
        try: return b.decode(encoding)
        except UnicodeDecodeError: pass
    raise ValueError('Encodage inconnu : exporter en UTF-8.')

def parse(b):
    text = decode(b)
    sep = '\t' if '\t' in text.splitlines()[0] else ';'
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    if set(CSV_MAP).issubset(df.columns):
        original=df.copy()
        df=df.rename(columns=CSV_MAP)
        df['PieceDate']=df['EcritureDate']
        df['JournalLib']='Ventes'
        df['CompteLib']=df['CompteNum'].map(lambda c: 'Clients' if c.startswith('411') else ('Ventes / prestations' if c.startswith('7') else 'TVA collectée' if c.startswith('4457') else c))
        df['EcritureLib']=original['Client à facturer']
    else:
        df=df.rename(columns={'CompteAuxNum':'CompAuxNum','CompteAuxLib':'CompAuxLib'})
        required={'JournalCode','EcritureNum','EcritureDate','CompteNum','PieceRef','Debit','Credit'}
        if not required.issubset(df.columns): raise ValueError('Format non reconnu : utiliser le CSV comptable de cet export ou un FEC à en-têtes.')
    for c in COLS:
        if c not in df: df[c]=''
    df=df[COLS].copy()
    for c in COLS: df[c]=df[c].astype(str).str.strip()
    # Le nom du client s'applique aussi aux lignes de produits et de TVA.
    # Résolution par écriture, jamais par numéro auxiliaire (parfois partagé).
    for _, group in df.groupby(['JournalCode','EcritureNum','PieceRef'], sort=False):
        names = set(group.loc[group.CompteNum.str.startswith('411'), 'CompAuxLib']) - {''}
        if len(names) == 1:
            df.loc[group.index, 'EcritureLib'] = next(iter(names))
        elif len(names) > 1:
            raise ValueError('Plusieurs noms clients dans une écriture : ' + group.PieceRef.iloc[0])
    df.loc[df.CompAuxNum.eq(''),'CompAuxLib']=''
    return df

def read_zip(data):
    files={}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos=z.infolist()
        if len(infos)>10000 or sum(i.file_size for i in infos)>500*1024**2: raise ValueError('Archive trop volumineuse (maximum 500 Mo décompressés / 10 000 fichiers).')
        for i in infos:
            p=PurePosixPath(i.filename.replace('\\','/'))
            if i.is_dir() or '__MACOSX' in p.parts or p.name.startswith('.'): continue
            if p.is_absolute() or '..' in p.parts: raise ValueError('Chemin non sûr dans le ZIP.')
            if i.filename in files: raise ValueError('Nom dupliqué dans le ZIP : '+i.filename)
            files[i.filename]=z.read(i)
    candidates={}
    for n,b in files.items():
        if n.lower().endswith(('.csv','.txt')):
            try: candidates[n]=parse(b)
            except (ValueError,UnicodeError, pd.errors.ParserError): pass
    if not candidates: raise ValueError('Aucun CSV comptable / FEC reconnu dans le ZIP.')
    return candidates,{n:b for n,b in files.items() if n.lower().endswith('.pdf')}

def money(v):
    s=str(v).strip().replace('\u00a0','').replace('\u202f','').replace(' ','').replace(',','.')
    try: d=Decimal(s or '0')
    except InvalidOperation: raise ValueError('Montant invalide : '+str(v))
    if not d.is_finite() or d != d.quantize(Decimal('.01')): raise ValueError('Montant non fini ou plus de deux décimales : '+str(v))
    return d

def date(v, optional=False):
    s=str(v).strip()
    if optional and not s:return ''
    for fmt in ('%Y%m%d','%Y-%m-%d','%d/%m/%Y'):
        try:return datetime.strptime(s,fmt).strftime('%Y%m%d')
        except ValueError:pass
    raise ValueError('Date invalide : '+s)

def matches(df,pdfs):
    rows=[]
    for ref in dict.fromkeys(df.PieceRef):
        found=[n for n in pdfs if PurePosixPath(n).stem==ref]
        rows.append({'PieceRef':ref,'PDF':found[0] if len(found)==1 else ''})
    return pd.DataFrame(rows)

def collisions(df):
    d=df[df.CompAuxNum.ne('')].groupby('CompAuxNum').CompAuxLib.agg(lambda x:sorted(set(x)-{''}))
    return [{'Compte':k,'Noms':' / '.join(v)} for k,v in d.items() if len(v)>1]

def convert(df,pdfs,links,journal='VT',accept_collision=False):
    df=df.copy().fillna('').astype(str)
    issues=[]
    def issue(ref,problem):issues.append({'PieceRef':ref,'Anomalie':problem})
    if not re.fullmatch('[A-Za-z0-9]{1,10}',journal):issue('','Code journal invalide')
    for i,r in df.iterrows():
        try:
            for c in ('EcritureDate','PieceDate'):df.at[i,c]=date(r[c])
            for c in ('DateLet','ValidDate'):df.at[i,c]=date(r[c],True)
            d,cr=money(r.Debit),money(r.Credit)
            if d<0 or cr<0 or (d and cr): raise ValueError('Débit/crédit négatifs ou simultanément renseignés')
            df.at[i,'Debit']=str(d.quantize(Decimal('.01')))
            df.at[i,'Credit']=str(cr.quantize(Decimal('.01')))
            if not re.fullmatch('[0-9][A-Za-z0-9]*',r.CompteNum):raise ValueError('Compte général invalide')
            if r.CompAuxNum and not re.fullmatch('[A-Za-z0-9]+',r.CompAuxNum):raise ValueError('Compte auxiliaire invalide')
            if not r.PieceRef or not r.EcritureNum:raise ValueError('Référence de pièce ou numéro écriture manquant')
        except ValueError as e:issue(r.PieceRef,f'Ligne {i+1} : {e}')
    for x in collisions(df):
        if not accept_collision:issue('',f"Auxiliaire {x['Compte']} partagé : {x['Noms']} (corriger ou confirmer)")
    # Group by original identity, never merge distinct entries with the same invoice name.
    groups=list(df.groupby(['JournalCode','EcritureNum','PieceRef'],sort=False,dropna=False))
    used=set(); out=[]; attachments={}; mapping=[]
    links=links.fillna('').astype(str)
    linkmap=dict(zip(links.PieceRef,links.PDF))
    for (j,num,ref),g in groups:
        try:
            debit=sum((money(v) for v in g.Debit),Decimal(0));credit=sum((money(v) for v in g.Credit),Decimal(0))
            if debit!=credit:issue(ref,f'Écriture déséquilibrée : débit {debit}, crédit {credit}, écart {debit-credit}')
            if debit==credit==0:issue(ref,'Écriture entièrement nulle')
        except ValueError:pass
        if g.EcritureDate.nunique()!=1:issue(ref,'Plusieurs dates pour la même écriture')
        name=linkmap.get(ref,'')
        if not name or name not in pdfs:issue(ref,'PDF manquant ou association ambiguë')
        elif not pdfs[name].lstrip().startswith(b'%PDF-'):issue(ref,'Le fichier associé ne semble pas être un PDF')
        safe=re.sub(r'[^A-Za-z0-9_-]','_',ref).strip('_') or 'PIECE'
        new=safe;n=2
        while new.casefold() in used:new=f'{safe}-{journal}-{n}';n+=1
        used.add(new.casefold())
        if name in pdfs:attachments[new+'.pdf']=pdfs[name]
        g=g.copy();g['JournalCode']=journal;g['JournalLib']='Ventes' if journal=='VT' else journal
        g['EcritureNum']=journal+'-'+new;g['PieceRef']=new
        for c in COLS:g[c]=g[c].map(lambda v:re.sub(r'[\t\r\n;]',' ',str(v)))
        out.append(g)
        mapping.append({'PieceRef_source':ref,'PieceRef_export':new,'PDF_source':name,'PDF_export':new+'.pdf','Lignes':len(g)})
    if not groups:issue('','Aucune écriture')
    report=pd.DataFrame(issues,columns=['PieceRef','Anomalie'])
    if issues:return {'issues':report}
    result=pd.concat(out,ignore_index=True)[COLS]
    fec=result.to_csv(index=False,sep='\t',lineterminator='\r\n').encode('utf-8-sig')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in attachments.items():z.writestr(n,b)
    pj=buf.getvalue()
    control=pd.DataFrame(mapping).to_csv(index=False,sep=';').encode('utf-8-sig')
    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('FEC_IMPORT.txt',fec);z.writestr('PIECES_JOINTES.zip',pj);z.writestr('CONTROLE.csv',control)
        z.writestr('LIRE_MOI.txt','1. Extraire ce ZIP.\n2. Pennylane : Saisie comptable > Imports > FEC : importer FEC_IMPORT.txt.\n3. Après import : trombone / Joindre une archive > PIECES_JOINTES.zip.\n4. Contrôler la balance, les tiers et les images. Ne pas importer à nouveau des écritures déjà présentes.\nFichier partiel destiné à un import, pas un FEC fiscal annuel.\n')
    return {'issues':report,'fec':fec,'pj':pj,'bundle':bundle.getvalue(),'df':result,'control':pd.DataFrame(mapping),'unused':[n for n in pdfs if n not in set(linkmap.values())]}


def propose_accounts(df, saved=None):
    """Suggestions numériques ; fichier de correspondance réutilisable chaque mois."""
    import hashlib
    clients=df.loc[df.CompAuxNum.ne(''),['CompAuxNum','CompAuxLib']].drop_duplicates().copy()
    shared={r['Compte'] for r in collisions(df)}
    prior={} if saved is None else {(str(r.CompAuxNum),str(r.CompAuxLib)):str(r.Compte_cible) for r in saved.itertuples()}
    used=set(df.CompAuxNum)-{''}
    used.update(prior.values())
    values=[]
    for r in clients.itertuples():
        key=(r.CompAuxNum,r.CompAuxLib)
        if key in prior: target=prior[key]
        elif r.CompAuxNum in shared and r.CompAuxLib:
            prefix='401' if r.CompAuxNum.startswith('401') else '411'
            seed='|'.join(key);n=0
            while True:
                suffix=str(int(hashlib.sha256((seed+'|'+str(n)).encode()).hexdigest(),16)%10**10).zfill(10)
                target=prefix+'9'+suffix
                if target not in used:break
                n+=1
        else:target=r.CompAuxNum
        used.add(target);values.append(target)
    clients['Compte_cible']=values
    return clients.reset_index(drop=True)


def process_batch(df,pdfs,links,journal='VT'):
    """Livre toujours un rapport ; isole les écritures entières non importables."""
    df=df.copy().fillna('').astype(str).reset_index(drop=True)
    notes=[];accepted=[];rejected=[]
    if not re.fullmatch('[A-Za-z0-9]{1,10}',journal):
        notes.append({'PieceRef':'','Anomalie':f'Journal invalide {journal!r} remplacé par VT'})
        journal='VT'
    for _,g in df.groupby(['JournalCode','EcritureNum','PieceRef'],sort=False,dropna=False):
        # Validation locale pour ne pas bloquer les autres factures.
        result=convert(g.reset_index(drop=True),pdfs,links,journal,accept_collision=True)
        if result['issues'].empty:accepted.append(g)
        else:
            reasons=' | '.join(result['issues'].Anomalie)
            copy=g.copy();copy['Motif']=reasons;rejected.append(copy)
            notes.extend(result['issues'].to_dict('records'))
    valid=pd.concat(accepted,ignore_index=True) if accepted else pd.DataFrame(columns=COLS)
    excluded=pd.concat(rejected,ignore_index=True) if rejected else pd.DataFrame(columns=COLS+['Motif'])
    report=pd.DataFrame(notes,columns=['PieceRef','Anomalie'])
    output=convert(valid,pdfs,links,journal,accept_collision=True) if len(valid) else {}
    if len(valid) and 'fec' not in output:raise ValueError('Échec inattendu de validation du lot final')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        if 'bundle' in output:
            with zipfile.ZipFile(io.BytesIO(output['bundle'])) as original:
                for n in original.namelist():z.writestr(n,original.read(n))
        z.writestr('ECRITURES_A_VERIFIER.csv',excluded.to_csv(index=False,sep=';').encode('utf-8-sig'))
        z.writestr('ANOMALIES.csv',report.to_csv(index=False,sep=';').encode('utf-8-sig'))
        z.writestr('BILAN_EXPORT.txt',f'Lignes source : {len(df)}\nLignes dans le FEC : {len(valid)}\nLignes à vérifier (non importées) : {len(excluded)}\nLes écritures à vérifier sont conservées intégralement, sans modification des montants.\n')
    output.update(bundle=buf.getvalue(),issues=report,excluded=excluded,valid_rows=len(valid),source_rows=len(df))
    return output
