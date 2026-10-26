"""Reuse only successful same-commit main CI with intact, unexpired artifacts."""
import argparse,hashlib,io,json,os,subprocess,urllib.error,urllib.parse,urllib.request,zipfile
from pathlib import Path

WORKFLOW='.github/workflows/release.yml'
REQUIRED={'lunetile-release-assets','build-diagnostics'}

def verified_run(run,sha,repo):
 return all([run.get('head_sha')==sha,run.get('head_branch')=='main',run.get('event')=='push',
  run.get('path')==WORKFLOW,run.get('status')=='completed',run.get('conclusion')=='success',
  (run.get('head_repository') or {}).get('full_name')==repo])

def verify_archive(data,sha):
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  if z.testzip() or any(n.startswith(('/','\\')) or '..' in n.replace('\\','/').split('/') for n in z.namelist()):raise ValueError('Artifact CRC/path failure')
  proof=json.loads(z.read('ci-provenance.json'))
  if proof.get('schema')!=1 or proof.get('source_commit')!=sha or proof.get('passed') is not True or proof.get('workflow')!=WORKFLOW:raise ValueError('Artifact provenance mismatch')
  lines=z.read('SHA256SUMS.txt').decode('ascii').splitlines()
  sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in lines if line}
  expected={'lunetile-template-xp-windows-x86.zip','lunetile-template-xp-diagnostics.zip','lunetile-template-vxa-windows-x86.zip','lunetile-template-vxa-diagnostics.zip','lunetile-vxa-editor-fix.zip','lunetile-vxa-speed-fix.zip','lunetile-xp-speed-fix.zip'}
  if set(sums)!=expected or sums!=proof.get('assets'):raise ValueError('Required artifact files missing')
  for name,h in sums.items():
   content=z.read(name)
   if hashlib.sha256(content).hexdigest()!=h:raise ValueError('Artifact asset hash mismatch')
   with zipfile.ZipFile(io.BytesIO(content)) as child:
    if child.testzip():raise ValueError('Nested artifact ZIP CRC failure')
 return proof

def find_reuse(request,sha,repo):
 runs=request('/actions/workflows/release.yml/runs?head_sha='+sha+'&branch=main&event=push&status=success&per_page=100')['workflow_runs']
 for run in runs:
  if not verified_run(run,sha,repo):continue
  items=request('/actions/runs/'+str(run['id'])+'/artifacts?per_page=100')['artifacts']
  artifacts={a['name']:a for a in items if not a.get('expired')}
  if not REQUIRED.issubset(artifacts):continue
  try:verify_archive(request('/actions/artifacts/'+str(artifacts['lunetile-release-assets']['id'])+'/zip',raw=True),sha)
  except (ValueError,KeyError,zipfile.BadZipFile):continue
  return dict(reuse=True,run_id=run['id'],source_commit=sha,source_url=run['html_url'],reason='Same-commit main passed; required artifacts and nested checksums verified')
 return dict(reuse=False,run_id='',source_commit=sha,reason='No complete matching main evidence; build normally')

class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):
  result=super().redirect_request(request,fp,code,msg,headers,newurl)
  if result and urllib.parse.urlsplit(request.full_url).netloc!=urllib.parse.urlsplit(newurl).netloc:result.remove_header('Authorization')
  return result

def probe(sha,repo,ref,token):
 if not ref.startswith('refs/tags/'):return dict(reuse=False,run_id='',source_commit=sha,reason='Main/manual execution always builds')
 opener=urllib.request.build_opener(Redirect)
 def request(route,raw=False):
  headers={'Authorization':'Bearer '+token,'User-Agent':'Lunetile-CI-reuse','Accept':'application/octet-stream' if raw else 'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
  with opener.open(urllib.request.Request('https://api.github.com/repos/'+repo+route,headers=headers),timeout=60) as response:body=response.read()
  return body if raw else json.loads(body)
 try:return find_reuse(request,sha,repo)
 except (OSError,ValueError,KeyError):return dict(reuse=False,run_id='',source_commit=sha,reason='Evidence unavailable; build normally')

def stamp(directory,verification,vxa):
 reports=[json.loads(p.read_text(encoding='utf-8')) for p in [verification,vxa]]
 if not all(r.get('passed') is True for r in reports):raise ValueError('CI checks not successful')
 commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 if reports[0].get('source_commit')!=commit:raise ValueError('CI source commit mismatch')
 sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (directory/'SHA256SUMS.txt').read_text().splitlines() if line}
 if any(hashlib.sha256((directory/n).read_bytes()).hexdigest()!=h for n,h in sums.items()):raise ValueError('CI package hash mismatch')
 (directory/'ci-provenance.json').write_text(json.dumps(dict(schema=1,passed=True,source_commit=commit,workflow=WORKFLOW,assets=sums),indent=2)+'\n')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['probe','stamp']);ap.add_argument('output',type=Path)
 ap.add_argument('--verification',type=Path);ap.add_argument('--vxa',type=Path);a=ap.parse_args()
 if a.action=='stamp':stamp(a.output,a.verification,a.vxa);return
 result=probe(os.environ['GITHUB_SHA'],os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_REF'],os.environ.get('GH_TOKEN',''))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
 with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:out.write(f"reuse={str(result['reuse']).lower()}\nrun_id={result['run_id']}\n")
 print(result['reason'])
if __name__=='__main__':main()
