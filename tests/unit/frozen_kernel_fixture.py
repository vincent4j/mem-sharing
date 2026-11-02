"""Fixed Git kernels for historical tests; never replace the live candidate exporter."""
import contextlib
import importlib
import importlib.util
import inspect
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
FROZEN_NATIVE = '542f248f35e9de8fb2e7566b6312e6f13d26cd41'
FROZEN_016 = 'eb31607bcd5fb1c2e5a6332e9e67682cd0cf956b'

def export(root, pin):
    from agm_core.plugin_release import managed_source
    from hashlib import sha256
    root=Path(root); files={}
    records=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-rz',pin])
    for row in records.split(b'\0'):
        if not row: continue
        meta,name=row.split(b'\t');mode,kind,blob=meta.split();name=name.decode()
        if kind!=b'blob' or not managed_source(name):continue
        if pin in ('4cfe7bedfde695b0bd4085ccc453afd3ef161711', '04c32e24b9ab9504514908f2368cddca4356e478'):
            if not name.startswith('scripts/') and name not in ('SKILL.md','README.md','INSTALL.md','llms.txt'):continue
        raw=subprocess.check_output(['git','-C',str(REPO),'cat-file','blob',blob.decode()])
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);p.chmod(int(mode,8)&0o777)
        files[name]=sha256(raw).hexdigest()
    return files

class Kernel:
    def __init__(self, root):
        self.root=Path(root);self.name='frozen_test_'+uuid.uuid4().hex
        spec=importlib.util.spec_from_file_location(self.name,self.root/'scripts/agm_core/__init__.py',submodule_search_locations=[str(self.root/'scripts/agm_core')])
        package=importlib.util.module_from_spec(spec);sys.modules[self.name]=package;spec.loader.exec_module(package)
    def module(self,name):return importlib.import_module(self.name+'.'+name)
    @contextlib.contextmanager
    def active(self):
        saved_path=list(sys.path)
        saved={k:v for k,v in sys.modules.items() if k=='agm_core' or k.startswith('agm_core.')}
        for k in saved:sys.modules.pop(k,None)
        sys.modules['agm_core']=sys.modules[self.name]
        for k,v in list(sys.modules.items()):
            if k.startswith(self.name+'.'):sys.modules['agm_core'+k[len(self.name):]]=v
        try:yield
        finally:
            for k in list(sys.modules):
                if k=='agm_core' or k.startswith('agm_core.'):sys.modules.pop(k,None)
            sys.modules.update(saved)
            sys.path[:]=saved_path
    def cli(self):
        spec=importlib.util.spec_from_file_location(self.name+'_cli',self.root/'scripts/install.py');module=importlib.util.module_from_spec(spec)
        with self.active():spec.loader.exec_module(module)
        owner=self
        class CLI:
            def __getattr__(self,name):
                value=getattr(module,name)
                if not inspect.isfunction(value):return value
                def call(*a,**kw):
                    with owner.active():return value(*a,**kw)
                return call
        return CLI()

def bind(test, namespace, root):
    """Temporarily bind a test module to one exact exported running kernel."""
    kernel=Kernel(root);names={'install':'user_install','legacy':'legacy_import'};replacement={}
    for name in ('detect','paths','registry','user_entries','user_install','install','legacy','upgrade','versions','policy_migration','public_layout','legacy_reconcile'):
        if name in namespace:replacement[name]=kernel.module(names.get(name,name))
    if 'cli' in namespace:replacement['cli']=kernel.cli()
    guard=patch.dict(namespace,replacement);guard.start();test.addCleanup(guard.stop)
    return kernel
