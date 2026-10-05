"""Execute the sharing script to verify native files, app fallback, and uncluttered UI."""

import json
import shutil
import subprocess
from io import BytesIO

import pytest
from PIL import Image

from clipboard_ui import _clipboard_report_png, _report_share_script


def png(size, color):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


FILES = [("sales.png", png((3, 2), "red")), ("category.png", png((2, 3), "blue"))]


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
        "copy_all",
        "unsupported_payload",
        "throws",
    ],
)
def test_browser_share_paths(mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to execute browser sharing logic")
    files = FILES[:1] if mode in {"copy", "copy_denied"} else FILES
    script = _report_share_script(files, "share", "message", "Report", None)
    runner = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const button = {};
const message = {textContent:'',setAttribute(){},style:{}};
// Extra links/buttons fail the test: only the existing controls should be used.
const document = {getElementById:id=>id==='share'?button:message};
const events = [];
let shared, copied, sharedKeys;
const navigator = {userAgent:input.mode==='mobile'?'Android':'Windows'};
if (!['unsupported','copy','copy_denied','copy_all'].includes(input.mode)) {
  navigator.canShare = payload => {
    if(input.mode==='throws') throw new Error('Blocked');
    return input.mode !== 'unsupported_payload';
  };
  navigator.share = async payload => {
    events.push('share');
    sharedKeys = Object.keys(payload);
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
  events.push('copy_complete');
}};
const opened=[];
const window={location:{set href(url){events.push('open');opened.push(url)}}};
vm.runInNewContext(input.script,{document,navigator,window,File,Blob,Uint8Array,atob,ClipboardItem});
const initial={message:message.textContent,events:[...events]};
button.onclick().then(()=>console.log(JSON.stringify({
  initial,shared,sharedKeys,copied,opened,events,message:message.textContent,disabled:button.disabled
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
        assert output["sharedKeys"] == ["files"]
        assert output["shared"] == [
            {"name": name, "type": "image/png", "bytes": list(data)} for name, data in files
        ]
        assert output["opened"] == []
        assert output["message"] == ""
    elif mode == "cancelled":
        assert output["message"] == ""
        assert output["opened"] == []
    elif mode in {"rejected", "throws", "copy_denied"}:
        assert "Sharing unavailable" in output["message"]
        assert output["opened"] == []
    elif mode in {"copy", "copy_all"}:
        assert output["opened"] == ["whatsapp://send"]
        assert output["events"] == ["copy", "copy_complete", "open"]
        assert bytes(output["copied"]) == _clipboard_report_png(files)
        assert "Ctrl+V" in output["message"]
    else:
        assert output["opened"] == []
        assert "download and attach" in output["message"]


def test_no_caption_only_fallback():
    script = _report_share_script(FILES, "share", "message", "Boteco & sales\n₹1", None)
    config = json.loads(script.rsplit("})(", 1)[1].split(");", 1)[0])
    assert "text" not in config
    assert "appUrl" not in config
    assert "?text=" not in script


def test_combined_clipboard_image_contains_every_section_without_scaling():
    with Image.open(BytesIO(_clipboard_report_png(FILES))) as combined:
        assert combined.size == (3, 5)
        assert combined.getpixel((2, 1)) == (255, 0, 0)
        assert combined.getpixel((1, 2)) == (0, 0, 255)
        assert combined.getpixel((1, 4)) == (0, 0, 255)
        assert combined.getpixel((2, 4)) == (255, 255, 255)
