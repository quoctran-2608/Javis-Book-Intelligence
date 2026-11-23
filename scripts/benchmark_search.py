"""Run an explicit *synthetic* FTS benchmark; NOT proof of realistic AI quality.

Example: python scripts/benchmark_search.py --units 100000
"""
import argparse
import platform
from pathlib import Path
import sqlite3
import tempfile
import time
try:
    import resource
except ImportError:  # Windows
    resource = None
from javis_book_intelligence.db import initialize, connection, transaction
from javis_book_intelligence.search import search

p=argparse.ArgumentParser()
p.add_argument('--units',type=int,default=10000)
p.add_argument('--queries',type=int,default=100)
p.add_argument('--db',type=Path,default=None)
a=p.parse_args()
if a.units<=0 or a.queries<=0: p.error('positive units and queries required')
folder=Path(tempfile.mkdtemp(prefix='javis_bench_')) if a.db is None else a.db.parent
folder.mkdir(parents=True,exist_ok=True)
db=a.db or folder/'bench.db'
initialize(db)
with connection(db) as con,transaction(con):
    con.execute("INSERT INTO books(id,title) VALUES('bench_book','Synthetic benchmark')")
    con.execute("INSERT INTO editions(id,book_id) VALUES('bench_edition','bench_book')")
    con.execute("INSERT INTO source_files(id,edition_id,sha256,original_filename,storage_name,size_bytes) VALUES(?,?,?,?,?,?)",
        ('bench_file','bench_edition','f'*64,'bench.epub','bench.epub',1))
start=time.perf_counter()
with connection(db) as con:
    for batch_start in range(0,a.units,500):
        with transaction(con):
            con.executemany("""INSERT INTO content_units
                (id,edition_id,source_file_id,spine_index,title,href,body_text,char_count)
                VALUES(?,?,?,?,?,?,?,?)""",[
                (f'unit_{i}','bench_edition','bench_file',i,f'Chapter {i}',f'{i}.xhtml',
                f'Knowledge library matter mindfulness chapter {i} Sanskrit Vietnamese philosophy medicine reference termword{i % 91}. ' * 3,220)
                for i in range(batch_start,min(a.units,batch_start+500))])
indexed=time.perf_counter()-start
samples=[]
for i in range(a.queries):
    q=f'termword{i % 91}'
    t=time.perf_counter()
    result=search(db,q)
    samples.append((time.perf_counter()-t)*1000)
samples.sort()
percentile=lambda p: samples[max(0,min(len(samples)-1,round((len(samples)-1)*p)))]
print(f'Host={platform.platform()} | Python={platform.python_version()} | SQLite={sqlite3.sqlite_version}')
cpu='unknown'
if Path('/proc/cpuinfo').exists():
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):
            cpu=line.split(':',1)[-1].strip();break
rss=f'{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.1f} MiB (Linux)' if resource is not None and platform.system()=='Linux' else 'N/A on this platform'
print(f'CPU={cpu} | peak process RSS={rss}')
print(f'Synthetic units={a.units}; queries={a.queries}; DB={db} ({db.stat().st_size/1048576:.1f} MiB)')
print(f'Indexing elapsed={indexed:.2f} s; response p50={percentile(.50):.2f} ms p95={percentile(.95):.2f} ms p99={percentile(.99):.2f} ms')
print('This tests synthetic repetitive data only; run with actual legally usable EPUB text to assess real-world performance.')
