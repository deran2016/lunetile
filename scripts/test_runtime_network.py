"""Exercise the actual DLL/launcher with isolated HTTP, TCP and TLS fixtures."""
import argparse,contextlib,gzip,http.server,json,os,socket,socketserver,ssl,subprocess,threading,time
from pathlib import Path
from test_runtime import ROOT,run

class HTTPHandler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args):pass
 def handle_request(self):
  try:
   data=self.rfile.read(int(self.headers.get('Content-Length','0')))
   path=self.path.split('?',1)[0]
   status=200;headers=[]
   body=json.dumps({'method':self.command,'path':self.path,'body':data.decode('utf-8',errors='replace'),'body_hex':data.hex(),'authorization':self.headers.get('Authorization'),'cookie':self.headers.get('Cookie')},ensure_ascii=False).encode()
   if path=='/slow':time.sleep(1.5)
   elif path=='/drip':body=b'x'*100
   elif path=='/binary':body=bytes(range(256))*3
   elif path=='/invalid-json':body=b'{nope'
   elif path=='/invalid-utf8':body=b'\xff'
   elif path=='/deep':body=b'['*101+b'0'+b']'*101
   elif path=='/nan':body=b'NaN'
   elif path=='/huge':body=b'x'*(4*1024*1024+1)
   elif path=='/gzip-huge':body=gzip.compress(b'x'*(4*1024*1024+1));headers.append(('Content-Encoding','gzip'))
   elif path=='/redirect':status=302;headers.append(('Location','/echo'))
   elif path=='/cookies':headers.extend([('Set-Cookie','a=1'),('Set-Cookie','b=2')])
   elif path=='/headers':headers.append(('X-Huge','x'*70000))
   elif path.startswith('/status/'):status=int(path.rsplit('/',1)[1])
   if status==204:body=b''
   self.send_response(status);self.send_header('Content-Length',str(len(body)))
   for name,value in headers:self.send_header(name,value)
   self.end_headers()
   if self.command!='HEAD':
    if path=='/drip':
     for byte in body:self.wfile.write(bytes([byte]));self.wfile.flush();time.sleep(.08)
    else:self.wfile.write(body)
  except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
 do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=do_HEAD=do_OPTIONS=handle_request

class TCPHandler(socketserver.BaseRequestHandler):
 def handle(self):
  try:
   self.request.settimeout(60)
   if self.server.mode=='stall':time.sleep(3);return
   if self.server.mode=='junk':self.request.sendall(b'not a TLS server\n');return
   while data:=self.request.recv(65536):
    if data==b'CLOSE':self.request.sendall(b'tail');return
    for part in (data[:1],data[1:7],data[7:]):
     if part:self.request.sendall(part)
  except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError,TimeoutError,ssl.SSLError):pass

class TCPServer(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True
 request_queue_size=64
 def handle_error(self,*args):pass

class HTTPServer(http.server.ThreadingHTTPServer):
 daemon_threads=True
 def handle_error(self,*args):pass

class TCP6Server(TCPServer):
 address_family=socket.AF_INET6

@contextlib.contextmanager
def fixtures(certificates):
 servers=[];threads=[];ports={}
 try:
  for name,kind,mode,certificate in [('http','http',None,None),('tcp','tcp','echo',None),('stall','tcp','stall',None),('junk','tcp','junk',None),
    ('https','http',None,'valid'),('tls','tcp','echo','valid'),('expired_https','http',None,'expired'),('expired_tls','tcp','echo','expired'),
    ('wrong_https','http',None,'wrong-host'),('wrong_tls','tcp','echo','wrong-host')]:
   server=(HTTPServer if kind=='http' else TCPServer)(('127.0.0.1',0),HTTPHandler if kind=='http' else TCPHandler)
   server.mode=mode
   if certificate:
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificates/(certificate+'.pem'),certificates/(certificate+'-key.pem'))
    server.socket=context.wrap_socket(server.socket,server_side=True)
   servers.append(server);ports[name]=server.server_address[1]
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();threads.append(thread)
  try:ipv6=TCP6Server(('::1',0),TCPHandler)
  except OSError:pass
  else:
   ipv6.mode='echo';servers.append(ipv6);ports['tcp6']=ipv6.server_address[1]
   thread=threading.Thread(target=ipv6.serve_forever,daemon=True);thread.start();threads.append(thread)
  with socket.socket() as unused:unused.bind(('127.0.0.1',0));ports['refused']=unused.getsockname()[1]
  yield ports
 finally:
  for server in servers:server.shutdown();server.server_close()
  for thread in threads:thread.join(timeout=2)

def verify(output,dll,exe,profiles=('stock120',None)):
 output.mkdir(parents=True,exist_ok=False)
 certificates=output/'certificates'
 script=ROOT/'scripts/test_network_certificates.ps1'
 def cert(action):
  result=subprocess.run(['pwsh','-NoProfile','-File',str(script),'-Directory',str(certificates),'-Action',action],capture_output=True,text=True,timeout=30)
  if result.returncode:raise RuntimeError('Certificate fixture '+action+' failed: '+result.stderr)
 cert('Create')
 trusted=os.environ.get('GITHUB_ACTIONS')=='true'
 report={'passed':False,'trusted_tls_test':trusted,'scope':'Local fixture servers and actual Game.exe; no production server or endurance acceptance','runs':[]}
 try:
  if trusted:cert('Trust')
  with fixtures(certificates) as ports:
   setup=('NETWORK_PORTS = '+repr(ports).replace("'",'"').replace(': ', ' => ')+'\nNETWORK_TRUSTED_TLS = '+str(trusted).lower()+'\n').encode()
   source=setup+(ROOT/'tests/runtime_network.rb').read_bytes()
   for profile in profiles:
    folder=output/('logic120' if profile else 'logic40')
    try:result=run(exe,dll,folder,'',source,timeout=100,screen_size=(1280,720) if profile else (640,480),timing_profile=profile)
    except AssertionError as error:
     if error.args and isinstance(error.args[0],dict):raise RuntimeError(error.args[0].get('log','Launcher failed')) from None
     raise
    assertions=json.loads((folder/'network-results.json').read_text(encoding='utf-8'))
    finalized=json.loads((folder/'network-finalized.json').read_text())
    assert finalized==[0,0],finalized
    assert 'LUNETILE-TEST-SECRET' not in result['log']
    report['runs'].append({'dll_sha256':result['runtime_sha256'],'profile':profile,'assertions':assertions,'finalized':finalized})
  report['passed']=True
 finally:
  if trusted:cert('Remove')
  (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
 parser.add_argument('--dll',type=Path,default=ROOT/'build/runtime-native/bin/Release/Lunetile.dll')
 parser.add_argument('--exe',type=Path,default=ROOT/'template-xp/Game.exe')
 args=parser.parse_args();result=verify(args.output.resolve(),args.dll.resolve(),args.exe.resolve())
 print('REST/TCP/TLS actual-launcher fixture tests PASS; trusted TLS success tested='+str(result['trusted_tls_test']))
