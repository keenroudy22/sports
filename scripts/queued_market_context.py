"""Annotate only a provider-confirmed private X draft; public originals stay intact."""
from datetime import timedelta
import buffer_post
import gates
import x_post


def update(entry,pick,quote,now):
    if not quote or pick.get('legs') or entry.get('sentAt') or entry.get('cancelledAt'):return False
    due=gates.when(entry['dueAt'])
    if due<=now+timedelta(minutes=3):return False
    line=x_post.now_line(pick,quote)
    if not line:return False
    provider=buffer_post.graphql(buffer_post.STATUS,{'id':entry['bufferPostId']},essential=True).get('post') or {}
    if provider.get('status')!='scheduled' or provider.get('sentAt'):
        raise buffer_post.BufferError('market context requires a provider-confirmed private scheduled post')
    original=provider.get('text') or ''
    if x_post.text_hash(original)!=entry.get('textHash'):
        raise buffer_post.BufferError('queued caption changed outside the verified local receipt')
    base=entry.get('originalQueuedText') or original
    parts=base.split('\n\n');parts.insert(1,line+' · Original play only.')
    text='\n\n'.join(parts)
    if x_post.tweet_length(text)>x_post.LIMIT or x_post.x_style(text):
        raise buffer_post.BufferError('complete original plus market context does not fit safely')
    reason=x_post.load_reasons().get(pick['id'])
    problems=x_post.guard(text,pick,reason,quote)
    if problems:raise buffer_post.BufferError('market context failed caption guard: '+'; '.join(problems))
    image=entry.get('bufferImage') or (buffer_post.card_url(entry.get('cardKey') or entry['id']) if entry.get('card') else None)
    if entry.get('card') and not image:raise buffer_post.BufferError('original card unavailable')
    channel=buffer_post.x_channel(wanted='keenkooks')
    new=buffer_post.create_post(text,channel['id'],due,image,essential=True)
    old=entry['bufferPostId']
    try:
        current=buffer_post.graphql(buffer_post.STATUS,{'id':old},essential=True).get('post') or {}
        if current.get('status')!='scheduled' or current.get('sentAt'):
            raise buffer_post.BufferError('old draft is no longer confirmed private; preserve it')
        buffer_post.delete_post(old)
    except buffer_post.BufferError as error:
        try:buffer_post.delete_post(new)
        except buffer_post.BufferError:
            import run
            run.alert('Queued market context needs attention',f"{entry['id']}: rollback failed for {new}; original {old} preserved")
        raise error
    entry.setdefault('priorBufferPosts',[]).append(dict(id=old,text=original,dueAt=entry['dueAt'],replacedAt=gates.stamp(now)))
    entry.update(bufferPostId=new,queuedText=text,textHash=x_post.text_hash(text),originalQueuedText=base,
                 requotedAt=gates.stamp(now),currentQuote=list(quote))
    return True
