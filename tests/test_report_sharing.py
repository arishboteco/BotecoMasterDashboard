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


@pytest.mark.parametrize(
    "mode",
    [
        "unsupported",
        "native",
        "rejected",
        "cancelled",
        "unsupported_payload",
        "throws",
        "copy",
        "copy_denied",
        "desktop_with_native_api",
        "desktop_single",
        "desktop_single_denied",
    ],
)
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
let copied;
let opened = [];
const navigator = input.mode === 'unsupported' ? {} : {
  canShare(payload){
    if (input.mode === 'throws') throw new Error('Blocked');
    checked = payload.files.map(f=>f.name);
    return input.mode !== 'unsupported_payload' && !input.mode.startsWith('copy');
  },
  async share(payload){
    if (input.mode !== 'native') {
      throw {name:input.mode === 'cancelled' ? 'AbortError' : 'NotAllowedError'};
    }
    shared = payload.files.map(f=>f.name);
  }
};
class ClipboardItem {constructor(data){this.data = data}}
navigator.userAgent = input.mode.startsWith('desktop') ? 'Windows' : 'Android';
if (input.mode.startsWith('copy') || input.mode.startsWith('desktop_single'))
  navigator.clipboard = {
  async write(items){
    if (input.mode.endsWith('denied')) throw new Error('Blocked');
    copied = Array.from(new Uint8Array(await items[0].data['image/png'].arrayBuffer()));
  }
};
const window = {open(...args){opened.push(args)}};
vm.runInNewContext(input.script,
  {document,navigator,window,File,Blob,URL,Uint8Array,atob,ClipboardItem});
const initialLinks = links.length;
button.onclick().then(async()=>{
  if(input.mode.startsWith('copy')) await links.find(e=>e.textContent==='Copy sales.png').onclick();
  console.log(JSON.stringify({
  shared, checked, initialLinks, copied, opened,
  links:links.map(e=>({text:e.textContent,href:e.href,download:e.download})),
  message:message.textContent, disabled:button.disabled
}));});
"""
    result = subprocess.run(
        [node, "-e", runner],
        input=json.dumps(
            {
                "mode": mode,
                "script": make_script(FILES[:1] if mode.startswith("desktop_single") else FILES),
            }
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(result.stdout)
    assert output["disabled"] is False
    if mode == "native":
        assert output["shared"] == [name for name, _ in FILES]
        assert output["checked"] == output["shared"]
        assert not output["links"]
    elif mode == "cancelled":
        assert not output["links"]
    elif mode == "copy":
        assert bytes(output["copied"]) == FILES[0][1]
        assert "Image copied" in output["message"]
    elif mode == "copy_denied":
        assert "copied" not in output
        assert "Clipboard access was denied" in output["message"]
        assert any(link.get("download") == "sales.png" for link in output["links"])
    elif mode.startswith("desktop_single"):
        assert output["links"][0]["download"] == "sales.png"
        if mode.endswith("denied"):
            assert "copied" not in output
            assert "Clipboard access was denied" in output["message"]
        else:
            assert bytes(output["copied"]) == FILES[0][1]
            assert "Image copied" in output["message"]
    else:
        assert output["links"][0]["download"] == "boteco_reports.zip"
        assert output["links"][0]["href"].startswith("blob:")
        assert output["links"][1]["href"] == "https://web.whatsapp.com/send?text=Report"
        assert [link.get("download") for link in output["links"][2:4]] == [
            name for name, _ in FILES
        ]
        assert output["links"][-1]["href"] == "https://wa.me/?text=Report"
        assert "unzip" in output["message"]
        if mode in {"unsupported", "unsupported_payload", "throws"}:
            assert output["initialLinks"] == len(output["links"])
    if mode.startswith("desktop"):
        assert not output["shared"]
        assert output["opened"] == [
            ["https://web.whatsapp.com/send?text=Report", "_blank", "noopener,noreferrer"]
        ]
        assert output["initialLinks"] == len(output["links"])


def test_individual_fallback_keeps_original_png():
    config = json.loads(make_script(FILES[:1]).rsplit("})(", 1)[1].split(");", 1)[0])
    assert config["downloadName"] == "sales.png"
    assert base64.b64decode(config["downloadUrl"].split(",", 1)[1]) == FILES[0][1]


def test_desktop_url_encodes_report_caption():
    script = _report_share_script(FILES, "share", "message", "Boteco & sales\n₹1", None)
    config = json.loads(script.rsplit("})(", 1)[1].split(");", 1)[0])
    assert config["desktopUrl"] == (
        "https://web.whatsapp.com/send?text=Boteco%20%26%20sales%0A%E2%82%B91"
    )
