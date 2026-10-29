import hashlib
import pandas as pd
import streamlit as st
from core import read_zip, matches, collisions, convert, propose_accounts, process_batch
st.set_page_config(page_title='FEC + pièces • Pennylane',page_icon='📎',layout='wide')
st.title('📎 FEC + pièces jointes')
st.caption('Déposez votre export comptable ZIP. Vérifiez les comptes, puis téléchargez le FEC et les PDF associés.')
st.caption('Libellé d’écriture : nom du client sur toutes les lignes de chaque facture ou avoir, y compris produits et TVA.')
upload=st.file_uploader('Export ZIP contenant le CSV comptable ou le FEC et les PDF',type=['zip'])
if not upload:
    st.info('Compatible avec le format de votre export fourni : CSV comptable + factures PDF, ou FEC à en-têtes + PDF. Un seul fichier comptable est lu pour éviter les doublons CSV / XLSX / TXT.')
    st.stop()
try:candidates,pdfs=read_zip(upload.getvalue())
except Exception as e:
    st.error(str(e));st.stop()
names=sorted(candidates,key=lambda n:(not n.lower().endswith('.csv'),n))
source=st.selectbox('Fichier comptable à utiliser (une seule source)',names)
digest=hashlib.sha256(upload.getvalue()+source.encode()).hexdigest()[:12]
raw=candidates[source]
a,b,c=st.columns(3)
a.metric('Lignes source',len(raw));b.metric('Références de pièces',raw.PieceRef.nunique());c.metric('PDF disponibles',len(pdfs))
st.subheader('Paramètres et corrections')
journal=st.text_input('Journal de destination','VT',help='VT proposé pour cet export de ventes. Toutes les écritures seront affectées à ce journal.')
saved=None
mapping_upload=st.file_uploader('Correspondance clients du mois précédent (facultatif)',type=['csv'])
if mapping_upload:
    try:
        saved=pd.read_csv(mapping_upload,sep=';',dtype=str,keep_default_na=False)
        if not {'CompAuxNum','CompAuxLib','Compte_cible'}.issubset(saved.columns):raise ValueError('Colonnes manquantes')
    except Exception:
        st.warning('Correspondance non reconnue : les suggestions automatiques sont utilisées.')
        saved=None
with st.expander('Corrections proposées des comptes clients',expanded=bool(collisions(raw))):
    clients=propose_accounts(raw,saved)
    edited=st.data_editor(clients,disabled=['CompAuxNum','CompAuxLib'],hide_index=True,key='clients_v3_'+digest)
    lookup={(r.CompAuxNum,r.CompAuxLib):r.Compte_cible for r in edited.itertuples()}
    raw=raw.copy()
    raw['CompAuxNum']=[lookup.get((r.CompAuxNum,r.CompAuxLib),r.CompAuxNum) for r in raw.itertuples()]
    changed=edited[edited.CompAuxNum.ne(edited.Compte_cible)]
    if len(changed):
        st.info('Les comptes partagés sont séparés automatiquement par client. Vous pouvez remplacer les propositions par les comptes existants du dossier Pennylane.')
        st.dataframe(changed,hide_index=True)
    st.caption('Les nouveaux numéros proposés sont numériques. Leur disponibilité dans Pennylane ne peut pas être vérifiée par cette application.')
    mapping=edited if saved is None else pd.concat([saved,edited],ignore_index=True).drop_duplicates(['CompAuxNum','CompAuxLib'],keep='last')
    mapping_bytes=mapping.to_csv(index=False,sep=';').encode('utf-8-sig')
    st.download_button('Télécharger la correspondance pour le mois suivant',mapping_bytes,'CORRESPONDANCE_CLIENTS.csv','text/csv')
with st.expander('Voir / modifier les écritures'):
    df=st.data_editor(raw,num_rows='dynamic',hide_index=True,key='lines_'+digest)
    st.caption('Les dates et montants sont conservés. Aucun écart n’est compensé automatiquement. Les comptes de TVA restent ceux de la source.')
with st.expander('Association des PDF',expanded=False):
    links=st.data_editor(matches(df,pdfs),disabled=['PieceRef'],column_config={'PDF':st.column_config.SelectboxColumn('PDF',options=['']+list(pdfs))},hide_index=True,key='pdf_'+digest)
result=process_batch(df,pdfs,links,journal.strip())
# La correspondance et la source sont conservées dans le pack pour les imports suivants.
import io
import zipfile
pack=io.BytesIO(result['bundle'])
with zipfile.ZipFile(pack,'a',zipfile.ZIP_DEFLATED) as z:
    z.writestr('CORRESPONDANCE_CLIENTS.csv',mapping_bytes)
    z.writestr('EXPORT_SOURCE_ORIGINAL.zip',upload.getvalue())
st.subheader('Téléchargement')
st.write(f"**{result['valid_rows']} lignes exportables sur {result['source_rows']} — {len(result['excluded'])} lignes à vérifier.**")
if len(result['excluded']):
    st.warning('Export partiel : les écritures à vérifier sont conservées dans le pack avec leur motif et ne sont pas incluses dans le FEC. Corrigez-les dans le tableau pour les intégrer.')
    st.dataframe(result['issues'],hide_index=True)
else:
    st.success('Toutes les écritures sont exportables avec leurs PDF.')
st.download_button('⬇ Télécharger le pack FEC + PJ + contrôles' if result['valid_rows'] else '⬇ Télécharger les écritures à corriger et les sources',pack.getvalue(),'PENNYLANE_FEC_ET_PJ.zip','application/zip',type='primary')
if result['valid_rows']:
    a,b=st.columns(2)
    a.download_button('FEC seul',result['fec'],'FEC_IMPORT.txt','text/plain')
    b.download_button('Archive PDF seule',result['pj'],'PIECES_JOINTES.zip','application/zip')
st.download_button('Écritures à vérifier',result['excluded'].to_csv(index=False,sep=';').encode('utf-8-sig'),'ECRITURES_A_VERIFIER.csv','text/csv')
st.info('Dans Pennylane : importer le fichier FEC_IMPORT.txt, puis cliquer sur le trombone « Joindre une archive » de cet import et sélectionner PIECES_JOINTES.zip. Le ZIP global sert uniquement au téléchargement.')
st.caption('Vérifiez les correspondances des comptes et journaux dans Pennylane. L’application ne consulte pas le dossier : elle ne peut détecter les écritures déjà présentes ni les comptes réservés. Export partiel au format FEC, non destiné au dépôt fiscal annuel. Les données ne sont pas enregistrées sur disque par l’application.')
st.link_button('Documentation officielle Pennylane','https://help.pennylane.com/fr/articles/18792-importer-un-fec')
