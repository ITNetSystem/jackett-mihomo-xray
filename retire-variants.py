"""Delete only registry versions tagged exclusively as retired light/compact."""
import json,os,urllib.request,urllib.error
base='https://api.github.com/users/'+os.environ['REPO_OWNER']+'/packages/container/jackett-mihomo-xray/versions'
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
def request(endpoint,method='GET'):
    with urllib.request.urlopen(urllib.request.Request(endpoint,headers=headers,method=method)) as r:
        raw=r.read();return json.loads(raw) if raw else None
versions=[]
try:
    for page in range(1,101):
        items=request(base+'?per_page=100&page='+str(page));versions.extend(items)
        if len(items)<100:break
    removed=0
    for version in versions:
        tags=version.get('metadata',{}).get('container',{}).get('tags',[])
        if tags and all(t.startswith(('mikrotik-light-','mikrotik-compact-')) for t in tags):
            request(base+'/'+str(version['id']),'DELETE');removed+=1
    print('Retired tagged versions removed:',removed)
except urllib.error.HTTPError as e:
    print('::warning::Registry cleanup unavailable (HTTP '+str(e.code)+'); retired builds are disabled, but old tags may remain.')
