"""Verified ordinary-browser official PDF intake when direct transport fails.

This is an operator/browser research path, not an unattended browser worker.
All pages, their actual screenshots, source listing and receipt clocks must be
reviewed. The same official text parser/identity/freshness rules still apply.
An unsubmitted report stays unsubmitted; an old ESPN observation stays old.
"""
import argparse
import copy
import hashlib
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path

import boxscores
import deployment_lock
import nba_capture
import nba_official_availability as official


def with_pdf(packet, pdf):
    """Use actual downloaded bytes, never an AI-generated status transcription."""
    text=official.extract(pdf)
    pages=[page for page in text.split('\f') if page.strip()]
    if len(pages)!=len(packet['pages']):
        raise ValueError('Downloaded PDF and reviewed page counts differ')
    result=copy.deepcopy(packet)
    for page,text in zip(result['pages'],pages):page['text']=text
    result['pdfSha256']=hashlib.sha256(pdf).hexdigest()
    return result


def build(packet, now, root):
    root=Path(root);listing=packet['listing'];received=boxscores.instant(packet['retrievedAt'])
    listed=boxscores.instant(listing['retrievedAt'])
    if (listing['source']!=official.index_url(listed) or not listed<=received<=now
            or now-listed>timedelta(minutes=90) or now-received>timedelta(minutes=90)):
        raise ValueError('Browser report listing/receipt clock unavailable')
    source,expected=official.published_report(listing['html'],listed)
    if packet['source']!=source:raise ValueError('Browser report is not the newest observed published link')
    pages=packet['pages']
    if (packet.get('allPagesReviewed') is not True or not isinstance(pages,list) or not 1<=len(pages)<=20):
        raise ValueError('Complete official PDF page review required')
    evidence=[];texts=[]
    for number,page in enumerate(pages,1):
        text=page['text'];image=Path(page['screenshot']).read_bytes()
        if (page['number']!=number or page['totalPages']!=len(pages) or not isinstance(text,str)
                or not 20<=len(text)<=100_000 or not (image.startswith(b'\x89PNG\r\n\x1a\n') or image.startswith(b'\xff\xd8\xff'))
                or not 24<=len(image)<=20_000_000 or hashlib.sha256(image).hexdigest()!=page['sha256']
                or not re.search(r'Page\s+'+str(number)+r'\s+of\s+'+str(len(pages))+r'\b',text)):
            raise ValueError('Official PDF page text/image evidence incomplete')
        texts.append(text);evidence.append(dict(page=number,sha256=page['sha256']))
    if len({p['sha256'] for p in evidence})!=len(evidence):
        raise ValueError('Duplicate official PDF page image')
    text='\n'.join(texts)
    # Keep the original observed clock. Rebuilding does not refresh the source.
    slate=json.loads((root/'slate.json').read_text())
    if not timedelta(0)<=now-boxscores.instant(slate['retrievedAt'])<=timedelta(hours=24):
        raise ValueError('Current official game identities unavailable')
    games=slate['games'];rosters={}
    for path in (root/'rosters').glob('*.json'):
        try:rosters[path.stem]=json.loads(path.read_text())
        except (OSError,ValueError):continue
    report=official.parse(text,games,rosters,expected,received,source)
    if not report['teams']:raise ValueError('No official teams reconciled to current slate')
    seasons={g['season'] for g in games if str(g['providerId']) in {r['eventId'] for r in report['teams']}}
    if len(seasons)!=1:raise ValueError('Official season identity unavailable')
    if packet.get('pdfSha256'):
        if not re.fullmatch('[0-9a-f]{64}',packet['pdfSha256']):raise ValueError('Invalid original PDF digest')
        report['browserPdfSha256']=packet['pdfSha256']
    report.update(league='NBA',season=seasons.pop(),observedMethod='Reviewed ordinary-browser official PDF',
        browserEvidence=evidence,discovery=dict(source=listing['source'],retrievedAt=listing['retrievedAt'],method='Newest published official link; complete browser PDF review'))
    return report


def ingest(packet, now, root=nba_capture.STORE):
    root=Path(root);report=build(packet,now,root)
    if boxscores.verify(root/'official-availability'):
        raise ValueError('Official availability store integrity failed')
    previous_reports=[r for p in (root/'official-availability').glob('*.jsonl') for r in boxscores.read_store(p)]
    if any(boxscores.instant(r['retrievedAt'])<=now and boxscores.instant(r['reportedAt'])>boxscores.instant(report['reportedAt']) for r in previous_reports):
        raise ValueError('Browser report would replace a newer official report')
    snapshot=json.loads((root/'injuries-current.json').read_text())
    current=snapshot.get('official',{})
    if current.get('reportedAt') and boxscores.instant(current['reportedAt'])>boxscores.instant(report['reportedAt']):
        raise ValueError('Browser report would replace a newer official report')
    if snapshot.get('season')!=report['season']:raise ValueError('Provider injury season unavailable')
    if not boxscores.instant(snapshot['retrievedAt'])<=now:raise ValueError('Future provider observation')
    slate=json.loads((root/'slate.json').read_text())
    count=nba_capture.append_changed([report],root/'official-availability',lambda r:r['retrievedAt'])
    # Preserve the independent ESPN source clock, status rows and transport
    # failure evidence; browser success is not direct-collector recovery.
    previous=snapshot.get('official',{})
    if previous.get('state')=='unavailable':snapshot['lastOfficialTransportFailure']=previous
    snapshot.update(official=report,gameAvailability=official.merge(snapshot.get('rows',[]),report,slate['games']))
    boxscores.write_json(root/'injuries-current.json',snapshot)
    return dict(ingested=count,teams=len(report['teams']),submitted=sum(r['submitted'] is True for r in report['teams']),
                reportedAt=report['reportedAt'],retrievedAt=report['retrievedAt'],providerRetrievedAt=snapshot['retrievedAt'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--pdf',required=True)
    parser.add_argument('--root',type=Path,default=nba_capture.STORE);args=parser.parse_args()
    packet=with_pdf(json.loads(Path(args.input).read_text()),Path(args.pdf).read_bytes())
    with deployment_lock.bounded_lock(Path.home()/'.config/keenroudy/run.lock'):
        result=ingest(packet,datetime.now(timezone.utc),args.root)
        import nba_validation_runtime
        try:
            result['validationCompletion']=nba_validation_runtime.finish(args.root,datetime.now(timezone.utc))
        except (OSError,ValueError,KeyError,TypeError):
            result['validationCompletion']=dict(state='held',reason='Validation source completion failed; original report retained',admissionReady=False,requests=0)
    print(json.dumps(result))

if __name__=='__main__':main()
