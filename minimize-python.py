"""Store Python's pure standard library in its supported compressed import ZIP."""
from pathlib import Path
import sys,zipfile,shutil
root=Path('/usr/lib')/('python'+sys.version.split()[0].rsplit('.',1)[0])
target=root.parent/('python'+str(sys.version_info.major)+str(sys.version_info.minor)+'.zip')
items=[p for p in root.iterdir() if p.name not in ('site-packages','lib-dynload','EXTERNALLY-MANAGED') and not p.name.startswith(('config-','_sysconfig'))]
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for item in items:
        files=item.rglob('*') if item.is_dir() else [item]
        for file in files:
            if file.is_file():archive.write(file,file.relative_to(root))
for item in items:
    if item.is_dir():shutil.rmtree(item)
    else:item.unlink()
