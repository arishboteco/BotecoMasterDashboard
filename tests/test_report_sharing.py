"""Report sharing: native sharing and complete desktop fallback bundles."""
import base64
import json
import shutil
import subprocess
from io import BytesIO
from zipfile import ZipFile

import pytest

from clipboard_ui import _report_share_script

FILES = [("sales.png", b"sales-image"), ("category.png", b"category-image")]


def make_script(files=FILES):
    return _report_share_script(files, "share", "message", "Report", "https://wa.me/?text=Report")


def test_desktop_zip_contains_every_report():
    config = json.loads(make_script().rsplit("})(", 1)[1].split(");", 1)[0])
    data = base64.b64decode(config["downloadUrl"].split(",", 1)[1])
    with ZipFile(BytesIO(data)) as archive:
        assert archive.namelist() == [name for name, _ in FILES]
        for name, image in FILES:
            assert archive.read(name) == image


@pytest.mark.parametrize("mode", ["unsupported", "native", "rejected", "cancelled", "unsupported_payload"])
def test_browser_share_paths(mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute browser sharing logic")
    runner = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const links = [];
const button = {};
const message = {setAttribute(){}, style:{}, after(e){links.push(...e.children || [])}};
const document = {
  getElementById: id => id === 'share' ? button : message,
  createElement: () => ({style:{}, children:[], appendChild(e){this.children.push(e)}})
};
let shared = [];
let checked = [];
const navigator = input.mode === 'unsupported' ? {} : {
  canShare(payload){checked = payload.files.map(f=>f.name); return input.mode !== 'unsupported_payload'},
  async share(payload){
    if (input.mode !== 'native') {
      throw {name:input.mode === 'cancelled' ? 'AbortError' : 'NotAllowedError'};
    }
    shared = payload.files.map(f=>f.name);
  }
};
vm.runInNewContext(input.script, {document,navigator,File,Uint8Array,atob});
button.onclick().then(()=>console.log(JSON.stringify({
  shared, checked, links:links.map(e=>({text:e.textContent,href:e.href,download:e.download})),
  message:message.textContent, disabled:button.disabled
})));
"""
    result = subprocess.run(
        [node, "-e", runner], input=json.dumps({"mode": mode, "script": make_script()}),
        capture_output=True, text=True, check=True,
    )
    output = json.loads(result.stdout)
    assert output["disabled"] is False
    if mode == "native":
        assert output["shared"] == [name for name, _ in FILES]
        assert output["checked"] == output["shared"]
        assert not output["links"]
    elif mode == "cancelled":
        assert not output["links"]
    else:
        assert output["links"][0]["download"] == "boteco_reports.zip"
        assert output["links"][1]["href"] == "https://wa.me/?text=Report"
        assert "unzip" in output["message"]


def test_individual_fallback_keeps_original_png():
    config = json.loads(make_script(FILES[:1]).rsplit("})(", 1)[1].split(");", 1)[0])
    assert config["downloadName"] == "sales.png"
    assert base64.b64decode(config["downloadUrl"].split(",", 1)[1]) == FILES[0][1]
