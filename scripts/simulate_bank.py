import argparse,base64,hashlib,hmac,json,os,time,urllib.request
parser=argparse.ArgumentParser()
parser.add_argument('--url',required=True)
parser.add_argument('--invoice',required=True)
parser.add_argument('--txid',required=True)
parser.add_argument('--amount',required=True)
parser.add_argument('--currency',default='USD')
parser.add_argument('--date',required=True)
args=parser.parse_args()
if not args.url.startswith('http://127.0.0.1:'):
    raise SystemExit('This simulator is restricted to a loopback HTTP endpoint.')
secret=os.environ.get('LAB_BANK_SECRET')
if not secret: raise SystemExit('Load only this project secret into LAB_BANK_SECRET first.')
data={'invoice_reference':args.invoice,'transaction_id':args.txid,'amount':args.amount,
      'currency':args.currency,'date':args.date,'timestamp':int(time.time()),'status':'success'}
raw=json.dumps(data).encode()
signature=base64.b64encode(hmac.new(secret.encode(),raw,hashlib.sha256).digest()).decode()
request=urllib.request.Request(args.url,data=raw,headers={'Content-Type':'application/json','X-Lab-Signature':signature})
print(urllib.request.urlopen(request,timeout=20).read().decode())
