import csv, io, json, re, urllib.request, pathlib, datetime, time
BASE = pathlib.Path(__file__).resolve().parent
URLS = ['https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt','https://nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt','https://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt']
EXCH = {'Q':'Nasdaq','N':'NYSE','P':'NYSE Arca','A':'NYSE American','Z':'Cboe BZX','V':'IEX','M':'NYSE Texas'}
OVERRIDE = {'TQQQ':3,'SQQQ':-3,'QLD':2,'QID':-2,'PSQ':-1,'SSO':2,'SDS':-2,'SH':-1,'UPRO':3,'SPXU':-3,'SPXL':3,'SPXS':-3,'TNA':3,'TZA':-3,'UWM':2,'TWM':-2,'RWM':-1,'UDOW':3,'SDOW':-3,'DDM':2,'DXD':-2,'DOG':-1,'SOXL':3,'SOXS':-3,'TECL':3,'TECS':-3,'FAS':3,'FAZ':-3,'LABU':3,'LABD':-3,'NUGT':2,'DUST':-2,'GUSH':2,'DRIP':-2,'ERX':2,'ERY':-2,'UVXY':1.5,'UVIX':2,'SVIX':-1,'SVXY':-0.5,'VXX':None,'VIXY':None,'VIXM':None,'VXZ':None,'BITX':2,'BITU':2,'SBIT':-2,'BITI':-1,'ETHU':2,'ETHT':2,'ETHD':-2,'BOIL':2,'KOLD':-2,'UGL':2,'GLL':-2,'AGQ':2,'ZSL':-2,'TMF':3,'TMV':-3,'UBT':2,'TBT':-2,'TBF':-1,'YINN':3,'YANG':-3,'FNGU':3,'FNGD':-3,'TSLL':2,'TSLS':-1,'TSLZ':-2,'NVDL':2,'NVDS':-1.5,'NVDQ':-2,'NVDU':2}
def leverage(ticker,name):
    if ticker in OVERRIDE: return OVERRIDE[ticker]
    n=name.lower()
    # Do not treat short duration or short maturity bond funds as inverse.
    if re.search(r'\b(?:ultra)?short[- ](?:term|duration|maturity|dated)\b',n): return None
    m=re.search(r'(?<![\w.])([+\-−]?\d+(?:\.\d+)?)\s*(?:x\b|×|times\b)',n)
    if not m:
        m=re.search(r'(?<![\w.])([+\-−]?\d+(?:\.\d+)?)\s*%',n) if re.search(r'\b(daily|leveraged|inverse)\b',n) else None
        if m and abs(float(m.group(1).replace('−','-')))>=100:
            val=float(m.group(1).replace('−','-'))/100
            return -abs(val) if val<0 or re.search(r'\b(inverse|bear|short)\b',n) else val if val>1 else None
        m=None
    bearish=bool(re.search(r'\b(?:inverse|bear|short)\b|ultrashort|ultrapro short',n))
    if m:
        value=float(m.group(1).replace('−','-'))
        return -abs(value) if bearish or value<0 else value if value>1 else None
    if 'ultrapro short' in n: return -3
    if 'ultrashort' in n and 'proshares' in n: return -2
    if 'ultrapro' in n: return 3
    if 'proshares ultra' in n: return 2
    if re.search(r'proshares short\b|\bdaily short\b|\binverse\b|\bdaily.*\bbear\b',n): return -1
    return None
def category(name,ticker):
    n=name.lower()
    if re.search(r'\bbitcoin\b|\bbtc\b|\bethereum\b|\bether\b|\bcrypto\b|\bsolana\b|\bxrp\b|\bdigital assets?\b|\bdogecoin\b|\bcardano\b|\bavalanche\b',n):return 'Crypto'
    if re.search(r'\bvix\b|\bvolatility\b',n):return 'Volatility'
    if re.search(r'\b(gold|silver|copper|natural gas|crude oil|commodit\w*|agriculture|platinum)\b',n):return 'Commodities'
    if re.search(r'\b(treasury|treasuries|bond|bonds|fixed income|municipal|credit|duration|t-bill|t bill)\b',n):return 'Fixed income'
    if re.search(r'\b(currency|yen|euro|dollar)\b',n):return 'Currency'
    if re.search(r'\b(buffer|defined outcome|target outcome|floor)\b',n):return 'Defined outcome'
    if re.search(r'\b(covered call|option income|option strategy|yieldmax|income option)\b',n):return 'Options / income'
    if re.search(r'\b(s&p|nasdaq|russell|dow jones|total market|500 index|broad market)\b',n):return 'Broad index'
    if re.search(r'\b(technology|semiconductor|financial|healthcare|energy|biotech|utilities|real estate|industrials|consumer)\b',n):return 'Sector / thematic'
    return 'Other / unclassified'
def download():
    errors=[]
    for url in URLS:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'ETF Directory contact via github.com/mikesheer001-source/etf-directory'})
            with urllib.request.urlopen(req,timeout=45) as r: raw=r.read().decode('utf-8-sig')
            if 'Nasdaq Traded|Symbol|Security Name|' not in raw[:300]:raise ValueError('Unexpected file header')
            return raw
        except Exception as e:errors.append(str(e))
    raise RuntimeError('Nasdaq download failed: '+ '; '.join(errors))
def parse(raw,assets):
    result={}
    for row in csv.DictReader(io.StringIO(raw),delimiter='|'):
        if row.get('ETF')!='Y' or row.get('Test Issue')!='N' or row.get('Nasdaq Traded')!='Y':continue
        ticker=row['Symbol'].strip();name=row['Security Name'].strip()
        if not ticker or not name:continue
        lev=leverage(ticker,name)
        kind='inverse' if lev is not None and lev<0 else 'long' if lev is not None and lev>1 else 'other'
        result[ticker]={'ticker':ticker,'name':name,'exchange':EXCH.get(row['Listing Exchange'],row['Listing Exchange']),'kind':kind,'multiple':lev,'category':category(name,ticker),'aum':assets.get(ticker)}
    return sorted(result.values(),key=lambda f:f['ticker'])
def load_aum():
    assets={}
    dates={}
    try:
        req=urllib.request.Request('https://tickerinside.com/api/v1/funds.json',headers={'User-Agent':'ETFDirectory/1.0 (+https://github.com/mikesheer001-source/etf-directory)'})
        with urllib.request.urlopen(req,timeout=50) as response: doc=json.load(response)
        for key in ['funds','sec_funds','sponsor_funds','prospectus_funds','bond_funds','multi_asset_funds','derivative_funds','trust_funds']:
            for f in doc.get(key,[]):
                ticker=f.get('t')
                if not ticker:continue
                value=f.get('aum_b')
                if isinstance(value,(float,int)) and 0<value<float('inf'):
                    amount=value*1e9; date=doc.get('as_of'); source='TickerInside market data'
                else:
                    amount=f.get('net_assets'); date=f.get('report_date'); source='TickerInside reported net assets'
                if not isinstance(amount,(float,int)) or not 0<amount<float('inf'):continue
                if ticker not in assets or (date or '')>(dates[ticker][0] or ''):
                    assets[ticker]=amount; dates[ticker]=(date,source)
        print(f'AUM for {len(assets)} funds from TickerInside')
    except Exception as e:
        print(f'Warning: AUM feed unavailable: {e}')
    return assets,dates

def main():
    assets,dates=load_aum()
    p=BASE/'assets.csv'
    if p.exists():
        for row in csv.DictReader(p.open()):
            try:
                v=float(row['aum_usd'])
                if 0<=v<float('inf'):
                    t=row['ticker'].strip().upper();assets[t]=v;dates[t]=(row.get('updated_date'),'Local CSV')
            except (ValueError,KeyError):continue
    raw=download();funds=parse(raw,assets)
    for fund in funds:
        fund['aum_date'],fund['aum_source']=dates.get(fund['ticker'],(None,None))
    if len(funds)<1000:raise ValueError(f'Only {len(funds)} listings: refusing incomplete snapshot')
    stamp=next((line.split('|')[0] for line in raw.splitlines() if line.startswith('File Creation Time')),None)
    data={'updated':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),'sourceDate':stamp,'funds':funds}
    (BASE/'data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(f'Loaded {len(funds)} listings, {sum(f["kind"]!="other" for f in funds)} estimated leveraged or inverse')
if __name__=='__main__':
    assert leverage('TQQQ','')==3 and leverage('SQQQ','')==-3 and leverage('TEST','Daily 2X Short ETF')==-2
    assert leverage('TEST','Ultra Short Duration Bond ETF') is None
    main()
