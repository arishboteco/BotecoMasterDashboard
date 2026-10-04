"""Execute the sharing script to verify native files, app fallback, and uncluttered UI."""

import json
import shutil
import subprocess

import pytest

from clipboard_ui import _report_share_script

FILES = [("sales.png", b"sales-image"), ("category.png", b"category-image")]


@pytest.mark.parametrize(
    "mode",
    [
        "desktop",
        "mobile",
        "cancelled",
        "rejected",
        "unsupported",
        "copy",
        "copy_denied",
        "unsupported_payload",
        "throws",
    ],
)
def test_browser_share_paths(mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute browser sharing logic")
    files = FILES[:1] if mode.startswith("copy") else FILES
    script = _report_share_script(files, "share", "message", "Report", None)
    runner = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const button = {};
const message = {textContent:'',setAttribute(){},style:{}};
// Extra links/buttons fail the test: only the existing controls should be used.
const document = {getElementById:id=>id==='share'?button:message};
const events = [];
let shared, copied;
const navigator = {userAgent:input.mode==='mobile'?'Android':'Windows'};
if (!['unsupported','copy','copy_denied'].includes(input.mode)) {
  navigator.canShare = payload => {
    if(input.mode==='throws') throw new Error('Blocked');
    return input.mode !== 'unsupported_payload';
  };
  navigator.share = async payload => {
    events.push('share');
    if(['cancelled','rejected'].includes(input.mode))
      throw {name:input.mode==='cancelled'?'AbortError':'NotAllowedError'};
    shared = await Promise.all(payload.files.map(async f=>({
      name:f.name,type:f.type,bytes:Array.from(new Uint8Array(await f.arrayBuffer()))
    })));
  };
}
class ClipboardItem {constructor(data){this.data=data}}
if(input.mode.startsWith('copy')) navigator.clipboard = {async write(items){
  events.push('copy');
  if(input.mode==='copy_denied') throw new Error('Denied');
  copied=Array.from(new Uint8Array(await items[0].data['image/png'].arrayBuffer()));
}};
const opened=[];
const window={open(...args){events.push('open');opened.push(args)}};
vm.runInNewContext(input.script,{document,navigator,window,File,Uint8Array,atob,ClipboardItem});
const initial={message:message.textContent,events:[...events]};
button.onclick().then(()=>console.log(JSON.stringify({
  initial,shared,copied,opened,events,message:message.textContent,disabled:button.disabled
})));
"""
    result = subprocess.run(
        [node, "-e", runner],
        input=json.dumps({"mode": mode, "script": script}),
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(result.stdout)
    assert output["initial"] == {"message": "", "events": []}
    assert output["disabled"] is False
    if mode in {"desktop", "mobile"}:
        assert output["shared"] == [
            {"name": name, "type": "image/png", "bytes": list(data)} for name, data in files
        ]
        assert output["opened"] == []
        assert output["message"] == ""
    elif mode == "cancelled":
        assert output["message"] == ""
        assert output["opened"] == []
    elif mode in {"rejected", "throws"}:
        assert "Sharing unavailable" in output["message"]
        assert output["opened"] == []
    else:
        assert output["opened"] == [
            ["whatsapp://send?text=Report", "_blank", "noopener,noreferrer"]
        ]
        if mode == "copy":
            assert output["events"] == ["copy", "open"]
            assert bytes(output["copied"]) == FILES[0][1]
            assert "Paste" in output["message"]
        else:
            assert "Attach" in output["message"]


def test_app_url_encodes_report_caption():
    script = _report_share_script(FILES, "share", "message", "Boteco & sales\n₹1", None)
    config = json.loads(script.rsplit("})(", 1)[1].split(");", 1)[0])
    assert config["appUrl"] == "whatsapp://send?text=Boteco%20%26%20sales%0A%E2%82%B91"
