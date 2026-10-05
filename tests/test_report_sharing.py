"""Verify the original native file-and-caption handoff without clipboard fallbacks."""

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
        "unsupported_payload",
        "throws",
    ],
)
def test_browser_share_paths(mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute browser sharing logic")
    files = FILES
    script = _report_share_script(files, "share", "message", "Report", None)
    runner = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const button = {};
const message = {textContent:'',setAttribute(){},style:{}};
// Extra links/buttons fail the test: only the existing controls should be used.
const document = {getElementById:id=>id==='share'?button:message};
const events = [];
let shared, sharedKeys, caption, checked;
const navigator = {userAgent:input.mode==='mobile'?'Android':'Windows'};
if (input.mode !== 'unsupported') {
  navigator.canShare = payload => {
    checked = payload.files.map(f=>f.name);
    if(input.mode==='throws') throw new Error('Blocked');
    return input.mode !== 'unsupported_payload';
  };
  navigator.share = async payload => {
    events.push('share');
    sharedKeys = Object.keys(payload);
    caption = payload.text;
    if(['cancelled','rejected'].includes(input.mode))
      throw {name:input.mode==='cancelled'?'AbortError':'NotAllowedError'};
    shared = await Promise.all(payload.files.map(async f=>({
      name:f.name,type:f.type,bytes:Array.from(new Uint8Array(await f.arrayBuffer()))
    })));
  };
}
// Clipboard use is a regression: the WhatsApp action must not require pasting.
navigator.clipboard = {write(){throw new Error('Clipboard must not be used')}};
const opened=[];
const window={location:{set href(url){events.push('open');opened.push(url)}}};
vm.runInNewContext(input.script,{document,navigator,window,File,Uint8Array,atob});
const initial={message:message.textContent,events:[...events]};
button.onclick().then(()=>console.log(JSON.stringify({
  initial,shared,sharedKeys,caption,checked,opened,events,message:message.textContent,disabled:button.disabled
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
        assert output["sharedKeys"] == ["files", "text"]
        assert output["caption"] == "Report"
        assert output["checked"] == ["sales.png"]
        assert output["shared"] == [
            {"name": name, "type": "image/png", "bytes": list(data)} for name, data in files
        ]
        assert output["opened"] == []
        assert output["message"] == ""
    elif mode == "cancelled":
        assert output["message"] == ""
        assert output["opened"] == []
    elif mode in {"rejected", "throws"}:
        assert "could not be opened" in output["message"]
        assert output["opened"] == []
    else:
        assert output["opened"] == []
        assert "unavailable in this browser" in output["message"]
    assert "Ctrl+V" not in output["message"]


def test_no_caption_only_fallback():
    script = _report_share_script(FILES, "share", "message", "Boteco & sales\n₹1", None)
    config = json.loads(script.rsplit("})(", 1)[1].split(");", 1)[0])
    assert config["text"] == "Boteco & sales\n₹1"
    assert "appUrl" not in config
    assert "?text=" not in script
    assert "clipboard" not in script
