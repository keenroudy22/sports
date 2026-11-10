"""Typed official NBA injury-report observations; no model or bet promotion.

Read one actual published link from the official season page, then at most one
PDF within the shared capture budget. Earlier captures retain their quarter-hour
protocol. No URL probing, report-time invention or extra job. Parse only names/statuses;
wrapped medical-reason cells are deliberately not reconstructed.
"""
import re
import json
import shutil
import subprocess
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
import socket
import ssl

import boxscores

START = datetime(2026,10,27,12,tzinfo=timezone.utc)
PUBLISHED_LINKS_FROM = datetime(2026,10,30,17,5,tzinfo=timezone.utc)
BROWSER_LAG_FROM = datetime(2026,11,10,16,30,tzinfo=timezone.utc)
EASTERN = ZoneInfo('America/New_York')
STATUSES = ('Out','Doubtful','Questionable','Probable','Available')
ALIASES = {'SA':'SAS','GS':'GSW','NY':'NYK','NO':'NOP','UTAH':'UTA','PHO':'PHX','WSH':'WAS'}


def normal(value):
    text=unicodedata.normalize('NFKD',str(value or '')).casefold().replace('los angeles','la')
    return re.sub(r'[^a-z0-9]','',text)


def player_identity(value):
    parts=[p.strip() for p in value.split(',')]
    if len(parts)==2 and all(parts):
        return normal(parts[1]+' '+parts[0])
    # The official PDF also prints "Udeh, Jr., Ernest". Reorder only
    # an explicit suffix; nicknames and other ambiguous comma rows stay held.
    if len(parts)==3 and all(parts) and normal(parts[1]) in ('jr','sr','ii','iii','iv','v'):
        return normal(parts[2]+' '+parts[0]+' '+parts[1])
    return None


def report_url(now):
    local=now.astimezone(EASTERN)-timedelta(minutes=15)
    local=local.replace(minute=15*(local.minute//15),second=0,microsecond=0)
    return ('https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+local.strftime('%Y-%m-%d_%I_%M%p')+'.pdf',local.astimezone(timezone.utc))




def index_url(now):
    local = now.astimezone(EASTERN)
    year = local.year if local.month >= 10 else local.year-1
    return f'https://official.nba.com/nba-injury-report-{year}-{(year+1)%100:02d}-season'


class PublishedReportUnavailable(ValueError):
    def __init__(self, source, latest=None):
        super().__init__('Official report listing has no recent published PDF')
        self.source, self.latest = source, latest


def published_report(html, now):
    """One bounded official listing, one exact linked PDF, never URL probing."""
    if not isinstance(html, str) or len(html.encode('utf-8')) > 1_000_000:
        raise ValueError('Invalid official report listing')
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links=[]
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.links.extend(v for k,v in attrs if k == 'href' and isinstance(v,str))
    parser=Links(); parser.feed(html)
    candidates={}
    for href in parser.links:
        source=urljoin(index_url(now),href)
        found=re.fullmatch(r'https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(?:AM|PM))\.pdf',source)
        if not found: continue
        try: reported=datetime.strptime(found[1],'%Y-%m-%d_%I_%M%p').replace(tzinfo=EASTERN).astimezone(timezone.utc)
        except ValueError: continue
        if reported <= now: candidates[reported]=source
    latest=max(candidates,default=None)
    if latest is None or now-latest > timedelta(minutes=90):
        raise PublishedReportUnavailable(index_url(now),latest)
    return candidates[latest],latest


def failure(error, attempted_at):
    """Bounded private diagnostics; never copy response bodies or exception URLs.

    A refused/missing PDF remains unavailable, not evidence of a healthy team.
    Keep one request per approved capture and retry only in the next normal pass.
    """
    result = dict(state='unavailable', attemptedAt=boxscores.stamp(attempted_at),
                  source=index_url(attempted_at) if attempted_at>=PUBLISHED_LINKS_FROM else report_url(attempted_at)[0])
    stage = getattr(error, 'official_stage', None)
    if stage in ('listing', 'pdf', 'extraction', 'verification'):
        result['stage'] = stage
    if isinstance(error, PublishedReportUnavailable):
        result.update(source=error.source, reason='Official report listing has no recent published PDF')
        if error.latest is not None: result['latestPublishedAt']=boxscores.stamp(error.latest)
    elif isinstance(error, HTTPError):
        result.update(reason='Official report request failed', httpStatus=error.code)
    elif isinstance(error, TimeoutError):
        result['reason']=('NBA capture budget exhausted' if str(error) in ('NBA free capture budget exhausted','NBA capture timebox exhausted') else 'Official report request timed out')
    elif isinstance(error, URLError):
        # urllib wraps transport failures. Classify the typed cause only;
        # exception strings can contain URLs or other private request details.
        cause = error.reason
        result['reason'] = ('Official report request timed out' if isinstance(cause, TimeoutError)
                            else 'Official report host lookup failed' if isinstance(cause, socket.gaierror)
                            else 'Official report TLS verification failed' if isinstance(cause, ssl.SSLError)
                            else 'Official report connection unavailable')
    elif isinstance(error, subprocess.SubprocessError):
        result['reason']='Official report PDF extraction failed'
    elif isinstance(error, ValueError) and str(error)=='Official injury PDF reader unavailable':
        result['reason']='Official report PDF reader unavailable'
    elif isinstance(error, (ValueError, KeyError, TypeError)):
        result['reason']='Official report could not be verified'
    else:
        result['reason']='Official report connection or capture budget unavailable'
    return result


def extract(pdf):
    binary=shutil.which('pdftotext')
    if not binary:
        raise ValueError('Official injury PDF reader unavailable')
    if not isinstance(pdf,bytes) or not pdf.startswith(b'%PDF-') or len(pdf)>3_000_000:
        raise ValueError('Invalid official injury PDF')
    result=subprocess.run([binary,'-layout','-enc','UTF-8','-','-'],input=pdf,
                          capture_output=True,timeout=10,check=True)
    if len(result.stdout)>1_000_000:
        raise ValueError('Official injury text exceeds bound')
    return result.stdout.decode('utf-8')


def parse(text, games, rosters, expected_at, observed_at, source, *, archive=False):
    expected_source='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+expected_at.astimezone(EASTERN).strftime('%Y-%m-%d_%I_%M%p')+'.pdf'
    if source!=expected_source:raise ValueError('Official source URL/report clock mismatch')
    headers=re.findall(r'Injury Report:\s*(\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}\s+[AP]M)',text)
    moments={datetime.strptime(h,'%m/%d/%y %I:%M %p').replace(tzinfo=EASTERN).astimezone(timezone.utc) for h in headers}
    if (moments!={expected_at} or observed_at<expected_at
            or not archive and observed_at-expected_at>timedelta(minutes=90)):
        raise ValueError('Official report clock unavailable, mismatched or stale')
    if 'Player Name' not in text or 'Current Status' not in text:
        raise ValueError('Official report columns unavailable')
    index={};names={}
    for game in games:
        try:
            local=boxscores.instant(game['kickoff']).astimezone(EASTERN)
            away,home=(game['teams'][s] for s in ('away','home'))
            abbr=lambda t:ALIASES.get(t['abbreviation'],t['abbreviation'])
            key=(local.strftime('%m/%d/%Y'),abbr(away)+'@'+abbr(home))
            if key in index:raise ValueError('Ambiguous official game identity')
            index[key]=game
            for team in (away,home):
                names[(str(game['providerId']),normal(team.get('name') or team.get('displayName')))]=str(team['id'])
        except KeyError:
            continue
    rows={};day=matchup=team_id=game=None;game_time=None
    for raw in text.splitlines():
        line=raw.strip('\f \t')
        if not line or line.startswith(('Injury Report:','Game Date','Page ')):continue
        parts=re.split(r'\s{2,}',line)
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}',parts[0]):day=parts.pop(0);game=None;team_id=None
        if parts and re.fullmatch(r'\d{2}:\d{2}\s*\(ET\)',parts[0]):game_time=parts.pop(0).split()[0]
        if parts and re.fullmatch(r'[A-Z]{2,4}@[A-Z]{2,4}',parts[0]):
            matchup=parts.pop(0);game=index.get((day,matchup));team_id=None
            if game:
                local=boxscores.instant(game['kickoff']).astimezone(EASTERN)
                if game_time not in (local.strftime('%I:%M'),local.strftime('%H:%M')):
                    if archive:
                        game=None;continue  # No historical clearance for this fixture.
                    raise ValueError('Official matchup kickoff differs from stored schedule')
        if not game or not parts:continue
        provider=str(game['providerId'])
        found=names.get((provider,normal(parts[0])))
        if found:
            team_id=found;parts.pop(0)
            rows.setdefault((provider,team_id),dict(eventId=provider,team=team_id,kickoff=game['kickoff'],submitted=None,rows=[],unmapped=[],unmappedRows=[]))
        if not team_id:
            raise ValueError('Official team identity unavailable')
        record=rows[(provider,team_id)]
        if 'NOT YET SUBMITTED' in ' '.join(parts):
            record['submitted']=False;continue
        if not parts:continue
        if parts==['None']:
            record['submitted']=True;continue
        body='  '.join(parts)
        player=re.match(r'^(.+?,\s*.+?)\s+('+'|'.join(STATUSES)+r')\b',body)
        if not player:
            if ',' in body or any(re.search(r'\b'+s+r'\b',body) for s in STATUSES):
                if archive:
                    record['unmapped'].append('Unrecognized status row');continue
                raise ValueError('Unrecognized official player/status row')
            continue  # Wrapped reason only, never a participation claim.
        identity=player_identity(player[1])
        record['submitted']=True
        roster=rosters.get(team_id,{})
        roster_ok=(roster.get('team')==team_id and roster.get('season')==game['season']
                   and (roster.get('identityOnly') is True if archive else
                        roster.get('identityOnly') is not True and roster.get('retrievedAt')
                        and timedelta(0)<=observed_at-boxscores.instant(roster['retrievedAt'])<=timedelta(hours=24)))
        matches=[p for p in roster.get('players',[]) if normal(p.get('name'))==identity] if roster_ok else []
        if len(matches)!=1:
            record['unmapped'].append(player[1]);record['unmappedRows'].append(dict(name=player[1],status=player[2]));continue
        record['rows'].append(dict(league='NBA',season=game['season'],team=team_id,
            athleteId=matches[0]['id'],name=matches[0]['name'],status=player[2],
            source=source,date=boxscores.stamp(expected_at),retrievedAt=boxscores.stamp(observed_at)))
    for record in rows.values():
        ids=[r['athleteId'] for r in record['rows']]
        if len(ids)!=len(set(ids)) or (not record['submitted'] and record['rows']):
            raise ValueError('Conflicting official team/player entries')
    result=dict(reportedAt=boxscores.stamp(expected_at),retrievedAt=boxscores.stamp(observed_at),
                source=source,teams=list(rows.values()),scope='Official participation statuses, not expected minutes or a model adjustment')
    if archive:
        result.update(archive=True,analysisOnly=True,scope='Retrospectively retrieved official report; identity mapping only, not an original capture or current roster clearance')
    return result


def merge(provider_rows, report, games):
    """Official submitted rows take precedence; disagreements stay explicit holds."""
    records={(r['eventId'],r['team']):r for r in report['teams']}
    out={}
    for game in games:
        event=str(game['providerId']);rows=[];holds={};conflicts=[]
        for t in game['teams'].values():
            team=str(t['id']);observed=[r for r in provider_rows if r['team']==team]
            record=records.get((event,team))
            if not record or record['submitted'] is not True:
                holds[team]='Official team report not submitted or not found';rows+=observed;continue
            if record['unmapped']:holds[team]='Official report player/roster identity needs verification'
            official={r['athleteId']:r for r in record['rows']}
            for old in observed:
                new=official.get(old['athleteId'])
                if new is None and str(old['status']).casefold() not in ('active','available'):
                    holds[team]='Availability sources disagree; ESPN designation missing from official report'
                    conflicts.append(dict(team=team,athleteId=old['athleteId'],providerStatus=old['status'],officialStatus='not listed'))
                elif new and str(old['status']).casefold() not in ('active','available') and new['status']=='Available':
                    try:newer=boxscores.instant(old['date'])>boxscores.instant(report['reportedAt'])
                    except (KeyError,TypeError,ValueError):newer=True
                    if newer:holds[team]='Availability sources disagree after official report'
            rows+=record['rows']
        out[event]=dict(rows=rows,teamHolds=holds,conflicts=conflicts,kickoff=game['kickoff'])
    return out


def browser_observation(root, source, expected, games, now):
    """Reuse only a verified observation of this exact newest published file.

    Keep its original receipt clock. A newer URL, stale observation, changed
    fixture or unresolved current roster cannot inherit an older clearance.
    """
    root=Path(root)
    if boxscores.verify(root/'official-availability'):return None
    candidates=[r for p in (root/'official-availability').glob('*.jsonl') for r in boxscores.read_store(p)
                if r.get('observedMethod')=='Reviewed ordinary-browser official PDF' and r.get('source')==source]
    candidates.sort(key=lambda r:r.get('retrievedAt',''),reverse=True)
    indexed={str(g['providerId']):g for g in games}
    for report in candidates:
        try:
            received=boxscores.instant(report['retrievedAt'])
            if (boxscores.instant(report['reportedAt'])!=expected or not expected<=received<=now
                    or now-expected>timedelta(minutes=90) or not report.get('browserEvidence')
                    or report.get('archive') or report.get('analysisOnly') or not report.get('teams')):continue
            valid=True
            for team in report['teams']:
                game=indexed.get(team['eventId'])
                if (not game or report['season']!=game['season'] or team['team'] not in {str(t['id']) for t in game['teams'].values()}
                        or boxscores.instant(team['kickoff'])!=boxscores.instant(game['kickoff'])):
                    valid=False;break
                if team['rows']:
                    roster=json.loads((root/'rosters'/f"{team['team']}.json").read_text())
                    if (roster.get('identityOnly') or roster.get('team')!=team['team'] or roster.get('season')!=report['season']
                            or not timedelta(0)<=now-boxscores.instant(roster['retrievedAt'])<=timedelta(hours=24)):
                        valid=False;break
                    for player in team['rows']:
                        matches=[p for p in roster['players'] if p.get('id')==player['athleteId'] and normal(p.get('name'))==normal(player['name'])]
                        if len(matches)!=1:valid=False;break
            if valid:return dict(report,_from_verified_browser_cache=True)
        except (OSError,ValueError,KeyError,TypeError):continue
    return None


def newer_browser_discovery(root, games, now, latest):
    """A stale direct index cannot erase a newer, actually reviewed discovery.

    No guessed link, freshened clock or stale PDF. An equal/newer known direct
    publication cannot inherit an older browser observation.
    """
    if now<BROWSER_LAG_FROM:return None
    root=Path(root)
    if boxscores.verify(root/'official-availability'):return None
    reports=[r for p in (root/'official-availability').glob('*.jsonl') for r in boxscores.read_store(p)
             if r.get('observedMethod')=='Reviewed ordinary-browser official PDF']
    for report in sorted(reports,key=lambda r:r.get('reportedAt',''),reverse=True):
        try:
            reported=boxscores.instant(report['reportedAt']);discovery=report['discovery']
            listed=boxscores.instant(discovery['retrievedAt']);received=boxscores.instant(report['retrievedAt'])
            if (latest and reported<=latest or discovery['source'].rstrip('/')!=index_url(now)
                    or not reported<=listed<=received<=now or now-listed>timedelta(minutes=90)):
                continue
            cached=browser_observation(root,report['source'],reported,games,now)
            if cached:
                cached['directListingLag']=dict(observedAt=boxscores.stamp(now),
                    latestReportedAt=boxscores.stamp(latest) if latest else None)
                return cached
        except (OSError,ValueError,KeyError,TypeError):continue
    return None


def capture(budget, games, root, now, clock=lambda:datetime.now(timezone.utc)):
    def observed(stage, action):
        try:
            return action()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            error.official_stage = stage
            raise
    if now >= PUBLISHED_LINKS_FROM:
        try:listing=observed('listing', lambda: budget.report_index(index_url(now)))
        except OSError as error:
            checked=clock()
            cached=newer_browser_discovery(root,games,checked,None)
            if cached:
                cached['directListingFailure']=failure(error,checked)
                return cached
            raise
        listed_at=clock()
        try:source,expected=published_report(listing,listed_at)
        except PublishedReportUnavailable as error:
            cached=newer_browser_discovery(root,games,listed_at,error.latest)
            if cached:return cached
            raise
        cached=browser_observation(root,source,expected,games,listed_at)
        if cached:return cached
    else:
        source,expected=report_url(now)
    pdf=observed('pdf', lambda: budget.raw(source));received=clock()
    text=observed('extraction', lambda: extract(pdf))
    rosters={}
    for p in (Path(root)/'rosters').glob('*.json'):
        try:rosters[p.stem]=json.loads(p.read_text())
        except (OSError,ValueError):continue
    report=observed('verification', lambda: parse(text,games,rosters,expected,received,source))
    if now >= PUBLISHED_LINKS_FROM:
        report['discovery']=dict(source=index_url(now),retrievedAt=boxscores.stamp(listed_at),method='Newest published official link; one PDF attempt')
    return report
