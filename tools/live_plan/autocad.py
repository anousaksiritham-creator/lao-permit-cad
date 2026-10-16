"""Attach-only AutoCAD 2025 runner. Never automatically retry mutations."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid

from .render import render


class UncertainMutation(RuntimeError):
    """Inspect the application before issuing another drawing command."""


class AutoCAD2025:
    def __init__(self, application=None):
        if application is None:
            try:
                import pythoncom
                import win32com.client
            except ImportError as error:
                raise RuntimeError('Live drawing requires Windows and pywin32') from error
            pythoncom.CoInitialize()
            application = win32com.client.GetActiveObject('AutoCAD.Application.25')
        self.application = application

    @staticmethod
    def read(operation, attempts=10):
        # Reads can safely be retried after busy calls or transient COM wrappers.
        last = None
        for _ in range(attempts):
            try:
                return operation()
            except Exception as error:
                last = error
                time.sleep(.2)
        raise last

    def status(self):
        def inspect():
            app = self.application
            docs = []
            for i in range(app.Documents.Count):
                d = app.Documents.Item(i)
                docs.append({'name': d.Name, 'path': d.FullName, 'entities': d.ModelSpace.Count})
            return {'progid':'AutoCAD.Application.25','version':app.Version,
                    'active':app.ActiveDocument.Name if docs else None,
                    'units':app.ActiveDocument.GetVariable('INSUNITS') if docs else None,
                    'documents':docs}
        return self.read(inspect)

    def new_empty(self, before, wait_seconds=10):
        old = {d['name'] for d in before['documents']}
        creation_error = None
        try:
            self.application.Documents.Add()   # ONCE, even if COM loses the response.
        except Exception as error:
            creation_error = error
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            current = self.status()
            new = [d for d in current['documents'] if d['name'] not in old]
            if len(new) == 1 and new[0]['name'] == current['active'] and new[0]['entities'] == 0:
                return self.read(lambda: self.application.ActiveDocument)
            if len(new) > 1:
                break
            time.sleep(.2)
        raise UncertainMutation('New drawing not uniquely confirmed. Do not retry Add(); inspect AutoCAD.') from creation_error

    def draw(self, plan, output, work_dir, timeout=120):
        output, work_dir = Path(output).resolve(), Path(work_dir).resolve()
        if output.suffix.lower() != '.dwg' or output.exists():
            raise ValueError('Choose a new .dwg path; existing drawings are never overwritten')
        font = Path(plan['font_file'])
        if not font.is_absolute():
            font = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/font
        if not font.is_file():
            raise ValueError(f'Font file not found; configure an installed font: {font}')
        plan = dict(plan, font_file=str(font.resolve()))
        run = uuid.uuid4().hex
        job = work_dir / run
        job.mkdir(parents=True, exist_ok=False)
        receipt, snapshot = job/'receipt.json', job/'actual.json'
        # Validate rendering, including sheet fit, before any CAD mutation.
        render(plan, 'NEW', output, snapshot, receipt, run)
        before = self.status()
        if self.read(lambda: self.application.ActiveDocument.GetVariable('LISPSYS')) == 0:
            raise RuntimeError('Set LISPSYS=1 and restart AutoCAD before using UTF-8 live batches')
        output.parent.mkdir(parents=True, exist_ok=True)
        doc = self.new_empty(before)
        name = self.read(lambda: doc.Name)
        if self.status()['active'] != name:
            raise UncertainMutation('Active drawing changed; no batch submitted')
        script = job/'draw.lsp'
        script.write_text(render(plan, name, output, snapshot, receipt, run), encoding='utf-8')
        (job/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
        (job/'before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
        submitted = {'run_id':run,'target':name,'output':str(output),'state':'SUBMITTING_ONCE'}
        (job/'run.json').write_text(json.dumps(submitted,indent=2),encoding='utf-8')
        # Use the generated command as code; JSON quoting also escapes LISP quotes.
        command = '(load '+json.dumps(str(script).replace('\\','/'),ensure_ascii=False)+')\n'
        try:
            doc.SendCommand(command)
        except Exception as error:
            raise UncertainMutation(f'Batch submission response lost. Do not resubmit; inspect {job}') from error
        deadline = time.monotonic() + timeout
        result = None
        while time.monotonic() < deadline:
            if receipt.exists():
                try:
                    result = json.loads(receipt.read_text(encoding='utf-8-sig'))
                except (ValueError, OSError):
                    result = None
                if result:
                    break
            time.sleep(.2)
        if not result:
            raise UncertainMutation(f'No completion receipt. Do not retry the mutation; inspect AutoCAD and {job}')
        if result.get('run_id') != run or result.get('status') != 'DONE':
            raise RuntimeError(f'Live batch did not complete: {result}')
        actual = json.loads(snapshot.read_text(encoding='utf-8-sig'))
        if actual.get('run_id') != run:
            raise RuntimeError('Stale or mismatched CAD readback')
        after = self.status()
        prior = {(d['name'],d['path']):d['entities'] for d in before['documents']}
        now = {(d['name'],d['path']):d['entities'] for d in after['documents']}
        if any(now.get(k) != count for k,count in prior.items()):
            raise RuntimeError('A prior drawing changed or closed during the run; investigate before claiming preservation')
        return actual, job
